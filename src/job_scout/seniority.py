"""Drop senior-looking job titles before ranking (owner wants entry and intermediate roles).

Title only; the description is not read. "Manager" is deliberately allowed. A role titled "Senior" that is
really mid-level is lost, and a plain-titled job that wants many years is not caught: accepted for now.
"""

from __future__ import annotations

import re

from job_scout.graph.schemas import JobPosting

SENIOR_TITLE = re.compile(r"\b(senior|sr|staff|lead|principal|director|head|vp|vice president|chief)\b", re.IGNORECASE)


def is_senior(title: str) -> bool:
    """Whether the title contains a senior-level word as a whole word."""
    return bool(SENIOR_TITLE.search(title))


def drop_senior(jobs: list[JobPosting]) -> tuple[list[JobPosting], list[JobPosting]]:
    """Split jobs into ``(kept, dropped)``, preserving order."""
    kept: list[JobPosting] = []
    dropped: list[JobPosting] = []
    for job in jobs:
        (dropped if is_senior(job.title) else kept).append(job)
    return kept, dropped
