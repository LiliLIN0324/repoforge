"""Simple ripgrep-style text search within the repo sandbox."""

from __future__ import annotations

import re
from dataclasses import dataclass

from repoforge.tools.filesystem import RepoSandbox


@dataclass
class SearchHit:
    path: str
    line: int
    text: str


def search_text(
    sandbox: RepoSandbox,
    pattern: str,
    *,
    glob: str = "*.py",
    max_hits: int = 50,
) -> list[SearchHit]:
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex: {exc}") from exc

    hits: list[SearchHit] = []
    for path in sandbox.root.rglob(glob):
        if any(part.startswith(".") or part in {"__pycache__", ".venv", "node_modules"} for part in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, start=1):
            if regex.search(line):
                hits.append(
                    SearchHit(
                        path=str(path.relative_to(sandbox.root)),
                        line=i,
                        text=line.rstrip()[:200],
                    )
                )
                if len(hits) >= max_hits:
                    return hits
    return hits
