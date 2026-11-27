# Project Plan — Scholarship Copilot

> Working name. Architecture approved at Checkpoint 2 on 2026-11-26.
> Full proposal (with diagrams, costs, and sources): https://claude.ai/artifact/9MgugoaywTNCqbKR62DzAE

## Vision

A personal scholarship assistant that finds scholarships from trusted sources, checks eligibility
against cited requirements, and prepares a complete, reviewed application packet for each one,
so effort goes into the applications that are actually worth it.

## Context and constraints

| Item | Decision |
|---|---|
| Users | One (the author). Built so more users could be added later without a rewrite. |
| Purpose | Personal tool + public GitHub portfolio project. Not a public product. |
| Runtime | Local on macOS (Apple M3, 16 GB). Cloud deployment is optional and deferred. |
| Budget | ~$0/month by default; Claude API (≈ $2–6/month est.) only if a key becomes available. |
| Time | ~3–4 hours/week. End-of-year 2026 milestone = Phases 3–6. |
| Learning goal | The author learns full-stack development by reviewing and writing scoped pieces. |

## Operating modes

- **Hybrid (flagship):** the app prepares everything; the student reviews, approves, and submits.
- **Discovery:** find, evaluate, and track scholarships only.
- **Automation (later, Phase 9):** a browser extension that fills forms from an approved packet. It never submits on its own.

## Guiding principles

1. **Never fabricate.** Every claim in a response traces back to a fact the student provided.
2. **Evidence over guesses.** Each eligibility criterion carries a quote and a source URL. Code decides the verdict, not the AI.
3. **Respect the rules.** AI-policy check before any writing help. Unclear rules count as "no AI writing."
4. **Respect websites.** robots.txt, rate limits, no aggregator scraping, no CAPTCHA bypass, no auto-submit.
5. **Private by default.** Personal data never enters the repository.
6. **Simple first.** Modular monolith, SQLite, no infrastructure we don't need yet.

## Roadmap and checkpoints

Each phase ends with a demo, test results, and an explicit approval before the next one starts.

| Phase | Scope | Target |
|---|---|---|
| 1–2 | Requirements, architecture | ✅ Done 2026-11-26 |
| 3 | Project setup: repo, tooling, backend/frontend skeletons, DB + migrations, tests, CI, secret scanning, docs | ✅ Done 2026-11-26 |
| 4 | Profile: onboarding wizard, profile facts, story bank, resume import | ✅ Done 2026-11-26 |
| 5 | Discovery + eligibility: sources, polite fetcher, extraction, AI provider switch, criteria engine, dedup | ✅ Done 2026-11-27 |
| 6 | Dashboard: Today screen, scholarship table, detail with evidence, status tracking | ✅ Done 2026-11-27 (**end-of-year milestone reached**) |
| 7 | Application packets: rules check, checklist, coaching, allowed drafting, provenance check, approvals | ✅ Done 2026-11-27 (ahead of the January 2027 target) |
| 8 | Daily monitoring + notifications (launchd job with on/off switch, change detection, weekly search) | ✅ Done 2026-11-27 (ahead of the February 2027 target) |
| 9 | Browser-extension autofill from approved packets | Spring 2027 |
| 10 | Security review, hardening, optional cloud deployment (Checkpoint 4) | After Phase 9 |

The week targets are estimates. Scraping work (Phase 5) is the most likely to slip. If it does,
dashboard polish moves to January.

## Approval checkpoints

1. Discovery complete: ✅ approved
2. Architecture approved: ✅ approved 2026-11-26
3. After each major phase (3–10): Phase 3 ✅ approved 2026-11-26; Phase 4 ✅ approved 2026-11-26; Phase 5 ✅ approved 2026-11-27; Phases 6 and 7 approved 2026-11-27 (overnight run); Phase 8 approved 2026-11-27; Phase 9 approved 2026-11-27; Phase 10 pending
4. Before any deployment: pending
