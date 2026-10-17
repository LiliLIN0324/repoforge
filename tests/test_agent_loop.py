"""End-to-end dry-run against demo_repo (mock LLM)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from repoforge.agent.loop import (
    AgentLoop,
    extract_json_patch,
    heuristic_calculator_patch,
    normalize_next_phase,
    require_tool,
)
from repoforge.config import Settings
from repoforge.llm.client import LLMClient
from repoforge.tools.filesystem import RepoSandbox

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo_repo"


@pytest.fixture
def isolated_demo(tmp_path: Path) -> Path:
    dest = tmp_path / "demo_repo"
    shutil.copytree(
        DEMO,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return dest


def test_dry_run_fixes_demo_repo(isolated_demo: Path):
    settings = Settings()
    object.__setattr__(settings, "dry_run", True)
    object.__setattr__(settings, "nebius_api_key", "")

    agent = AgentLoop(
        isolated_demo,
        "fix failing tests",
        settings=settings,
        llm=LLMClient(settings),
        on_event=lambda _m: None,
    )
    result = agent.run()
    assert result.mock is True
    assert result.success is True
    assert "return a + b" in (isolated_demo / "calculator.py").read_text(encoding="utf-8")
    phases = [s.phase for s in result.steps]
    assert phases[0] == "plan"
    assert "explore" in phases
    assert "edit" in phases
    assert "test" in phases
    assert "reflect" in phases


def test_normalize_next_phase_implement_means_edit():
    assert normalize_next_phase("implement") == "edit"
    assert normalize_next_phase(" Implementation ") == "edit"
    assert normalize_next_phase("edit") == "edit"
    assert normalize_next_phase("nope") == "explore"
    assert normalize_next_phase(None) == "explore"


def test_extract_json_patch_from_fence():
    patch = {
        "path": "calculator.py",
        "old": "return a - b",
        "new": "return a + b",
    }
    content = "I think this is it:\n```json\n" + json.dumps(patch) + "\n```\n"
    assert extract_json_patch(content) == patch
    assert extract_json_patch("no patch here") is None


class ScriptedLLM:
    is_mock = True

    def __init__(self, replies: list[dict]) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if not self.replies:
            raise AssertionError("ScriptedLLM ran out of replies")
        return self.replies.pop(0)


def _reply(content: str = "", tool_calls: list | None = None) -> dict:
    return {
        "content": content,
        "tool_calls": tool_calls,
        "model": "scripted",
        "tier": "nano",
        "finish_reason": "tool_calls" if tool_calls else "stop",
    }


def _plan() -> dict:
    return _reply(
        json.dumps(
            {
                "goal": "Fix calculator",
                "steps": ["edit", "test"],
                "risk": "low",
                "tier_hint": "nano",
            }
        )
    )


def _phase_of(call: dict) -> str:
    system = next(m["content"] for m in call["messages"] if m["role"] == "system")
    for name in ("plan", "explore", "edit", "test", "reflect"):
        if f"phase={name}" in system:
            return name
    return "?"


def _run(isolated_demo: Path, llm: ScriptedLLM, task: str = "fix failing tests"):
    settings = Settings()
    object.__setattr__(settings, "dry_run", True)
    object.__setattr__(settings, "max_iterations", 12)
    return AgentLoop(
        isolated_demo,
        task,
        settings=settings,
        llm=llm,
        on_event=lambda _m: None,
    ).run()


def test_edit_forces_apply_edit_and_implement_goes_to_edit(isolated_demo: Path):
    real_fix = {
        "path": "calculator.py",
        "old": "return a - b",
        "new": "return a + b",
    }
    noop = {
        "path": "calculator.py",
        "old": "return a * b",
        "new": "return a * b",
    }
    llm = ScriptedLLM(
        [
            _plan(),
            _reply(
                "",
                [
                    {
                        "id": "list",
                        "name": "list_dir",
                        "arguments": json.dumps({"path": "."}),
                    }
                ],
            ),
            _reply(
                "noop",
                [
                    {
                        "id": "edit1",
                        "name": "apply_edit",
                        "arguments": json.dumps(noop),
                    }
                ],
            ),
            _reply(
                "",
                [
                    {
                        "id": "test1",
                        "name": "run_tests",
                        "arguments": json.dumps({"command": "pytest -q"}),
                    }
                ],
            ),
            _reply(
                json.dumps(
                    {
                        "status": "retry",
                        "summary": "still red",
                        "next_phase": "implement",
                    }
                )
            ),
            _reply(
                "fix",
                [
                    {
                        "id": "edit2",
                        "name": "apply_edit",
                        "arguments": json.dumps(real_fix),
                    }
                ],
            ),
            _reply(
                "",
                [
                    {
                        "id": "test2",
                        "name": "run_tests",
                        "arguments": json.dumps({"command": "pytest -q"}),
                    }
                ],
            ),
            _reply(json.dumps({"status": "done", "summary": "Tests passed."})),
        ]
    )
    result = _run(isolated_demo, llm)
    assert result.success is True
    assert _tests_passed(result)
    phases = [_phase_of(call) for call in llm.calls]
    assert phases == ["plan", "explore", "edit", "test", "reflect", "edit", "test", "reflect"]
    edit_calls = [call for call in llm.calls if _phase_of(call) == "edit"]
    test_calls = [call for call in llm.calls if _phase_of(call) == "test"]
    assert all(call["kwargs"]["tool_choice"] == require_tool("apply_edit") for call in edit_calls)
    assert all(call["kwargs"]["tool_choice"] == require_tool("run_tests") for call in test_calls)
    second_edit = edit_calls[1]["messages"][1]["content"]
    assert "Explore findings" in second_edit
    assert "assert add(2, 3) == 5" in second_edit
    assert "Last test result" in second_edit
    assert "[FAILED]" in second_edit
    assert "return a + b" in (isolated_demo / "calculator.py").read_text(encoding="utf-8")


def test_edit_fallback_when_model_only_reads(isolated_demo: Path):
    """Live failure mode: edit calls read_file and never apply_edit."""
    llm = ScriptedLLM(
        [
            _plan(),
            _reply(
                "",
                [
                    {
                        "id": "list",
                        "name": "list_dir",
                        "arguments": json.dumps({"path": "."}),
                    }
                ],
            ),
            _reply(
                "add() subtracts. I will only read the file.",
                [
                    {
                        "id": "read",
                        "name": "read_file",
                        "arguments": json.dumps({"path": "calculator.py"}),
                    }
                ],
            ),
            _reply(""),  # forget run_tests; fallback must still run them
            _reply(json.dumps({"status": "done", "summary": "Tests passed."})),
        ]
    )
    result = _run(isolated_demo, llm)
    assert result.success is True
    assert _tests_passed(result)
    text = (isolated_demo / "calculator.py").read_text(encoding="utf-8")
    assert "return a + b" in text
    # Heuristic replaces the operator and leaves the demo comment in place.
    assert "BUG" in text
    edit_call = next(call for call in llm.calls if _phase_of(call) == "edit")
    assert edit_call["kwargs"]["tool_choice"] == require_tool("apply_edit")


def test_edit_fallback_prefers_json_patch_over_heuristic(isolated_demo: Path):
    patch = {
        "path": "calculator.py",
        "old": "def add(a: int, b: int) -> int:\n    return a - b  # BUG: should be addition\n",
        "new": "def add(a: int, b: int) -> int:\n    return a + b\n",
    }
    llm = ScriptedLLM(
        [
            _plan(),
            _reply(
                "",
                [
                    {
                        "id": "list",
                        "name": "list_dir",
                        "arguments": json.dumps({"path": "."}),
                    }
                ],
            ),
            _reply("```json\n" + json.dumps(patch) + "\n```"),
            _reply(""),
            _reply(json.dumps({"status": "done", "summary": "Tests passed."})),
        ]
    )
    result = _run(isolated_demo, llm)
    assert result.success is True
    assert _tests_passed(result)
    text = (isolated_demo / "calculator.py").read_text(encoding="utf-8")
    assert "return a + b" in text
    assert "BUG" not in text


def _tests_passed(result) -> bool:
    test_steps = [step for step in result.steps if step.phase == "test"]
    if not test_steps:
        return False
    return any(
        str(item.get("result", "")).startswith("[PASSED]")
        for item in test_steps[-1].tool_results
    )


def test_heuristic_skips_unrelated_tasks(isolated_demo: Path):
    sandbox = RepoSandbox(isolated_demo)
    assert heuristic_calculator_patch("fix failing tests", sandbox) is not None
    assert heuristic_calculator_patch("add a README section", sandbox) is None
    text = (isolated_demo / "calculator.py").read_text(encoding="utf-8")
    (isolated_demo / "calculator.py").write_text(
        text.replace("return a - b", "return a + b"),
        encoding="utf-8",
    )
    assert heuristic_calculator_patch("fix failing tests", sandbox) is None
