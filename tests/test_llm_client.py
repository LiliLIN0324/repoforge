"""LLMClient forwards tool_choice to the OpenAI SDK and ignores it when mocking."""

from __future__ import annotations

from repoforge.config import Settings
from repoforge.llm.client import LLMClient


class _Message:
    def __init__(self, content: str = "ok", tool_calls=None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self) -> None:
        self.message = _Message()
        self.finish_reason = "stop"


class _Response:
    def __init__(self) -> None:
        self.choices = [_Choice()]


def _live_settings() -> Settings:
    settings = Settings()
    object.__setattr__(settings, "dry_run", False)
    object.__setattr__(settings, "nebius_api_key", "test-key-not-real")
    return settings


def test_chat_passes_tool_choice_to_openai(monkeypatch):
    captured: dict = {}

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            self.chat = _Chat()

    monkeypatch.setattr("repoforge.llm.client.OpenAI", _FakeOpenAI)
    client = LLMClient(_live_settings())
    choice = {"type": "function", "function": {"name": "apply_edit"}}
    tools = [{"type": "function", "function": {"name": "apply_edit", "parameters": {}}}]
    result = client.chat(
        [{"role": "user", "content": "fix it"}],
        tools=tools,
        tool_choice=choice,
    )
    assert captured["tool_choice"] == choice
    assert captured["tools"] == tools
    assert result["content"] == "ok"
    assert client.is_mock is False


def test_chat_omits_tool_choice_when_unset(monkeypatch):
    captured: dict = {}

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            self.chat = _Chat()

    monkeypatch.setattr("repoforge.llm.client.OpenAI", _FakeOpenAI)
    client = LLMClient(_live_settings())
    client.chat([{"role": "user", "content": "plan"}])
    assert "tool_choice" not in captured
    assert "tools" not in captured


def test_mock_chat_accepts_tool_choice_without_calling_openai():
    settings = Settings()
    object.__setattr__(settings, "dry_run", True)
    object.__setattr__(settings, "nebius_api_key", "")
    client = LLMClient(settings)
    result = client.chat(
        [
            {"role": "system", "content": "You are RepoForge editor. phase=edit."},
            {"role": "user", "content": "Propose a patch."},
        ],
        tools=[{"type": "function", "function": {"name": "apply_edit"}}],
        tool_choice={"type": "function", "function": {"name": "apply_edit"}},
    )
    assert client.is_mock is True
    assert result["tool_calls"]
    assert result["tool_calls"][0]["name"] == "apply_edit"
