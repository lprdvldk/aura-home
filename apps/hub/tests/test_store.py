import asyncio

from smarthouse_hub.models import Metric, SensorSample
from smarthouse_hub.store import HouseStore


def test_agent_sample_marks_device_online(store: HouseStore) -> None:
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


def test_broadcast_keeps_slow_subscriber(store: HouseStore) -> None:
    async def run() -> None:
        queue = store.subscribe()
        for i in range(400):
            await store._broadcast({"type": "sample", "n": i})
        assert store.subscriber_count() == 1
        assert queue.qsize() == 256
        store.unsubscribe(queue)

    asyncio.run(run())


def test_unknown_device_rejected(store: HouseStore) -> None:
    async def run() -> None:
        ok = await store.push_sample(
            SensorSample(device_id="nope", unix_ms=1, metrics=[]),
            from_agent=True,
        )
        assert ok is False

    asyncio.run(run())
