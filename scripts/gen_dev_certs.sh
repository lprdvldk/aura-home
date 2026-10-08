#!/usr/bin/env bash
# Self-signed hub certificate for local TLS. Not for a public hostname.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/certs"
openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:hub,IP:127.0.0.1" \
  -keyout "$ROOT/certs/hub.key" \
  -out "$ROOT/certs/hub.crt"
chmod 600 "$ROOT/certs/hub.key"
echo "wrote $ROOT/certs/hub.crt and $ROOT/certs/hub.key"
echo "hub:   SMART_HOUSE_TLS_CERTFILE=certs/hub.crt SMART_HOUSE_TLS_KEYFILE=certs/hub.key"
echo "agent: --tls-ca certs/hub.crt"
