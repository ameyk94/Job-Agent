# Phase 2a: Canada Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The scheduled scan searches Adzuna Canada and We Work Remotely from a CSV of the owner's roles, ranks at most 40 unseen jobs, and reports per-source counts.

**Architecture:** A deterministic `search_plan` (CSV rows x sources) replaces the LLM query step for scheduled scans via a `preset_jobs` state key. The Gradio UI path is untouched. Seen jobs are dropped before the cap and before any LLM call.

**Tech Stack:** Python 3.12, httpx, stdlib `csv` and `xml.etree`, pytest, existing `job_scout` modules. Spec: `docs/superpowers/specs/2026-10-06-canada-sources-design.md`.

## Global Constraints

- Tests never touch the network or spend credits. New behaviour needs a test.
- Run tools with `python -m uv run ...` from `D:\Github\Job-Agent` (venv is `.venv` on D:).
- Ruff line length 130. Run `python -m uv run ruff format . && python -m uv run ruff check .` before each commit.
- Conventional commits. Every commit message ends with these two lines after a blank line:
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01Xw8RWC3bkVy9AEW9Xtbhz6`
- Cap: 40 jobs ranked per scan. Search rows are in priority order.
- No personal data (CV text, names, employers) in code, tests, docs or commits.
- Work on branch `phase-2-sources`. `main` is protected (CI check `test` must pass); merge only when the owner says so.

## File Structure

- Create `src/job_scout/tools/sources/__init__.py` (empty) and `src/job_scout/tools/sources/wwr.py`: the WWR RSS source.
- Create `src/job_scout/search_plan.py`: `SearchRow`, `load_plan`, `run_plan`, `default_sources`.
- Create `config/search.csv`: the owner's role list.
- Create `scripts/baseline_sources.py`: prints the baseline numbers (no LLM).
- Modify `src/job_scout/graph/schemas.py` (add `"wwr"`), `graph/state.py` (`preset_jobs`), `graph/nodes/fetch_jobs.py`, `graph/graph.py`, `runner.py`, `store.py`, `notify.py`, `cli.py`, `config.py`, `tools/jobs_api.py` (Adzuna remote), `.env.example`, `CHANGELOG.md`.
- Tests: `tests/test_wwr.py`, `tests/test_search_plan.py`, plus additions to `tests/test_notify_cli.py`, `tests/test_runner.py`, `tests/test_nodes.py`, `tests/test_graph.py`.

---

### Task 1: We Work Remotely source

**Files:**
- Create: `src/job_scout/tools/sources/__init__.py`, `src/job_scout/tools/sources/wwr.py`
- Modify: `src/job_scout/graph/schemas.py:15`
- Test: `tests/test_wwr.py`

**Interfaces:**
- Produces: `WWRSource(feeds=FEEDS, timeout=15.0)` with `name = "wwr"`, `remote_only = True`, and
  `fetch(query: str, location: str | None, country: str | None, remote: bool, limit: int) -> list[JobPosting]`
  (the existing `JobSource` protocol). Feeds are downloaded once per instance and cached.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wwr.py`:

```python
"""We Work Remotely RSS source: parsing, role and region filters, failure handling. Offline."""

from __future__ import annotations

import httpx
import pytest

from job_scout.tools.sources import wwr
from job_scout.tools.sources.wwr import WWRSource

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>WWR</title>
<item><title>Acme: Data Scientist</title><region>Anywhere in the World</region><category>Other</category>
<link>https://weworkremotely.com/remote-jobs/acme-data-scientist</link>
<description>&lt;p&gt;Build &amp;amp; ship models&lt;/p&gt;</description></item>
<item><title>Beta: Senior Data Scientist</title><region>USA Only</region><category>Other</category>
<link>https://weworkremotely.com/remote-jobs/beta-senior-data-scientist</link><description>x</description></item>
<item><title>Gamma: Backend Engineer</title><region>Anywhere in the World</region><category>Programming</category>
<link>https://weworkremotely.com/remote-jobs/gamma-backend-engineer</link><description>x</description></item>
<item><title>Delta: Data Analyst</title><region>North America</region><category>Other</category>
<link>https://weworkremotely.com/remote-jobs/delta-data-analyst</link><description>x</description></item>
<item><title>Data Engineer without company</title><region>Canada</region><category>Other</category>
<link>https://weworkremotely.com/remote-jobs/nocompany</link><description>x</description></item>
</channel></rss>"""


class _Resp:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


@pytest.fixture
def feed(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _Resp(RSS.encode())

    monkeypatch.setattr(wwr.httpx, "get", fake_get)
    return calls


def test_role_and_region_filter(feed):
    src = WWRSource(feeds=("https://x/feed.rss",))
    jobs = src.fetch("Data Scientist", "Canada", "ca", True, 10)
    assert [j.title for j in jobs] == ["Data Scientist"]  # Beta dropped: USA Only. Gamma: wrong role.
    job = jobs[0]
    assert job.company == "Acme" and job.source == "wwr" and job.remote is True
    assert job.location == "Anywhere in the World"
    assert job.job_id == "wwr-acme-data-scientist"
    assert job.description == "Build & ship models"
    assert job.tags == ["Other"]


def test_every_word_of_role_must_match(feed):
    src = WWRSource(feeds=("https://x/feed.rss",))
    assert [j.title for j in src.fetch("Data Analyst", None, "ca", True, 10)] == ["Data Analyst"]
    assert src.fetch("Data", None, "ca", True, 10) != []
    assert src.fetch("Analytics Engineer", None, "ca", True, 10) == []


def test_item_without_company_prefix(feed):
    jobs = WWRSource(feeds=("https://x/feed.rss",)).fetch("Data Engineer", None, "ca", True, 10)
    assert jobs[0].company == "Unknown" and jobs[0].title == "Data Engineer without company"


def test_feeds_downloaded_once_per_instance(feed):
    src = WWRSource(feeds=("https://x/a.rss", "https://x/b.rss"))
    src.fetch("Data Scientist", None, "ca", True, 10)
    src.fetch("Data Analyst", None, "ca", True, 10)
    assert feed == ["https://x/a.rss", "https://x/b.rss"]


def test_same_job_in_two_feeds_is_deduped(feed):
    jobs = WWRSource(feeds=("https://x/a.rss", "https://x/b.rss")).fetch("Data Scientist", None, "ca", True, 10)
    assert len(jobs) == 1


def test_limit_applies(feed):
    assert len(WWRSource(feeds=("https://x/a.rss",)).fetch("Data", None, "ca", True, 1)) == 1


def test_network_error_returns_empty(monkeypatch):
    def boom(url, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(wwr.httpx, "get", boom)
    assert WWRSource(feeds=("https://x/a.rss",)).fetch("Data Scientist", None, "ca", True, 10) == []


def test_malformed_xml_returns_empty(monkeypatch):
    monkeypatch.setattr(wwr.httpx, "get", lambda url, **kw: _Resp(b"<rss><item>"))
    assert WWRSource(feeds=("https://x/a.rss",)).fetch("Data Scientist", None, "ca", True, 10) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_wwr.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'job_scout.tools.sources'`

- [ ] **Step 3: Implement**

Create empty `src/job_scout/tools/sources/__init__.py`.

Edit `src/job_scout/graph/schemas.py` line 15 to:

```python
JobSourceName = Literal["jsearch", "adzuna", "remotive", "wwr", "cache"]
```

Create `src/job_scout/tools/sources/wwr.py`:

```python
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
                root = ET.fromstring(resp.content)
            except (httpx.HTTPError, ET.ParseError):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest tests/test_wwr.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
python -m uv run ruff format . && python -m uv run ruff check .
git add src/job_scout/tools/sources src/job_scout/graph/schemas.py tests/test_wwr.py
git commit -m "feat: We Work Remotely RSS source"
```
(Append the two trailer lines from Global Constraints to every commit message.)

---

### Task 2: Search plan (CSV, runner, default sources)

**Files:**
- Create: `src/job_scout/search_plan.py`, `config/search.csv`
- Modify: `src/job_scout/tools/jobs_api.py` (Adzuna `what` gets `" remote"` when `remote=True`)
- Test: `tests/test_search_plan.py`, `tests/test_jobs_api.py` (one added test)

**Interfaces:**
- Consumes: `JobPosting`, `_dedupe` from `job_scout.tools.jobs_api`, `AdzunaSource`, `WWRSource`.
- Produces:
  - `SearchRow(role: str, location: str, remote_only: bool)` frozen dataclass.
  - `load_plan(path: str | Path) -> list[SearchRow]`; raises `FileNotFoundError` or `ValueError("<path>: row N: ...")`.
  - `run_plan(rows: list[SearchRow], sources: list, per_query_limit: int = 25) -> tuple[list[JobPosting], dict[str, int]]`.
  - `default_sources() -> list` returning `[AdzunaSource(), WWRSource()]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_search_plan.py`:

```python
"""Search plan: CSV loading and running rows against sources. Offline."""

from __future__ import annotations

import pytest

from job_scout.search_plan import SearchRow, load_plan, run_plan
from tests.conftest import make_job


class FakeSource:
    def __init__(self, name, by_role, remote_only=False, fail=False):
        self.name = name
        self.by_role = by_role
        self.remote_only = remote_only
        self.fail = fail
        self.calls = []

    def fetch(self, query, location, country, remote, limit):
        self.calls.append((query, location, country, remote, limit))
        if self.fail:
            raise RuntimeError("boom")
        return list(self.by_role.get(query, []))


def job(job_id, title, source):
    return make_job(job_id, title, "Acme", source=source)


def write(tmp_path, text):
    p = tmp_path / "search.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_plan_valid(tmp_path):
    p = write(tmp_path, "role,location,remote_only\nData Scientist,Toronto,false\nData Analyst,Canada,TRUE\n")
    assert load_plan(p) == [SearchRow("Data Scientist", "Toronto", False), SearchRow("Data Analyst", "Canada", True)]


def test_load_plan_blank_role(tmp_path):
    p = write(tmp_path, "role,location,remote_only\nData Scientist,Toronto,false\n ,Toronto,false\n")
    with pytest.raises(ValueError, match="row 3: blank role"):
        load_plan(p)


def test_load_plan_bad_flag(tmp_path):
    p = write(tmp_path, "role,location,remote_only\nData Scientist,Toronto,maybe\n")
    with pytest.raises(ValueError, match="row 2: remote_only"):
        load_plan(p)


def test_load_plan_missing_and_empty(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_plan(tmp_path / "nope.csv")
    with pytest.raises(ValueError, match="no rows"):
        load_plan(write(tmp_path, "role,location,remote_only\n"))


def test_repo_search_csv_is_valid():
    rows = load_plan("config/search.csv")
    assert rows[0].role == "Data Scientist" and len(rows) >= 8


def test_run_plan_order_dedupe_and_counts():
    a = FakeSource("adzuna", {"Data Scientist": [job("1", "Data Scientist", "adzuna")], "Data Analyst": [job("2", "Data Analyst", "adzuna")]})
    w = FakeSource("wwr", {"Data Scientist": [job("3", "Data Scientist", "wwr")]}, remote_only=True)  # same (title, company) as job 1
    rows = [SearchRow("Data Scientist", "Toronto", False), SearchRow("Data Scientist", "Canada", True), SearchRow("Data Analyst", "Toronto", False)]
    jobs, counts = run_plan(rows, [a, w])
    assert [j.job_id for j in jobs] == ["1", "2"]  # job 3 is a duplicate of job 1
    assert counts == {"adzuna": 2, "wwr": 0}


def test_remote_only_source_skipped_for_onsite_rows_and_canada_means_no_city():
    a = FakeSource("adzuna", {})
    w = FakeSource("wwr", {}, remote_only=True)
    run_plan([SearchRow("Data Scientist", "Toronto", False), SearchRow("Data Scientist", "Canada", True)], [a, w], per_query_limit=7)
    assert a.calls == [("Data Scientist", "Toronto", "ca", False, 7), ("Data Scientist", None, "ca", True, 7)]
    assert w.calls == [("Data Scientist", None, "ca", True, 7)]


def test_failing_source_is_ignored():
    bad = FakeSource("adzuna", {}, fail=True)
    good = FakeSource("wwr", {"Data Scientist": [job("3", "Data Scientist", "wwr")]}, remote_only=True)
    jobs, counts = run_plan([SearchRow("Data Scientist", "Canada", True)], [bad, good])
    assert [j.job_id for j in jobs] == ["3"] and counts == {"adzuna": 0, "wwr": 1}
```

Append to `tests/test_jobs_api.py`:

```python
def test_adzuna_remote_flag_adds_remote_to_query(monkeypatch):
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(params)
        resp = MagicMock()
        resp.json.return_value = {"results": []}
        return resp

    monkeypatch.setattr("job_scout.tools.jobs_api.httpx.get", fake_get)
    AdzunaSource(app_id="i", app_key="k").fetch("data analyst", None, "ca", True, 10)
    assert seen["what"] == "data analyst remote"
    AdzunaSource(app_id="i", app_key="k").fetch("data analyst", "Toronto", "ca", False, 10)
    assert seen["what"] == "data analyst" and seen["where"] == "Toronto"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_search_plan.py tests/test_jobs_api.py -v`
Expected: FAIL (`ModuleNotFoundError: job_scout.search_plan`; the Adzuna test fails on `what`)

- [ ] **Step 3: Implement**

Edit `src/job_scout/tools/jobs_api.py`, in `AdzunaSource.fetch` change `"what": query,` to:

```python
            "what": f"{query} remote" if remote else query,
```

Create `config/search.csv`:

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

Create `src/job_scout/search_plan.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest tests/test_search_plan.py tests/test_jobs_api.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
python -m uv run ruff format . && python -m uv run ruff check .
git add src/job_scout/search_plan.py src/job_scout/tools/jobs_api.py config/search.csv tests/test_search_plan.py tests/test_jobs_api.py
git commit -m "feat: settings-driven search plan (config/search.csv)"
```

---

### Task 3: Graph accepts preset jobs

**Files:**
- Modify: `src/job_scout/graph/state.py`, `src/job_scout/graph/nodes/fetch_jobs.py` (top of `fetch_jobs`), `src/job_scout/graph/graph.py` (`should_reformulate`), `src/job_scout/runner.py` (`stream_search`), `src/job_scout/store.py`
- Test: `tests/test_nodes.py`, `tests/test_graph.py`, `tests/test_runner.py`, `tests/test_notify_cli.py` (store test)

**Interfaces:**
- Produces:
  - `AgentState.preset_jobs: list[JobPosting] | None`.
  - `stream_search(profile, *, cv_text="", cv_path=None, thread_id, tags, selected_job_id=None, preset_jobs: list[JobPosting] | None = None)`; the key is added to graph inputs only when not `None`.
  - `store.filter_unseen_jobs(path: str | Path, jobs: list[JobPosting]) -> list[JobPosting]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_nodes.py` (it already imports `fetch_mod` and `make_job`; if `make_job` is not imported there add `from tests.conftest import make_job`):

```python
def test_fetch_jobs_uses_preset_jobs_without_llm(monkeypatch, sample_profile):
    def no_llm(*a, **k):
        raise AssertionError("LLM must not be called when preset_jobs is set")

    monkeypatch.setattr(fetch_mod, "get_chat_model", no_llm)
    preset = [make_job("a", "Data Analyst", "Acme", source="adzuna"), make_job("b", "Data Scientist", "Beta", source="wwr")]
    out = fetch_mod.fetch_jobs({"profile": sample_profile, "preset_jobs": preset})
    assert out["jobs"] == preset
    assert out["jobs_sources"] == ["adzuna", "wwr"]
```

Append to `tests/test_graph.py`:

```python
def test_preset_jobs_never_reformulate():
    from langgraph.graph import END

    from job_scout.graph.graph import should_reformulate

    assert should_reformulate({"preset_jobs": [], "ranked_jobs": []}) == END
    assert should_reformulate({"ranked_jobs": []}) == "reformulate_query"
```

Append to `tests/test_runner.py`:

```python
def test_preset_jobs_passed_to_graph_only_when_given(monkeypatch, sample_profile):
    fake = _FakeGraph()
    _patch(monkeypatch, fake)
    jobs = [make_job("a", "Data Analyst", "Acme")]
    list(stream_search(sample_profile, thread_id="t", tags=[], preset_jobs=jobs))
    assert fake.captured_inputs["preset_jobs"] == jobs
    list(stream_search(sample_profile, thread_id="t", tags=[]))
    assert "preset_jobs" not in fake.captured_inputs
```
(add `from tests.conftest import make_job` to `tests/test_runner.py` imports.)

Append to `tests/test_notify_cli.py`:

```python
def test_store_filter_unseen_jobs(tmp_path):
    from job_scout.store import filter_unseen_jobs

    db = tmp_path / "s.db"
    a, b = ranked("a", 80), ranked("b", 75)
    mark_seen(db, [a])
    assert [j.job_id for j in filter_unseen_jobs(db, [a.job, b.job])] == ["b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_nodes.py tests/test_graph.py tests/test_runner.py tests/test_notify_cli.py -v`
Expected: the four new tests FAIL (`KeyError`/`AttributeError`/`ImportError`)

- [ ] **Step 3: Implement**

`src/job_scout/graph/state.py`: add inside `AgentState`:

```python
    preset_jobs: list[JobPosting] | None
```
and extend the docstring with: ``preset_jobs`` carries jobs found by the deterministic search plan; when set, ``fetch_jobs`` skips the LLM and the reformulation loop is skipped.

`src/job_scout/graph/nodes/fetch_jobs.py`: at the top of `fetch_jobs`, before `settings = get_settings()`:

```python
    preset = state.get("preset_jobs")
    if preset is not None:
        return {"jobs": preset, "jobs_sources": sorted({j.source for j in preset})}
```

`src/job_scout/graph/graph.py`: at the top of `should_reformulate` body (after the docstring):

```python
    if state.get("preset_jobs") is not None:
        return END
```

`src/job_scout/runner.py`: import `JobPosting` (`from job_scout.graph.schemas import JobPosting, Profile, RankedJob`), add `preset_jobs: list[JobPosting] | None = None,` to the `stream_search` signature after `selected_job_id`, and after the `inputs = {...}` line add:

```python
    if preset_jobs is not None:
        inputs["preset_jobs"] = preset_jobs
```

`src/job_scout/store.py`: change the import to `from job_scout.graph.schemas import JobPosting, RankedJob` and add:

```python
def filter_unseen_jobs(path: str | Path, jobs: list[JobPosting]) -> list[JobPosting]:
    """Return the postings whose ``job_id`` has not been recorded yet (before ranking)."""
    with closing(_connect(path)) as con:
        seen = {row[0] for row in con.execute("SELECT job_id FROM seen")}
    return [j for j in jobs if j.job_id not in seen]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest -q`
Expected: all pass (previous 51 + new)

- [ ] **Step 5: Commit**

```bash
python -m uv run ruff format . && python -m uv run ruff check .
git add -A
git commit -m "feat: graph accepts preset jobs from the search plan"
```

---

### Task 4: Scheduled scan uses the plan

**Files:**
- Modify: `src/job_scout/config.py`, `src/job_scout/cli.py`, `src/job_scout/notify.py`, `.env.example`
- Test: `tests/test_notify_cli.py` (update fixture, add tests)

**Interfaces:**
- Consumes: `load_plan`, `run_plan`, `default_sources`, `filter_unseen_jobs`, `stream_search(..., preset_jobs=...)`.
- Produces: `Settings.search_plan_path: str` (`SEARCH_PLAN_PATH`, default `config/search.csv`), `Settings.max_jobs_per_scan: int` (`MAX_JOBS_PER_SCAN`, default 40);
  `build_digest(jobs, source_counts: dict[str, int] | None = None) -> tuple[str, str]`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_notify_cli.py`, add `make_job` usage and replace the `scan` fixture with:

```python
@pytest.fixture
def scan(monkeypatch, tmp_path, sample_profile):
    """Wire `cli.run` to a fake CV, fake plan, fake agent, and a recording notifier."""
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"x")
    monkeypatch.setenv("SCOUT_CV_PATH", str(cv))
    monkeypatch.setenv("SCOUT_DB_PATH", str(tmp_path / "s.db"))
    monkeypatch.setattr(cli, "extract_cv_text", lambda p: "cv text")
    monkeypatch.setattr(cli, "extract_profile", lambda *a, **k: sample_profile)
    state = {
        "result": RunResult(ranked_jobs=[ranked("a", 90), ranked("b", 50)]),
        "found": [ranked("a", 0).job, ranked("b", 0).job],
        "counts": {"adzuna": 2, "wwr": 0},
        "sent": [],
        "ok": True,
        "preset": None,
        "bodies": [],
    }

    def fake_stream(*a, **k):
        state["preset"] = k.get("preset_jobs")
        return iter([("result", state["result"])])

    monkeypatch.setattr(cli, "load_plan", lambda p: ["row"])
    monkeypatch.setattr(cli, "default_sources", lambda: [])
    monkeypatch.setattr(cli, "run_plan", lambda rows, sources: (state["found"], state["counts"]))
    monkeypatch.setattr(cli, "stream_search", fake_stream)

    def fake_notify(s, subj, body):
        state["sent"].append(subj)
        state["bodies"].append(body)
        return {"telegram": state["ok"]}

    monkeypatch.setattr(cli, "notify", fake_notify)
    return state
```

Add tests:

```python
def test_digest_has_source_counts_footer():
    subject, body = notify_mod.build_digest([ranked("a", 90)], {"adzuna": 31, "wwr": 0})
    assert body.endswith("Sources: adzuna 31, wwr 0")


def test_scan_passes_only_unseen_jobs_capped_to_preset(scan, monkeypatch, tmp_path):
    monkeypatch.setenv("MAX_JOBS_PER_SCAN", "1")
    get_settings.cache_clear()
    mark_seen(tmp_path / "s.db", [ranked("a", 90)])  # "a" already seen
    assert cli.run() == 0
    assert [j.job_id for j in scan["preset"]] == ["b"]


def test_scan_cap_default_is_40(scan):
    scan["found"] = [make_job(str(i), f"Data Analyst {i}", "Acme") for i in range(60)]
    assert cli.run() == 0
    assert len(scan["preset"]) == 40


def test_nothing_new_skips_llm_and_notification(scan, monkeypatch, tmp_path):
    mark_seen(tmp_path / "s.db", [ranked("a", 90), ranked("b", 50)])

    def no_llm(*a, **k):
        raise AssertionError("no LLM call when nothing is new")

    monkeypatch.setattr(cli, "extract_profile", no_llm)
    assert cli.run() == 0
    assert scan["sent"] == []


def test_all_sources_empty_alerts(scan):
    scan["found"], scan["counts"] = [], {"adzuna": 0, "wwr": 0}
    assert cli.run() == 1
    assert scan["sent"] == ["Job Scout: scan FAILED"]
    assert "adzuna 0" in scan["bodies"][0]


def test_bad_plan_alerts(scan, monkeypatch):
    def bad(path):
        raise ValueError("config/search.csv: row 3: blank role")

    monkeypatch.setattr(cli, "load_plan", bad)
    assert cli.run() == 1
    assert "row 3" in scan["bodies"][0]
```

Add imports at top of the test file if missing: `from tests.conftest import make_job` (already present) and `mark_seen` (already imported). The existing tests in the file (`test_run_notifies_only_new_jobs_above_threshold`, retry, dry run, failed scan, missing CV) keep working with the new fixture.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_notify_cli.py -v`
Expected: FAIL (`cli` has no `load_plan`, `build_digest` has no second parameter)

- [ ] **Step 3: Implement**

`src/job_scout/config.py`: next to `notify_min_score` add:

```python
    search_plan_path: str = Field(default="config/search.csv", alias="SEARCH_PLAN_PATH")
    max_jobs_per_scan: int = Field(default=40, alias="MAX_JOBS_PER_SCAN")
```

`.env.example`: after `NOTIFY_MIN_SCORE=70` add:

```
# What to search: roles in priority order (edit this CSV, not the code).
SEARCH_PLAN_PATH=config/search.csv
# Rank at most this many NEW jobs per scan (bounds OpenRouter cost).
MAX_JOBS_PER_SCAN=40
```

`src/job_scout/notify.py`: change `build_digest` to

```python
def build_digest(jobs: list[RankedJob], source_counts: dict[str, int] | None = None) -> tuple[str, str]:
```
and, just before `return subject, body`, add:

```python
    if source_counts:
        body += "\n\nSources: " + ", ".join(f"{name} {n}" for name, n in source_counts.items())
```

`src/job_scout/cli.py`: add imports

```python
from job_scout.search_plan import default_sources, load_plan, run_plan
from job_scout.store import filter_unseen, filter_unseen_jobs, mark_seen
```
(replace the existing `from job_scout.store import filter_unseen, mark_seen`), and replace the body of `run` from `thread_id = ...` through the `result is None or result.failed` check with:

```python
    try:
        found, counts = run_plan(load_plan(settings.search_plan_path), default_sources())
    except Exception as exc:  # noqa: BLE001 - a bad plan must alert, not die silently
        return _fail(settings, f"{type(exc).__name__}: {exc}", dry_run)
    sources_line = ", ".join(f"{name} {n}" for name, n in counts.items())
    if not found:
        return _fail(settings, f"all sources returned 0 jobs ({sources_line})", dry_run)
    fresh = filter_unseen_jobs(settings.scout_db_path, found)[: settings.max_jobs_per_scan]
    logger.info("found=%d unseen=%d sources: %s", len(found), len(fresh), sources_line)
    if not fresh:
        return 0  # nothing new: no LLM calls, no message

    thread_id = f"scheduled-{uuid.uuid4().hex[:8]}"
    tags = ["scheduled"]
    try:
        cv_text = extract_cv_text(cv)
        profile = extract_profile(cv_text, thread_id=thread_id, tags=tags)
        result = None
        for kind, payload in stream_search(
            profile, cv_text=cv_text, cv_path=str(cv), thread_id=thread_id, tags=tags, preset_jobs=fresh
        ):
            if kind == "result":
                result = payload
    except Exception as exc:  # noqa: BLE001 - a failed scan must alert, not die silently
        return _fail(settings, f"{type(exc).__name__}: {exc}", dry_run)
    if result is None or result.failed:
        return _fail(settings, result.error_message if result else "no result", dry_run)
```

Then in the rest of `run`, replace the `new = filter_unseen(...)` line with `new = result.ranked_jobs` (all ranked jobs are already unseen), keep `good = [...]`, and change `build_digest(good)` to `build_digest(good, counts)`. Remove the now-unused `filter_unseen` import. Leave the `if not dry_run: mark_seen(settings.scout_db_path, new)` ending.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
python -m uv run ruff format . && python -m uv run ruff check .
git add -A
git commit -m "feat: scheduled scan runs the search plan, caps at 40 unseen jobs"
```

---

### Task 5: Baseline script, findings note, docs, PR

**Files:**
- Create: `scripts/baseline_sources.py`, `docs/findings/phase2a-sources.md`
- Modify: `CHANGELOG.md`, `docs/extending_sources.md` (one paragraph), `deploy/hermes/README.md` (one line on `MAX_JOBS_PER_SCAN`)

**Interfaces:**
- Consumes: `load_plan`, `run_plan`, `default_sources`.
- Produces: a script printing per-source and per-row counts and the share of senior-looking titles.

- [ ] **Step 1: Write the script**

Create `scripts/baseline_sources.py`:

```python
"""Print baseline numbers for the search plan: jobs per source, per role, and how many look senior.

No LLM, no notifications, nothing written. Needs ADZUNA_APP_ID/KEY in .env for Adzuna numbers.
Usage: uv run python scripts/baseline_sources.py [config/search.csv]
"""

from __future__ import annotations

import re
import sys

from job_scout.config import get_settings
from job_scout.search_plan import default_sources, load_plan, run_plan

SENIOR = re.compile(r"\b(senior|sr\.?|staff|lead|principal|manager|director|head|vp)\b", re.I)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else get_settings().search_plan_path
    rows = load_plan(path)
    sources = default_sources()
    jobs, counts = run_plan(rows, sources)
    print(f"plan rows: {len(rows)}  unique jobs: {len(jobs)}")
    print("per source:", counts)
    senior = [j for j in jobs if SENIOR.search(j.title)]
    print(f"senior-looking titles: {len(senior)} of {len(jobs)} ({100 * len(senior) // max(len(jobs), 1)}%)")
    print("per row (jobs returned before de-duplication):")
    for row in rows:
        per = {s.name: len(s.fetch(row.role, None if row.location.lower() == "canada" else row.location, "ca", row.remote_only, 25))
               for s in sources if not (getattr(s, "remote_only", False) and not row.remote_only)}
        print(f"  {row.role:22s} {row.location:8s} remote={str(row.remote_only):5s} {per}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it on the server and record numbers**

```bash
git add -A && git commit -m "feat: baseline script for the search plan"   # (plus trailers)
git push -u origin phase-2-sources
ssh hermes@bazzite 'cd ~/Job-Agent && git fetch -q && git checkout -q phase-2-sources && ~/.local/bin/uv run --no-dev python scripts/baseline_sources.py'
```
Expected: prints the counts. Write only the numbers into `docs/findings/phase2a-sources.md`
with this structure: date, command, jobs per source, share of senior-looking titles, per-row table,
and one line stating what the numbers say (for example whether WWR contributes anything). No CV text,
no company names.

- [ ] **Step 3: Docs**

`CHANGELOG.md` under `## Unreleased` -> `### Added`: Adzuna Canada and We Work Remotely sources, `config/search.csv`, 40-job cap, per-source counts in the digest, baseline note.
`docs/extending_sources.md`: add a short section pointing at `tools/sources/wwr.py` as the pattern for a keyless RSS source and at `search_plan.default_sources()` where to register a new one.
`deploy/hermes/README.md`: one line: "`MAX_JOBS_PER_SCAN` (default 40) bounds OpenRouter cost per scan; `config/search.csv` defines the roles."

- [ ] **Step 4: Full verification**

Run: `python -m uv run pytest -q && python -m uv run ruff check . && python -m uv run ruff format --check . && python -m uv run pre-commit run --all-files`
Expected: all pass.

- [ ] **Step 5: Commit, push, open PR (do not merge)**

```bash
git add -A && git commit -m "docs: Phase 2a baseline, changelog, source docs"   # (plus trailers)
git push -q origin phase-2-sources
gh pr create -R ameyk94/Job-Agent -B main -H phase-2-sources -l phase-2 -t "feat: Canada sources and settings-driven search plan (Phase 2a)" -F <body file>
```
PR body: what changed, the baseline numbers, what is verified (tests, server baseline run), what is not
(a real scheduled scan with the new plan, until merged and installed). End with the Claude Code attribution
line. Wait for CI green. The owner decides on merge.
