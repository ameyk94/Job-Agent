"""We Work Remotely RSS source. Keyless, remote-only.

WWR has no data or analytics category feed (verified 2026-10-06), so three working feeds are merged
and filtered by role words in the title. Only jobs open to a Canadian are kept: region "Anywhere",
"Canada" or "North America". "USA Only" and similar are dropped.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

import httpx
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from job_scout.graph.schemas import JobPosting
from job_scout.tools.jobs_api import _truncate

FEEDS = (
    "https://weworkremotely.com/remote-jobs.rss",
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
    "https://weworkremotely.com/categories/all-other-remote-jobs.rss",
)
_OK_REGIONS = ("anywhere", "canada", "north america")
_HEADERS = {"User-Agent": "Mozilla/5.0 (job-scout)"}


def _clean(raw: str) -> str:
    """Turn escaped HTML from the feed into plain text."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(raw))
    return " ".join(html.unescape(text).split())


def _to_posting(el: ET.Element) -> JobPosting | None:
    """Convert one RSS ``<item>``; ``None`` if it is not open to a Canadian or is malformed."""
    title_raw = (el.findtext("title") or "").strip()
    region = (el.findtext("region") or "").strip()
    link = (el.findtext("link") or "").strip()
    if not title_raw or not link or not any(ok in region.lower() for ok in _OK_REGIONS):
        return None
    company, sep, title = title_raw.partition(": ")
    if not sep:
        company, title = "Unknown", title_raw
    category = (el.findtext("category") or "").strip()
    return JobPosting(
        job_id="wwr-" + link.rstrip("/").rsplit("/", 1)[-1],
        title=title.strip(),
        company=company.strip(),
        location=region,
        remote=True,
        description=_truncate(_clean(el.findtext("description") or "")),
        url=link,
        tags=[category] if category else [],
        source="wwr",
    )


class WWRSource:
    """Remote jobs from We Work Remotely feeds. Downloads the feeds once per instance."""

    name = "wwr"
    remote_only = True  # run_plan only calls this source for remote rows

    def __init__(self, feeds: tuple[str, ...] = FEEDS, timeout: float = 15.0) -> None:
        self.feeds = feeds
        self.timeout = timeout
        self._items: list[JobPosting] | None = None

    def _load(self) -> list[JobPosting]:
        if self._items is not None:
            return self._items
        seen: dict[str, JobPosting] = {}
        for url in self.feeds:
            try:
                resp = httpx.get(url, timeout=self.timeout, follow_redirects=True, headers=_HEADERS)
                resp.raise_for_status()
                root = SafeET.fromstring(resp.content)
            except (httpx.HTTPError, ET.ParseError, DefusedXmlException):
                continue
            for el in root.iter("item"):
                job = _to_posting(el)
                if job and job.job_id not in seen:
                    seen[job.job_id] = job
        self._items = list(seen.values())  # cached even if empty: do not retry a dead feed per row
        return self._items

    def fetch(self, query: str, location: str | None, country: str | None, remote: bool, limit: int) -> list[JobPosting]:
        """Return remote jobs whose title contains every word of ``query``."""
        words = query.lower().split()
        if not words:
            return []
        return [j for j in self._load() if all(w in j.title.lower() for w in words)][:limit]
