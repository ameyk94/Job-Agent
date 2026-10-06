# Phase 2a baseline: Canada sources

Date: 2026-10-06. Command: `uv run python scripts/baseline_sources.py` on Hermes (real Adzuna key).
Plan: `config/search.csv`, 10 rows. No LLM was called; these are job counts only.

## Result

| Measure | Value |
|---|---|
| Unique jobs after de-duplication | 167 |
| From Adzuna | 165 |
| From We Work Remotely | 2 |
| Titles that look senior (senior, staff, lead, principal, manager, director, head, VP) | 67 (40%) |
| Titles that look entry-level (junior, entry, graduate, associate, intern, co-op) | 9 (5%) |

## Jobs per row (before de-duplication)

| Role | Location | Remote | Adzuna | WWR |
|---|---|---|---|---|
| Data Scientist | Toronto | no | 25 | |
| Data Scientist | Canada | yes | 25 | 1 |
| Data Analyst | Toronto | no | 25 | |
| Data Analyst | Canada | yes | 12 | 0 |
| Product Analyst | Toronto | no | 25 | |
| Product Analyst | Canada | yes | 2 | 0 |
| Analytics Engineer | Toronto | no | 25 | |
| Analytics Engineer | Canada | yes | 3 | 3 |
| Strategy Analytics | Toronto | no | 25 | |
| Business Analyst | Toronto | no | 25 | |

## What the numbers say

- Adzuna carries the plan. WWR adds 2 jobs in total, so it is a minor source today. It is cheap to keep.
- Every Toronto row returns 25, the per-query limit, so there are more Toronto jobs than one page shows.
  Adding pages is a later option if the 40-job daily cap is not the limit first.
- 40% of titles look senior and only 5% look entry-level. The owner wants entry and intermediate roles,
  so a seniority filter (next slice) should cut roughly 40% of what is fetched before any LLM ranking.
- The cap of 40 follows plan order, so the first scan is mostly Data Scientist rows. Seen jobs are dropped
  before the cap, so later scans reach the Data Analyst, Product Analyst and Analytics Engineer rows.
- Remote Canada rows for Product Analyst (2) and Analytics Engineer (3) are thin. Appending "remote" to the
  Adzuna query narrows results; this is the cost of keeping remote roles separate from Toronto.

## Before and after

The "before" is the 2026-10-06 dry run with the old LLM-chosen query: 18 jobs ranked from Remotive only,
2 of 18 above score 70, both titled Senior. Quality numbers (score distribution, share of entry/mid roles
in the digest) will be recorded after the first live scans with the new plan.
