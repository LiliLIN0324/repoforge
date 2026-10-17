"""Planning helpers — parse structured plan JSON from the LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Plan:
    goal: str
    steps: list[str] = field(default_factory=list)
    risk: str = "unknown"
    tier_hint: str = "nano"
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": self.steps,
            "risk": self.risk,
            "tier_hint": self.tier_hint,
        }


def parse_plan(content: str) -> Plan:
    try:
        data = json.loads(content)
        return Plan(
            goal=str(data.get("goal", "")),
            steps=[str(s) for s in data.get("steps", [])],
            risk=str(data.get("risk", "unknown")),
            tier_hint=str(data.get("tier_hint", "nano")),
            raw=content,
        )
    except (json.JSONDecodeError, TypeError, AttributeError):
        return Plan(goal=content.strip()[:500] or "Unstructured plan", raw=content)
