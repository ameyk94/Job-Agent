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
    a = FakeSource(
        "adzuna",
        {"Data Scientist": [job("1", "Data Scientist", "adzuna")], "Data Analyst": [job("2", "Data Analyst", "adzuna")]},
    )
    w = FakeSource(
        "wwr", {"Data Scientist": [job("3", "Data Scientist", "wwr")]}, remote_only=True
    )  # same title+company as job 1
    rows = [
        SearchRow("Data Scientist", "Toronto", False),
        SearchRow("Data Scientist", "Canada", True),
        SearchRow("Data Analyst", "Toronto", False),
    ]
    jobs, counts = run_plan(rows, [a, w])
    assert [j.job_id for j in jobs] == ["1", "2"]  # job 3 is a duplicate of job 1
    assert counts == {"adzuna": 2, "wwr": 0}


def test_remote_only_source_skipped_for_onsite_rows_and_canada_means_no_city():
    a = FakeSource("adzuna", {})
    w = FakeSource("wwr", {}, remote_only=True)
    rows = [SearchRow("Data Scientist", "Toronto", False), SearchRow("Data Scientist", "Canada", True)]
    run_plan(rows, [a, w], per_query_limit=7)
    assert a.calls == [("Data Scientist", "Toronto", "ca", False, 7), ("Data Scientist", None, "ca", True, 7)]
    assert w.calls == [("Data Scientist", None, "ca", True, 7)]


def test_failing_source_is_ignored():
    bad = FakeSource("adzuna", {}, fail=True)
    good = FakeSource("wwr", {"Data Scientist": [job("3", "Data Scientist", "wwr")]}, remote_only=True)
    jobs, counts = run_plan([SearchRow("Data Scientist", "Canada", True)], [bad, good])
    assert [j.job_id for j in jobs] == ["3"] and counts == {"adzuna": 0, "wwr": 1}
