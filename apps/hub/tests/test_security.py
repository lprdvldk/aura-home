from smarthouse_hub.security import agent_allowed, token_from_metadata, tokens_match
from smarthouse_hub.settings import Settings


def test_tokens_match_rejects_empty_and_wrong() -> None:
    assert tokens_match("abc", "abc") is True
    assert tokens_match("abc", "abd") is False
    assert tokens_match("", "abc") is False
    assert tokens_match("abc", "") is False


def test_agent_allowed_can_be_disabled() -> None:
    open_settings = Settings(require_agent_token=False, agent_token="")
    assert agent_allowed(open_settings, "") is True
    locked = Settings(require_agent_token=True, agent_token="secret")
    assert agent_allowed(locked, "secret") is True
    assert agent_allowed(locked, "nope") is False
    assert agent_allowed(locked, "") is False


def test_token_from_metadata_bearer_and_custom() -> None:
    assert token_from_metadata((("x-agent-token", "one"),)) == "one"
    assert token_from_metadata((("authorization", "Bearer two"),)) == "two"
    assert token_from_metadata((("authorization", "bearer two"),)) == "two"
    assert token_from_metadata(()) == ""
