import asyncio
from collections.abc import AsyncIterator

import grpc

from smarthouse_hub.generated.smarthouse.v1 import house_pb2, house_pb2_grpc
from smarthouse_hub.models import (
    KIND_TO_PROTO,
    STATUS_TO_PROTO,
    Device,
    Metric,
    SensorSample,
)
from smarthouse_hub.security import agent_allowed, token_from_metadata
from smarthouse_hub.settings import Settings
from smarthouse_hub.store import HouseStore


def device_to_proto(device: Device) -> house_pb2.Device:
    return house_pb2.Device(
        id=device.id,
        name=device.name,
        room=device.room,
        kind=KIND_TO_PROTO[device.kind],
        status=STATUS_TO_PROTO[device.status],
        enabled=device.enabled,
        driver=device.driver,
        gpio_pin=device.gpio_pin,
    )


def sample_to_proto(sample: SensorSample) -> house_pb2.SensorSample:
    return house_pb2.SensorSample(
        device_id=sample.device_id,
        unix_ms=sample.unix_ms,
        metrics=[
            house_pb2.Metric(name=m.name, value=m.value, unit=m.unit) for m in sample.metrics
        ],
        error_code=sample.error_code,
        error_message=sample.error_message,
        source=sample.source,
    )


def sample_from_proto(message: house_pb2.SensorSample) -> SensorSample:
    return SensorSample(
        device_id=message.device_id,
        unix_ms=message.unix_ms,
        metrics=[Metric(m.name, m.value, m.unit) for m in message.metrics],
        error_code=message.error_code,
        error_message=message.error_message,
        source=message.source or "agent",
    )


class HouseHubServicer(house_pb2_grpc.HouseHubServicer):
    def __init__(self, store: HouseStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    async def _require_agent(self, context: grpc.aio.ServicerContext) -> None:
        provided = token_from_metadata(context.invocation_metadata())
        if not agent_allowed(self.settings, provided):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid agent token")

    async def ListDevices(
        self,
        request: house_pb2.ListDevicesRequest,
        context: grpc.aio.ServicerContext,
    ) -> house_pb2.ListDevicesResponse:
        return house_pb2.ListDevicesResponse(
            devices=[device_to_proto(d) for d in self.store.devices.values()]
        )

    async def GetLatest(
        self,
        request: house_pb2.GetLatestRequest,
        context: grpc.aio.ServicerContext,
    ) -> house_pb2.SensorSample:
        sample = self.store.latest.get(request.device_id)
        if sample is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "no sample yet")
            raise RuntimeError("unreachable")
        return sample_to_proto(sample)

    async def SetEnabled(
        self,
        request: house_pb2.SetEnabledRequest,
        context: grpc.aio.ServicerContext,
    ) -> house_pb2.Device:
        if request.device_id not in self.store.devices:
            await context.abort(grpc.StatusCode.NOT_FOUND, "unknown device")
        device = await self.store.set_enabled(request.device_id, request.enabled)
        return device_to_proto(device)

    async def PushSample(
        self,
        request: house_pb2.SensorSample,
        context: grpc.aio.ServicerContext,
    ) -> house_pb2.PushSampleResponse:
        await self._require_agent(context)
        sample = sample_from_proto(request)
        accepted = await self.store.push_sample(sample, from_agent=True)
        if not accepted:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "device missing or disabled")
        return house_pb2.PushSampleResponse(accepted=True)

    async def PushSamples(
        self,
        request: house_pb2.PushSamplesRequest,
        context: grpc.aio.ServicerContext,
    ) -> house_pb2.PushSamplesResponse:
        await self._require_agent(context)
        accepted = 0
        rejected = 0
        for item in request.samples:
            ok = await self.store.push_sample(sample_from_proto(item), from_agent=True)
            if ok:
                accepted += 1
            else:
                rejected += 1
        return house_pb2.PushSamplesResponse(accepted=accepted, rejected=rejected)

    async def Subscribe(
        self,
        request: house_pb2.SubscribeRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[house_pb2.SensorSample]:
        wanted = set(request.device_ids)
        queue = self.store.subscribe()
        try:
            while True:
                if context.cancelled():
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except TimeoutError:
                    continue
                if event.get("type") != "sample":
                    continue
                sample = SensorSample.from_json(event["sample"])
                if wanted and sample.device_id not in wanted:
                    continue
                yield sample_to_proto(sample)
        finally:
            self.store.unsubscribe(queue)
