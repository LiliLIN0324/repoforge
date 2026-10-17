"""Agent tools: filesystem, search, edit, tests, (stub) research."""

from __future__ import annotations

import json
from typing import Any, Callable

from repoforge.tools.edit import apply_edit
from repoforge.tools.filesystem import RepoSandbox
from repoforge.tools.search import search_text
from repoforge.tools.tests import detect_test_command, run_tests


def tavily_research(query: str, api_key: str = "") -> dict[str, Any]:
    """Stub for Tavily bonus-track research. Returns a placeholder."""
    if not api_key:
        return {
            "status": "stub",
            "query": query,
            "results": [],
            "note": "TAVILY_API_KEY not set. Wire real Tavily client for bonus track.",
        }
    return {
        "status": "stub_with_key",
        "query": query,
        "results": [],
        "note": "Tavily client not implemented in MVP; key detected.",
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories under a relative path in the repo.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the repo.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Regex search across source files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "glob": {"type": "string", "default": "*.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_edit",
            "description": "Replace an exact old string with new string in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
                "required": ["path", "old", "new"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the project test suite.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research",
            "description": "Optional web research via Tavily (bonus track stub).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


def build_tool_dispatcher(sandbox: RepoSandbox, tavily_key: str = "") -> Callable[[str, str], str]:
    """Return a function(name, arguments_json) -> result_string."""

    def dispatch(name: str, arguments_json: str) -> str:
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as exc:
            return f"Invalid tool arguments JSON: {exc}"

        try:
            if name == "list_dir":
                entries = sandbox.list_dir(args.get("path", "."))
                return "\n".join(entries) or "(empty)"
            if name == "read_file":
                return sandbox.read_file(args["path"])
            if name == "search_text":
                hits = search_text(sandbox, args["pattern"], glob=args.get("glob", "*.py"))
                if not hits:
                    return "No matches."
                return "\n".join(f"{h.path}:{h.line}: {h.text}" for h in hits)
            if name == "apply_edit":
                result = apply_edit(sandbox, args["path"], args["old"], args["new"])
                return json.dumps({"applied": result.applied, "message": result.message})
            if name == "run_tests":
                cmd = args.get("command") or detect_test_command(sandbox.root)
                result = run_tests(sandbox, cmd)
                return result.summary()
            if name == "research":
                return json.dumps(tavily_research(args["query"], tavily_key))
            return f"Unknown tool: {name}"
        except Exception as exc:  # noqa: BLE001 — surface tool errors to the agent
            return f"Tool error ({name}): {exc}"

    return dispatch
