"""Run test commands inside the repo sandbox."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from repoforge.tools.filesystem import RepoSandbox

# Leading `pytest`, `python -m pytest`, or `python3 -m pytest`.
_PYTEST_LEAD = re.compile(r"^(?:(?:python3?|py)\s+-m\s+)?pytest\b")


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
    """Execute a shell test command with cwd = the sandbox repo root.

    Pytest walks parents for ``pyproject.toml``. A demo repo checked out
    inside this package would otherwise adopt the parent ``testpaths`` and
    ``pythonpath``. Commands are pinned to ``sandbox.root`` and, when that
    directory has no pytest config of its own, an empty config file so the
    parent project is not the rootdir.
    """
    cmd, config_file = prepare_test_command(command, sandbox.root)
    # Ignore bytecode copied alongside the sources (a parent checkout's
    # __pycache__ can keep executing the unfixed module).
    pyc_dir = Path(tempfile.mkdtemp(prefix="repoforge-pyc-"))
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(pyc_dir)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(sandbox.root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    finally:
        if config_file is not None:
            config_file.unlink(missing_ok=True)
        shutil.rmtree(pyc_dir, ignore_errors=True)
    return TestResult(
        command=cmd,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def prepare_test_command(command: str, root: Path) -> tuple[str, Path | None]:
    """Return ``(shell_command, temp_config_or_none)`` for ``run_tests``.

    The temp ini must be deleted by the caller. Non-pytest commands are unchanged.
    """
    original = command.strip()
    if not _PYTEST_LEAD.match(original):
        return command, None

    cmd = _bind_pytest_interpreter(original)
    extras: list[str] = []
    # Relative --rootdir/--confcutdir are resolved against cwd, which run_tests
    # sets to the sandbox root (not the parent package).
    if "--rootdir" not in cmd:
        extras.append("--rootdir .")
    if "--confcutdir" not in cmd:
        extras.append("--confcutdir .")

    config_file: Path | None = None
    if not _has_local_pytest_config(root) and "-c " not in cmd and "--config-file" not in cmd:
        fd, name = tempfile.mkstemp(prefix="repoforge-pytest-", suffix=".ini")
        os.close(fd)
        config_file = Path(name)
        config_file.write_text("[pytest]\n", encoding="utf-8")
        extras.append(f"-c {shlex.quote(str(config_file))}")

    if extras:
        cmd = f"{cmd} {' '.join(extras)}"
    return cmd, config_file


def _bind_pytest_interpreter(command: str) -> str:
    """Use this process's interpreter so ``pytest`` / ``python`` need not be on PATH."""
    exe = shlex.quote(sys.executable)
    return _PYTEST_LEAD.sub(f"{exe} -m pytest", command.strip(), count=1)


def _has_local_pytest_config(root: Path) -> bool:
    if (root / "pytest.ini").is_file():
        return True
    tox = root / "tox.ini"
    if tox.is_file() and "[pytest]" in tox.read_text(encoding="utf-8", errors="ignore"):
        return True
    setup_cfg = root / "setup.cfg"
    if setup_cfg.is_file():
        text = setup_cfg.read_text(encoding="utf-8", errors="ignore")
        if "[tool:pytest]" in text or "[pytest]" in text:
            return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and "[tool.pytest" in pyproject.read_text(encoding="utf-8", errors="ignore"):
        return True
    return False


def detect_test_command(root: Path) -> str:
    """Suggest a test command. ``run_tests`` still forces cwd to ``root``."""
    if (root / "package.json").exists():
        return "npm test --silent"
    if (
        (root / "pyproject.toml").exists()
        or (root / "pytest.ini").exists()
        or list(root.glob("test_*.py"))
        or list(root.glob("**/test_*.py"))
    ):
        return "python -m pytest -q"
    return "python -m pytest -q"
