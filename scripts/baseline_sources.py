"""Print baseline numbers for the search plan: jobs per source, per role, and how many look senior.

No LLM, no notifications, nothing written. Needs ADZUNA_APP_ID/KEY in .env for Adzuna numbers.
Usage: uv run python scripts/baseline_sources.py [config/search.csv]
"""

from __future__ import annotations

import re
import sys

from job_scout.config import get_settings
from job_scout.search_plan import COUNTRY, NATIONWIDE, default_sources, load_plan, run_plan

SENIOR = re.compile(r"\b(senior|sr\.?|staff|lead|principal|manager|director|head|vp)\b", re.I)
ENTRY = re.compile(r"\b(junior|jr\.?|entry|graduate|associate|intern|co-?op)\b", re.I)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else get_settings().search_plan_path
    rows = load_plan(path)
    sources = default_sources()
    jobs, counts = run_plan(rows, sources)
    n = max(len(jobs), 1)
    senior = sum(1 for j in jobs if SENIOR.search(j.title))
    entry = sum(1 for j in jobs if ENTRY.search(j.title))
    print(f"plan rows: {len(rows)}  unique jobs: {len(jobs)}")
    print("per source (after de-dup):", counts)
    print(f"senior-looking titles: {senior} of {len(jobs)} ({100 * senior // n}%)")
    print(f"entry-looking titles:  {entry} of {len(jobs)} ({100 * entry // n}%)")
    print("per row (jobs returned before de-duplication):")
    for row in rows:
        where = None if not row.location or row.location.lower() == NATIONWIDE else row.location
        per = {
            s.name: len(s.fetch(row.role, where, COUNTRY, row.remote_only, 25))
            for s in sources
            if not (getattr(s, "remote_only", False) and not row.remote_only)
        }
        print(f"  {row.role:20s} {row.location:8s} remote={str(row.remote_only):5s} {per}")


if __name__ == "__main__":
    main()
