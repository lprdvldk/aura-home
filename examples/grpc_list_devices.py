#!/usr/bin/env python3
"""List hub devices over gRPC. Run from the repo root with PYTHONPATH=apps/hub."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path("apps/hub")))

import grpc
from smarthouse_hub.generated.smarthouse.v1 import house_pb2, house_pb2_grpc


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="127.0.0.1:18551")
    args = parser.parse_args()
    async with grpc.aio.insecure_channel(args.target) as channel:
        stub = house_pb2_grpc.HouseHubStub(channel)
        response = await stub.ListDevices(house_pb2.ListDevicesRequest())
        for device in response.devices:
            print(f"{device.id:24}  {device.room:16}  kind={device.kind}  on={device.enabled}")


if __name__ == "__main__":
    asyncio.run(main())
