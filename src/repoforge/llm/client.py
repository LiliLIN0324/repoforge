"""OpenAI-compatible LLM client pointed at Nebius Token Factory."""

from __future__ import annotations

from typing import Any, Literal

from openai import OpenAI

from repoforge.config import Settings, get_settings
from repoforge.llm.mock import MockLLMClient

Tier = Literal["nano", "super", "ultra"]


class LLMClient:
    """Thin wrapper around the OpenAI SDK for Token Factory."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: OpenAI | None = None
        if not self.settings.use_mock:
            self._client = OpenAI(
                api_key=self.settings.nebius_api_key,
                base_url=self.settings.nebius_base_url,
            )

    @property
    def is_mock(self) -> bool:
        return self.settings.use_mock

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = "nano",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return a normalized response dict with content / tool_calls / model."""
        if self.settings.use_mock:
            return MockLLMClient().chat(messages, tier=tier, tools=tools)

        assert self._client is not None
        model = self.settings.model_for(tier)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in msg.tool_calls
            ]
        return {
            "content": msg.content or "",
            "tool_calls": tool_calls,
            "model": model,
            "tier": tier,
            "finish_reason": choice.finish_reason,
        }


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    return LLMClient(settings)
