# Aura Home architecture

Local-first household monitor. There is no Kafka, no cloud identity provider, and no shared SQL database. Devices, the hub, and the desktop stay on the LAN.

## System context

```
                     ┌──────────────────────────────────────────┐
                     │              Operators                   │
                     │  Qt desktop (macOS/Windows/Linux)        │
                     │  Browser: monitor, login, register, bio  │
                     └───────────────┬──────────────────────────┘
                                     │ HTTP / WebSocket :18443
                                     │ gRPC :18551 (queries)
                     ┌───────────────▼──────────────────────────┐
                     │                 Hub                      │
                     │  Telemetry store (in-memory history)     │
                     │  Device registry (config/house.json)     │
                     │  Account vault (AES-256-GCM at rest)     │
                     │  Agent token on ingest                   │
                     │  Optional TLS on HTTP + gRPC             │
                     │  Simulators until a live agent appears   │
                     └───────────────┬──────────────────────────┘
                                     │ gRPC PushSample / PushSamples
                                     │ (x-agent-token or Bearer)
                     ┌───────────────▼──────────────────────────┐
                     │              Agents                      │
                     │  sensor-agent: every house.json device   │
                     │  dht11-agent: GPIO DHT11 HTTP fallback   │
                     └──────────────────────────────────────────┘
```

## Repositories and images

| Component | Path | Runtime | Image |
| --- | --- | --- | --- |
| Contract | `proto/smarthouse/v1/house.proto` | — | — |
| Hub | `apps/hub` | FastAPI + uvicorn (Python 3.12), pydantic-settings | `aura-home-hub:local` |
| Sensor agent | `apps/sensor-agent` | Python gRPC `PushSamples` | `aura-home-sensor-agent:local` |
| DHT11 agent | `apps/dht11-agent` + `libs/dht11` | C++23 HTTP fallback | `aura-home-dht11-agent:local` |
| Desktop | `apps/desktop` | Qt 6 / C++23 | `aura-home-desktop:local` (Linux) |
| House map | `config/house.json` | — | mounted into hub and sensor-agent |
| Encrypted bios | `data/users/*.json` | — | hub volume |

CI (`.github/workflows/ci.yml`) runs hub + sensor-agent tests, DHT11 unit tests, then builds those images and publishes:

- `dist/aura-home-images.tar.gz` — `docker load` this on a laptop
- `dist/SmartHouse-linux` — Linux desktop executable
- `dist/smarthouse_dht11_agent-linux` — Linux GPIO agent executable

Origin/Depot can run the same GitHub Actions YAML.

## Hub runtime

The hub is **FastAPI + uvicorn** (HTTP, WebSocket, account pages) and **gRPC asyncio** on a second port. Paths come from **pydantic-settings** (`SMART_HOUSE_*`, optional `.env`), relative to the process working directory:

| Setting | Default |
| --- | --- |
| `SMART_HOUSE_HOUSE_CONFIG` | `config/house.json` |
| `SMART_HOUSE_DATA_DIR` | `data/users` |
| `SMART_HOUSE_HTTP_HOST` / `HTTP_PORT` | `0.0.0.0` / `18443` |
| `SMART_HOUSE_GRPC_HOST` / `GRPC_PORT` | `0.0.0.0` / `18551` |
| `SMART_HOUSE_CORS_ORIGINS` | `http://127.0.0.1:18443,http://localhost:18443` |
| `SMART_HOUSE_AGENT_TOKEN` | empty (hub generates one at start if required) |
| `SMART_HOUSE_REQUIRE_AGENT_TOKEN` | `true` |
| `SMART_HOUSE_TLS_CERTFILE` / `TLS_KEYFILE` | unset (plain HTTP + insecure gRPC) |

House JSON is parsed with Pydantic (`HouseFile`). Package assets (dashboard, login pages) are loaded via `importlib.resources`, not hardcoded filesystem roots.

## Multi-sensor ingest

`config/house.json` is the registry. Add another DHT11 or a non-DHT11 gadget by appending a device (`kind` + `driver` + optional `gpio_pin`). The Python **sensor-agent** loads the same file and pushes a `PushSamples` batch every `sample_interval_ms`. Filter with `--device` / `--kind` if one host should not own every probe.

gRPC metadata for ingest:

- `x-agent-token: <token>`
- or `authorization: Bearer <token>`

HTTP fallback (C++ GPIO agent): `POST /v1/samples` with the same headers.

`PushSamples` returns `{accepted, rejected}` so a bad device id does not drop the rest of the batch.

## Control plane vs data plane

**gRPC `HouseHub`** (`:18551`) is the control plane: `ListDevices`, `GetLatest`, `SetEnabled`, `PushSample`, `PushSamples`, `Subscribe`.

**WebSocket** `ws://hub:18443/v1/telemetry` is the data plane for charts. The first frame is a snapshot; then `sample` and `alert` events.

**HTTP** mirrors queries so the Qt app does not have to link `grpc++`. **Read** routes stay unauthenticated so charts keep working. **Write ingest** (`POST /v1/samples`) requires the agent token.

**Account HTTP** is separate and **authenticated**:

| Route | Purpose |
| --- | --- |
| `GET /account/login` | Sign-in page |
| `GET /account/register` | Register page |
| `GET /account/bio` | Bio page (redirects if signed out) |
| `POST /v1/auth/register` | Create account |
| `POST /v1/auth/login` | Unlock vault |
| `POST /v1/auth/logout` | Drop in-memory session |
| `GET /v1/auth/me` | Session check |
| `GET /v1/bio` / `PUT /v1/bio` | Read/write personal info |

## Personal-info protection

Bio fields (name, email, phone, date of birth, address, city, country, emergency contact, household role, notes) never go to disk in plaintext.

1. **Password** — Argon2id hash only (`password_hash`).
2. **Data key** — Argon2id KDF from the password + per-user random salt → 32-byte AES key. The key is **not** stored.
3. **Profile** — AES-256-GCM with random 12-byte nonce and AAD `smarthouse-bio-v1`.
4. **Files** — `data/users/<sha256(username)>.json`, mode `0600`. Filename is not the username.
5. **Session** — unguessable cookie `sh_session`, HttpOnly, SameSite=Lax, Secure when TLS is enabled. The AES key lives in hub RAM for 12 hours. Restarting the hub forgets sessions; ciphertext stays.
6. **Transport** — optional hub TLS (`scripts/gen_dev_certs.sh`). Without it, bind to the LAN only.

Wrong password cannot decrypt the blob. The hub never logs profile fields.

## Ingest protection

- Token compare uses `secrets.compare_digest`.
- Empty `SMART_HOUSE_AGENT_TOKEN` with `REQUIRE_AGENT_TOKEN=true` makes the hub mint a token at startup and print it once — it is not written to disk.
- CORS is an explicit origin list (not `*`) so a browser on another site cannot drive the API with cookies.
- Optional TLS covers both uvicorn and the gRPC port from the same cert/key pair.
- `--no-require-agent-token` is debug-only.

Telemetry **reads** stay open so a Pi outage cannot lock the desktop behind a login prompt. Do not expose the hub to the public internet without TLS and a reverse proxy.

## Desktop

The Qt process is a viewer/controller only. It does not talk to GPIO. **Connect** still opens WebSocket telemetry (unchanged). **Account** opens the hub login page in the system browser so register/bio stay on the encrypted vault.

## Failure and fallback

- If `sensor-agent` is down, the hub simulates every device after `agent_timeout_ms` (5 s).
- If WebSocket drops, the dashboard and desktop reconnect; gRPC agents keep posting.
- If the vault file is truncated, login fails closed; telemetry is unaffected.
- A rejected sample in `PushSamples` does not abort the rest of the batch.

## Adding a gadget

1. Entry in `config/house.json`.
2. Restart hub + sensor-agent (or pass `--device` for a dedicated process).
3. Hub fans out on the existing WebSocket. No new broker.
