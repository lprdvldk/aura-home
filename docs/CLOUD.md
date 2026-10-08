# Cloud hub + Raspberry Pi sensors + desktop

The hub can live on a VPS. A Raspberry Pi 4 Model B at home runs **device-reader** and pushes samples over **gRPC + TLS**. The Qt desktop (or browser) pulls charts over **HTTPS / WSS** with a viewer token or a signed-in account.

```
 Raspberry Pi 4 (LAN)                         Cloud VPS
 ┌─────────────────────────┐                  ┌──────────────────────┐
 │ device-reader           │  gRPC TLS :443   │ hub                  │
 │  GPIO  DHT11            │  x-agent-token   │  ingest (agent)      │
 │  Zigbee coordinator     │ ───────────────► │  store + alerts      │
 │  Wi-Fi ESP / HTTP       │                  │  account vault       │
 └─────────────────────────┘                  └──────────┬───────────┘
                                                         │ HTTPS / WSS
                                              Qt desktop │ x-viewer-token
                                              Browser    │ or login cookie
```

Local-only (`cloud_mode=false`) still allows open telemetry reads on the LAN. **Cloud mode does not.**

## Tokens (two secrets)

| Secret | Who holds it | Used for |
| --- | --- | --- |
| `SMART_HOUSE_AGENT_TOKEN` | Pi `device-reader` only | `PushSample` / `PushSamples` (and ListDevices so the Pi can apply `SetEnabled`) |
| `SMART_HOUSE_VIEWER_TOKEN` | Your laptop / phone | HTTP snapshot, history, WebSocket `/v1/telemetry` |
| Account session | Anyone who registered | Same as viewer token, via `sh_session` cookie |

Do not put the agent token in the desktop app. A stolen viewer token can watch charts; a stolen agent token can inject fake sensors.

## 1. Hub on a VPS

TLS is mandatory in cloud mode (`--cloud` or `SMART_HOUSE_CLOUD_MODE=true`). Use a real certificate (Caddy, nginx, or Let's Encrypt) or the repo's `scripts/gen_dev_certs.sh` for a first test.

```bash
# on the VPS, repo root
export SMART_HOUSE_CLOUD_MODE=true
export SMART_HOUSE_AGENT_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
export SMART_HOUSE_VIEWER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
export SMART_HOUSE_TLS_CERTFILE=certs/hub.crt
export SMART_HOUSE_TLS_KEYFILE=certs/hub.key
export SMART_HOUSE_CORS_ORIGINS=https://hub.example.com
PYTHONPATH=apps/hub .venv/bin/python -m smarthouse_hub --cloud
```

Docker: same env vars, publish 18443 (HTTPS) and 18551 (gRPC TLS). Put Caddy in front if you only want port 443; see `examples/Caddyfile`.

Health (`GET /health`) stays unauthenticated for probes. Everything else that returns house data needs the viewer token, a session, or the agent token.

## 2. Raspberry Pi 4 — device-reader

The Pi never exposes ports. It dials out to the hub.

```bash
# on the Pi
sudo apt-get install -y python3-venv python3-pip
python3 -m venv .venv
.venv/bin/pip install -r apps/hub/requirements.txt -r apps/device-reader/requirements.txt

# copy the hub's TLS cert (Let's Encrypt: use the public CA; self-signed: copy hub.crt)
export SMART_HOUSE_AGENT_TOKEN=…          # same as the VPS
export SMART_HOUSE_GRPC_TARGET=hub.example.com:18551
export SMART_HOUSE_TLS_CA=certs/hub.crt   # or skip if the cert is publicly trusted
export SMART_HOUSE_HOUSE_CONFIG=config/house.json

PYTHONPATH=apps/hub:apps/device-reader .venv/bin/python -m smarthouse_device_reader \
  --target "$SMART_HOUSE_GRPC_TARGET" \
  --tls-ca "$SMART_HOUSE_TLS_CA" \
  --gpio
```

`--gpio` makes `protocol: gpio` devices call `smarthouse_dht11_agent --once --gpio --pin N` (build that binary on the Pi from `libs/dht11`). Without `--gpio`, DHT11 rows are still pushed, using the simulator so you can test the tunnel before wiring probes.

systemctl snippet: `docs/device-reader.service` is not required; a user unit that restarts on failure is enough.

### Builder / protocols

`house.json` picks the transport per gadget:

```json
{ "id": "living-room-dht11", "driver": "dht11", "protocol": "gpio", "gpio_pin": 16 }
{ "id": "patio-zigbee-motion", "driver": "zigbee", "protocol": "zigbee", "endpoint": "sim://patio-motion" }
{ "id": "garage-wifi-climate", "driver": "dht11", "protocol": "wifi", "endpoint": "http://192.168.1.40/metrics" }
```

| Protocol | Read | Write |
| --- | --- | --- |
| `gpio` | C++ oneshot (DHT11 bit-bang) or simulator | read-only |
| `zigbee` | `sim://`, `file:///report.json`, later `mqtt://` | enable command recorded / published |
| `wifi` | `GET` JSON from ESP/ESPHome, or `sim://` | `POST` `{action, enabled}` |
| `simulator` | hub-matching fake series | enable stored locally |

Python side:

```python
reader = (
    DeviceReaderBuilder()
    .protocol(GpioProtocol(hardware=True))
    .protocol(ZigbeeProtocol())
    .protocol(WifiProtocol())
    .protocol(SimulatorProtocol())
    .devices_from_house("config/house.json")
    .hub("hub.example.com:18551", token=agent_token, tls_ca="certs/hub.crt")
    .build()
)
samples = reader.read()
reader.write("garage-wifi-climate", WriteCommand(action="enable", enabled=False))
```

## 3. Desktop (laptop) — pull securely

1. Hub host = `hub.example.com`, port `18443` (or `443` behind Caddy).
2. Check **TLS**. For the repo self-signed cert, also check **Trust self-signed**.
3. Paste `SMART_HOUSE_VIEWER_TOKEN` into **viewer token**.
4. Connect. Charts use `wss://…/v1/telemetry?token=…`.

Browser: `https://hub.example.com/?token=VIEWER` or sign in at `/account/login` (cookie is enough; no token in the URL).

## Checklist

- [ ] Hub `cloud_mode` + TLS cert for the public hostname
- [ ] Agent token only on the Pi
- [ ] Viewer token (or account) on the desktop
- [ ] Pi outbound 443/18551 allowed; no inbound ports on the Pi
- [ ] `config/house.json` copied to both hub and Pi (same device ids)
- [ ] DHT11 DATA on BCM pins with 4.7 kΩ pull-up to 3.3 V
