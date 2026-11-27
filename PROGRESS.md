# Progress

## Current status
**Phase 4: Profile** in progress (started 2026-11-26). Phase 3 complete; Checkpoint 3 approved 2026-11-26.

## Completed
- 2026-11-26: Phase 1 (requirements/clarification) and Phase 2 (architecture). Checkpoints 1 and 2 approved.
- 2026-11-26: Repository created. PROJECT_PLAN, REQUIREMENTS, ARCHITECTURE, PROGRESS, README, CLAUDE.md written.
- 2026-11-26: Phase 3 (project setup) complete. Checkpoint 3 approved.

## Phase 3 checklist
- [x] Local git repository + planning docs
- [x] Developer tools: Node.js 26.13.1 (Homebrew), npm 11.20, pyright, typescript, typescript-language-server (global npm). uv, git, gh were already installed.
- [x] Claude Code plugins: pyright-lsp, typescript-lsp, playwright, context7, security-guidance (project scope, in `.claude/settings.json`); learning-output-style (local scope, only on this machine)
- [x] Python tooling in `api/`: uv + Python 3.13.15, pytest, mypy (strict), pylint, ruff, pre-commit hooks (root `.pre-commit-config.yaml`), VS Code recommendations, `pyrightconfig.json`
- [x] Backend skeleton: FastAPI app factory, `GET /api/v1/health`, `python -m app` server bound to 127.0.0.1 (NFR-3), settings via `SCHOLARSHIP_*` env vars, data dir resolution (defaults to `~/ScholarshipCopilotData`, rejects paths inside the repo incl. `..` and symlinks, created with 0700 permissions; NFR-1). **Tested:** 9 pytest tests pass, mypy/pylint/ruff/pyright clean, live server answered on 127.0.0.1.
- [x] Database: SQLAlchemy 2.1 + Alembic 1.20 (config in `api/pyproject.toml`), SQLite at `<data dir>/scholarship.db` or `SCHOLARSHIP_DATABASE_URL` (NFR-8), foreign keys enforced on SQLite, constraint naming convention, batch mode for SQLite migrations. First migration: `users` table. **Tested:** 14 pytest tests pass (upgrade, downgrade, round trip, FK pragma, models-match-migrations via `alembic check`); mypy/pylint/ruff/pyright and all pre-commit hooks clean. Not yet run against the real data dir.
- [x] Frontend skeleton in `web/`: Vite 8 + React 19 + TypeScript 5.9, Tailwind 4, shadcn/ui (Radix base, Nova preset), TanStack Query, generated API types (`npm run gen:api` → `src/api/schema.d.ts`), typed `apiGet()` client, health status card. Dev server on 127.0.0.1:5173 proxies `/api` to FastAPI. **Tested:** `tsc -b` and `npm run build` pass; verified in a browser that the card shows "Online" with the API up and "Unreachable" with it down. No frontend unit tests yet (next item).
- [x] Quality: root `.pre-commit-config.yaml` with 7 hooks: gitleaks 8.30.1 (secret scan on staged changes, NFR-2), ruff format, pylint, mypy, Prettier 3.10, oxlint (`--deny-warnings`; shadcn `ui/` and generated files ignored), tsc. npm scripts: `lint`, `typecheck`, `format`, `format:check`. **Tested:** all 7 hooks pass on the full staged tree; a planted fake GitHub token was blocked by gitleaks (`github-pat`); oxlint fails on a planted `debugger`; generated API types stay untouched by Prettier.
- [x] Tests: pytest (14 tests: health, config/NFR-1, DB + migrations) and Vitest 5 + Testing Library + jsdom (6 tests: `HealthStatus` loading/online/unreachable states, `apiGet` success/ApiError). Mock API responses are test-only (NFR-10). Run with `uv run pytest` in `api/` and `npm test` in `web/`. **Tested:** all pass; a deliberate break in `HealthStatus` made the matching test fail.
- [x] CI: `.github/workflows/ci.yml`, 4 parallel jobs on push to main + PRs: backend (ruff, pylint, mypy, pytest, `alembic upgrade` + `alembic check`), frontend (Prettier, oxlint, tsc, Vitest, build), api-contract (regenerated types must match committed ones), secrets (gitleaks over full history). Read-only `contents` permission. **Tested locally** on a fresh copy of the 68 to-be-tracked files installed from lockfiles: every step passes; a deliberately stale API type made the contract check fail. First GitHub run was rejected: `runner.temp` isn't allowed in job-level `env` (fixed; actionlint pre-commit hook added so GitHub-invalid workflows are caught locally). Actions pinned to full commit SHAs. **Green on GitHub** (all 4 jobs).
- [x] Public GitHub repo: https://github.com/yanivbecker/scholarship-copilot. Commits use the GitHub noreply email (repo-local git config). All 68 files scanned for personal emails before the first commit; gitleaks hook passed on commit.

## Phase 4 checklist
- [x] 4.1 Fact catalog + data model (FR-P3, FR-P4, FR-P5, FR-P6, FR-P7, NFR-8, NFR-12): `app/modules/profile/catalog.py` (26 typed facts in 7 sections; citizenship/financial/demographic flagged sensitive; strict validation, no coercion), tables `profiles` (operating mode, onboarding progress), `profile_facts` (JSON value + origin + origin detail, unique per user+key; custom scholarship answers as `custom.<slug>`), `stories` (body stored verbatim, normalized themes); migration `f25a6cf931f4`; repository + service layers; single local owner user. **Tested:** 76 pytest tests pass (62 new); deliberately breaking user scoping and verbatim story storage each failed the matching test; mypy, pylint, ruff, pyright clean.
- [x] 4.2 Profile API (FR-P3-P7): `GET/PATCH /profile`, `GET /facts/catalog`, `GET /facts`, `PUT/DELETE /facts/{key}`, `GET /facts/missing`, `GET/POST /stories`, `PUT/DELETE /stories/{id}`, `GET /stories/themes`. Strict request types (no coercion); API can only set `manual`/`questionnaire` origins; service errors mapped to readable 422/404 in `app/api/errors.py`; `get_current_user` dependency (single owner; the only thing that changes with real auth); short OpenAPI operation ids. Frontend types regenerated. **Tested:** 93 pytest tests pass (17 new API tests); mypy, pylint, ruff, pyright, frontend typecheck + Vitest clean.
- [x] 4.3 Frontend shell + profile pages (FR-P3, FR-P5, FR-P6, FR-P7, NFR-11): React Router 8 layout with skip link and `aria-current` nav; profile editor generated from `/facts/catalog` (one form per section, sensitive sections marked optional, origin shown per fact, cleared field = delete); operating-mode selector; custom-answers list; story bank (create/edit/two-step delete, theme picker, theme filter, body sent and shown verbatim). Pure form logic in `factForm.ts` (form strings <-> typed values, zod rules mirroring the backend, change planning). Choice labels now come from the backend catalog. **Tested:** 37 Vitest tests (31 new, incl. user-event page tests with a fake API); 96 pytest; deliberate breaks (numbers sent as text, trimmed story body, stale "Saved.") each failed the matching tests. Verified in a browser against the real API on a scratch DB: typed values stored, validation messages, verbatim story body, phone width. Found and fixed a stale "Saved." message during browser testing.
- [ ] 4.4 Onboarding wizard, resumable (FR-P1)
- [ ] 4.5 Resume import: PDF/DOCX, rule-based extraction, confirm each fact (FR-P2)

## Known issues
None open.
- Resolved 2026-11-26: linter decision. Owner chose oxlint over ESLint (see ARCHITECTURE.md decision log).
- Resolved 2026-11-26: Starlette's TestClient deprecated `httpx`; switched the dev dependency to `httpx2` 2.16.2 (owner-approved; verified same maintainer, pydantic/httpx2).

## Next steps
- Owner: run `uv run alembic upgrade head` in `api/` to create the real database (not done by Claude: it writes to the personal data dir).
- Phase 4 milestones 4.1–4.5, then the end-of-Phase-4 review and approval before Phase 5.
- Later hardening (Phase 10): Dependabot for actions and dependencies.
