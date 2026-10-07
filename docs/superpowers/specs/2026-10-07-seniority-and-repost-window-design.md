# Phase 2b: seniority filter and repost window

Date: 2026-10-07. Status: approved by the owner in chat.

## Problem

Baseline (docs/findings/phase2a-sources.md): 40% of fetched titles look senior, 5% look entry-level, and the
owner wants entry and intermediate roles. Separately, the seen-jobs store keys on the source's `job_id` and
never expires: a repost with the same id is hidden forever, and a repost with a new id shows as new at once.

## Decisions (owner)

1. Drop senior-looking titles **before ranking**. Titles only; the description is not read.
2. **Manager is kept.**
3. A job told about once may show again after **30 days**, and is keyed on company + title.

## Design

### `src/job_scout/seniority.py`

```python
SENIOR_TITLE = re.compile(r"\b(senior|sr|staff|lead|principal|director|head|vp|vice president|chief)\b", re.I)
def is_senior(title: str) -> bool
def drop_senior(jobs: list[JobPosting]) -> tuple[list[JobPosting], list[JobPosting]]   # (kept, dropped)
```

Whole-word match on the title only. "Leadership Analyst" and "Staffing Analyst" pass; "Sr." matches; "Data Analyst II",
"Associate Data Scientist" and "Analytics Manager" pass. Known limit: a "Senior" role that is really mid-level
is lost; a plain-titled job that wants 8 years is not caught.

### Seen store keyed on company + title with expiry

- New table `seen_jobs(key TEXT PRIMARY KEY, job_id, title, company, url, fit_score, first_seen TEXT)`.
  `key = job_key(company, title)` = lowercase, whitespace collapsed, `"company|title"`.
  The old `seen` table is left in place and ignored (no migration; no real scan has written to it).
- `filter_unseen_jobs(path, jobs, days, now=None)` returns jobs whose key is absent or whose `first_seen`
  is older than `days`.
- `mark_seen(path, ranked, now=None)` upserts by key and resets `first_seen` to `now`, so a resurfaced job
  starts a new 30-day window.
- `Settings.repost_gap_days` (`REPOST_GAP_DAYS`, default 30).
- The old `filter_unseen(path, ranked)` is removed (unused after this change).

### Scan order (`cli.run`)

found -> `drop_senior` -> `filter_unseen_jobs` -> cap `MAX_JOBS_PER_SCAN` -> rank. Dropped-senior jobs are not marked
seen (dropping them again costs nothing). The log line becomes
`found=N senior_dropped=N unseen=N sources: ...`. If nothing is left, the scan returns 0 with no LLM call.

### Digest wording

"+N more in the app." becomes "+N more above the cutoff, not shown." (the app does not list scheduled jobs).

### Baseline script

`scripts/baseline_sources.py` also prints how many jobs the seniority filter keeps.

## Not changing

The ranking prompt (reserved for Phase 3), the notify cutoff of 70 (loose: 29 of 40 passed in the 2026-10-06 dry
run; tune after more scans), the sources.

## Tests (offline)

- `is_senior`: dropped: Senior Data Scientist, Sr. Analyst, Lead Data Analyst, Head of Data, Principal Scientist,
  Director of Analytics, VP Data, Staff Data Scientist. Kept: Analytics Manager, Data Analyst II, Associate Data
  Scientist, Leadership Analytics Analyst, Staffing Analyst, Data Scientist.
- `job_key`: case and whitespace insensitive.
- Store: unseen at first; seen after `mark_seen`; still hidden at day 29; visible again at day 31; re-marking
  restarts the window; a repost with a new `job_id` but same company+title stays hidden inside the window.
- Scan: senior jobs never reach `preset_jobs`, are not marked seen, and do not count toward the cap; all-senior
  results return 0 with no LLM call.
- Digest footer wording.
