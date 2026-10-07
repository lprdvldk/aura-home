from __future__ import annotations

import json
from pathlib import Path

from aiohttp import WSMsgType, web

from smarthouse_hub.auth_http import setup_auth
from smarthouse_hub.crypto_vault import UserVault
from smarthouse_hub.models import SensorSample
from smarthouse_hub.store import HouseStore

DASHBOARD_PATH = Path(__file__).with_name("dashboard.html")
STATIC_DIR = Path(__file__).with_name("static")
STORE_KEY = web.AppKey("store", HouseStore)


def create_http_app(store: HouseStore, vault: UserVault | None = None) -> web.Application:
    app = web.Application()
    app[STORE_KEY] = store
    setup_auth(app, vault or UserVault())
    app.router.add_get("/", dashboard)
    app.router.add_get("/favicon.ico", favicon)
    app.router.add_get("/health", health)
    app.router.add_static("/static", STATIC_DIR)
    app.router.add_get("/v1/snapshot", snapshot)
    app.router.add_get("/v1/devices", list_devices)
    app.router.add_get("/v1/devices/{device_id}/latest", latest)
    app.router.add_get("/v1/devices/{device_id}/history", history)
    app.router.add_post("/v1/devices/{device_id}/enabled", set_enabled)
    app.router.add_post("/v1/samples", push_sample)
    app.router.add_get("/v1/telemetry", telemetry)
    app.on_response_prepare.append(_cors)
    return app


async def _cors(_request: web.Request, response: web.StreamResponse) -> None:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,OPTIONS"


async def dashboard(_request: web.Request) -> web.Response:
    return web.FileResponse(DASHBOARD_PATH)


async def favicon(_request: web.Request) -> web.Response:
    return web.Response(status=204)


async def health(request: web.Request) -> web.Response:
    store: HouseStore = request.app[STORE_KEY]
    return web.json_response(
        {
            "ok": True,
            "house": store.config.house_name,
            "devices": len(store.devices),
            "subscribers": store.subscriber_count(),
        }
    )


async def snapshot(request: web.Request) -> web.Response:
    store: HouseStore = request.app[STORE_KEY]
    return web.json_response(store.snapshot())


async def list_devices(request: web.Request) -> web.Response:
    store: HouseStore = request.app[STORE_KEY]
    return web.json_response({"devices": [d.to_json() for d in store.devices.values()]})


async def latest(request: web.Request) -> web.Response:
    store: HouseStore = request.app[STORE_KEY]
    device_id = request.match_info["device_id"]
    sample = store.latest.get(device_id)
    if sample is None:
        raise web.HTTPNotFound(text="no sample yet")
    return web.json_response(sample.to_json())


async def history(request: web.Request) -> web.Response:
    store: HouseStore = request.app[STORE_KEY]
    device_id = request.match_info["device_id"]
    if device_id not in store.devices:
        raise web.HTTPNotFound(text="unknown device")
    limit = int(request.query.get("limit", "180"))
    return web.json_response({"points": store.history_json(device_id, limit)})


async def set_enabled(request: web.Request) -> web.Response:
    store: HouseStore = request.app[STORE_KEY]
    device_id = request.match_info["device_id"]
    if device_id not in store.devices:
        raise web.HTTPNotFound(text="unknown device")
    body = await request.json()
    device = await store.set_enabled(device_id, bool(body.get("enabled", True)))
    return web.json_response(device.to_json())


async def push_sample(request: web.Request) -> web.Response:
    store: HouseStore = request.app[STORE_KEY]
    body = await request.json()
    sample = SensorSample.from_json(body)
    accepted = await store.push_sample(sample, from_agent=True)
    if not accepted:
        raise web.HTTPBadRequest(text="device missing or disabled")
    return web.json_response({"accepted": True})


async def telemetry(request: web.Request) -> web.WebSocketResponse:
    store: HouseStore = request.app[STORE_KEY]
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    await ws.send_json({"type": "snapshot", **store.snapshot()})
    queue = store.subscribe()
    sender = request.loop.create_task(_pump(ws, queue))
    try:
        async for msg in ws:
            if msg.type in {WSMsgType.CLOSE, WSMsgType.ERROR}:
                break
            if msg.type == WSMsgType.TEXT and msg.data == "ping":
                await ws.send_str("pong")
    finally:
        sender.cancel()
        store.unsubscribe(queue)
        await ws.close()
    return ws


async def _pump(ws: web.WebSocketResponse, queue) -> None:
    try:
        while True:
            event = await queue.get()
            if ws.closed:
                return
            await ws.send_str(json.dumps(event))
    except Exception:
        return
