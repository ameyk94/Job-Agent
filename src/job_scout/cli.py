"""``job-scout run``: one scheduled scan. Search plan -> unseen jobs -> rank -> notify on NEW good jobs."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

from job_scout.config import Settings, get_settings
from job_scout.notify import build_digest, notify, send_digest
from job_scout.profile import extract_profile
from job_scout.runner import stream_search
from job_scout.search_plan import default_sources, load_plan, run_plan
from job_scout.seniority import drop_senior
from job_scout.store import filter_unseen_jobs, mark_seen
from job_scout.tools.cv_reader import extract_cv_text

logger = logging.getLogger("job_scout")


def run(dry_run: bool = False) -> int:
    """Run one scan. Returns a process exit code (0 ok, 1 failed)."""
    settings = get_settings()
    cv = Path(settings.scout_cv_path)
    if not cv.is_file():
        return _fail(settings, f"CV not found: {cv} (set SCOUT_CV_PATH)", dry_run)

    try:
        found, counts = run_plan(load_plan(settings.search_plan_path), default_sources())
    except Exception as exc:  # noqa: BLE001 - a bad plan must alert, not die silently
        return _fail(settings, f"{type(exc).__name__}: {exc}", dry_run)
    sources_line = ", ".join(f"{name} {n}" for name, n in counts.items())
    if not found:
        return _fail(settings, f"all sources returned 0 jobs ({sources_line})", dry_run)
    # Drop senior titles, then recently reported jobs, then cap: each day reaches the next unseen entry/mid jobs.
    kept, senior = drop_senior(found)
    fresh = filter_unseen_jobs(settings.scout_db_path, kept, settings.repost_gap_days)[: settings.max_jobs_per_scan]
    logger.info("found=%d senior_dropped=%d unseen=%d sources: %s", len(found), len(senior), len(fresh), sources_line)
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

    ranked = result.ranked_jobs  # all unseen: senior and recently reported jobs were dropped before ranking
    good = sorted((j for j in ranked if j.fit_score >= settings.notify_min_score), key=lambda j: j.fit_score, reverse=True)
    logger.info("ranked=%d above_threshold=%d", len(ranked), len(good))
    if good:
        if dry_run:
            subject, body = build_digest(good, counts)
            print(subject, body, sep="\n\n")
        else:
            sent = send_digest(settings, good, counts)
            if not any(sent.values()):
                # Nothing delivered: leave the jobs unseen so the next run retries.
                logger.error("no notification channel succeeded")
                return 1
    if not dry_run:
        mark_seen(settings.scout_db_path, ranked)
    return 0


def _fail(settings: Settings, message: str, dry_run: bool) -> int:
    logger.error("scan failed: %s", message)
    if not dry_run:
        notify(settings, "Job Scout: scan FAILED", message[:500])
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="job-scout")
    sub = parser.add_subparsers(dest="cmd", required=True)
    runp = sub.add_parser("run", help="run one scan and notify about new jobs")
    runp.add_argument("--dry-run", action="store_true", help="print the digest; send nothing, record nothing")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
