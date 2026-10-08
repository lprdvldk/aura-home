#!/usr/bin/env python3
"""Generate Python gRPC stubs from proto/smarthouse/v1/house.proto. Run from the repo root."""

import sys
from pathlib import Path

from grpc_tools import protoc


PROTO_DIR = Path("proto")
OUT_DIR = Path("apps/hub/smarthouse_hub/generated")


def generate() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").write_text("", encoding="utf-8")
    proto = PROTO_DIR / "smarthouse" / "v1" / "house.proto"
    code = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={OUT_DIR}",
            f"--grpc_python_out={OUT_DIR}",
            str(proto),
        ]
    )
    if code != 0:
        raise SystemExit(f"protoc failed with exit code {code}")

    grpc_file = OUT_DIR / "smarthouse" / "v1" / "house_pb2_grpc.py"
    text = grpc_file.read_text(encoding="utf-8")
    text = text.replace(
        "from smarthouse.v1 import house_pb2 as smarthouse_dot_v1_dot_house__pb2",
        "from . import house_pb2 as smarthouse_dot_v1_dot_house__pb2",
    )
    grpc_file.write_text(text, encoding="utf-8")
    print(f"generated stubs in {OUT_DIR / 'smarthouse' / 'v1'}")


if __name__ == "__main__":
    generate()
