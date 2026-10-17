# RepoForge

**A coding agent that plans, explores, patches, and tests — powered by NVIDIA Nemotron via Nebius Token Factory.**

> Devpost one-liner: RepoForge is a coding agent that plans with NVIDIA Nemotron Ultra/Super, explores your repo, writes patches, runs tests in a sandbox, and iterates until green — via Nebius Token Factory.

Built for the **Nebius × NVIDIA Global AI Hackathon** (Coding & Agentic Engineering Track).  
License: **MIT**.

---

## Why RepoForge?

IDE autocomplete helps you type. Chatbots wait for you to paste files. RepoForge takes a **repo + natural-language task** and runs a closed loop:

**plan → explore → edit → test → reflect**

…routing cheap **Nemotron Nano** for exploration and **Super / Ultra** for hard planning and recovery — all through Nebius Token Factory’s OpenAI-compatible API.

## Features (MVP)

- CLI: `python -m repoforge --dry-run "fix failing tests in ./demo_repo"`
- FastAPI + minimal web UI (`/`, `/api/run`, `/health`)
- Tool sandbox: `list_dir`, `read_file`, `search_text`, `apply_edit`, `run_tests`
- Model router: Nano / Super / Ultra
- **Dry-run / mock mode** — works with no API key (CI-friendly)
- Tavily research tool **stub** (bonus-track ready)
- Intentional `demo_repo/` with a failing test for demos

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ CLI / Web   │────▶│  Agent Loop      │────▶│ Nebius Token Factory    │
│ FastAPI     │     │  plan→…→reflect  │     │ Nemotron Nano/Super/Ultra│
└─────────────┘     └────────┬─────────┘     └─────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Tools + Pytest │
                    │ git sandbox    │
                    └────────────────┘
```

See [PLAN.md](./PLAN.md) for the full product plan, sprint calendar, and judging mapping.

## How Nemotron & Token Factory are used

| Role | Model (Token Factory id) | When |
|------|--------------------------|------|
| Fast explore / tool calls | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | explore, test, easy edits |
| Planning & recovery | `nvidia/nemotron-3-super-120b-a12b` | default plan, reflect after failures |
| Hard reasoning | `nvidia/Nemotron-3-Ultra-550b-a55b` | architecture / security / concurrency tasks |

Client: official `openai` Python SDK with

```text
base_url = https://api.tokenfactory.nebius.com/v1/
api_key  = $NEBIUS_API_KEY
```

Set `REPOFORGE_DRY_RUN=1` (default) to use the deterministic mock LLM — no network, no key.

## Quick start

### 1. Install

```bash
cd repoforge
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# or: pip install -r requirements.txt && pip install -e .
```

### 2. Dry-run demo (no API key)

```bash
# Confirm demo_repo tests are red
python -m pytest demo_repo -q || true

# Run the agent (mock LLM fixes calculator.add)
python -m repoforge --dry-run "fix failing tests in ./demo_repo"

# Tests should now be green
python -m pytest demo_repo -q
```

Reset the bug anytime:

```bash
git checkout -- demo_repo/calculator.py   # if tracked
# or restore the intentional bug line: return a - b
```

### 3. Live mode (Nebius Token Factory)

Live mode needs **both** `NEBIUS_API_KEY` and the `--live` flag. Dry-run is the default and does not call Token Factory.

```bash
cp .env.example .env
# Put NEBIUS_API_KEY in .env only. Do not commit the key.
python -m repoforge --live "fix failing tests in ./demo_repo"
```

If `NEBIUS_API_KEY` is unset, RepoForge stays on the mock LLM even when you pass `--live`.

In live mode the edit phase forces the `apply_edit` tool (`tool_choice`) so Nemotron applies a patch instead of only listing or reading files. The test phase forces `run_tests`. Pytest runs with its working directory set to the target repo root (for example `demo_repo/`), and does not adopt a parent package `pyproject.toml`.

### 4. Web UI

```bash
python -m repoforge serve
# open http://127.0.0.1:8000
```

### 5. Project tests

```bash
python -m pytest tests -q
```

## Project layout

```text
repoforge/
├── PLAN.md                 # Internal plan (ZH) + Devpost one-liner
├── README.md               # This file (EN, submission)
├── LICENSE                 # MIT
├── pyproject.toml
├── requirements.txt
├── .env.example
├── demo_repo/              # Intentional failing tests
├── src/repoforge/
│   ├── cli.py              # Typer CLI
│   ├── config.py
│   ├── agent/              # loop, router, planner
│   ├── llm/                # Token Factory client + mock
│   ├── tools/              # fs, search, edit, tests, tavily stub
│   └── api/                # FastAPI routes
├── tests/
└── web/index.html
```

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `NEBIUS_API_KEY` | empty | Token Factory key |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1/` | API base |
| `NEBIUS_MODEL_NANO` / `_SUPER` / `_ULTRA` | see `.env.example` | Model ids |
| `REPOFORGE_DRY_RUN` | `1` | Mock LLM if `1` or key missing |
| `TAVILY_API_KEY` | empty | Optional research (stubbed) |

## Roadmap (post-MVP)

- Clone GitHub URLs into isolated worktrees
- Open PR drafts from successful runs
- Real Tavily research in the plan phase
- Broader test runners (Go, Rust, Node)
- Evaluation suite of public bugfix tasks

## License

[MIT](./LICENSE) © 2026 RepoForge Contributors

## Acknowledgments

- [Nebius Token Factory](https://tokenfactory.nebius.com/)
- [NVIDIA Nemotron](https://www.nvidia.com/) model family
- Hackathon: Nebius × NVIDIA Global AI Hackathon
