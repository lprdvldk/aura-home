# Aura Home (Smart House)

Local-first house monitor: multiple climate sensors (DHT11 and anything else you list in `config/house.json`), air quality, light, motion, a portable Qt 6 desktop app, and an encrypted household bio. Device agents talk to a single **house hub over gRPC**; the desktop and the live view subscribe to **WebSocket** telemetry. Ingest is token-gated.

- **Run everything:** [docs/RUNBOOK.md](docs/RUNBOOK.md)
- **Architecture layout:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Quickest local stack (hub + multi-sensor gRPC agent):

```bash
docker compose up --build
```

Then open http://127.0.0.1:18443/ (monitor) and http://127.0.0.1:18443/account/register (encrypted bio).

## Architecture

```
  Qt 6 desktop (macOS / Windows)          optional browser live view
           │  gRPC queries / commands              │
           │  WebSocket /v1/telemetry              │
           └──────────────┬────────────────────────┘
                          │
                   House hub
            gRPC :18551  HTTP/WS :18443
            ingest: x-agent-token (or Bearer)
                          │
            ┌─────────────┴──────────────────────────┐
            │                                        │
     sensor-agent (Python, gRPC)              dht11-agent (C++23, HTTP)
     every house.json device                  GPIO DHT11 fallback
     PushSamples + token                      POST /v1/samples + token
```

| Path | What it is |
| --- | --- |
| `proto/smarthouse/v1/house.proto` | Contract: devices, samples, `PushSample` / `PushSamples` |
| `apps/hub` | FastAPI hub (Python 3.12): gRPC + REST + WebSocket + live view |
| `apps/sensor-agent` | One process that pushes **all** configured sensors over gRPC |
| `apps/desktop` | Qt 6 / C++23 desktop with realtime charts |
| `libs/dht11` | DHT11 frame decoder, simulator, Linux GPIO bit-bang |
| `apps/dht11-agent` | C++ GPIO/HTTP fallback for a single DHT11 |
| `config/house.json` | Rooms, devices, GPIO pins, alert thresholds |
| `.env.example` | Agent token, optional TLS paths |

There is no Kafka, MySQL, or cloud dependency. The hub keeps a rolling in-memory history so a laptop and a Raspberry Pi on the LAN are enough.

## Multiple sensors

Every gadget is a row in `config/house.json`. The default house has three DHT11 climate sensors, two air-quality nodes, hallway light, and entry motion. Kinds: `climate` | `air_quality` | `light` | `motion`. Drivers: `dht11` (GPIO pin used by the C++ agent) or `simulator`.

The Python **sensor-agent** reads that file and calls `HouseHub.PushSamples` once per interval, so one process covers every device (more than one DHT11, plus non-DHT11 kinds):

```bash
export SMART_HOUSE_AGENT_TOKEN=change-me-to-a-long-random-token
PYTHONPATH=apps/hub:apps/sensor-agent .venv/bin/python -m smarthouse_sensor_agent \
  --target 127.0.0.1:18551
# only two DHT11s:
PYTHONPATH=apps/hub:apps/sensor-agent .venv/bin/python -m smarthouse_sensor_agent \
  --device living-room-dht11 --device bedroom-dht11
# only motion + light:
PYTHONPATH=apps/hub:apps/sensor-agent .venv/bin/python -m smarthouse_sensor_agent \
  --kind motion --kind light
```

A live gRPC agent heartbeat replaces the hub simulator for those device ids. If the agent stops, the hub falls back to simulation after 5 seconds.

## Security

Ingest is **not** public. `PushSample`, `PushSamples`, and `POST /v1/samples` require `x-agent-token` or `Authorization: Bearer …` matching `SMART_HOUSE_AGENT_TOKEN`. Charts, device lists, and WebSocket telemetry stay open on the LAN so the Qt app does not need the agent secret. Account pages still use Argon2id + AES-256-GCM for the bio vault.

Copy `.env.example` to `.env` and replace the token:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Optional TLS for HTTP/WebSocket **and** gRPC:

```bash
bash scripts/gen_dev_certs.sh
SMART_HOUSE_TLS_CERTFILE=certs/hub.crt SMART_HOUSE_TLS_KEYFILE=certs/hub.key \
  PYTHONPATH=apps/hub .venv/bin/python -m smarthouse_hub
PYTHONPATH=apps/hub:apps/sensor-agent .venv/bin/python -m smarthouse_sensor_agent \
  --tls-ca certs/hub.crt
```

CORS defaults to the local dashboard origin, not `*`. Session cookies are `HttpOnly` / `SameSite=Lax` and `Secure` when TLS is on.

## Run the hub (any machine)

```bash
python3 -m venv .venv
.venv/bin/pip install -r apps/hub/requirements.txt -r apps/sensor-agent/requirements.txt
cp .env.example .env   # set SMART_HOUSE_AGENT_TOKEN
PYTHONPATH=apps/hub .venv/bin/python -m smarthouse_hub --http-port 18443 --grpc-port 18551
```

If the token env var is empty, the hub prints a generated `SMART_HOUSE_AGENT_TOKEN` at startup — copy it into the agent process.

Open http://127.0.0.1:18443/ for the live view, or point the Qt app at that host.

gRPC methods: `ListDevices`, `GetLatest`, `SetEnabled`, `PushSample`, `PushSamples`, `Subscribe`.  
WebSocket: `ws://127.0.0.1:18443/v1/telemetry` (snapshot, then `sample` / `alert` events).  
HTTP `POST /v1/samples` remains as a fallback for the C++ DHT11 agent (same token).

```bash
PYTHONPATH=apps/hub .venv/bin/python examples/grpc_list_devices.py --target 127.0.0.1:18551
```

## Qt 6 desktop (macOS and Windows)

C++23, Qt Widgets, Qt Charts, Qt WebSockets. No GPIO in this process — it is a portable viewer/controller.

**macOS**

```bash
brew install qt cmake ninja
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$(brew --prefix qt)"
cmake --build build --target smarthouse_desktop
open build/apps/desktop/SmartHouse.app
```

Ship a `.app` with `macdeployqt build/apps/desktop/SmartHouse.app`.

**Windows**

Install Qt 6.5+ (MSVC) and CMake. From a Developer Command Prompt:

```bat
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/Qt/6.8.0/msvc2022_64
cmake --build build --config Release --target smarthouse_desktop
```

Ship with `windeployqt build/apps/desktop/Release/SmartHouse.exe`.

Connect to the hub host (the Pi, or `127.0.0.1` if the hub is local). Charts follow the selected device: temperature/humidity, PM2.5/CO₂, lux, or motion.

## DHT11 on a Raspberry Pi (C++ GPIO fallback)

The Python sensor-agent is the default gRPC path (including extra DHT11s). Use the C++ agent when you want real GPIO bit-bang for one probe:

Wiring (3.3 V logic): VCC → 3V3, GND → GND, DATA → GPIO (default 16 / BCM) with a 4.7 kΩ pull-up to 3V3.

```bash
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent --target smarthouse_dht11_agent
./build-agent/apps/dht11-agent/smarthouse_dht11_agent \
  --host 127.0.0.1 --device-id living-room-dht11 --gpio --pin 16 \
  --token "$SMART_HOUSE_AGENT_TOKEN"
```

On a laptop use `--simulate` (default). `libs/dht11` decodes the 40-bit DHT11 frame. Timing is tight — run GPIO reads on the Pi.

## Add another gadget

1. Add a device in `config/house.json` (`kind`: `climate` | `air_quality` | `light` | `motion`).
2. Restart the hub (it reloads the house map) and the sensor-agent (it pushes every enabled row over `PushSamples`).
3. The desktop already charts climate, air quality, light, and motion.

## Tests

```bash
PYTHONPATH=apps/hub:apps/sensor-agent .venv/bin/pytest apps/hub/tests apps/sensor-agent/tests -q
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent
ctest --test-dir build-agent --output-on-failure
```

## Account (encrypted bio)

Register and sign in at `/account/register` and `/account/login`. Personal fields are Argon2id + AES-256-GCM encrypted at rest under `data/users/`. Telemetry **reads** stay public; **ingest** requires the agent token. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Ports

| Service | Default |
| --- | --- |
| Hub HTTP + WebSocket + account pages | 18443 |
| Hub gRPC | 18551 |
