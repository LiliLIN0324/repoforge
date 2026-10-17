"""Model routing: Nano for cheap exploration, Super/Ultra for hard reasoning."""

from __future__ import annotations

from typing import Literal

Tier = Literal["nano", "super", "ultra"]

HARD_KEYWORDS = (
    "architecture",
    "refactor",
    "race condition",
    "deadlock",
    "security",
    "migrate",
    "performance",
    "distributed",
    "concurrency",
    "design",
)


def route_tier(
    phase: str,
    task: str,
    *,
    failure_count: int = 0,
    force: Tier | None = None,
) -> Tier:
    """Pick a Nemotron tier based on phase and task difficulty signals."""
    if force:
        return force

    task_l = task.lower()
    hard = any(k in task_l for k in HARD_KEYWORDS) or failure_count >= 2

    if phase == "plan":
        return "ultra" if hard else "super"
    if phase == "reflect":
        return "super" if failure_count else "nano"
    if phase in {"explore", "edit", "test"}:
        return "super" if hard and phase == "edit" else "nano"
    return "nano"
