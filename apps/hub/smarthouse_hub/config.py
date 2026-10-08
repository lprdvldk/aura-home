from pathlib import Path

from pydantic import BaseModel, Field

from smarthouse_hub.models import Device, DeviceKind, HouseConfig, Threshold


class ThresholdModel(BaseModel):
    low: float
    high: float


class DeviceModel(BaseModel):
    id: str
    name: str
    room: str
    kind: DeviceKind
    driver: str = "simulator"
    gpio_pin: int = 0
    enabled: bool = True


class HouseFile(BaseModel):
    house_name: str = "Home"
    sample_interval_ms: int = 1000
    agent_timeout_ms: int = 5000
    history_points: int = 360
    thresholds: dict[str, ThresholdModel] = Field(default_factory=dict)
    devices: list[DeviceModel] = Field(default_factory=list)

    def to_house_config(self) -> HouseConfig:
        return HouseConfig(
            house_name=self.house_name,
            sample_interval_ms=self.sample_interval_ms,
            agent_timeout_ms=self.agent_timeout_ms,
            history_points=self.history_points,
            thresholds={name: Threshold(low=item.low, high=item.high) for name, item in self.thresholds.items()},
            devices=[
                Device(
                    id=item.id,
                    name=item.name,
                    room=item.room,
                    kind=item.kind,
                    driver=item.driver,
                    gpio_pin=item.gpio_pin,
                    enabled=item.enabled,
                )
                for item in self.devices
            ],
        )


def load_house_config(path: Path) -> HouseConfig:
    return HouseFile.model_validate_json(path.read_text(encoding="utf-8")).to_house_config()


def locate_house_config(preferred: Path) -> Path:
    if preferred.is_file():
        return preferred
    for candidate in (
        Path("config/house.json"),
        Path("../config/house.json"),
        Path("../../config/house.json"),
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "house config not found; set SMART_HOUSE_HOUSE_CONFIG or run from the repo root"
    )
