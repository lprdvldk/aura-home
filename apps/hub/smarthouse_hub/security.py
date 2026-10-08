import secrets

from fastapi import Request, WebSocket

from smarthouse_hub.settings import Settings


def tokens_match(provided: str, expected: str) -> bool:
    if not expected:
        return False
    return secrets.compare_digest(provided, expected)


def token_from_metadata(metadata: object) -> str:
    values = dict(metadata or [])
    bearer = values.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[7:].strip()
    return str(values.get("x-agent-token", "")).strip()


def viewer_from_metadata(metadata: object) -> str:
    values = dict(metadata or [])
    return str(values.get("x-viewer-token", "")).strip()


def token_from_request(request: Request) -> str:
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[7:].strip()
    return request.headers.get("x-agent-token", "").strip()


def viewer_from_request(request: Request) -> str:
    header = request.headers.get("x-viewer-token", "").strip()
    if header:
        return header
    return request.query_params.get("token", "").strip()


def viewer_from_websocket(websocket: WebSocket) -> str:
    header = websocket.headers.get("x-viewer-token", "").strip()
    if header:
        return header
    return websocket.query_params.get("token", "").strip()


def agent_allowed(settings: Settings, provided: str) -> bool:
    if not settings.require_agent_token:
        return True
    return tokens_match(provided, settings.agent_token)


def viewer_allowed(
    settings: Settings,
    *,
    viewer: str = "",
    agent: str = "",
    session: bool = False,
) -> bool:
    if not settings.require_viewer_token:
        return True
    if session:
        return True
    if settings.viewer_token and tokens_match(viewer, settings.viewer_token):
        return True
    return agent_allowed(settings, agent)
