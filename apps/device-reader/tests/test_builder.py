import json
from pathlib import Path

from smarthouse_device_reader.builder import DeviceReaderBuilder
from smarthouse_device_reader.protocol import DeviceBinding, WriteCommand
from smarthouse_device_reader.protocols import GpioProtocol, SimulatorProtocol, WifiProtocol, ZigbeeProtocol


def test_builder_reads_each_protocol(tmp_path: Path) -> None:
    zb = tmp_path / "zb.json"
    zb.write_text(json.dumps({"motion": 1}), encoding="utf-8")
    reader = (
        DeviceReaderBuilder()
        .protocol(SimulatorProtocol())
        .protocol(GpioProtocol(hardware=False))
        .protocol(ZigbeeProtocol())
        .protocol(WifiProtocol())
        .device(
            DeviceBinding(
                id="dht",
                name="dht",
                room="Lab",
                kind="climate",
                driver="dht11",
                protocol="gpio",
                gpio_pin=16,
            )
        )
        .device(
            DeviceBinding(
                id="air",
                name="air",
                room="Lab",
                kind="air_quality",
                driver="simulator",
                protocol="simulator",
            )
        )
        .device(
            DeviceBinding(
                id="zb",
                name="zb",
                room="Lab",
                kind="motion",
                driver="zigbee",
                protocol="zigbee",
                endpoint=zb.resolve().as_uri(),
            )
        )
        .device(
            DeviceBinding(
                id="wifi",
                name="wifi",
                room="Lab",
                kind="climate",
                driver="dht11",
                protocol="wifi",
                endpoint="sim://unit",
            )
        )
        .build()
    )
    samples = {item.device_id: item for item in reader.read(unix_ms=1_700_000_000_000)}
    assert samples["dht"].source == "agent"
    assert samples["dht"].metric_map()["temperature_c"] == int(samples["dht"].metric_map()["temperature_c"])
    assert "pm25_ugm3" in samples["air"].metric_map()
    assert samples["zb"].metric_map()["motion"] == 1.0
    assert "temperature_c" in samples["wifi"].metric_map()


def test_write_simulator_and_gpio_readonly() -> None:
    sim = SimulatorProtocol()
    reader = (
        DeviceReaderBuilder()
        .protocol(sim)
        .protocol(GpioProtocol())
        .device(
            DeviceBinding(
                id="lamp",
                name="lamp",
                room="Hall",
                kind="light",
                driver="simulator",
                protocol="simulator",
            )
        )
        .device(
            DeviceBinding(
                id="probe",
                name="probe",
                room="Lab",
                kind="climate",
                driver="dht11",
                protocol="gpio",
            )
        )
        .build()
    )
    reader.write("lamp", WriteCommand(action="enable", enabled=False))
    assert sim.last_write["lamp"].enabled is False
    assert next(d for d in reader.devices if d.id == "lamp").enabled is False
    try:
        reader.write("probe", WriteCommand(action="enable", enabled=False))
        assert False, "gpio write should fail"
    except NotImplementedError:
        pass


def test_house_json_loads_all_protocols() -> None:
    reader = (
        DeviceReaderBuilder()
        .protocol(SimulatorProtocol())
        .protocol(GpioProtocol())
        .protocol(ZigbeeProtocol())
        .protocol(WifiProtocol())
        .devices_from_house("config/house.json")
        .build()
    )
    names = {d.protocol for d in reader.devices}
    assert {"gpio", "simulator", "zigbee", "wifi"} <= names
    samples = reader.read(unix_ms=42)
    assert len(samples) == len(reader.devices)
