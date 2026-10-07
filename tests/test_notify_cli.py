"""Scheduled scan: seen-store, digest, notification channels, and the `job-scout run` flow. Offline."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime, timedelta

import pytest

import job_scout.cli as cli
import job_scout.notify as notify_mod
from job_scout.config import get_settings
from job_scout.graph.schemas import RankedJob
from job_scout.runner import RunResult
from job_scout.store import filter_unseen_jobs, job_key, mark_seen
from tests.conftest import make_job


def ranked(job_id: str, score: int) -> RankedJob:
    return RankedJob(
        job=make_job(job_id, f"Data Analyst {job_id}", "Acme"),
        fit_score=score,
        fit_explanation="ok",
        matched_skills=["python", "sql"],
        gaps=["dbt"],
    )


T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def test_job_key_ignores_case_and_spacing():
    assert job_key("Acme  Corp", "Data  Analyst") == job_key("acme corp", "data analyst")


def test_store_repost_window(tmp_path):
    db = tmp_path / "s.db"
    a = ranked("a", 80)
    assert [j.job_id for j in filter_unseen_jobs(db, [a.job], 30, now=T0)] == ["a"]
    mark_seen(db, [a], now=T0)
    assert filter_unseen_jobs(db, [a.job], 30, now=T0 + timedelta(days=29)) == []
    assert [j.job_id for j in filter_unseen_jobs(db, [a.job], 30, now=T0 + timedelta(days=31))] == ["a"]
    mark_seen(db, [a], now=T0 + timedelta(days=31))  # resurfaced: window restarts
    assert filter_unseen_jobs(db, [a.job], 30, now=T0 + timedelta(days=45)) == []


def test_repost_with_new_id_stays_hidden_inside_window(tmp_path):
    db = tmp_path / "s.db"
    mark_seen(db, [ranked("a", 80)], now=T0)
    repost = make_job("zzz", "Data Analyst a", "Acme")  # same company + title, new id
    assert filter_unseen_jobs(db, [repost], 30, now=T0 + timedelta(days=3)) == []


def test_digest_lists_every_job_sorted():
    jobs = [ranked(str(i), 70 + i) for i in range(12)]
    subject, body = notify_mod.build_digest(jobs)
    assert subject == "Job Scout: 12 new jobs"
    assert body.startswith("81  Data Analyst 11")
    assert body.count("Data Analyst") == 12 and "more" not in body
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
        "email": False,
        "digest_jobs": None,
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

    def fake_send_digest(settings, jobs, counts):
        state["sent"].append(notify_mod.build_digest(jobs)[0])
        state["digest_jobs"] = jobs
        return {"telegram": state["ok"], "email": state["email"]}

    monkeypatch.setattr(cli, "send_digest", fake_send_digest)
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


def test_digest_has_source_counts_footer():
    subject, body = notify_mod.build_digest([ranked("a", 90)], {"adzuna": 31, "wwr": 0})
    assert body.endswith("Sources: adzuna 31, wwr 0")


def fat(i: int) -> RankedJob:
    """A job with realistic, long skill and gap lists (about 450 characters in the digest)."""
    return ranked(str(i), 70 + i % 30).model_copy(
        update={
            "matched_skills": [f"skill number {k} for job {i}" for k in range(6)],
            "gaps": [f"requirement number {k} that is missing" for k in range(4)],
        }
    )


def test_telegram_messages_fit_limit_and_keep_every_job():
    jobs = [fat(i) for i in range(40)]
    msgs = notify_mod.telegram_messages(jobs, {"adzuna": 40})
    assert len(msgs) > 1
    assert all(len(m) <= notify_mod.TELEGRAM_LIMIT for m in msgs)
    assert msgs[0].startswith(f"Job Scout: 40 new jobs (1/{len(msgs)})")
    assert msgs[-1].startswith(f"Job Scout: 40 new jobs ({len(msgs)}/{len(msgs)})")
    assert sum(m.count("Data Analyst") for m in msgs) == 40
    assert msgs[-1].endswith("Sources: adzuna 40")


def test_single_telegram_message_has_no_part_numbers():
    msgs = notify_mod.telegram_messages([ranked("a", 90)], None)
    assert len(msgs) == 1 and msgs[0].startswith("Job Scout: 1 new job\n\n") and "(1/" not in msgs[0]


def test_both_channels_carry_every_job(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")
    sent = {"tg": [], "email": None}
    monkeypatch.setattr(notify_mod, "send_telegram", lambda s, text: sent["tg"].append(text) or True)
    monkeypatch.setattr(notify_mod, "send_email", lambda s, subject, body: sent.update(email=body) or True)
    jobs = [fat(i) for i in range(25)]
    assert notify_mod.send_digest(get_settings(), jobs, None) == {"telegram": True, "email": True}
    assert sent["email"].count("Data Analyst") == 25
    assert sum(m.count("Data Analyst") for m in sent["tg"]) == 25


def test_partial_telegram_failure_is_not_delivered(monkeypatch):
    results = iter([True, False, True])
    monkeypatch.setattr(notify_mod, "send_telegram", lambda s, text: next(results))
    monkeypatch.setattr(notify_mod, "send_email", lambda s, subject, body: False)
    jobs = [fat(i) for i in range(40)]
    assert notify_mod.send_digest(get_settings(), jobs, None) == {"telegram": False, "email": False}


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


def test_senior_jobs_never_reach_ranking_or_the_cap(scan, monkeypatch, tmp_path):
    monkeypatch.setenv("MAX_JOBS_PER_SCAN", "1")
    get_settings.cache_clear()
    scan["found"] = [make_job("s", "Senior Data Analyst", "Acme"), make_job("k", "Data Analyst", "Beta")]
    assert cli.run() == 0
    assert [j.job_id for j in scan["preset"]] == ["k"]  # the senior job did not use the cap slot


def test_all_senior_means_no_llm_call(scan, monkeypatch):
    scan["found"] = [make_job("s", "Senior Data Analyst", "Acme")]

    def no_llm(*a, **k):
        raise AssertionError("no LLM when everything is senior")

    monkeypatch.setattr(cli, "extract_profile", no_llm)
    assert cli.run() == 0 and scan["sent"] == []


def test_repost_with_new_id_is_not_ranked_again(scan, tmp_path):
    mark_seen(tmp_path / "s.db", [ranked("a", 90)])
    scan["found"] = [make_job("new-id", "Data Analyst a", "Acme")]  # same company + title as seen "a"
    assert cli.run() == 0 and scan["preset"] is None


def test_main_silences_httpx_url_logging(monkeypatch):
    """httpx INFO lines contain request URLs, which carry the Adzuna key and the Telegram bot token."""
    import logging

    monkeypatch.setattr(cli, "run", lambda dry_run=False: 0)
    logging.getLogger("httpx").setLevel(logging.NOTSET)
    assert cli.main(["run"]) == 0
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
