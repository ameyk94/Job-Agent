"""SQLite store of jobs already reported, keyed on company + title with an expiry window.

Keyed on company + title (not the source's job id) so a repost with a new id stays hidden. After the
window (``REPOST_GAP_DAYS``) the same job may be reported again.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from job_scout.graph.schemas import JobPosting, RankedJob

_FMT = "%Y-%m-%d %H:%M:%S"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def job_key(company: str, title: str) -> str:
    """Normalised ``company|title`` (case and whitespace insensitive)."""
    return f"{_norm(company)}|{_norm(title)}"


def _connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS seen_jobs ("
        "key TEXT PRIMARY KEY, job_id TEXT, title TEXT, company TEXT, url TEXT, fit_score INTEGER,"
        "first_seen TEXT NOT NULL)"
    )
    return con


def filter_unseen_jobs(path: str | Path, jobs: list[JobPosting], days: int, now: datetime | None = None) -> list[JobPosting]:
    """Return the postings not reported within the last ``days`` days (by company + title)."""
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=days)).strftime(_FMT)
    with closing(_connect(path)) as con:
        recent = {row[0] for row in con.execute("SELECT key FROM seen_jobs WHERE first_seen >= ?", (cutoff,))}
    return [j for j in jobs if job_key(j.company, j.title) not in recent]


def mark_seen(path: str | Path, jobs: list[RankedJob], now: datetime | None = None) -> None:
    """Record jobs as reported now. Re-marking restarts the window."""
    stamp = (now or datetime.now(UTC)).strftime(_FMT)
    rows = [
        (job_key(j.job.company, j.job.title), j.job.job_id, j.job.title, j.job.company, j.job.url, j.fit_score, stamp)
        for j in jobs
    ]
    with closing(_connect(path)) as con, con:
        con.executemany("INSERT OR REPLACE INTO seen_jobs VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
