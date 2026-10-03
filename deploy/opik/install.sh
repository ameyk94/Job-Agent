#!/usr/bin/env bash
# Install or upgrade self-hosted Opik on a Podman host (tested: Bazzite 44, Podman 5.8, docker-compose v2 shim).
# Usage: OPIK_VERSION=2.2.88 ./install.sh   (pin to a PUBLISHED release tag, not main)
set -euo pipefail

OPIK_VERSION="${OPIK_VERSION:-2.2.88}"
SRC="${OPIK_SRC:-$HOME/opik}"

[ -d "$SRC/.git" ] || git clone --depth 1 https://github.com/comet-ml/opik.git "$SRC"
git -C "$SRC" fetch -q --depth 1 origin tag "$OPIK_VERSION"
git -C "$SRC" checkout -q "$OPIK_VERSION"
cd "$SRC/deployment/docker-compose"

# 1. SELinux (Bazzite/Fedora): let containers read the bind-mounted config files.
chcon -R -t container_file_t . 2>/dev/null || true

# 2. ClickHouse: the config volume is pre-filled by clickhouse-init, which hides the image's
#    listen config, so ClickHouse binds to localhost only and the backend cannot reach it.
cat > clickhouse_config/docker_related_config.xml <<'XML'
<clickhouse>
    <listen_host>::</listen_host>
    <listen_host>0.0.0.0</listen_host>
    <listen_try>1</listen_try>
</clickhouse>
XML

# 3. nginx: upstream hardcodes Docker's DNS (127.0.0.11). Podman's DNS is the network gateway.
export OPIK_VERSION
COMPOSE=(docker-compose -p opik -f docker-compose.yaml --profile opik)
"${COMPOSE[@]}" pull
"${COMPOSE[@]}" up -d --no-build || true   # first run: creates the network; frontend may fail on DNS
gw=$(podman network inspect opik_default --format '{{(index .Subnets 0).Gateway}}')
sed -i "s/^resolver [0-9.]* /resolver $gw /" nginx_default_local.conf
chcon -t container_file_t nginx_default_local.conf 2>/dev/null || true
"${COMPOSE[@]}" up -d --no-build --force-recreate frontend

# 4. Survive reboots (needs `systemctl --user enable podman-restart` and linger; see README).
for n in $(podman ps -a --format '{{.Names}}' | grep '^opik-' | grep -vE 'init|-mc-|demo'); do
  podman update --restart unless-stopped "$n" >/dev/null
done

echo "Opik $OPIK_VERSION: http://$(hostname):5173  (SDK URL: http://$(hostname):5173/api)"
