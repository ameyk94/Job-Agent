"""Deterministic search plan: a CSV of roles run against every source, in priority order."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from job_scout.graph.schemas import JobPosting
from job_scout.tools.jobs_api import AdzunaSource, _dedupe
from job_scout.tools.sources.wwr import WWRSource

logger = logging.getLogger(__name__)

COUNTRY = "ca"
NATIONWIDE = "canada"  # a location of "Canada" means: no city filter


@dataclass(frozen=True)
class SearchRow:
    role: str
    location: str
    remote_only: bool


def load_plan(path: str | Path) -> list[SearchRow]:
    """Read the search CSV. Raises ``FileNotFoundError`` or ``ValueError`` naming the bad row."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Search plan not found: {p}")
    rows: list[SearchRow] = []
    with p.open(newline="", encoding="utf-8") as f:
        for n, rec in enumerate(csv.DictReader(f), start=2):
            role = (rec.get("role") or "").strip()
            if not role:
                raise ValueError(f"{p}: row {n}: blank role")
            flag = (rec.get("remote_only") or "false").strip().lower()
            if flag not in ("true", "false"):
                raise ValueError(f"{p}: row {n}: remote_only must be true or false, got {flag!r}")
            rows.append(SearchRow(role, (rec.get("location") or "").strip(), flag == "true"))
    if not rows:
        raise ValueError(f"{p}: no rows")
    return rows


def default_sources() -> list:
    """The sources used by the scheduled scan."""
    return [AdzunaSource(), WWRSource()]


def run_plan(rows: list[SearchRow], sources: list, per_query_limit: int = 25) -> tuple[list[JobPosting], dict[str, int]]:
    """Run every row against every source; return de-duplicated jobs in row order and per-source counts.

    A source marked ``remote_only`` is only called for remote rows. A source that raises contributes
    nothing. Counts are taken after de-duplication, so they add up to ``len(jobs)``.
    """
    found: list[JobPosting] = []
    for row in rows:
        where = None if row.location.lower() == NATIONWIDE or not row.location else row.location
        for source in sources:
            if getattr(source, "remote_only", False) and not row.remote_only:
                continue
            try:
                found.extend(source.fetch(row.role, where, COUNTRY, row.remote_only, per_query_limit))
            except Exception as exc:  # noqa: BLE001 - one bad source must not stop the scan
                logger.warning("source %s failed for %r: %s", source.name, row.role, type(exc).__name__)
    jobs = _dedupe(found)
    counts = {s.name: 0 for s in sources}
    for j in jobs:
        counts[j.source] = counts.get(j.source, 0) + 1
    return jobs, counts
