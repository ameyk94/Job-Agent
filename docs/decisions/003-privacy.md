# ADR-003: Privacy by construction

Status: accepted, 2026-10-03

## Context
The repo is public. The tool handles a real CV and real applications.

## Decision
- Real CVs and outputs live only in git-ignored `private/`.
- Pre-commit hooks and CI block `.env*` (except `.env.example`, `.env.test`), PDFs outside
  `data/fixture_cvs/`, anything in `private/`, and secrets (gitleaks).
- Personal runs trace to self-hosted Opik, so CV text never leaves the home network.
- Attaching the CV PDF to traces is off by default (`TRACE_ATTACH_CV=false`).
- Fixture CVs are synthetic.

## Consequences
- CI repeats the hooks, so a skipped local hook still fails the PR.
- Gitleaks catches secrets, not personal prose. Diffs that touch data, docs or fixtures still need a manual grep.
