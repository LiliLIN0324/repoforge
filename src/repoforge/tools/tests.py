"""Run test commands inside the repo sandbox."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from repoforge.tools.filesystem import RepoSandbox


@dataclass
class TestResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    def summary(self, max_chars: int = 4000) -> str:
        blob = (self.stdout or "") + ("\n" + self.stderr if self.stderr else "")
        blob = blob.strip()
        status = "PASSED" if self.passed else "FAILED"
        header = f"[{status}] `{self.command}` (exit={self.returncode})\n"
        if len(blob) > max_chars:
            blob = blob[:max_chars] + "\n... [truncated]"
        return header + blob


def run_tests(
    sandbox: RepoSandbox,
    command: str = "pytest -q",
    *,
    timeout: int = 60,
) -> TestResult:
    """Execute a shell test command with cwd=repo root. No network assumed."""
    # Prefer local venv pytest if present; otherwise system pytest / python -m
    cmd = command
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=str(sandbox.root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return TestResult(
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def detect_test_command(root: Path) -> str:
    if (root / "package.json").exists():
        return "npm test --silent"
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or list(root.glob("test_*.py")) or list(root.glob("**/test_*.py")):
        return "python -m pytest -q"
    return "python -m pytest -q"
