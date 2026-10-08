from smarthouse_hub.models import Device, DeviceKind
from smarthouse_sensor_agent.readers import read_sample, to_proto


def _device(device_id: str, kind: DeviceKind, driver: str = "simulator") -> Device:
    return Device(
        id=device_id,
        name=device_id,
        room="Lab",
        kind=kind,
        driver=driver,
        gpio_pin=16 if kind == DeviceKind.CLIMATE else 0,
    )


def test_dht11_sample_is_whole_degrees() -> None:
    sample = read_sample(_device("living-room-dht11", DeviceKind.CLIMATE, "dht11"), 1_700_000_000_000)
    values = sample.metric_map()
    assert sample.source == "agent"
    assert values["temperature_c"] == int(values["temperature_c"])
    assert values["humidity_pct"] == int(values["humidity_pct"])


def test_other_kinds_have_expected_metrics() -> None:
    air = read_sample(_device("kitchen-air", DeviceKind.AIR_QUALITY), 1)
    light = read_sample(_device("hallway-light", DeviceKind.LIGHT), 1)
    motion = read_sample(_device("entry-motion", DeviceKind.MOTION), 1)
    assert "pm25_ugm3" in air.metric_map()
    assert "lux" in light.metric_map()
    assert motion.metric_map()["motion"] in (0.0, 1.0)


def test_proto_round_trip_fields() -> None:
    from smarthouse_hub.generated.smarthouse.v1 import house_pb2

    sample = read_sample(_device("bedroom-dht11", DeviceKind.CLIMATE, "dht11"), 42)
    message = to_proto(sample, house_pb2)
    assert message.device_id == "bedroom-dht11"
    assert message.source == "agent"
    assert message.unix_ms == 42
    assert {m.name for m in message.metrics} == {"temperature_c", "humidity_pct"}
