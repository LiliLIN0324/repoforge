"""Filesystem tools: list and read files within a repo root sandbox."""

from __future__ import annotations

from pathlib import Path


class RepoSandbox:
    """Confine all file ops to a single repository root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Repo root does not exist: {self.root}")

    def resolve(self, rel: str) -> Path:
        target = (self.root / rel).resolve()
        if not str(target).startswith(str(self.root)):
            raise PermissionError(f"Path escapes sandbox: {rel}")
        return target

    def list_dir(self, path: str = ".", max_entries: int = 200) -> list[str]:
        target = self.resolve(path)
        if not target.is_dir():
            raise NotADirectoryError(path)
        entries: list[str] = []
        for p in sorted(target.iterdir()):
            if p.name.startswith(".") or p.name in {"__pycache__", ".venv", "node_modules"}:
                continue
            suffix = "/" if p.is_dir() else ""
            entries.append(f"{p.relative_to(self.root)}{suffix}")
            if len(entries) >= max_entries:
                break
        return entries

    def read_file(self, path: str, max_chars: int = 40_000) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise FileNotFoundError(path)
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + f"\n\n... [truncated at {max_chars} chars]"
        return text
