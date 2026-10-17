"""Apply exact-string replacements inside the sandbox."""

from __future__ import annotations

from dataclasses import dataclass

from repoforge.tools.filesystem import RepoSandbox


@dataclass
class EditResult:
    path: str
    applied: bool
    message: str


def apply_edit(sandbox: RepoSandbox, path: str, old: str, new: str) -> EditResult:
    target = sandbox.resolve(path)
    if not target.is_file():
        return EditResult(path=path, applied=False, message=f"File not found: {path}")
    original = target.read_text(encoding="utf-8")
    if old not in original:
        return EditResult(
            path=path,
            applied=False,
            message="Old text not found (exact match required). Re-read the file.",
        )
    count = original.count(old)
    if count > 1:
        return EditResult(
            path=path,
            applied=False,
            message=f"Old text matched {count} times; refine the snippet for uniqueness.",
        )
    target.write_text(original.replace(old, new, 1), encoding="utf-8")
    return EditResult(path=path, applied=True, message="Edit applied successfully.")
