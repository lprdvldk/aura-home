import secrets

from fastapi import Request

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


def token_from_request(request: Request) -> str:
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[7:].strip()
    return request.headers.get("x-agent-token", "").strip()


def agent_allowed(settings: Settings, provided: str) -> bool:
    if not settings.require_agent_token:
        return True
    return tokens_match(provided, settings.agent_token)
