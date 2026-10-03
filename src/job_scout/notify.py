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
MAX_JOBS = 10


def build_digest(jobs: list[RankedJob]) -> tuple[str, str]:
    """Return ``(subject, body)`` for the best ``MAX_JOBS`` jobs, highest score first."""
    jobs = sorted(jobs, key=lambda j: j.fit_score, reverse=True)
    total = len(jobs)
    subject = f"Job Scout: {total} new job{'s' if total != 1 else ''}"
    blocks = []
    for j in jobs[:MAX_JOBS]:
        where = "Remote" if j.job.remote else j.job.location
        lines = [f"{j.fit_score}  {j.job.title} @ {j.job.company} ({where})", j.job.url]
        if j.matched_skills:
            lines.append("Matches: " + ", ".join(j.matched_skills[:6]))
        if j.gaps:
            lines.append("Gaps: " + ", ".join(j.gaps[:4]))
        blocks.append("\n".join(lines))
    body = "\n\n".join(blocks)
    if total > MAX_JOBS:
        body += f"\n\n+{total - MAX_JOBS} more in the app."
    return subject, body


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
