# Job Scout on Hermes

Runs the Gradio UI as a systemd **user** service: starts at boot, restarts 5 s after any crash.

```bash
git clone https://github.com/ameyk94/Job-Agent.git ~/Job-Agent
cp ~/Job-Agent/.env.example ~/Job-Agent/.env && $EDITOR ~/Job-Agent/.env   # chmod 600 .env
~/Job-Agent/deploy/hermes/install.sh
```

UI: `http://hermes:7860`. Needs `loginctl enable-linger $USER` (already on for `hermes`).

**No login.** The UI takes CV uploads and spends your OpenRouter credits. Keep port 7860 on the LAN.

| Task | Command |
|---|---|
| Status | `systemctl --user status job-scout` |
| Logs | `journalctl --user -u job-scout -f` |
| Update | `~/Job-Agent/deploy/hermes/install.sh` (pulls, syncs, restarts) |
| Stop | `systemctl --user stop job-scout` |

Opik runs separately ([../opik/README.md](../opik/README.md)). If it is down the app still runs, untraced.
Set `OPIK_URL_OVERRIDE=http://localhost:5173/api` in the server's `.env`.

## Daily scan and notifications

`job-scout-scan.timer` runs `job-scout run` every day at **08:00 server time** (Toronto). If Hermes was off
at 08:00, it runs at next boot. Each scan:

1. reads your CV (`SCOUT_CV_PATH`, default `private/cv.pdf`), extracts a profile
2. searches and ranks jobs
3. keeps jobs **not seen before** with a fit score of at least `NOTIFY_MIN_SCORE` (default 70)
4. sends one digest (top 10, best first) to **Telegram and email**; sends nothing if nothing is new
5. marks all ranked jobs as seen, but only if at least one channel delivered

If a scan fails (no CV, API error, nothing delivered) you get a "scan FAILED" message instead of silence.

One-time setup on the server:

```bash
mkdir -p ~/Job-Agent/private && chmod 700 ~/Job-Agent/private
# copy your CV from your PC:  scp cv.pdf hermes@hermes:Job-Agent/private/cv.pdf
$EDITOR ~/Job-Agent/.env     # OPENROUTER_API_KEY, TELEGRAM_*, SMTP_*, EMAIL_TO
~/Job-Agent/deploy/hermes/install.sh
cd ~/Job-Agent && uv run --no-dev job-scout run --dry-run   # prints the digest, sends nothing
```

| Task | Command |
|---|---|
| Next run | `systemctl --user list-timers job-scout-scan` |
| Run now | `systemctl --user start job-scout-scan.service` |
| Scan logs | `journalctl --user -u job-scout-scan -n 50` |
| Change time | edit `OnCalendar=` in `job-scout-scan.timer`, rerun `install.sh` |
| Forget seen jobs | delete `~/Job-Agent/private/scout.db` |

**Telegram:** reuse the Hermes bot. Copy `TELEGRAM_BOT_TOKEN` and `TELEGRAM_HOME_CHANNEL` from
`~/.hermes/.env` into this `.env` as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Sending does not
interfere with Hermes (it only reads updates). Or create a separate bot with @BotFather.

**Email:** Gmail needs 2-step verification, then an App Password at
<https://myaccount.google.com/apppasswords>. Use it as `SMTP_PASSWORD`, never your account password.

Keep `.env` at mode 600. Free job APIs cap requests (JSearch ~200 per month), so keep the scan daily or less.
