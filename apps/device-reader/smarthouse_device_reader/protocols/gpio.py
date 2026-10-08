import json
import os
import shutil
import subprocess

from smarthouse_hub.models import SensorSample
from smarthouse_hub.simulators import simulate_sample

from smarthouse_device_reader.protocol import DeviceBinding, DeviceProtocol, WriteCommand


class GpioProtocol(DeviceProtocol):
    """Raspberry Pi GPIO / 1-wire. DHT11 uses the C++ oneshot reader when present."""

    name = "gpio"

    def __init__(self, *, hardware: bool = False, binary: str | None = None, chip: str = "/dev/gpiochip0") -> None:
        self.hardware = hardware
        self.binary = binary or os.environ.get("SMART_HOUSE_GPIO_READER", "smarthouse_dht11_agent")
        self.chip = chip

    def read(self, device: DeviceBinding, unix_ms: int) -> SensorSample:
        if self.hardware:
            sample = self._read_hardware(device, unix_ms)
            if sample is not None:
                return sample
        sample = simulate_sample(device.as_hub_device(), unix_ms)
        sample.source = "agent"
        return sample

    def write(self, device: DeviceBinding, command: WriteCommand) -> None:
        raise NotImplementedError(f"GPIO device {device.id} is read-only ({command.action})")

    def _read_hardware(self, device: DeviceBinding, unix_ms: int) -> SensorSample | None:
        path = shutil.which(self.binary) or (self.binary if os.path.isfile(self.binary) else "")
        if not path:
            return SensorSample(
                device_id=device.id,
                unix_ms=unix_ms,
                metrics=[],
                error_code=3,
                error_message=f"gpio reader not found: {self.binary}",
                source="agent",
            )
        cmd = [
            path,
            "--once",
            "--gpio",
            "--pin",
            str(device.gpio_pin),
            "--device-id",
            device.id,
        ]
        try:
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return SensorSample(
                device_id=device.id,
                unix_ms=unix_ms,
                metrics=[],
                error_code=3,
                error_message=str(exc),
                source="agent",
            )
        line = (completed.stdout or "").strip().splitlines()
        if completed.returncode != 0 or not line:
            return SensorSample(
                device_id=device.id,
                unix_ms=unix_ms,
                metrics=[],
                error_code=completed.returncode or 3,
                error_message=(completed.stderr or "gpio read failed").strip(),
                source="agent",
            )
        return SensorSample.from_json(json.loads(line[-1]))
