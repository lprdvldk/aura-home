# Smart House

Local-first house monitor: climate (DHT11 temperature + humidity), air quality, and a portable Qt 6 desktop app. The previous Kafka bus is gone. Device agents talk to a single **house hub** over **gRPC**; the desktop (and the hub live view) subscribe to **WebSocket** telemetry for realtime charts.

This monorepo is the structure for a whole-home console — rooms, gadgets, thresholds — with one working slice already wired: DHT11 climate plus simulated air quality.

## Architecture

```
  Qt 6 desktop (macOS / Windows)          optional browser live view
           │  gRPC queries / commands              │
           │  WebSocket /v1/telemetry              │
           └──────────────┬────────────────────────┘
                          │
                   House hub
            gRPC :18551  HTTP/WS :18443
                          │
            ┌─────────────┴──────────────┐
            │                            │
     dht11-agent (C++23)          future agents
     GPIO or --simulate           (PMS5003, SGP30, lux, motion)
```

| Path | What it is |
| --- | --- |
| `proto/smarthouse/v1/house.proto` | Contract: devices, samples, `HouseHub` RPCs |
| `apps/hub` | Local hub (Python 3.12): gRPC + REST + WebSocket + live view |
| `apps/desktop` | Qt 6 / C++23 desktop with realtime charts |
| `libs/dht11` | DHT11 frame decoder, simulator, Linux GPIO bit-bang |
| `apps/dht11-agent` | Pushes DHT11 readings into the hub |
| `config/house.json` | Rooms, devices, GPIO pins, alert thresholds |

There is no Kafka, MySQL, or cloud dependency. The hub keeps a rolling in-memory history so a laptop and a Raspberry Pi on the LAN are enough.

## Run the hub (any machine)

```bash
python3 -m venv .venv
.venv/bin/pip install -r apps/hub/requirements.txt
PYTHONPATH=apps/hub .venv/bin/python -m smarthouse_hub --http-port 18443 --grpc-port 18551
```

Open http://127.0.0.1:18443/ for the live climate view, or point the Qt app at that host. Simulated DHT11 and air-quality devices start immediately so you can develop without hardware.

gRPC methods: `ListDevices`, `GetLatest`, `SetEnabled`, `PushSample`, `Subscribe`.  
WebSocket: `ws://127.0.0.1:18443/v1/telemetry` (snapshot, then `sample` / `alert` events).  
HTTP mirrors the same model for the desktop and for agents that do not link `grpc++`.

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

Connect to the hub host (the Pi, or `127.0.0.1` if the hub is local). The chart follows the selected device: temperature/humidity for climate, PM2.5/CO₂ for air quality.

## DHT11 on a Raspberry Pi

Wiring (3.3 V logic): VCC → 3V3, GND → GND, DATA → GPIO (default 16 / BCM) with a 4.7 kΩ pull-up to 3V3.

```bash
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent --target smarthouse_dht11_agent
./build-agent/apps/dht11-agent/smarthouse_dht11_agent \
  --host 127.0.0.1 --device-id living-room-dht11 --gpio --pin 16
```

On a laptop use `--simulate` (default). A live agent heartbeat replaces the hub simulator for that device; if the agent stops, the hub falls back to simulation after 5 seconds.

`libs/dht11` decodes the 40-bit DHT11 frame (humidity, temperature, checksum). The Linux GPIO backend bit-bangs the start condition and 40 data bits via `/dev/gpiochip0`. Timing is tight — run the agent on the Pi, not over SSH with a loaded CPU if reads fail checksums.

## Add another gadget

1. Add a device in `config/house.json` (`kind`: `climate` | `air_quality` | `light` | `motion`).
2. Push `SensorSample` metrics with `HouseHub.PushSample` or `POST /v1/samples`.
3. The desktop already charts climate and air quality; light/motion show up in the device tree and snapshot for the next UI pass.

## Tests

```bash
PYTHONPATH=apps/hub .venv/bin/pytest apps/hub/tests -q
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent
ctest --test-dir build-agent --output-on-failure
```

## Ports

| Service | Default |
| --- | --- |
| Hub HTTP + WebSocket | 18443 |
| Hub gRPC | 18551 |
