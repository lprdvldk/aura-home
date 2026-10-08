from pathlib import Path

from smarthouse_hub.config import load_house_config, locate_house_config
from smarthouse_hub.generated.smarthouse.v1 import house_pb2
from smarthouse_hub.models import SensorSample

from smarthouse_device_reader.protocol import DeviceBinding, DeviceProtocol, WriteCommand


class DeviceReader:
    """Reads and writes gadgets through the protocol registered for each device."""

    def __init__(
        self,
        devices: list[DeviceBinding],
        protocols: dict[str, DeviceProtocol],
        default_protocol: str = "simulator",
    ) -> None:
        if not protocols:
            raise ValueError("DeviceReader requires at least one protocol")
        self._devices = {item.id: item for item in devices}
        self._protocols = protocols
        self._default = default_protocol if default_protocol in protocols else next(iter(protocols))

    @property
    def devices(self) -> list[DeviceBinding]:
        return list(self._devices.values())

    def protocol_for(self, device: DeviceBinding) -> DeviceProtocol:
        proto = self._protocols.get(device.protocol) or self._protocols.get(self._default)
        if proto is None:
            raise KeyError(f"no protocol registered for {device.id} ({device.protocol})")
        return proto

    def read(self, device_id: str | None = None, unix_ms: int = 0) -> list[SensorSample]:
        targets = [self._devices[device_id]] if device_id else [d for d in self._devices.values() if d.enabled]
        if device_id and device_id not in self._devices:
            raise KeyError(device_id)
        samples = []
        for device in targets:
            if not device.enabled and device_id is None:
                continue
            samples.append(self.protocol_for(device).read(device, unix_ms))
        return samples

    def write(self, device_id: str, command: WriteCommand) -> None:
        device = self._devices[device_id]
        self.protocol_for(device).write(device, command)
        if command.enabled is not None:
            device.enabled = command.enabled

    def to_proto(self, samples: list[SensorSample], house_pb2_mod=house_pb2):
        return [
            house_pb2_mod.SensorSample(
                device_id=sample.device_id,
                unix_ms=sample.unix_ms,
                metrics=[
                    house_pb2_mod.Metric(name=m.name, value=m.value, unit=m.unit) for m in sample.metrics
                ],
                error_code=sample.error_code,
                error_message=sample.error_message,
                source=sample.source or "agent",
            )
            for sample in samples
        ]


class DeviceReaderBuilder:
    """Fluent builder: register protocols, load house.json, optionally attach a hub target."""

    def __init__(self) -> None:
        self._protocols: dict[str, DeviceProtocol] = {}
        self._devices: list[DeviceBinding] = []
        self._default = "simulator"
        self.hub_target = ""
        self.hub_token = ""
        self.tls_ca = ""

    def protocol(self, proto: DeviceProtocol) -> "DeviceReaderBuilder":
        self._protocols[proto.name] = proto
        return self

    def default_protocol(self, name: str) -> "DeviceReaderBuilder":
        self._default = name
        return self

    def device(self, binding: DeviceBinding) -> "DeviceReaderBuilder":
        self._devices.append(binding)
        return self

    def devices_from_house(self, path: str | Path) -> "DeviceReaderBuilder":
        house = load_house_config(locate_house_config(Path(path)))
        self._devices.extend(DeviceBinding.from_device(item) for item in house.devices)
        return self

    def hub(self, target: str, *, token: str = "", tls_ca: str = "") -> "DeviceReaderBuilder":
        self.hub_target = target
        self.hub_token = token
        self.tls_ca = tls_ca
        return self

    def build(self) -> DeviceReader:
        if not self._devices:
            raise ValueError("no devices configured")
        return DeviceReader(self._devices, dict(self._protocols), default_protocol=self._default)
