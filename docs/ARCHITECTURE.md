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
                                     │ gRPC :18551
                     ┌───────────────▼──────────────────────────┐
                     │                 Hub                      │
                     │  Telemetry store (in-memory history)     │
                     │  Device registry (config/house.json)     │
                     │  Account vault (AES-256-GCM at rest)     │
                     │  Simulators until a live agent appears   │
                     └───────────────┬──────────────────────────┘
                                     │ POST /v1/samples  or  HouseHub.PushSample
                     ┌───────────────▼──────────────────────────┐
                     │              Agents                      │
                     │  dht11-agent (GPIO or --simulate)        │
                     │  future: air quality, light, motion      │
                     └──────────────────────────────────────────┘
```

## Repositories and images

| Component | Path | Runtime | Image |
| --- | --- | --- | --- |
| Contract | `proto/smarthouse/v1/house.proto` | — | — |
| Hub | `apps/hub` | Python 3.12 | `aura-home-hub:local` |
| DHT11 agent | `apps/dht11-agent` + `libs/dht11` | C++23 | `aura-home-dht11-agent:local` |
| Desktop | `apps/desktop` | Qt 6 / C++23 | `aura-home-desktop:local` (Linux) |
| House map | `config/house.json` | — | mounted into hub |
| Encrypted bios | `data/users/*.json` | — | hub volume |

CI (`.github/workflows/ci.yml`) runs hub tests, DHT11 unit tests, then builds those three images and publishes:

- `dist/aura-home-images.tar.gz` — `docker load` this on a laptop
- `dist/SmartHouse-linux` — Linux desktop executable
- `dist/smarthouse_dht11_agent-linux` — Linux agent executable

Origin/Depot can run the same GitHub Actions YAML.

## Control plane vs data plane

**gRPC `HouseHub`** (`:18551`) is the control plane for gadgets: `ListDevices`, `GetLatest`, `SetEnabled`, `PushSample`, `Subscribe`.

**WebSocket** `ws://hub:18443/v1/telemetry` is the data plane for charts. The first frame is a snapshot; then `sample` and `alert` events.

**HTTP** mirrors both so the Qt app and agents do not have to link `grpc++`. Existing telemetry routes stay **unauthenticated** so a Pi agent cannot get stuck behind a login.

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
5. **Session** — unguessable cookie `sh_session`, HttpOnly, SameSite=Lax. The AES key lives in hub RAM for 12 hours. Restarting the hub forgets sessions; ciphertext stays.
6. **Transport** — bind to LAN or put TLS in front for anything beyond localhost. The hub itself speaks HTTP for local use.

Wrong password cannot decrypt the blob. The hub never logs profile fields.

## Desktop

The Qt process is a viewer/controller only. It does not talk to GPIO. **Connect** still opens WebSocket telemetry (unchanged). **Account** opens the hub login page in the system browser so register/bio stay on the encrypted vault.

## Failure and fallback

- If `dht11-agent` is down, the hub simulates climate after `agent_timeout_ms` (5 s).
- If WebSocket drops, the dashboard and desktop reconnect; gRPC agents keep posting.
- If the vault file is truncated, login fails closed; telemetry is unaffected.

## Adding a gadget

1. Entry in `config/house.json`.
2. Agent pushes `SensorSample` metrics.
3. Hub fans out on the existing WebSocket. No new broker.
