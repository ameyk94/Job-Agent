# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Versions follow the phases in CLAUDE.md.

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
