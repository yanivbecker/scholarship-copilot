# CLAUDE.md

Guidance for Claude Code sessions in this repository.

## Working agreement
- **Approval gates:** do not start a new phase (see PROJECT_PLAN.md), add major dependencies, or deploy without the owner's explicit approval. Silence is not approval.
- **Learning project:** the owner is learning full-stack development. Explain the "why" before building. Leave well-scoped, meaningful pieces for the owner to write. Keep code readable over clever.
- **After each milestone:** update PROGRESS.md (built / tested / remaining), and update ARCHITECTURE.md's decision log if a decision changed.
- **Never claim something works until it is implemented and tested.** Label any mock or demo data clearly.

## Hard rules
- No personal data, documents, `.env`, or databases in the repo. Data lives in `~/ScholarshipCopilotData/` (configured via env var).
- Secrets only via environment variables. Never hardcode them.
- Eligibility verdicts are deterministic code. AI only extracts criteria, each with a verbatim quote and source URL.
- Never fabricate student experiences. Writing help draws only from profile facts and the story bank.
- Scraper: respect robots.txt and rate limits; never scrape aggregators or login-only portals; block private IP targets.
- No automatic submission, no CAPTCHA interaction.

## Docs
PROJECT_PLAN.md (roadmap) · REQUIREMENTS.md (FR/NFR IDs, reference them in tests/commits) · ARCHITECTURE.md · PROGRESS.md · README.md
