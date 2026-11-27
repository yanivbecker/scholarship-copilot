# Architecture — Scholarship Copilot

Condensed from the approved proposal (https://claude.ai/artifact/9MgugoaywTNCqbKR62DzAE).
Update this file whenever an architectural decision changes, and record the change in the decision log below.

## System overview

```mermaid
flowchart TB
  subgraph Mac["Local machine"]
    UI["React + TypeScript (Vite)"]
    API["FastAPI · 127.0.0.1"]
    JOB["Daily job · launchd → scholar daily"]
    DB[("SQLite → Postgres later")]
    FILES[["~/ScholarshipCopilotData/files"]]
    OLL["Ollama (optional)"]
  end
  WEB["Approved scholarship sites"]
  SRCH["Tavily search (weekly, optional)"]
  CL["Claude API (optional)"]
  UI <-->|"REST /api/v1 + generated types"| API
  API <--> DB
  API <--> FILES
  JOB <--> DB
  JOB --> WEB
  JOB --> SRCH
  API -.-> OLL
  API -.-> CL
  JOB -.-> OLL
  JOB -.-> CL
```

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.13 (uv), FastAPI, Pydantic, SQLAlchemy 2, Alembic |
| Database | SQLite (local) → PostgreSQL (cloud) |
| Frontend | React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, React Router, react-hook-form + zod |
| API contract | FastAPI OpenAPI schema → `openapi-typescript` generated types |
| Scraping | httpx2, trafilatura (+ lxml fallback), urllib.robotparser; Playwright for JS-only pages deferred |
| Parsing | pypdf / pdfplumber, python-docx; python-multipart for uploads |
| Matching | rapidfuzz |
| AI | Provider interface: `none` · `ollama` · `anthropic` |
| Tests | pytest, Vitest + Testing Library, Playwright e2e |
| Quality | ruff, mypy, pylint, oxlint, Prettier, pre-commit, gitleaks, GitHub Actions |

## Repository layout (planned)

```
scholarship-copilot/
  api/                     Python backend (uv project)
    app/
      api/                 HTTP routes only
      modules/             profile, sources, discovery, eligibility, ranking, packets, coaching, notify
      ai/                  provider switch, prompts, output schemas
      jobs/                CLI jobs (daily, recheck, digest, background on/off)
      core/                config, db session, logging, security helpers
    migrations/            Alembic
    tests/
  web/                     React frontend (Vite)
    src/{api,components,features,routes}
  extension/               Chrome extension (Phase 9)
  ops/launchd/             launchd agent template
  docs/                    extra docs and screenshots
```

## Key design rules

1. **Eligibility verdicts are deterministic code.** AI extracts criteria (with quotes), and code evaluates them.
2. **Layering:** routes → services → repositories. Routes contain no business logic.
3. **Jobs are CLI commands.** Any scheduler (launchd, cron, cloud) can run them. Each run writes a `job_runs` row.
4. **Background on/off:** `scholar background off` unloads the launchd agent (`launchctl bootout`), and `on` loads it again. The app's Settings page calls the same code. Ollama's idle unload keeps model memory free when not in use.
5. **Status changes enforced by the system**, with an audit log for approvals and submissions.
6. **Untrusted input:** scraped text is passed to AI as data, never as instructions. The fetcher blocks private IP ranges.
7. **Data outside the repo:** `~/ScholarshipCopilotData/` (DB, files, backups). Path set via env var.

## Core data model (initial)

`users`, `profiles`, `profile_facts`, `stories`, `sources`, `source_candidates`, `page_snapshots`,
`scholarships`, `scholarship_cycles`, `criteria`, `eligibility_results`, `packets`, `packet_items`,
`responses`, `response_versions`, `documents`, `notifications`, `settings`, `job_runs`, `audit_log`.

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-26 | Python backend + React/TS frontend | Python strengths for scraping/AI. React/TS is the industry standard (user preference). |
| 2026-11-26 | SQLite first | Single local user; no server to run. ORM keeps Postgres migration cheap. |
| 2026-11-26 | Hybrid mode as flagship; no auto-submit | Legal, ToS, and integrity limits. Highest value per effort. |
| 2026-11-26 | Code decides eligibility | Auditable, testable, never presents a guess as a confirmed match. |
| 2026-11-26 | launchd daily job with on/off switch | Runs on wake after sleep. User can free resources on demand. |
| 2026-11-26 | TypeScript pinned to 5.9 (not 7) | `openapi-typescript` needs TS 5.x. Revisit when it supports TS 7. |
| 2026-11-26 | oxlint instead of ESLint | Ships with the Vite template, very fast, covers React hooks + TS rules. Fewer plugins than ESLint; revisit if a needed rule is missing. |
| 2026-11-26 | Test HTTP client: `httpx2` | Starlette's TestClient deprecated `httpx`. Same maintainer (pydantic/httpx2). |
| 2026-11-26 | Profile facts come from a typed catalog defined in code | Eligibility (Phase 5) compares typed values deterministically; "never ask twice" (FR-P4) is a lookup by key. Scholarship-specific answers are stored as custom text facts. |
| 2026-11-26 | Forms: react-hook-form + zod | Owner-approved. Schema-based validation and types for ~6 forms, instead of hand-rolled state. |
| 2026-11-26 | Phase 4 resume import is rule-based | Owner-approved. AI extraction joins the same confirm-each-fact flow in Phase 5. Works with AI provider = none (NFR-6). |
| 2026-11-26 | python-multipart added for uploads | Owner-approved. FastAPI's documented dependency for file uploads (resume import). |
| 2026-11-26 | Native `<select>` (shadcn native-select) instead of Radix Select | Accessible by default (keyboard, screen readers, mobile pickers) and testable in jsdom. Enough for every choice field so far. |
| 2026-11-26 | Resume provenance is decided by the server | Confirm re-runs the deterministic extraction on the stored file: unchanged = `resume`, edited = `manual`. The browser can't label a value "from your resume" that isn't in it. |
| 2026-11-26 | Uploaded files: random names, 0600, behind `FileStorage` | Hostile file names can't choose paths; files stay in the data dir (NFR-1); swappable for cloud storage (NFR-8). |
| 2026-11-26 | `scholar` CLI with argparse (stdlib) | Jobs and data deletion run from any scheduler or terminal. No CLI framework dependency needed yet. |
| 2026-11-26 | Data deletion ends with SQLite VACUUM | Deleted rows otherwise stay readable in the database file's free pages (NFR-12). |
| 2026-11-26 | Fetcher pins the vetted IP | Resolve DNS ourselves, require every address to be public, connect to that IP with Host + TLS SNI = real name. Closes the DNS-rebinding gap between check and connect (NFR-4). |
| 2026-11-26 | httpx2 as the runtime HTTP client | Same maintainer as httpx; already used for tests; supports per-request SNI. |
| 2026-11-26 | Unknown robots.txt = don't fetch | 401/403/429/5xx/unreachable robots.txt means we don't know the rules, so the page isn't read (FR-D2). 404 means no rules. |
| 2026-11-26 | Playwright (JS-only pages) deferred | Not needed for the sources tested so far; adds a browser runtime. Revisit if real sources are JS-only (paste text works meanwhile). |
| 2026-11-26 | AI default model `claude-opus-5-5`, configurable | Current Opus; `SCHOLARSHIP_ANTHROPIC_MODEL` can switch to a cheaper model (owner's call). Only changed pages are re-extracted (FR-D7), which keeps cost low. |
| 2026-11-26 | One validation path for every provider | Providers return JSON text; Pydantic validation + one retry live in `ai/structured.py` (NFR-5), so Claude and Ollama are held to the same rules. |
| 2026-11-26 | Untrusted text: labeled, escaped, no tools | Scraped text can't escape its block or trigger actions; code (not the model) checks quotes and decides eligibility (NFR-4). |
| 2026-11-26 | Extraction: AI proposes, code verifies | Names, quotes, amounts and deadlines are checked against the page text before saving; unverifiable parts are dropped and counted, not trusted (FR-D5). |
| 2026-11-26 | Unfit criteria become free text | A requirement that doesn't match a kind exactly is kept with its quote as free_text (unknown until the student confirms, FR-E3) instead of being forced into a kind that could produce a wrong verdict. |
| 2026-11-26 | pylint: unsubscriptable-object off, similarity >= 8 lines | pylint misreads SQLAlchemy 2 generics (mypy --strict covers subscripts); short shared field lists between layers aren't duplication. |
| 2026-11-26 | Eligibility computed on read, not stored | Pure, fast, deterministic; always reflects the current profile and criteria (FR-E4). A stored copy may be added for sorting at scale later. |
| 2026-11-26 | When in doubt: unknown, never not met | A wrong "not met" hides a winnable scholarship; a question costs a moment. Applied to scales, places, majors and unreadable data. |
| 2026-11-26 | FastAPI dependencies take no request-bindable config | Any dependency parameter becomes request input; server configuration only comes from the environment (security review finding). |
| 2026-11-26 | Dedup: auto-merge only near-certain matches | A wrong merge mixes criteria and verdicts; uncertain pairs are suggested to the student instead (FR-D6). |
| 2026-11-26 | Discovery commits per source | A failure late in a run doesn't lose earlier sources' results; the run is marked partial (`job_runs`). |
| 2026-11-27 | Warning signs lower the priority score | A flagged listing is still shown with its evidence (FR-D9) but its score is cut to 25%, so it's never recommended first. |
| 2026-11-27 | Status path is fixed, one step at a time (overnight decision) | Conservative reading of FR-UI4: no skipping, one step back to undo; eligibility confirmation needs an Eligible verdict; Submitted needs explicit confirmation. No extra statuses (e.g. archived) were added. |
| 2026-11-27 | AI writing help needs confirmed "allowed" rules backed by a quote (overnight decision) | Conservative reading of FR-A1/A2: coaching and drafting are both off unless the student confirmed the rules as allowed, citing the sponsor's own words found verbatim on the source page. Unclear, prohibited and unchecked all mean off. The scan is deterministic keyword matching (no AI) and only suggests; permissions with conditions are suggested as unclear. |
