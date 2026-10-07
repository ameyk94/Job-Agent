# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Versions follow the phases in CLAUDE.md.

## Unreleased

### Added
- `job-scout run`: scheduled scan that reports only new jobs at or above `NOTIFY_MIN_SCORE`.
- SQLite seen-jobs store (`private/scout.db`).
- Telegram and email (SMTP) digests; a failed scan sends a "FAILED" alert.
- systemd daily timer (08:00) in `deploy/hermes/`.
- Adzuna Canada and We Work Remotely sources, driven by `config/search.csv` (roles in priority order).
- Scan ranks at most `MAX_JOBS_PER_SCAN` (40) unseen jobs; seen jobs are dropped before the cap and before any LLM call.
- Digest footer shows jobs per source; a scan where every source returns 0 jobs sends a FAILED alert.
- `scripts/baseline_sources.py` and `docs/findings/phase2a-sources.md`.

- Seniority filter: titles with senior, sr, staff, lead, principal, director, head, vp, vice president or chief are
  dropped before ranking. Manager is kept.
- Repost window: seen jobs are keyed on company + title and expire after `REPOST_GAP_DAYS` (30).
- The digest lists every job above the cutoff on both channels. Telegram splits it into numbered messages under
  its 4096-character limit; email is one message.

### Changed
- Adzuna adds "remote" to the query when the remote flag is set.
- Adzuna logs a warning with the HTTP status on failure and retries once after 2 s. A transient error used to drop a whole
  query silently (the 2026-10-07 08:00 scan found 48 jobs; the same plan found 164 an hour later).
- Seen-jobs store moved to a new table `seen_jobs` (old `seen` table is ignored). Digest no longer says "more in the app".

## [0.0.0] - Phase 0, unreleased

### Added
- Repo scaffold imported from `observable-job-agent` part1.0 (MIT), ADR-001.
- CI: ruff, ruff format check, pytest, and pre-commit (privacy guards + gitleaks).
- Pre-commit guards blocking `.env*`, stray PDFs, `private/`, and secrets.
- `OPIK_MODE=local|cloud`; tracing degrades to a no-op if Opik is unreachable.
- `TRACE_ATTACH_CV` switch (default off).
- Self-hosted Opik on Hermes: `deploy/opik/` script and runbook.
- Docs: `docs/setup.md`, ADRs 001-005, project README.
- Tests for the OpenRouter factory and Opik mode switch (40 tests, offline).

### Changed
- LLM provider: OpenAI-specific `init_chat_model` replaced by OpenRouter via `ChatOpenAI`.
  `SCOUT_MODEL` is now an OpenRouter id (`openai/gpt-4o-mini`).
- Python project author, README (stub with credits), LICENSE (our line added).

### Removed
- Groq extra, `OPENAI_API_KEY`, `docs/opik_setup.md` (superseded by `docs/setup.md`).
