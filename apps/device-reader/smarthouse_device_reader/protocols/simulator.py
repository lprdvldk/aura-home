from smarthouse_hub.simulators import simulate_sample
from smarthouse_hub.models import SensorSample

from smarthouse_device_reader.protocol import DeviceBinding, DeviceProtocol, WriteCommand


class SimulatorProtocol(DeviceProtocol):
    name = "simulator"

    def __init__(self) -> None:
        self.last_write: dict[str, WriteCommand] = {}

    def read(self, device: DeviceBinding, unix_ms: int) -> SensorSample:
        sample = simulate_sample(device.as_hub_device(), unix_ms)
        sample.source = "agent"
        return sample

    def write(self, device: DeviceBinding, command: WriteCommand) -> None:
        self.last_write[device.id] = command
