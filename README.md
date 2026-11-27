# Scholarship Copilot

A personal scholarship assistant. It finds scholarships from sources you approve, checks your
eligibility against cited requirements, and prepares a reviewed application packet for each one.
You always submit applications yourself.

> **Status:** early development (Phase 3: project setup). Not ready for use yet.
> See [PROGRESS.md](PROGRESS.md) for current status and [PROJECT_PLAN.md](PROJECT_PLAN.md) for the roadmap.

## Highlights (planned)
- **Evidence-based eligibility:** every requirement is shown with a quote from its source. Verdicts are computed by tested code, not guessed by an AI.
- **Application packets:** checklists, coaching for written responses, copy-ready form fields, and an approval step.
- **Integrity first:** checks each scholarship's AI-use rules before helping, and never invents experiences.
- **Works without paid AI:** optional local models (Ollama) or the Claude API.

## Tech stack
Python · FastAPI · SQLAlchemy · SQLite · React · TypeScript · Vite · Tailwind · shadcn/ui. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Development setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/) (installs Python 3.13 for you), Node.js 26,
and [gitleaks](https://github.com/gitleaks/gitleaks) (`brew install gitleaks`) for the commit hook.

```bash
# Backend (api/)
cd api
uv sync                              # create .venv from uv.lock
cp .env.example .env                 # optional: SCHOLARSHIP_DATA_DIR defaults to ~/ScholarshipCopilotData
uv run alembic upgrade head          # create/upgrade the database in the data dir
uv run python -m app                 # API on http://127.0.0.1:8000 (docs at /docs)

# Frontend (web/), in a second terminal
cd web
npm ci
npm run dev                          # app on http://127.0.0.1:5173, proxies /api to the backend

# Git hooks (once, from api/)
uv run pre-commit install
```

Both servers listen on `127.0.0.1` only.

### Checks

| | Backend (`api/`) | Frontend (`web/`) |
|---|---|---|
| Tests | `uv run pytest` | `npm test` |
| Types | `uv run mypy app tests migrations` | `npm run typecheck` |
| Lint | `uv run pylint app tests` | `npm run lint` |
| Format | `uv run ruff format .` | `npm run format` |

After changing an API route or response model, run `npm run gen:api` in `web/` to regenerate the
TypeScript types, and commit them. CI fails if they are stale. After changing a model, run
`uv run alembic revision --autogenerate -m "..."` in `api/` and review the generated migration.

### Recommended Claude Code plugins
From Anthropic's official marketplace (`/plugin install <name>@claude-plugins-official`):
`learning-output-style`, `pyright-lsp`, `typescript-lsp`, `playwright`, `context7`, `security-guidance`.

## Privacy
This repository never contains personal data. All personal data (database, uploaded documents)
lives outside the repo in `~/ScholarshipCopilotData/`. Any demo data is fictional and labeled as such.
