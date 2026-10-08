import asyncio

import grpc
import pytest

from smarthouse_hub.config import load_house_config
from smarthouse_hub.generated.smarthouse.v1 import house_pb2, house_pb2_grpc
from smarthouse_hub.grpc_servicer import HouseHubServicer
from smarthouse_hub.settings import Settings
from smarthouse_hub.store import HouseStore


def _climate(device_id: str, unix_ms: int = 1) -> house_pb2.SensorSample:
    return house_pb2.SensorSample(
        device_id=device_id,
        unix_ms=unix_ms,
        source="agent",
        metrics=[
            house_pb2.Metric(name="temperature_c", value=23, unit="°C"),
            house_pb2.Metric(name="humidity_pct", value=40, unit="%"),
        ],
    )


def test_grpc_push_samples_requires_token_and_accepts_batch(house_config_path) -> None:
    async def run() -> None:
        store = HouseStore(load_house_config(house_config_path))
        settings = Settings(agent_token="secret-token", require_agent_token=True)
        server = grpc.aio.server()
        house_pb2_grpc.add_HouseHubServicer_to_server(HouseHubServicer(store, settings), server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub = house_pb2_grpc.HouseHubStub(channel)
                with pytest.raises(grpc.aio.AioRpcError) as denied:
                    await stub.PushSample(_climate("living-room-dht11"))
                assert denied.value.code() == grpc.StatusCode.UNAUTHENTICATED

                ok = await stub.PushSample(
                    _climate("living-room-dht11"),
                    metadata=(("x-agent-token", "secret-token"),),
                )
                assert ok.accepted is True
                assert store.devices["living-room-dht11"].status.value == "online"

                batch = await stub.PushSamples(
                    house_pb2.PushSamplesRequest(
                        samples=[
                            _climate("bedroom-dht11", 2),
                            _climate("bathroom-dht11", 3),
                            house_pb2.SensorSample(device_id="nope", unix_ms=4, source="agent"),
                        ]
                    ),
                    metadata=(("authorization", "Bearer secret-token"),),
                )
                assert batch.accepted == 2
                assert batch.rejected == 1
                assert "bedroom-dht11" in store.latest
                assert "bathroom-dht11" in store.latest
        finally:
            await server.stop(0)

    asyncio.run(run())
