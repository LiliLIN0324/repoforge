"""Core agent loop: plan → explore → edit → test → reflect."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from rich.console import Console

from repoforge.agent.planner import Plan, parse_plan
from repoforge.agent.router import route_tier
from repoforge.config import Settings, get_settings
from repoforge.llm.client import LLMClient, get_llm_client
from repoforge.tools import TOOL_SCHEMAS, build_tool_dispatcher
from repoforge.tools.filesystem import RepoSandbox
from repoforge.tools.tests import detect_test_command

Phase = Literal["plan", "explore", "edit", "test", "reflect", "done"]
console = Console()


@dataclass
class StepLog:
    phase: str
    tier: str
    model: str
    content: str
    tool_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    task: str
    repo: str
    success: bool
    plan: Plan | None
    steps: list[StepLog]
    summary: str
    mock: bool


class AgentLoop:
    """Deterministic phase machine with LLM-driven actions inside each phase."""

    def __init__(
        self,
        repo_path: str | Path,
        task: str,
        *,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
        on_event: Callable[[str], None] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or get_llm_client(self.settings)
        self.sandbox = RepoSandbox(repo_path)
        self.task = task
        self.dispatch = build_tool_dispatcher(
            self.sandbox, tavily_key=self.settings.tavily_api_key
        )
        self.on_event = on_event or (lambda msg: console.print(msg))
        self.steps: list[StepLog] = []
        self.failure_count = 0
        self.plan: Plan | None = None

    def run(self) -> AgentResult:
        self.on_event(
            f"[bold cyan]RepoForge[/] repo={self.sandbox.root} "
            f"mock={self.llm.is_mock} task={self.task!r}"
        )

        phase: Phase = "plan"
        summary = ""
        success = False

        for iteration in range(1, self.settings.max_iterations + 1):
            self.on_event(f"\n[bold]── iteration {iteration} · phase={phase} ──[/]")
            if phase == "plan":
                self.plan = self._phase_plan()
                phase = "explore"
            elif phase == "explore":
                self._phase_explore()
                phase = "edit"
            elif phase == "edit":
                self._phase_edit()
                phase = "test"
            elif phase == "test":
                passed, test_blob = self._phase_test()
                if passed:
                    phase = "reflect"
                    summary = "Tests passed after edits."
                else:
                    self.failure_count += 1
                    phase = "reflect"
                    summary = test_blob
            elif phase == "reflect":
                decision = self._phase_reflect(summary)
                if decision.get("status") == "done":
                    success = True
                    summary = decision.get("summary", summary)
                    phase = "done"
                    break
                phase = decision.get("next_phase", "explore")  # type: ignore[assignment]
                if phase not in {"explore", "edit", "test", "plan"}:
                    phase = "explore"
            else:
                break

        if phase != "done" and not success:
            summary = summary or "Max iterations reached without confirmed fix."

        return AgentResult(
            task=self.task,
            repo=str(self.sandbox.root),
            success=success,
            plan=self.plan,
            steps=self.steps,
            summary=summary,
            mock=self.llm.is_mock,
        )

    # ── phases ──────────────────────────────────────────────────────────

    def _phase_plan(self) -> Plan:
        tier = route_tier("plan", self.task, failure_count=self.failure_count)
        resp = self.llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are RepoForge planner. phase=plan. "
                        "Create a short plan as JSON with keys: "
                        "goal, steps (array), risk, tier_hint."
                    ),
                },
                {"role": "user", "content": f"Task: {self.task}\nRepo: {self.sandbox.root}"},
            ],
            tier=tier,
        )
        plan = parse_plan(resp["content"])
        self._log("plan", resp, [])
        self.on_event(f"Plan: {plan.goal}\nSteps: {plan.steps}")
        return plan

    def _phase_explore(self) -> None:
        tier = route_tier("explore", self.task, failure_count=self.failure_count)
        # First: list dir (mock or tool-calling model)
        resp = self.llm.chat(
            [
                {
                    "role": "system",
                    "content": "You are RepoForge explorer. phase=explore. Use tools to inspect the repo.",
                },
                {
                    "role": "user",
                    "content": f"Explore the codebase for: {self.task}",
                },
            ],
            tier=tier,
            tools=TOOL_SCHEMAS,
        )
        tool_results = self._exec_tools(resp)
        # Follow-up reads for demo_repo paths the mock expects
        listing = next((t["result"] for t in tool_results if t["name"] == "list_dir"), "")
        if "calculator.py" in listing or "test_calculator.py" in listing:
            for path in ("calculator.py", "test_calculator.py"):
                if path in listing:
                    content = self.dispatch("read_file", json.dumps({"path": path}))
                    tool_results.append({"name": "read_file", "arguments": {"path": path}, "result": content})
                    self.on_event(f"  read {path} ({len(content)} chars)")
        self._log("explore", resp, tool_results)

    def _phase_edit(self) -> None:
        tier = route_tier("edit", self.task, failure_count=self.failure_count)
        # Give the model the known buggy snippet context in mock/real alike
        try:
            calc = self.sandbox.read_file("calculator.py")
        except FileNotFoundError:
            calc = "(no calculator.py)"
        resp = self.llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are RepoForge editor. phase=edit. "
                        "Propose a patch via apply_edit tool (exact old→new)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Task: {self.task}\n\ncalculator.py:\n```\n{calc}\n```\nPropose a patch.",
                },
            ],
            tier=tier,
            tools=TOOL_SCHEMAS,
        )
        tool_results = self._exec_tools(resp)
        # If mock returned JSON patch without tool call, apply it
        if not tool_results and resp.get("content"):
            try:
                patch = json.loads(resp["content"])
                if {"path", "old", "new"} <= set(patch):
                    result = self.dispatch("apply_edit", json.dumps(patch))
                    tool_results.append(
                        {"name": "apply_edit", "arguments": patch, "result": result}
                    )
            except json.JSONDecodeError:
                pass
        self._log("edit", resp, tool_results)

    def _phase_test(self) -> tuple[bool, str]:
        tier = route_tier("test", self.task, failure_count=self.failure_count)
        cmd = detect_test_command(self.sandbox.root)
        resp = self.llm.chat(
            [
                {
                    "role": "system",
                    "content": "You are RepoForge tester. phase=test. Call run_tests.",
                },
                {"role": "user", "content": f"Run tests. Suggested command: {cmd}"},
            ],
            tier=tier,
            tools=TOOL_SCHEMAS,
        )
        tool_results = self._exec_tools(resp)
        if not tool_results:
            # Always run tests even if model forgot the tool
            result = self.dispatch("run_tests", json.dumps({"command": cmd}))
            tool_results.append({"name": "run_tests", "arguments": {"command": cmd}, "result": result})
        self._log("test", resp, tool_results)
        blob = tool_results[-1]["result"]
        passed = blob.startswith("[PASSED]")
        self.on_event(blob)
        return passed, blob

    def _phase_reflect(self, test_summary: str) -> dict[str, Any]:
        tier = route_tier("reflect", self.task, failure_count=self.failure_count)
        resp = self.llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are RepoForge reflector. phase=reflect. "
                        "Return JSON: {status: done|retry, summary, next_phase?}."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Reflect on test outcome:\n{test_summary}",
                },
            ],
            tier=tier,
        )
        self._log("reflect", resp, [])
        try:
            decision = json.loads(resp["content"])
        except json.JSONDecodeError:
            # Heuristic fallback
            if "[PASSED]" in test_summary:
                decision = {"status": "done", "summary": "Tests passed."}
            else:
                decision = {"status": "retry", "next_phase": "explore", "summary": test_summary}
        self.on_event(f"Reflect: {decision}")
        return decision

    # ── helpers ─────────────────────────────────────────────────────────

    def _exec_tools(self, resp: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tc in resp.get("tool_calls") or []:
            name = tc["name"]
            args = tc.get("arguments") or "{}"
            self.on_event(f"  → tool {name}({args})")
            result = self.dispatch(name, args)
            results.append({"name": name, "arguments": args, "result": result})
            preview = result if len(result) < 300 else result[:300] + "…"
            self.on_event(f"  ← {preview}")
        return results

    def _log(self, phase: str, resp: dict[str, Any], tool_results: list[dict[str, Any]]) -> None:
        self.steps.append(
            StepLog(
                phase=phase,
                tier=str(resp.get("tier", "")),
                model=str(resp.get("model", "")),
                content=str(resp.get("content") or ""),
                tool_results=tool_results,
            )
        )
