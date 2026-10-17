"""End-to-end dry-run against demo_repo (mock LLM)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from repoforge.agent.loop import AgentLoop
from repoforge.config import Settings
from repoforge.llm.client import LLMClient

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo_repo"


@pytest.fixture
def isolated_demo(tmp_path: Path) -> Path:
    dest = tmp_path / "demo_repo"
    shutil.copytree(DEMO, dest)
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
