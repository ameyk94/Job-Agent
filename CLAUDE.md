# CLAUDE.md — Job Scout

Context for Claude Code working in this repo. Read this first, every session.

## What this project is

Job Scout is an observable AI job-search agent. You upload a CV (PDF); it extracts a typed profile,
searches real job openings, ranks each 0–100 for fit with matched skills and gaps, and (from Phase 4)
drafts tailored cover letters and CV suggestions. **The human applies; the agent never submits.**

It builds on the MIT-licensed [jamwithai/observable-job-agent](https://github.com/jamwithai/observable-job-agent)
(release `part1.0`), from Part 1 of the *Jam with AI* series by Shirin Khosravi Jam. This repo is a fresh
repo of our own, not a fork. The original is imported once and credited.

Two goals carry equal weight:

1. **A tool the owner actually uses** for a Toronto-based job search, every week.
2. **A well-documented public portfolio repo**: a stranger can clone it, run it with zero keys, and
   understand every design decision.

## Working principles

- **Measure before fixing.** Every phase starts from recorded numbers (Opik traces, findings notes) and
  ends with new ones. Don't fix a documented weakness before its baseline is written down.
- **Document as you build.** Docs ship in the same PR as the code they describe.
- **Small PRs to `main`**, CI green before merge. Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- **Ask before** anything hard to undo: force-pushes, deleting files outside the working change,
  changing the licence, or publishing anything that could contain personal data.

## Decisions already made (each gets an ADR in `docs/decisions/`)

| # | Decision | Detail |
|---|---|---|
| ADR-001 | Repo origin | Fresh repo. First commit imports `part1.0` verbatim: "Import observable-job-agent part1.0 (MIT)". All later work is ours. |
| ADR-002 | Licence | MIT. Keep the original copyright line; add ours below it. Credit the original in README. |
| ADR-003 | Privacy | Real CV and outputs live only in git-ignored `private/`. Personal runs trace to **self-hosted Opik**. CV attachment on traces is switchable (`TRACE_ATTACH_CV`). |
| ADR-004 | LLM provider | **OpenRouter** via LangChain's OpenAI-compatible client, base URL `https://openrouter.ai/api/v1`. The default model is chosen in Phase 1 by cost and structured-output reliability. |
| ADR-005 | Opik deployment | Owner: self-hosted Opik in Docker on the **Hermes** machine. Public docs cover **both** self-hosted Docker and Opik Cloud (free tier). Switching between them is configuration only. |
| ADR-006 | Job sources | Canada-first: Adzuna (`ca`), JSearch (Canada), Remotive, We Work Remotely RSS, company boards (Greenhouse/Lever/Ashby). No LinkedIn/Indeed/Wellfound scraping; no sources whose terms forbid automated use. |

### Location preference (owner's order; implemented in Phase 2)

1. Toronto-based (on-site or hybrid)
2. Remote — Canada
3. Remote — US (open to Canadian residents)
4. Ontario-wide
5. Anywhere a Canadian passport holder can work. **Needs research and validation before building**; do not guess eligibility rules.

## Tech stack and commands

Python 3.12+, uv, LangGraph, LangChain, Opik, Gradio, Pydantic, httpx, pypdf. Dev: Ruff, Pytest, Pyright, pre-commit.

```
make setup     # uv sync + pre-commit hooks
make test      # unit tests: LLM, network and Opik all mocked; must pass offline
make lint      # ruff check
make format    # ruff format + fix
make app       # Gradio UI on http://localhost:7860
make batch     # baseline batch (prints projected cost first)
make snapshot  # rebuild offline job cache from live sources
```

Tests must never hit the network or spend credits. New behaviour needs a test.

## Configuration (`.env`, never committed; keep `.env.example` complete and commented)

```
# LLM via OpenRouter
OPENROUTER_API_KEY=
LLM_BASE_URL=https://openrouter.ai/api/v1
SCOUT_MODEL=            # an OpenRouter model id, set in Phase 1

# Opik — choose one mode
OPIK_ENABLED=true
OPIK_MODE=local         # local (self-hosted) | cloud
OPIK_URL_OVERRIDE=      # local mode: the API URL of the Hermes instance (confirm from opik.sh output)
OPIK_API_KEY=           # cloud mode only
OPIK_WORKSPACE=         # cloud mode only
OPIK_PROJECT_NAME=job-scout
TRACE_ATTACH_CV=false   # attach CV PDF to traces; keep false for real CVs on shared servers

# Job sources (all optional; app runs with zero keys)
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
JSEARCH_API_KEY=
```

Notes:
- OpenRouter returns per-call cost in the response `usage`. Write it to trace metadata; Opik's built-in
  pricing may not recognise OpenRouter model ids. Don't present a $0.00 Opik cost as real.
- Confirm Opik SDK settings for a self-hosted server (`opik configure` / `use_local` / URL override)
  against current Opik docs rather than assuming.

## Privacy rules (hard rules)

- Never commit: `.env`, anything in `private/`, any PDF outside `data/fixture_cvs/`, any real name,
  email, phone, address or employer from the owner's CV or applications.
- Fixture CVs are synthetic. They may resemble the owner's profile but must not be it.
- Before any push that touches data, docs or fixtures, grep the diff for personal details.
- Never paste real CV text into issues, PR descriptions, commit messages or docs.

## Documentation rules

Every phase ends with this definition of done:

- [ ] Code merged to `main` via PR, CI green
- [ ] `README.md` and `docs/architecture.md` reflect the change
- [ ] A findings note in `docs/findings/` with numbers from Opik
- [ ] An ADR for each non-obvious decision (`docs/decisions/NNN-title.md`: context, decision, consequences)
- [ ] A `CHANGELOG.md` entry and a tagged GitHub release (`v0.0`, `v0.1`, …)

Writing style for docs: lead with the point, short sentences, real numbers with units, no marketing language.

## Target repo layout

```
job-scout/
├── README.md, CHANGELOG.md, CONTRIBUTING.md, LICENSE, CLAUDE.md, Makefile
├── .github/workflows/ci.yml        # ruff + pytest on push and PR
├── src/job_scout/
│   ├── graph/                      # state, nodes, prompts, the loop
│   ├── tools/sources/              # one module per job source (Phase 2)
│   ├── tailor/                     # Phase 4
│   ├── store.py                    # SQLite: seen jobs, scores, status (Phase 2)
│   └── cli.py                      # `job-scout run` (Phase 5)
├── evals/                          # datasets, judges, runner (Phase 3–4)
├── deploy/opik/                    # notes/scripts for self-hosted Opik
├── docs/ architecture.md, setup.md, sources.md, evaluation.md, using-it.md,
│        decisions/, findings/
├── data/fixture_cvs/               # synthetic only
├── private/                        # git-ignored
└── tests/
```

## Phases

| Phase | Goal | Release |
|---|---|---|
| 0 | Repo scaffold, CI, privacy guards, Opik on Hermes, ADRs 001–005 | `v0.0` |
| 1 | Reproduce Part 1 on OpenRouter, traced; run on owner's CV; pick default model | `v0.1` |
| 2 | Canada-first sources, WWR, location tiers, SQLite store, honest baseline | `v0.2` |
| 3 | Fix the 5 known weaknesses + serial ranking; prove each vs baseline | `v0.3` |
| 4 | Tailoring node with deterministic + LLM-judge grounding checks | `v0.4` |
| 5 | Weekly real use (`job-scout run`, scheduled locally) | ongoing |
| 6 | Polish and publish | `v1.0` |

The full plan, with tasks and exit criteria per phase, is in the owner's plan doc.
Known weaknesses from Part 1 to fix in Phase 3, and only after the Phase 2 baseline: location ignored;
the loop fires often and rarely helps; the loop triples cost and latency; scores skew low and flatten at 90;
`matched_skills` unverified; ranking batches run serially.

## Phase 0 — current task list

1. Create the GitHub repo (name below), public, default branch `main`, branch protection requiring CI.
2. Clone `jamwithai/observable-job-agent` at tag `part1.0`; copy its tree (without `.git`) into the
   new repo; commit as "Import observable-job-agent part1.0 (MIT)". Tag nothing yet.
3. Rename the project in `pyproject.toml`; update `LICENSE` (keep original notice, add ours); README stub
   with credits and a "status: Phase 0" note.
4. Add `private/` to `.gitignore`. Add pre-commit hooks that block `.env*` (except `.env.example`) and
   PDFs outside `data/fixture_cvs/`, plus a secrets scanner.
5. Replace provider-specific model setup with an OpenRouter-capable chat-model factory
   (`LLM_BASE_URL` + `OPENROUTER_API_KEY` + `SCOUT_MODEL`). Keep tests mocked. Update `.env.example`.
6. Add an Opik mode switch (`OPIK_MODE=local|cloud`) in `tracing.py`; tracing must degrade gracefully
   if Opik is unreachable.
7. Write `deploy/opik/README.md`: running Opik with Docker on a home server (Hermes), pointing the SDK
   at it from another machine, upgrading and backups. Write `docs/setup.md` covering both Opik modes.
8. Add CI (`.github/workflows/ci.yml`): `uv sync`, `ruff check`, `pytest`.
9. Write ADR-001 to ADR-005 and `CHANGELOG.md`; set up labels and a milestone per phase.
10. Verify: fresh clone → `make setup && make test` passes with zero keys; open a PR, CI green, merge;
    tag `v0.0` with release notes.

## Target roles (confirmed 2026-10-03; drives Phase 2 fixtures and the ranking rubric)

In priority order: Data Scientist, Data Analyst, Product Analyst, Analytics Engineer.
Strategy + analytics roles (e.g. strategy & operations, business analytics) are also welcome, ranked below the four above.

## Still to confirm with the owner

- GitHub username and final repo name (working name: `job-scout`)
- Seniority (needed by Phase 2 for fixtures and the ranking rubric)
- Hermes details: OS, whether it's the dev machine or a separate server, and its LAN hostname
- Weekly hours available (plan assumes 8–10)
