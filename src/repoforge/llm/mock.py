"""Deterministic mock LLM for dry-run demos without an API key."""

from __future__ import annotations

import json
from typing import Any, Literal

Tier = Literal["nano", "super", "ultra"]


class MockLLMClient:
    """Emulates plan → explore → edit → test → reflect for the demo_repo bug."""

    def __init__(self) -> None:
        self._step = 0

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = "nano",
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # tool_choice is accepted so the live client and the mock share a
        # signature. The scripted demo already emits the phase's tool call.
        del tool_choice
        self._step += 1
        last_user = _last_role(messages, "user")
        last_system = _last_role(messages, "system")
        combined = f"{last_system}\n{last_user}".lower()

        # Phase detection from agent prompts
        if "create a short plan" in combined or "phase=plan" in combined:
            return _resp(
                tier,
                content=json.dumps(
                    {
                        "goal": "Fix failing calculator tests in demo_repo",
                        "steps": [
                            "List repo files",
                            "Read calculator.py and test_calculator.py",
                            "Identify bug (add returns wrong result)",
                            "Apply minimal patch",
                            "Re-run tests",
                        ],
                        "risk": "low",
                        "tier_hint": "nano",
                    },
                    indent=2,
                ),
            )

        if "phase=explore" in combined or "explore the codebase" in combined:
            # Prefer tool call if tools provided
            if tools:
                return _resp(
                    tier,
                    content="",
                    tool_calls=[
                        {
                            "id": "call_list_1",
                            "name": "list_dir",
                            "arguments": json.dumps({"path": "."}),
                        }
                    ],
                )
            return _resp(
                tier,
                content="Files of interest: calculator.py, test_calculator.py",
            )

        if "phase=edit" in combined or "propose a patch" in combined:
            patch = {
                "path": "calculator.py",
                "old": "def add(a: int, b: int) -> int:\n    return a - b  # BUG: should be addition\n",
                "new": "def add(a: int, b: int) -> int:\n    return a + b\n",
                "rationale": "add() incorrectly subtracts; tests expect a + b",
            }
            if tools:
                return _resp(
                    tier,
                    content="Applying fix to calculator.add",
                    tool_calls=[
                        {
                            "id": "call_edit_1",
                            "name": "apply_edit",
                            "arguments": json.dumps(patch),
                        }
                    ],
                )
            return _resp(tier, content=json.dumps(patch, indent=2))

        if "phase=test" in combined or "run tests" in combined:
            if tools:
                return _resp(
                    tier,
                    content="",
                    tool_calls=[
                        {
                            "id": "call_test_1",
                            "name": "run_tests",
                            "arguments": json.dumps({"command": "pytest -q"}),
                        }
                    ],
                )
            return _resp(tier, content="Run pytest -q")

        if "phase=reflect" in combined or "reflect on" in combined:
            if "passed" in combined or "ok" in combined or "0 failed" in combined:
                return _resp(
                    tier,
                    content=json.dumps(
                        {
                            "status": "done",
                            "summary": "Bug fixed: add() now returns a + b. All tests pass.",
                        }
                    ),
                )
            return _resp(
                tier,
                content=json.dumps(
                    {
                        "status": "retry",
                        "summary": "Tests still failing; re-read and patch again.",
                        "next_phase": "explore",
                    }
                ),
            )

        # Generic fallback — still useful for free-form prompts
        if "failing" in combined or "fix" in combined:
            return _resp(
                tier,
                content=(
                    "Plan: inspect demo_repo calculator, fix add() to return "
                    "a + b instead of a - b, then re-run pytest."
                ),
            )

        return _resp(
            tier,
            content=f"[mock/{tier}] Acknowledged. Step={self._step}. Provide a phase= hint.",
        )


def _last_role(messages: list[dict[str, str]], role: str) -> str:
    for m in reversed(messages):
        if m.get("role") == role:
            return m.get("content") or ""
    return ""


def _resp(
    tier: Tier,
    *,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "content": content,
        "tool_calls": tool_calls,
        "model": f"mock-nemotron-{tier}",
        "tier": tier,
        "finish_reason": "tool_calls" if tool_calls else "stop",
    }
