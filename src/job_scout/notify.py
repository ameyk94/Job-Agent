"""Digest formatting and delivery (Telegram, email).

Each channel is optional and independent: one failing never blocks the other or the run.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from job_scout.config import Settings
from job_scout.graph.schemas import RankedJob

logger = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096  # Bot API max message length
_CHUNK = TELEGRAM_LIMIT - 120  # room for the "(i/n)" header


def _blocks(jobs: list[RankedJob]) -> list[str]:
    """One text block per job, highest score first."""
    out = []
    for j in sorted(jobs, key=lambda j: j.fit_score, reverse=True):
        where = "Remote" if j.job.remote else j.job.location
        lines = [f"{j.fit_score}  {j.job.title} @ {j.job.company} ({where})", j.job.url]
        if j.matched_skills:
            lines.append("Matches: " + ", ".join(j.matched_skills[:6]))
        if j.gaps:
            lines.append("Gaps: " + ", ".join(j.gaps[:4]))
        out.append("\n".join(lines))
    return out


def _subject(n: int) -> str:
    return f"Job Scout: {n} new job{'s' if n != 1 else ''}"


def _sources_line(source_counts: dict[str, int] | None) -> str:
    if not source_counts:
        return ""
    return "Sources: " + ", ".join(f"{name} {n}" for name, n in source_counts.items())


def build_digest(jobs: list[RankedJob], source_counts: dict[str, int] | None = None) -> tuple[str, str]:
    """Return ``(subject, body)`` listing every job, highest score first."""
    parts = _blocks(jobs)
    if source_counts:
        parts.append(_sources_line(source_counts))
    return _subject(len(jobs)), "\n\n".join(parts)


def telegram_messages(jobs: list[RankedJob], source_counts: dict[str, int] | None = None) -> list[str]:
    """Pack every job into as few Telegram messages as fit the 4096-character limit.

    Jobs are never split across messages. With more than one message each starts with ``(i/n)``.
    """
    subject = _subject(len(jobs))
    parts = _blocks(jobs)
    if source_counts:
        parts.append(_sources_line(source_counts))
    chunks: list[str] = []
    cur = ""
    for part in parts:
        if cur and len(cur) + 2 + len(part) > _CHUNK:
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n\n{part}" if cur else part
    chunks.append(cur)
    if len(chunks) == 1:
        return [f"{subject}\n\n{chunks[0]}"]
    return [f"{subject} ({i}/{len(chunks)})\n\n{c}" for i, c in enumerate(chunks, start=1)]


def send_digest(settings: Settings, jobs: list[RankedJob], source_counts: dict[str, int] | None) -> dict[str, bool]:
    """Send every job to both channels: one email, and as many Telegram messages as needed.

    Telegram counts as delivered only if all of its messages were sent.
    """
    subject, email_body = build_digest(jobs, source_counts)
    telegram_ok = all(send_telegram(settings, m) for m in telegram_messages(jobs, source_counts))
    return {"telegram": telegram_ok, "email": send_email(settings, subject, email_body)}


def send_telegram(settings: Settings, text: str) -> bool:
    """Send via the Telegram Bot API. Returns True on success; never raises."""
    if not settings.has_telegram:
        return False
    payload = {"chat_id": settings.telegram_chat_id, "text": text[:TELEGRAM_LIMIT], "disable_web_page_preview": True}
    if settings.telegram_thread_id:
        payload["message_thread_id"] = settings.telegram_thread_id
    try:
        token = settings.telegram_bot_token.get_secret_value()
        httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=20).raise_for_status()
    except Exception as exc:  # noqa: BLE001 - log the type only: the exception text contains the bot token URL
        logger.warning("Telegram send failed: %s", type(exc).__name__)
        return False
    return True


def send_email(settings: Settings, subject: str, body: str) -> bool:
    """Send via SMTP with STARTTLS. Returns True on success; never raises."""
    if not settings.has_email:
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, settings.smtp_user, settings.email_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            smtp.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Email send failed: %s", type(exc).__name__)
        return False
    return True


def notify(settings: Settings, subject: str, body: str) -> dict[str, bool]:
    """Send to every configured channel; report which succeeded."""
    return {
        "telegram": send_telegram(settings, f"{subject}\n\n{body}"),
        "email": send_email(settings, subject, body),
    }
