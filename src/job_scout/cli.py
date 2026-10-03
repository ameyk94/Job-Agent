"""``job-scout run``: one scheduled scan. CV -> profile -> search and rank -> notify on NEW good jobs."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

from job_scout.config import Settings, get_settings
from job_scout.notify import build_digest, notify
from job_scout.profile import extract_profile
from job_scout.runner import stream_search
from job_scout.store import filter_unseen, mark_seen
from job_scout.tools.cv_reader import extract_cv_text

logger = logging.getLogger("job_scout")


def run(dry_run: bool = False) -> int:
    """Run one scan. Returns a process exit code (0 ok, 1 failed)."""
    settings = get_settings()
    cv = Path(settings.scout_cv_path)
    if not cv.is_file():
        return _fail(settings, f"CV not found: {cv} (set SCOUT_CV_PATH)", dry_run)

    thread_id = f"scheduled-{uuid.uuid4().hex[:8]}"
    tags = ["scheduled"]
    try:
        cv_text = extract_cv_text(cv)
        profile = extract_profile(cv_text, thread_id=thread_id, tags=tags)
        result = None
        for kind, payload in stream_search(profile, cv_text=cv_text, cv_path=str(cv), thread_id=thread_id, tags=tags):
            if kind == "result":
                result = payload
    except Exception as exc:  # noqa: BLE001 - a failed scan must alert, not die silently
        return _fail(settings, f"{type(exc).__name__}: {exc}", dry_run)
    if result is None or result.failed:
        return _fail(settings, result.error_message if result else "no result", dry_run)

    new = filter_unseen(settings.scout_db_path, result.ranked_jobs)
    good = [j for j in new if j.fit_score >= settings.notify_min_score]
    logger.info("ranked=%d new=%d new_above_threshold=%d", len(result.ranked_jobs), len(new), len(good))
    if good:
        subject, body = build_digest(good)
        if dry_run:
            print(subject, body, sep="\n\n")
        elif not any(notify(settings, subject, body).values()):
            # Nothing delivered: leave the jobs unseen so the next run retries.
            logger.error("no notification channel succeeded")
            return 1
    if not dry_run:
        mark_seen(settings.scout_db_path, new)
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
