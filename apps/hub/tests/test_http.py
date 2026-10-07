from __future__ import annotations

import asyncio
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

from smarthouse_hub.config import load_house_config
from smarthouse_hub.crypto_vault import UserVault
from smarthouse_hub.http_app import create_http_app
from smarthouse_hub.store import HouseStore


def _store() -> HouseStore:
    path = Path(__file__).resolve().parents[3] / "config" / "house.json"
    return HouseStore(load_house_config(path))


def test_health_and_push(tmp_path: Path) -> None:
    store = _store()
    app = create_http_app(store, UserVault(tmp_path))

    async def run() -> None:
        async with TestClient(TestServer(app)) as client:
            health = await client.get("/health")
            assert health.status == 200
            body = await health.json()
            assert body["ok"] is True
            assert body["devices"] == 4

            pushed = await client.post(
                "/v1/samples",
                json={
                    "device_id": "living-room-dht11",
                    "unix_ms": 1_700_000_000_000,
                    "source": "agent",
                    "metrics": [
                        {"name": "temperature_c", "value": 24, "unit": "°C"},
                        {"name": "humidity_pct", "value": 40, "unit": "%"},
                    ],
                },
            )
            assert pushed.status == 200
            latest = await client.get("/v1/devices/living-room-dht11/latest")
            sample = await latest.json()
            assert sample["metrics"][0]["value"] == 24

    asyncio.run(run())


def test_simulator_ticks() -> None:
    store = _store()

    async def run() -> None:
        await store.tick_simulators()
        assert "living-room-dht11" in store.latest
        temp = store.latest["living-room-dht11"].metric_map()["temperature_c"]
        assert temp == int(temp)

    asyncio.run(run())
