# How to run Aura Home

Two supported ways: **Docker Compose** (images, closest to CI) and **native** (Python hub + device-reader + optional Qt on your OS).

## 1. Docker Compose — test the microservices locally

From the repository root:

```bash
cp .env.example .env   # optional; Compose defaults the token to local-dev-agent-token
docker compose up --build
```

- Hub UI: http://127.0.0.1:18443/
- Sign in / register / bio: http://127.0.0.1:18443/account/register
- gRPC: `127.0.0.1:18551`
- `device-reader` pushes every `config/house.json` device (GPIO / Zigbee / Wi-Fi / simulator) over `PushSamples`

Cloud VPS + Pi 4: [CLOUD.md](CLOUD.md).

GPIO DHT11 C++ agent (HTTP fallback):

```bash
docker compose --profile gpio up dht11-agent
```

Linux desktop image (needs an X11 display):

```bash
docker compose --profile desktop up desktop
```

On macOS or Windows, do **not** use the desktop container for daily use. Build the native Qt app (section 3). The Linux image is what CI produces so you can still `docker load` a known binary.

### Load images built by CI

Download the `aura-home-local-images` artifact, then:

```bash
gzip -dc dist/aura-home-images.tar.gz | docker load
docker compose up
```

That loads `aura-home-hub:local`, `aura-home-device-reader:local`, `aura-home-dht11-agent:local`, and `aura-home-desktop:local`.

## 2. Native hub (no Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -r apps/hub/requirements.txt -r apps/device-reader/requirements.txt
cp .env.example .env
# set SMART_HOUSE_AGENT_TOKEN to a long random string
PYTHONPATH=apps/hub .venv/bin/python -m smarthouse_hub
# Paths are relative to the working directory (repo root):
# SMART_HOUSE_HOUSE_CONFIG=config/house.json SMART_HOUSE_DATA_DIR=data/users
```

If you skip `.env` and leave the token empty, the hub prints `generated SMART_HOUSE_AGENT_TOKEN=…` — export that in the agent shell.

Open:

- Monitor: http://127.0.0.1:18443/
- Register: http://127.0.0.1:18443/account/register
- Bio (after sign-in): http://127.0.0.1:18443/account/bio

Encrypted accounts land in `data/users/`. Do not commit that directory.

gRPC check (queries are unauthenticated; ingest is not):

```bash
PYTHONPATH=apps/hub .venv/bin/python examples/grpc_list_devices.py --target 127.0.0.1:18551
```

### device-reader (GPIO / Zigbee / Wi-Fi)

```bash
export SMART_HOUSE_AGENT_TOKEN=…   # same value as the hub
PYTHONPATH=apps/hub:apps/device-reader .venv/bin/python -m smarthouse_device_reader \
  --target 127.0.0.1:18551
```

### Optional TLS

```bash
bash scripts/gen_dev_certs.sh
SMART_HOUSE_TLS_CERTFILE=certs/hub.crt SMART_HOUSE_TLS_KEYFILE=certs/hub.key \
  PYTHONPATH=apps/hub .venv/bin/python -m smarthouse_hub
PYTHONPATH=apps/hub:apps/device-reader .venv/bin/python -m smarthouse_device_reader \
  --tls-ca certs/hub.crt
```

Then open https://127.0.0.1:18443/ (browser will warn on the self-signed cert).

## 3. Native desktop (macOS / Windows / Linux)

The desktop is a Qt 6 C++23 executable. It does not require Docker.

**macOS**

```bash
brew install qt cmake
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$(brew --prefix qt)"
cmake --build build --target smarthouse_desktop
open build/apps/desktop/SmartHouse.app
```

**Windows** (Qt 6.5+ MSVC)

```bat
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/Qt/6.8.0/msvc2022_64
cmake --build build --config Release --target smarthouse_desktop
```

**Linux**

```bash
sudo apt-get install -y g++ cmake qt6-base-dev qt6-charts-dev qt6-websockets-dev libgl1-mesa-dev
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target smarthouse_desktop
./build/apps/desktop/SmartHouse
```

In the window:

1. Hub host `127.0.0.1`, port `18443` (or the Pi’s LAN address).
2. **Connect** — live climate/air/light/motion charts (WebSocket).
3. **Account** — browser login/register/bio against the same hub.

## 4. DHT11 agent (C++ GPIO / HTTP fallback)

Without hardware (same as the Python agent, but HTTP for one device):

```bash
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent --target smarthouse_dht11_agent
./build-agent/apps/dht11-agent/smarthouse_dht11_agent \
  --host 127.0.0.1 --port 18443 --device-id living-room-dht11 --simulate \
  --token "$SMART_HOUSE_AGENT_TOKEN"
```

On a Raspberry Pi, wire DHT11 DATA to BCM 16 with a 4.7 kΩ pull-up to 3.3 V, then:

```bash
./build-agent/apps/dht11-agent/smarthouse_dht11_agent \
  --host <hub-ip> --device-id living-room-dht11 --gpio --pin 16 \
  --token "$SMART_HOUSE_AGENT_TOKEN"
```

Run a second GPIO oneshot with `--device-id bedroom-dht11 --pin 20`, or let device-reader cover every climate row over gRPC.

## 5. Tests

```bash
PYTHONPATH=apps/hub:apps/device-reader:apps/sensor-agent .venv/bin/pytest apps/hub/tests apps/device-reader/tests apps/sensor-agent/tests -q
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent
ctest --test-dir build-agent --output-on-failure
```

## Ports

| Service | Port |
| --- | --- |
| Hub HTTP, WebSocket, account pages | 18443 |
| Hub gRPC | 18551 |
