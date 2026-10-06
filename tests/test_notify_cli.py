"""Scheduled scan: seen-store, digest, notification channels, and the `job-scout run` flow. Offline."""

from __future__ import annotations

import smtplib

import pytest

import job_scout.cli as cli
import job_scout.notify as notify_mod
from job_scout.config import get_settings
from job_scout.graph.schemas import RankedJob
from job_scout.runner import RunResult
from job_scout.store import filter_unseen, mark_seen
from tests.conftest import make_job


def ranked(job_id: str, score: int) -> RankedJob:
    return RankedJob(
        job=make_job(job_id, f"Data Analyst {job_id}", "Acme"),
        fit_score=score,
        fit_explanation="ok",
        matched_skills=["python", "sql"],
        gaps=["dbt"],
    )


def test_store_reports_only_unseen(tmp_path):
    db = tmp_path / "s.db"
    jobs = [ranked("a", 80), ranked("b", 75)]
    assert len(filter_unseen(db, jobs)) == 2
    mark_seen(db, jobs[:1])
    mark_seen(db, jobs[:1])  # idempotent
    assert [j.job.job_id for j in filter_unseen(db, jobs)] == ["b"]


def test_digest_sorted_and_capped():
    jobs = [ranked(str(i), 70 + i) for i in range(12)]
    subject, body = notify_mod.build_digest(jobs)
    assert subject == "Job Scout: 12 new jobs"
    assert body.startswith("81  Data Analyst 11")
    assert "+2 more" in body
    assert "Matches: python, sql" in body and "Gaps: dbt" in body


def test_channels_off_without_config():
    s = get_settings()
    assert not s.has_telegram and not s.has_email
    assert notify_mod.notify(s, "x", "y") == {"telegram": False, "email": False}


def test_telegram_failure_is_swallowed_and_never_logs_token(monkeypatch, caplog):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "SECRET-TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    def boom(*a, **k):
        raise RuntimeError("https://api.telegram.org/botSECRET-TOKEN/sendMessage failed")

    monkeypatch.setattr(notify_mod.httpx, "post", boom)
    assert notify_mod.send_telegram(get_settings(), "hi") is False
    assert "SECRET-TOKEN" not in caplog.text


def test_telegram_payload_truncated(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(notify_mod.httpx, "post", lambda url, json, timeout: sent.update(json) or Resp())
    assert notify_mod.send_telegram(get_settings(), "x" * 5000) is True
    assert len(sent["text"]) == notify_mod.TELEGRAM_LIMIT and sent["chat_id"] == "42"


def test_email_sends_via_starttls(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-pw")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            calls.append("starttls")

        def login(self, user, pw):
            calls.append(("login", user, pw))

        def send_message(self, msg):
            calls.append(("send", msg["Subject"], msg["To"]))

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    assert notify_mod.send_email(get_settings(), "subj", "body") is True
    assert calls == [
        ("connect", "smtp.gmail.com", 587),
        "starttls",
        ("login", "me@example.com", "app-pw"),
        ("send", "subj", "me@example.com"),
    ]


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


def test_run_notifies_only_new_jobs_above_threshold(scan):
    assert cli.run() == 0
    assert scan["sent"] == ["Job Scout: 1 new job"]  # "b" scores 50 < 70
    assert cli.run() == 0
    assert scan["sent"] == ["Job Scout: 1 new job"]  # second scan: nothing new, nothing sent


def test_run_retries_if_no_channel_delivered(scan):
    scan["ok"] = False
    assert cli.run() == 1
    scan["ok"] = True
    assert cli.run() == 0 and len(scan["sent"]) == 2  # jobs were not marked seen, so they are resent


def test_dry_run_sends_and_records_nothing(scan):
    assert cli.run(dry_run=True) == 0
    assert scan["sent"] == []
    assert cli.run() == 0 and len(scan["sent"]) == 1


def test_failed_scan_alerts(scan):
    scan["result"] = RunResult(failed=True, error_message="boom")
    assert cli.run() == 1
    assert scan["sent"] == ["Job Scout: scan FAILED"]


def test_missing_cv_alerts(scan, monkeypatch, tmp_path):
    monkeypatch.setenv("SCOUT_CV_PATH", str(tmp_path / "nope.pdf"))
    get_settings.cache_clear()
    assert cli.run() == 1
    assert scan["sent"] == ["Job Scout: scan FAILED"]


def test_store_filter_unseen_jobs(tmp_path):
    from job_scout.store import filter_unseen_jobs

    db = tmp_path / "s.db"
    a, b = ranked("a", 80), ranked("b", 75)
    mark_seen(db, [a])
    assert [j.job_id for j in filter_unseen_jobs(db, [a.job, b.job])] == ["b"]


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
