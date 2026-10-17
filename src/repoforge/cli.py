"""RepoForge CLI — `python -m repoforge --dry-run "fix failing tests in ./demo_repo"`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from typing import Annotated

from repoforge import __version__
from repoforge.agent.loop import AgentLoop
from repoforge.config import Settings, get_settings
from repoforge.llm.client import LLMClient

console = Console()

app = typer.Typer(
    name="repoforge",
    help="Coding agent: plan → explore → edit → test → reflect (Nemotron via Nebius Token Factory).",
    add_completion=False,
    invoke_without_command=True,
)


def _parse_task_and_repo(task: str, repo: Optional[str]) -> tuple[str, Path]:
    if repo:
        return task, Path(repo).resolve()

    for marker in (" in ./", " in /", " in ~/"):
        if marker in task:
            idx = task.index(marker)
            path_part = task[idx + len(" in ") :].strip().strip("'\"")
            task_part = task[:idx].strip()
            return task_part or task, Path(path_part).expanduser().resolve()

    candidates = [
        Path.cwd() / "demo_repo",
        Path(__file__).resolve().parents[2] / "demo_repo",
        Path(__file__).resolve().parents[3] / "demo_repo",
    ]
    for c in candidates:
        if c.is_dir():
            return task, c.resolve()
    return task, Path.cwd().resolve()


def _run_agent(
    task: str,
    repo: Optional[str],
    dry_run: Optional[bool],
    json_out: bool,
) -> None:
    task_text, repo_path = _parse_task_and_repo(task, repo)
    if not repo_path.exists():
        console.print(f"[red]Repo path not found:[/] {repo_path}")
        raise typer.Exit(code=2)

    live_settings = Settings()
    if dry_run is not None:
        object.__setattr__(live_settings, "dry_run", dry_run)

    mode = "MOCK/dry-run" if live_settings.use_mock else "LIVE Token Factory"
    console.print(
        Panel.fit(
            f"[bold]RepoForge[/] v{__version__}\n"
            f"repo: {repo_path}\n"
            f"task: {task_text}\n"
            f"mode: {mode}",
            title="start",
        )
    )

    agent = AgentLoop(
        repo_path,
        task_text,
        settings=live_settings,
        llm=LLMClient(live_settings),
    )
    result = agent.run()

    if json_out:
        payload = {
            "success": result.success,
            "summary": result.summary,
            "mock": result.mock,
            "repo": result.repo,
            "task": result.task,
            "plan": result.plan.to_dict() if result.plan else None,
            "steps": [
                {
                    "phase": s.phase,
                    "tier": s.tier,
                    "model": s.model,
                    "content": s.content[:500],
                    "tools": [t["name"] for t in s.tool_results],
                }
                for s in result.steps
            ],
        }
        console.print_json(json.dumps(payload))
    else:
        style = "green" if result.success else "yellow"
        console.print(
            Panel.fit(
                f"[{style}]success={result.success}[/]\n{result.summary}",
                title="result",
            )
        )

    raise typer.Exit(code=0 if result.success else 1)


@app.callback()
def main(
    ctx: typer.Context,
    task: Annotated[
        Optional[str],
        typer.Argument(help='Task string, e.g. "fix failing tests in ./demo_repo"'),
    ] = None,
    repo: Annotated[Optional[str], typer.Option("--repo", "-r", help="Repo path override")] = None,
    dry_run: Annotated[
        Optional[bool],
        typer.Option("--dry-run/--live", help="Force mock LLM (default: env REPOFORGE_DRY_RUN)"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable result")] = False,
    version: Annotated[bool, typer.Option("--version")] = False,
) -> None:
    """RepoForge — put options before the task: `--dry-run "fix …"`."""
    if version:
        console.print(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is not None:
        return
    if not task:
        console.print(ctx.get_help())
        raise typer.Exit()
    _run_agent(task, repo, dry_run, json_out)


@app.command("serve")
def serve(
    host: Annotated[Optional[str], typer.Option("--host")] = None,
    port: Annotated[Optional[int], typer.Option("--port")] = None,
) -> None:
    """Start the FastAPI server (minimal web UI + API)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "repoforge.api.routes:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
    )


if __name__ == "__main__":
    app()
