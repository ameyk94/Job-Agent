"""SQLite store of jobs already seen, so each scheduled run only reports new ones."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from job_scout.graph.schemas import RankedJob


def _connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS seen ("
        "job_id TEXT PRIMARY KEY, title TEXT, company TEXT, url TEXT, fit_score INTEGER,"
        "first_seen TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    return con


def filter_unseen(path: str | Path, jobs: list[RankedJob]) -> list[RankedJob]:
    """Return the jobs whose ``job_id`` has not been recorded yet."""
    with closing(_connect(path)) as con:
        seen = {row[0] for row in con.execute("SELECT job_id FROM seen")}
    return [j for j in jobs if j.job.job_id not in seen]


def mark_seen(path: str | Path, jobs: list[RankedJob]) -> None:
    """Record jobs as seen (idempotent)."""
    with closing(_connect(path)) as con, con:
        con.executemany(
            "INSERT OR IGNORE INTO seen (job_id, title, company, url, fit_score) VALUES (?, ?, ?, ?, ?)",
            [(j.job.job_id, j.job.title, j.job.company, j.job.url, j.fit_score) for j in jobs],
        )
