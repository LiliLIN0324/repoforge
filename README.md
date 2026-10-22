# RepoForge

A small coding agent that works on **your** repository: give it a repo path and a task in plain English, and it plans, reads code, edits files, and runs the tests — in a loop you can watch.

Built for the Nebius × Global AI Hackathon using NVIDIA Nemotron models on Nebius Token Factory. Ships with a deterministic mock model, so the demo runs without an API key.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m repoforge run --repo ./demo_repo --task "Fix the failing tests in calculator.py" --dry-run
```

`demo_repo/` contains a deliberately buggy calculator, so the first run does something visible.

---

## How it works

```
task ──► planner ──► explore (tools) ──► edit ──► run tests ──► done / retry
                    └────────── Nemotron tiers ──────────┘
```

Three model tiers are routed by phase: Nano for file exploration, Super for editing, Ultra for the plan and for recovery after a failed test run. Edits and test runs use forced `tool_choice`, so the model must act rather than chat.

Tools are scoped to the target repo:

| Tool | Purpose |
|---|---|
| `list_dir` | list a directory |
| `read_file` | read a file |
| `search_text` | grep across the repo |
| `apply_edit` | write a file |
| `run_tests` | run pytest with cwd set to the target repo |

## Web UI

```bash
uvicorn repoforge.api.routes:app --reload
# http://127.0.0.1:8000
```

`POST /api/run` starts a run, `GET /health` reports readiness. The page in `web/index.html` is a thin console over the same API.

## Configuration

Copy `.env.example` to `.env`:

```
NEBIUS_API_KEY=...
REPOFORGE_MODEL_PLAN=...
```

Missing key → mock mode. `--dry-run` forces mock mode even when a key is present.

## Project layout

```
src/repoforge/
  agent/    loop, planner, router
  llm/      client, mock
  tools/    filesystem, search, edit, tests
  api/      FastAPI routes
tests/      5 test modules
demo_repo/  buggy sample project
```

```bash
pytest
```

## Known limits

- **Not a security sandbox.** `run_tests` executes the target repo's tests in a copied working directory, not a container. Point it at code you trust.
- Single-repo, single-task runs — no multi-agent parallelism, no long-horizon memory.
- Web search exists as an interface but is a stub.
- No benchmark numbers yet; the loop is validated by the demo repo's tests, not by a public eval.

## License

MIT.
