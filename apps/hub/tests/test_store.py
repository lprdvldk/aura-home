from __future__ import annotations

import asyncio
from pathlib import Path

from smarthouse_hub.config import load_house_config
from smarthouse_hub.models import Metric, SensorSample
from smarthouse_hub.store import HouseStore


def _store() -> HouseStore:
    path = Path(__file__).resolve().parents[3] / "config" / "house.json"
    return HouseStore(load_house_config(path))


def test_agent_sample_marks_device_online() -> None:
    store = _store()

    async def run() -> None:
        ok = await store.push_sample(
            SensorSample(
                device_id="living-room-dht11",
                unix_ms=1,
                metrics=[Metric("temperature_c", 22, "°C"), Metric("humidity_pct", 41, "%")],
                source="agent",
            ),
            from_agent=True,
        )
        assert ok
        assert store.devices["living-room-dht11"].status.value == "online"
        assert store.latest["living-room-dht11"].metric_map()["temperature_c"] == 22

    asyncio.run(run())


def test_unknown_device_rejected() -> None:
    store = _store()

    async def run() -> None:
        ok = await store.push_sample(
            SensorSample(device_id="nope", unix_ms=1, metrics=[]),
            from_agent=True,
        )
        assert ok is False

    asyncio.run(run())
