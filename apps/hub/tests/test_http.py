from fastapi.testclient import TestClient

from smarthouse_hub.store import HouseStore


def test_health_and_push(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["devices"] == 4

    pushed = client.post(
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
    assert pushed.status_code == 200
    latest = client.get("/v1/devices/living-room-dht11/latest")
    sample = latest.json()
    assert sample["metrics"][0]["value"] == 24


def test_simulator_ticks(store: HouseStore) -> None:
    import asyncio

    asyncio.run(store.tick_simulators())
    assert "living-room-dht11" in store.latest
    temp = store.latest["living-room-dht11"].metric_map()["temperature_c"]
    assert temp == int(temp)
