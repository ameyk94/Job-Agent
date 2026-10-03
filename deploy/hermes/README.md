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
