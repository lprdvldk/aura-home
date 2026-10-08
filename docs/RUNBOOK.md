# How to run Aura Home

Two supported ways: **Docker Compose** (images, closest to CI) and **native** (Python hub + optional Qt on your OS).

## 1. Docker Compose — test the microservices locally

From the repository root:

```bash
docker compose build hub dht11-agent
docker compose up
```

- Hub UI: http://127.0.0.1:18443/
- Sign in / register / bio: http://127.0.0.1:18443/account/register
- gRPC: `127.0.0.1:18551`
- DHT11 agent (simulator) posts into the hub once it is healthy

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

That loads `aura-home-hub:local`, `aura-home-dht11-agent:local`, and `aura-home-desktop:local`.

## 2. Native hub (no Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -r apps/hub/requirements.txt
PYTHONPATH=apps/hub .venv/bin/python -m smarthouse_hub
# Paths are relative to the working directory (repo root):
# SMART_HOUSE_HOUSE_CONFIG=config/house.json SMART_HOUSE_DATA_DIR=data/users
```

Open:

- Monitor: http://127.0.0.1:18443/
- Register: http://127.0.0.1:18443/account/register
- Bio (after sign-in): http://127.0.0.1:18443/account/bio

Encrypted accounts land in `data/users/`. Do not commit that directory.

gRPC check:

```bash
PYTHONPATH=apps/hub .venv/bin/python examples/grpc_list_devices.py --target 127.0.0.1:18551
```

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
2. **Connect** — live climate/air charts (WebSocket).
3. **Account** — browser login/register/bio against the same hub.

## 4. DHT11 agent

Without hardware (same as Compose):

```bash
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent --target smarthouse_dht11_agent
./build-agent/apps/dht11-agent/smarthouse_dht11_agent \
  --host 127.0.0.1 --port 18443 --device-id living-room-dht11 --simulate
```

On a Raspberry Pi, wire DHT11 DATA to BCM 16 with a 4.7 kΩ pull-up to 3.3 V, then:

```bash
./build-agent/apps/dht11-agent/smarthouse_dht11_agent \
  --host <hub-ip> --device-id living-room-dht11 --gpio --pin 16
```

## 5. Tests

```bash
PYTHONPATH=apps/hub .venv/bin/pytest apps/hub/tests -q
cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
cmake --build build-agent
ctest --test-dir build-agent --output-on-failure
```

## Ports

| Service | Port |
| --- | --- |
| Hub HTTP, WebSocket, account pages | 18443 |
| Hub gRPC | 18551 |
