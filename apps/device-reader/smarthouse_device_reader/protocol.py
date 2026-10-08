from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from smarthouse_hub.config import infer_protocol
from smarthouse_hub.models import Device, DeviceKind, SensorSample


@dataclass(slots=True)
class DeviceBinding:
    """One house.json gadget as the reader sees it."""

    id: str
    name: str
    room: str
    kind: str
    driver: str
    protocol: str
    gpio_pin: int = 0
    endpoint: str = ""
    enabled: bool = True

    @classmethod
    def from_device(cls, device: Device) -> "DeviceBinding":
        return cls(
            id=device.id,
            name=device.name,
            room=device.room,
            kind=device.kind.value,
            driver=device.driver,
            protocol=device.protocol or infer_protocol(device.driver),
            gpio_pin=device.gpio_pin,
            endpoint=device.endpoint,
            enabled=device.enabled,
        )

    def as_hub_device(self) -> Device:
        return Device(
            id=self.id,
            name=self.name,
            room=self.room,
            kind=DeviceKind(self.kind),
            driver=self.driver,
            gpio_pin=self.gpio_pin,
            protocol=self.protocol,
            endpoint=self.endpoint,
            enabled=self.enabled,
        )


@dataclass(slots=True)
class WriteCommand:
    action: str
    enabled: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class DeviceProtocol(ABC):
    """Transport for one class of gadgets: GPIO, Zigbee, Wi-Fi, simulator."""

    name: str = "protocol"

    def supports(self, device: DeviceBinding) -> bool:
        return device.protocol == self.name

    @abstractmethod
    def read(self, device: DeviceBinding, unix_ms: int) -> SensorSample:
        raise NotImplementedError

    def write(self, device: DeviceBinding, command: WriteCommand) -> None:
        raise NotImplementedError(f"{self.name} does not support write for {device.id}")
