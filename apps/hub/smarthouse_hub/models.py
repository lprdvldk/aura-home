from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self


class DeviceKind(StrEnum):
    CLIMATE = "climate"
    AIR_QUALITY = "air_quality"
    LIGHT = "light"
    MOTION = "motion"


class DeviceStatus(StrEnum):
    ONLINE = "online"
    SIMULATED = "simulated"
    OFFLINE = "offline"
    ERROR = "error"
    DISABLED = "disabled"


KIND_TO_PROTO = {
    DeviceKind.CLIMATE: 1,
    DeviceKind.AIR_QUALITY: 2,
    DeviceKind.LIGHT: 3,
    DeviceKind.MOTION: 4,
}

STATUS_TO_PROTO = {
    DeviceStatus.ONLINE: 1,
    DeviceStatus.SIMULATED: 2,
    DeviceStatus.OFFLINE: 3,
    DeviceStatus.ERROR: 4,
    DeviceStatus.DISABLED: 5,
}

PROTO_TO_KIND = {v: k for k, v in KIND_TO_PROTO.items()}
PROTO_TO_STATUS = {v: k for k, v in STATUS_TO_PROTO.items()}


@dataclass(slots=True)
class Metric:
    name: str
    value: float
    unit: str

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "unit": self.unit}


@dataclass(slots=True)
class SensorSample:
    device_id: str
    unix_ms: int
    metrics: list[Metric]
    error_code: int = 0
    error_message: str = ""
    source: str = "simulator"

    def metric_map(self) -> dict[str, float]:
        return {m.name: m.value for m in self.metrics}

    def to_json(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "unix_ms": self.unix_ms,
            "metrics": [m.to_json() for m in self.metrics],
            "error_code": self.error_code,
            "error_message": self.error_message,
            "source": self.source,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        metrics = [
            Metric(name=str(m["name"]), value=float(m["value"]), unit=str(m.get("unit", "")))
            for m in data.get("metrics", [])
        ]
        return cls(
            device_id=str(data["device_id"]),
            unix_ms=int(data.get("unix_ms", 0)),
            metrics=metrics,
            error_code=int(data.get("error_code", 0)),
            error_message=str(data.get("error_message", "")),
            source=str(data.get("source", "agent")),
        )


@dataclass(slots=True)
class Device:
    id: str
    name: str
    room: str
    kind: DeviceKind
    driver: str
    gpio_pin: int = 0
    enabled: bool = True
    status: DeviceStatus = DeviceStatus.SIMULATED
    last_seen_ms: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "room": self.room,
            "kind": self.kind.value,
            "driver": self.driver,
            "gpio_pin": self.gpio_pin,
            "enabled": self.enabled,
            "status": self.status.value,
            "last_seen_ms": self.last_seen_ms,
        }


@dataclass(slots=True)
class Alert:
    id: str
    device_id: str
    metric: str
    message: str
    severity: str
    unix_ms: int

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "metric": self.metric,
            "message": self.message,
            "severity": self.severity,
            "unix_ms": self.unix_ms,
        }


@dataclass(slots=True)
class Threshold:
    low: float
    high: float


@dataclass(slots=True)
class HouseConfig:
    house_name: str
    sample_interval_ms: int
    agent_timeout_ms: int
    history_points: int
    thresholds: dict[str, Threshold] = field(default_factory=dict)
    devices: list[Device] = field(default_factory=list)
