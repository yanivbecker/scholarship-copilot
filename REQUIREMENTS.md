# Requirements — Scholarship Copilot

IDs are stable so code, tests, and PROGRESS.md can reference them. **Phase** shows when each item is planned.

## Functional requirements

### Profile (Phase 4)
| ID | Requirement |
|---|---|
| FR-P1 | Onboarding wizard: basics/school, optional resume upload, questionnaire, mode + notification preferences, first sources. Resumable. |
| FR-P2 | Resume (PDF/DOCX) import extracts facts; each extracted value is shown for confirmation before saving. |
| FR-P3 | Profile facts are typed and record their origin (questionnaire, resume, scholarship-specific answer). |
| FR-P4 | Never ask for a fact already on file. Answers given for one scholarship are reused for others. |
| FR-P5 | Story bank: experiences in the student's own words, tagged by theme. The only source material for writing help. |
| FR-P6 | All profile data is editable. Sensitive fields (citizenship, financial, demographic) are optional. |
| FR-P7 | Operating mode (Discovery / Hybrid / Automation) is selectable and changeable later. |

### Sources and discovery (Phase 5; scheduling in Phase 8)
| ID | Requirement |
|---|---|
| FR-D1 | The student adds source URLs manually, or approves/rejects candidates suggested by weekly web search. |
| FR-D2 | Fetching respects robots.txt, ≤1 request/second per domain, timeouts, size limits, and HTTP caching. |
| FR-D3 | Known aggregators (Fastweb, Scholarships.com, Bold.org, and similar) are never scraped. |
| FR-D4 | Login-only portals are never crawled. A "paste listing text" input is provided instead. |
| FR-D5 | Extraction produces structured scholarship data. Each criterion includes a verbatim quote + source URL, and criteria without a quote are rejected. |
| FR-D6 | Duplicates are detected and merged (normalized name/sponsor/URL + fuzzy match). |
| FR-D7 | Unchanged pages (same content hash) are not re-extracted. |
| FR-D8 | Scholarships are tracked per cycle (year) so recurring awards keep their history. |
| FR-D9 | Scam signals (fees, "guaranteed" awards, SSN/bank requests, very new domains) are flagged and shown, not silently dropped. |

### Eligibility and ranking (Phase 5)
| ID | Requirement |
|---|---|
| FR-E1 | Each criterion evaluates to met / not met / unknown against the profile, using deterministic code. |
| FR-E2 | Verdict: any not met → Ineligible. All met → Eligible. Otherwise → Needs info, listing exact questions. |
| FR-E3 | Free-text criteria (e.g., "demonstrated leadership") stay unknown until the student confirms them. |
| FR-E4 | Verdicts recalculate when the profile or criteria change. |
| FR-E5 | The priority score combines eligibility, fit, amount, deadline, and effort. Verified facts and estimates are labeled separately. |
| FR-E6 | Never show invented statistics (acceptance rates, odds). Show only figures the sponsor published. |

### Dashboard (Phase 6)
| ID | Requirement |
|---|---|
| FR-UI1 | Today screen: actions needed, upcoming deadlines, new matches, last daily-run status. |
| FR-UI2 | Scholarship table with sort/filter by deadline, amount, relevance, eligibility, status, effort. Optional board view. |
| FR-UI3 | Detail page: all listing fields from the brief, per-criterion evidence, missing-info prompts, last verified date, official link. |
| FR-UI4 | Status tracking: Discovered → Eligibility confirmed → Ready to apply → In progress → Awaiting approval → Submitted → Won / Rejected. |

### Application packets — Hybrid mode (Phase 7)
| ID | Requirement |
|---|---|
| FR-A1 | Each packet starts with a rules check: AI policy classified as allowed / prohibited / unclear, with a quote. Unclear counts as prohibited. |
| FR-A2 | The student confirms the rules check before any writing assistance. |
| FR-A3 | Coaching (default): prompt breakdown, interview questions, outline from the student's answers, rubric feedback. |
| FR-A4 | Drafting only when the rules allow it. Built only from profile facts and the story bank. |
| FR-A5 | Provenance check highlights any claim not traceable to a stored fact. |
| FR-A6 | Copy-ready form fields respect each form's character limits. Document checklist (incl. recommendations, transcripts). |
| FR-A7 | Status transitions are enforced by the system. Approval and "Submitted" are explicit student actions, recorded in an audit log. |
| FR-A8 | Approved responses are versioned and stored in a reusable library. |

### Monitoring and notifications (Phase 8)
| ID | Requirement |
|---|---|
| FR-N1 | Daily job (default 07:00) rechecks approved sources, re-evaluates, and creates notifications. Runs on wake if the Mac was asleep. |
| FR-N2 | **Background running can be switched off and on** from Settings and from the CLI (`scholar background off/on/status`), e.g. to free memory for other projects. When off, nothing runs in the background. A manual "Run now" stays available. |
| FR-N3 | Weekly candidate-source search (when a search key is configured). |
| FR-N4 | Notifications are deduplicated: no repeat alerts unless something materially changes (deadline, amount, eligibility, requirements). |
| FR-N5 | Configurable notification preferences. v1: in-app only. Email optional later. |

### Automation (Phase 9)
| ID | Requirement |
|---|---|
| FR-X1 | Chrome extension fills form fields from an approved packet on student request. It highlights unmatched fields. |
| FR-X2 | The extension never submits, never interacts with CAPTCHAs, and never stores third-party site passwords. |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Privacy:** no personal data, documents, or secrets in the repository. Data lives outside the repo (`~/ScholarshipCopilotData/`). |
| NFR-2 | **Secrets:** environment variables via a git-ignored `.env`. `gitleaks` pre-commit hook. |
| NFR-3 | **Network exposure:** the API binds to 127.0.0.1 only. |
| NFR-4 | **Scraper safety:** block private/local IP targets (SSRF). Treat scraped text as untrusted (prompt-injection aware). |
| NFR-5 | **AI reliability:** every AI output validated against a schema. On failure, retry once, then mark for manual review. |
| NFR-6 | **AI optional:** the app is usable with AI provider = none. |
| NFR-7 | **Resource use:** idle background footprint ≈ 0 (the job is short-lived). Local models unload when idle. Background can be disabled (FR-N2). |
| NFR-8 | **Portability:** SQLite → Postgres via config + migrations. File storage behind an interface. `user_id` on all user-owned records. |
| NFR-9 | **Quality:** automated tests for core logic (eligibility engine required). CI on every push. Linting, formatting, and type checking. |
| NFR-10 | **Honesty:** demo/mock data is clearly labeled and never mixed with real data. |
| NFR-11 | **Accessibility:** keyboard navigable, visible focus, sufficient contrast. Usable at phone width. |
| NFR-12 | **Deletion:** a command to delete all personal data. |

## Out of scope (for now)
- Multiple users, public sign-up, real authentication (until cloud phase)
- Native mobile apps
- Inbox integration (Gmail/Outlook)
- Automatic submission of any kind
