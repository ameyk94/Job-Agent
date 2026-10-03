# Job Scout

An observable AI job-search agent. Upload a CV (PDF). It extracts a typed profile, searches real
job openings, and ranks each 0-100 for fit with matched skills and gaps. From Phase 4 it also drafts
tailored cover letters and CV suggestions. **You apply. The agent never submits.**

> **Status: Phase 0.** Scaffold, CI, privacy guards and a self-hosted Opik server are in place.
> The agent itself is still the upstream Part 1 code. See [CHANGELOG.md](CHANGELOG.md).

## Credit

Built on [jamwithai/observable-job-agent](https://github.com/jamwithai/observable-job-agent)
(release `part1.0`, MIT) from Part 1 of the *Jam with AI* series by Shirin Khosravi Jam. This is a
fresh repo, not a fork: the first commit imports `part1.0` verbatim and all later work is ours.
See [ADR-001](docs/decisions/001-repo-origin.md).

## Goals

1. A tool the owner uses every week for a Toronto-based search.
2. A public portfolio repo: clone it, run it with zero keys, understand every design decision.

## Quick start (zero keys)

```bash
git clone https://github.com/ameyk94/Job-Agent.git && cd Job-Agent
make setup     # uv sync + pre-commit hooks
make test      # offline: LLM, network and Opik are all mocked
make app       # Gradio UI on http://localhost:7860
```

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). With no keys the app searches Remotive and
the committed offline job cache. Add keys for real ranking: see [docs/setup.md](docs/setup.md).

## Configuration

Copy `.env.example` to `.env`. Every variable is documented there.

| Need | Variables |
|---|---|
| LLM (OpenRouter) | `OPENROUTER_API_KEY`, `SCOUT_MODEL` |
| Tracing, self-hosted Opik | `OPIK_MODE=local`, `OPIK_URL_OVERRIDE` |
| Tracing, Opik Cloud | `OPIK_MODE=cloud`, `OPIK_API_KEY`, `OPIK_WORKSPACE` |

## Docs

- [Setup (both Opik modes)](docs/setup.md)
- [Self-hosted Opik on a home server](deploy/opik/README.md)
- [Architecture](docs/architecture.md)
- [Adding job sources](docs/extending_sources.md)
- [Decisions (ADRs)](docs/decisions/)
- [Findings](docs/findings/)

## Privacy

Real CVs and outputs live only in git-ignored `private/`. Pre-commit hooks and CI block `.env*`,
PDFs outside `data/fixture_cvs/`, and secrets. Fixture CVs are synthetic.

## Licence

MIT. Original copyright Jam with AI; additions copyright Amey Karpe. See [LICENSE](LICENSE).
