"""Minimal FastAPI backend for RepoForge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from repoforge import __version__
from repoforge.agent.loop import AgentLoop
from repoforge.config import get_settings
from repoforge.llm.client import LLMClient

app = FastAPI(
    title="RepoForge",
    description="Coding agent powered by NVIDIA Nemotron via Nebius Token Factory",
    version=__version__,
)

WEB_DIR = Path(__file__).resolve().parents[3] / "web"
if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


class RunRequest(BaseModel):
    task: str = Field(..., min_length=1)
    repo: str = Field(..., description="Local path to a repository")
    dry_run: bool | None = None


class RunResponse(BaseModel):
    success: bool
    summary: str
    mock: bool
    plan: dict[str, Any] | None
    steps: list[dict[str, Any]]


@app.get("/")
def index() -> FileResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "web/index.html missing")
    return FileResponse(index_path)


@app.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "dry_run": s.dry_run,
        "has_api_key": s.has_api_key,
        "use_mock": s.use_mock,
    }


@app.post("/api/run", response_model=RunResponse)
def api_run(body: RunRequest) -> RunResponse:
    repo_path = Path(body.repo).expanduser().resolve()
    if not repo_path.is_dir():
        raise HTTPException(400, f"Repo not found: {repo_path}")

    from repoforge.config import Settings

    settings = Settings()
    if body.dry_run is not None:
        object.__setattr__(settings, "dry_run", body.dry_run)

    agent = AgentLoop(
        repo_path,
        body.task,
        settings=settings,
        llm=LLMClient(settings),
        on_event=lambda _msg: None,
    )
    result = agent.run()
    return RunResponse(
        success=result.success,
        summary=result.summary,
        mock=result.mock,
        plan=result.plan.to_dict() if result.plan else None,
        steps=[
            {
                "phase": s.phase,
                "tier": s.tier,
                "model": s.model,
                "content": s.content[:1000],
                "tools": [t["name"] for t in s.tool_results],
            }
            for s in result.steps
        ],
    )
