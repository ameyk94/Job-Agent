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


def test_entity_expansion_attack_is_rejected(monkeypatch):
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
        b"<rss><item><title>&b;</title></item></rss>"
    )
    monkeypatch.setattr(wwr.httpx, "get", lambda url, **kw: _Resp(bomb))
    assert WWRSource(feeds=("https://x/a.rss",)).fetch("Data", None, "ca", True, 10) == []
