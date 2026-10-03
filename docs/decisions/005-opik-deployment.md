# ADR-005: Opik self-hosted on Hermes; docs cover both modes

Status: accepted, 2026-10-03

## Context
Opik can be self-hosted or used via Opik Cloud. The owner has a home server (Hermes, Bazzite, Podman).

## Decision
- Owner: self-hosted Opik 2.2.88 on Hermes, UI and API on port 5173, LAN only.
- Public docs describe both self-hosted and Opik Cloud (free tier).
- `OPIK_MODE=local|cloud` switches between them; nothing else changes.
- Tracing never breaks a run: if Opik is unreachable, log one warning and continue untraced.

## Consequences
- Opik's compose file targets Docker. On Podman we need three fixes (SELinux labels, ClickHouse
  listen address, nginx resolver), scripted in `deploy/opik/install.sh`.
- Self-hosted Opik has no login. Exposure is limited by keeping it on the LAN.
- Upgrades are manual: pin a published tag and rerun the script.
