# Self-hosted Opik on Hermes

Opik traces every Job Scout run. The owner runs it in Podman on the **Hermes** home server
(Bazzite 44, 62 GB RAM). Public docs also cover [Opik Cloud](../../docs/setup.md); switching is
configuration only (`OPIK_MODE`).

## Install

On the server:

```bash
git clone https://github.com/ameyk94/Job-Agent.git && cd Job-Agent
OPIK_VERSION=2.2.88 ./deploy/opik/install.sh
```

Pin `OPIK_VERSION` to a **published** release (`gh api repos/comet-ml/opik/releases/latest --jq .tag_name`).
`main` is ahead of the published images and fails with `manifest unknown`.

The script starts the stack from `~/opik/deployment/docker-compose` with `docker-compose` (Podman
socket). It does not use Opik's `opik.sh`, which needs a real `docker` binary.

### Why the script patches three things

| Symptom | Cause | Fix in `install.sh` |
|---|---|---|
| `clickhouse-init` exits 1: `can't stat /clickhouse_config_files/*` | SELinux blocks bind mounts | `chcon -t container_file_t` |
| Backend: `Connect to clickhouse:8123 ... Connection refused` | ClickHouse listens on localhost only | add `listen_host` config file |
| UI loads, `/api` returns 502 (`backend could not be resolved`) | nginx hardcodes Docker DNS `127.0.0.11` | set `resolver` to the Podman network gateway |

The resolver patch hardcodes the gateway IP (`10.89.2.1` today). If you delete the `opik_default`
network, rerun `install.sh`.

## Check it works

```bash
curl http://hermes:5173/api/is-alive/ping    # {"message":"Healthy Server","healthy":true}
```

UI: `http://hermes:5173`. Open ports: **5173** only (UI and `/api`). Infrastructure containers
publish no ports.

## Point the SDK at it from another machine

In `.env` on the machine running Job Scout:

```
OPIK_MODE=local
OPIK_URL_OVERRIDE=http://hermes:5173/api
```

Use the LAN hostname or IP. Self-hosted Opik has **no login**: keep it on the
LAN and do not forward the port to the internet.

If Opik is down, Job Scout logs one warning and runs untraced.

## Reboots

Containers use `restart: unless-stopped` (set by `install.sh`). This needs lingering and the
Podman restart unit, both already enabled for `hermes`:

```bash
loginctl enable-linger hermes
systemctl --user enable podman-restart.service
```

`podman update` settings reset when `docker-compose up` recreates a container. Rerun `install.sh`
after any recreate.

## Upgrade

```bash
OPIK_VERSION=<new published tag> ./deploy/opik/install.sh
```

Read the Opik release notes first. Back up before major bumps.

## Backup and restore

Data lives in named Podman volumes: `opik_mysql` (projects, prompts), `opik_clickhouse`
(traces, spans), `opik_minio-data` (attachments).

```bash
cd ~/opik/deployment/docker-compose
docker-compose -p opik --profile opik stop
for v in mysql clickhouse minio-data; do
  podman volume export opik_$v -o ~/backups/opik_$v-$(date +%F).tar
done
docker-compose -p opik --profile opik start
```

Restore: `podman volume import opik_<name> <file>.tar` into empty volumes, then start the stack.
(Restore not yet rehearsed; do a dry run before relying on it.)
