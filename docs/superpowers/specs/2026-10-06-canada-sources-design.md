# Phase 2a: Canada sources and a settings-driven search plan

Date: 2026-10-06. Status: approved by the owner in chat, pending spec review.

## Problem

The scheduled scan returns Senior, non-Toronto jobs. Two causes in current code:

1. `fetch_jobs` lets an LLM choose one query, so results ignore the owner's role priorities.
2. Only Remotive (remote-only, one query) and an offline cache answer when no key is set. Adzuna and
   JSearch exist but are only called as fallbacks, with a country guessed from the CV.

## Scope (this slice only)

In: Adzuna Canada, We Work Remotely RSS, a CSV that defines what to search, a cap of 40 jobs per scan,
a baseline note.

Out (later specs): seniority filter, location tiers (including "anywhere a Canadian passport works"),
company boards (Greenhouse/Lever/Ashby), JSearch Canada, tailoring.

## Design

### `config/search.csv`

One row per search. Order of rows is priority order.

```
role,location,remote_only
Data Scientist,Toronto,false
Data Scientist,Canada,true
Data Analyst,Toronto,false
Data Analyst,Canada,true
Product Analyst,Toronto,false
Product Analyst,Canada,true
Analytics Engineer,Toronto,false
Analytics Engineer,Canada,true
Strategy Analytics,Toronto,false
Business Analyst,Toronto,false
```

No personal data, so it is committed. `SEARCH_PLAN_PATH` overrides the path. A malformed row (blank role)
fails the scan with a clear error; it is not skipped silently.

### `src/job_scout/search_plan.py`

`load_plan(path) -> list[SearchRow]`, and
`run_plan(rows, sources, cap=40) -> tuple[list[JobPosting], dict[str, int]]`.

- For each row, for each source: call `source.fetch(role, location, "ca", remote_only, per_query_limit)`.
- Merge in row order, de-duplicate by `(title, company)` using the existing `_dedupe` helper, return jobs
  and per-source counts.
- The cap is applied by the caller after dropping already-seen jobs (see data flow), so tomorrow's scan
  reaches the next unseen jobs instead of re-reading today's.
- A source that raises or returns nothing contributes 0 and never aborts the run.

### `src/job_scout/tools/sources/wwr.py` (new)

`WWRSource` implements the existing `JobSource` protocol. No API key. Verified 2026-10-06: WWR has no
data or analytics category feed (those slugs redirect to themselves), so jobs are read from three feeds
that do work and merged: `remote-jobs.rss` (all categories), `remote-product-jobs.rss`,
`all-other-remote-jobs.rss`. The feed list is a constant in `wwr.py`.

- Parse with `xml.etree.ElementTree` (stdlib). Item `<title>` is `Company: Job title`; split on the first colon.
- Keep an item only if the job title contains every word of the role (case-insensitive; "any word" would match every
  "Data Engineer") AND its `<region>` is
  `Anywhere in the World`, or mentions `Canada` or `North America`. Region values such as `USA Only` are
  dropped, because a Canadian cannot assume eligibility (see ADR-006 and the tier-5 research task).
- Return `JobPosting(source="wwr", remote=True, location=<region>)`. Errors and parse failures return `[]`.

`JobSourceName` in `schemas.py` becomes `Literal["jsearch", "adzuna", "remotive", "wwr", "cache"]`.

### Adzuna

The existing `AdzunaSource` is reused. The plan passes `country="ca"` and the row's location (`Toronto`, or
no `where` for `Canada`). Adzuna returns Canada-wide results when `where` is omitted. The key is already set
on the server.

### Graph wiring (minimal)

- `AgentState` gains `preset_jobs: list[JobPosting] | None`.
- `fetch_jobs`: if `state.get("preset_jobs") is not None`, return `{"jobs": preset_jobs, "jobs_sources": [...]}`
  immediately. No LLM call, no tool call.
- `should_reformulate`: if `preset_jobs` is set, return `END`. The plan already defines the search, so the
  loop that rewrites the query is skipped.
- `stream_search(..., preset_jobs=None)` passes it into the graph inputs. The Gradio UI never sets it, so
  its behaviour is unchanged.

### Scan flow (`job-scout run`)

1. Load CV, extract profile (unchanged).
2. `load_plan` then `run_plan` gives all candidate jobs and per-source counts.
3. Drop jobs whose `job_id` is in `scout.db` (new `store.filter_unseen_jobs`).
4. Cap the remainder at 40 in plan order. Pass them as `preset_jobs`.
5. Rank, keep score >= `NOTIFY_MIN_SCORE`, notify, mark all ranked jobs seen (unchanged).

The digest footer adds one line: `Sources: adzuna 31, wwr 7`. A source that returned 0 shows as `wwr 0`, so a
dead source is visible.

### Errors

| Case | Behaviour |
|---|---|
| One source fails or rate-limits | counts 0, logged, scan continues |
| All sources return 0 jobs | "scan FAILED" alert (nothing to rank is a failure, not a quiet day) |
| Bad CSV | scan FAILED alert naming the row |
| Adzuna key missing | Adzuna counts 0; WWR still runs |

Cost bound: at most 40 jobs ranked per scan, `MAX_LLM_CALLS_PER_RUN` unchanged.

## Testing (offline, no network)

- `load_plan`: valid file, blank role, missing file.
- `WWRSource`: recorded RSS fixture parses; `Company: Title` split; role-word filter; region filter keeps
  `Anywhere`/`Canada`/`North America` and drops `USA Only`; malformed XML returns `[]`.
- `run_plan`: priority order kept, duplicates across sources dropped, one failing source ignored, per-source counts.
- `fetch_jobs` with `preset_jobs`: no model call (assert the chat model factory is never invoked).
- `should_reformulate` returns `END` with `preset_jobs` set.
- `cli.run`: seen jobs excluded before the cap; the cap is 40; all-sources-empty alerts.

## Baseline (findings note, `docs/findings/phase2a-sources.md`)

Run once on the owner's real CV, before and after, and record: jobs returned per source, per role row, and
the share whose title contains Senior/Staff/Lead/Principal/Manager (the number the seniority filter will
later reduce). Numbers only; no CV text and no company names tied to the owner.

## Risks

- Adzuna free-tier limits are not documented in this repo. The plan makes at most 10 rows x 1 call each per
  day; if Adzuna returns 429 the source counts 0 and the footer shows it.
- WWR feeds mix all job types, so few items will match a data role on any given day. The baseline note records
  the actual count. Feed URLs can change; the list is a constant in `wwr.py`.
- Adzuna title relevance is loose (it matches the description). Title relevance is left to the ranker until
  the seniority and tier work.
