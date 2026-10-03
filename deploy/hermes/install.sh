#!/usr/bin/env bash
# Install or update Job Scout as a systemd user service (restarts on crash and on reboot).
# Run on the server, from a clone at ~/Job-Agent. Needs uv and `loginctl enable-linger $USER`.
set -euo pipefail
cd "$(dirname "$0")/../.."
[ "$PWD" = "$HOME/Job-Agent" ] || { echo "clone to ~/Job-Agent (unit file uses that path)"; exit 1; }

git pull --ff-only
~/.local/bin/uv sync --no-dev
mkdir -p ~/.config/systemd/user
install -m 644 deploy/hermes/job-scout.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable job-scout.service
systemctl --user restart job-scout.service
sleep 5
systemctl --user is-active job-scout.service
echo "UI: http://$(hostname):7860"
