from smarthouse_hub.models import Device, SensorSample
from smarthouse_hub.simulators import simulate_sample


def read_sample(device: Device, unix_ms: int) -> SensorSample:
    """Produce one sample for any configured device.

    DHT11, air-quality, light, and motion all share this path. GPIO DHT11
    on a Pi still uses the C++ agent; this reader is the gRPC ingest path.
    """
    sample = simulate_sample(device, unix_ms)
    sample.source = "agent"
    return sample


def to_proto(sample: SensorSample, house_pb2):
    return house_pb2.SensorSample(
        device_id=sample.device_id,
        unix_ms=sample.unix_ms,
        metrics=[
            house_pb2.Metric(name=m.name, value=m.value, unit=m.unit) for m in sample.metrics
        ],
        error_code=sample.error_code,
        error_message=sample.error_message,
        source=sample.source or "agent",
    )
