# Setup

## 1. Install

Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
make setup    # uv sync --all-groups, installs pre-commit hooks
make test     # must pass offline with zero keys
```

## 2. LLM: OpenRouter

1. Create a key at <https://openrouter.ai/keys>.
2. In `.env`: `OPENROUTER_API_KEY=...` and `SCOUT_MODEL=<an OpenRouter model id>`, for example
   `openai/gpt-4o-mini`.

`LLM_BASE_URL` defaults to `https://openrouter.ai/api/v1`. Any OpenAI-compatible endpoint works if
you change it. The default model is chosen in Phase 1 by cost and structured-output reliability.

OpenRouter reports per-call cost in the response `usage`. Opik's built-in pricing may not know
OpenRouter model ids, so a `$0.00` cost in Opik is not real.

## 3. Tracing: pick one Opik mode

Tracing is optional. With `OPIK_ENABLED=false`, or if Opik is unreachable, the app runs untraced
and logs a single warning.

### Self-hosted (`OPIK_MODE=local`)

Run Opik in Docker or Podman, then point the SDK at its API:

```
OPIK_ENABLED=true
OPIK_MODE=local
OPIK_URL_OVERRIDE=http://localhost:5173/api
```

On the owner's home server (Podman, Bazzite) follow [deploy/opik/README.md](../deploy/opik/README.md).
On a plain Docker machine, Opik's own `./opik.sh` from <https://github.com/comet-ml/opik> serves the
UI and API on port 5173, so the URL above applies.

Verify: `curl http://localhost:5173/api/is-alive/ping` returns `{"message":"Healthy Server",...}`.

### Opik Cloud (`OPIK_MODE=cloud`, free tier)

1. Sign up at <https://www.comet.com/>.
2. Copy your API key. Leave `OPIK_WORKSPACE` empty to use its default workspace.

```
OPIK_ENABLED=true
OPIK_MODE=cloud
OPIK_API_KEY=...
OPIK_WORKSPACE=
```

### Switching

Change `OPIK_MODE` and its variables. No code change.

## 4. CV attachments on traces

`TRACE_ATTACH_CV=false` (default) keeps CV PDFs off traces. Turn it on only for fixture CVs or a
server only you can reach. A real CV on a shared server is personal data.

## 5. Job sources (optional)

`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JSEARCH_API_KEY`. Without them: Remotive plus the offline cache.
See [extending_sources.md](extending_sources.md).

## Troubleshooting

- **No traces:** `OPIK_ENABLED=true`; local mode needs `OPIK_URL_OVERRIDE`, cloud mode needs
  `OPIK_API_KEY`. The app log says `Opik unavailable, tracing disabled` if the server is unreachable.
- **Opik on Podman, UI loads but `/api` gives 502:** see the table in
  [deploy/opik/README.md](../deploy/opik/README.md).
