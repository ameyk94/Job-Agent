"""Seniority title filter. Offline."""

from __future__ import annotations

import pytest

from job_scout.seniority import drop_senior, is_senior
from tests.conftest import make_job


@pytest.mark.parametrize(
    "title",
    [
        "Senior Data Scientist",
        "Sr. Data Analyst",
        "Lead Data Analyst",
        "Head of Data",
        "Principal Scientist",
        "Director of Analytics",
        "VP Data",
        "Vice President, Analytics",
        "Staff Data Scientist",
        "Chief Data Officer",
        "data scientist (SENIOR)",
    ],
)
def test_senior_titles_are_dropped(title):
    assert is_senior(title)


@pytest.mark.parametrize(
    "title",
    [
        "Analytics Manager",
        "Data Analyst II",
        "Associate Data Scientist",
        "Leadership Analytics Analyst",
        "Staffing Analyst",
        "Data Scientist",
        "Junior Data Analyst",
    ],
)
def test_other_titles_are_kept(title):
    assert not is_senior(title)


def test_drop_senior_splits_and_keeps_order():
    jobs = [
        make_job("1", "Data Analyst", "A"),
        make_job("2", "Senior Data Analyst", "B"),
        make_job("3", "Analytics Manager", "C"),
    ]
    kept, dropped = drop_senior(jobs)
    assert [j.job_id for j in kept] == ["1", "3"]
    assert [j.job_id for j in dropped] == ["2"]
