# Template stand runbook

## Purpose

Deploy one frozen candidate to a dedicated Linux container.
Use template mode without provider credentials.
Do not deploy this service to a shared application host.

## Build inputs

- Use the filtered public repository.
- Check out the exact protected release tag.
- Record the tag SHA before the build.
- Use Python 3.11 or later and Node.js 22 or later.

## Install

1. Create the `negotiation` system user.
2. Create `/opt/negotiation-trainer` and `/var/lib/negotiation-trainer`.
3. Give the service user write access only to `/var/lib/negotiation-trainer`.
4. Check out the release tag under `/opt/negotiation-trainer`.
5. Run `uv sync --frozen`.
6. Run `npm --prefix frontend ci`.
7. Run `VITE_ENABLE_PROVIDER_FEATURES=false npm --prefix frontend run build`.
8. Save `git rev-parse HEAD` to `/opt/negotiation-trainer/frontend/dist/version.txt`.
9. Install `deploy/template-stand/negotiation-trainer.service`.
10. Install `deploy/template-stand/Caddyfile` inside the public-site server block.

The Caddy route MUST return HTTP 403 for `/llm-debug` and `/api/v1/admin/*`.
The API MUST listen on loopback only.
The SQLite file MUST remain under `/var/lib/negotiation-trainer`.

## Gate before freeze

Run these checks from an external network:

1. Open `/app/training` in Chrome on a phone.
2. Complete the pinned README journey.
3. Confirm that `/llm-debug` returns 403.
4. Confirm that `/api/v1/admin/sessions` returns 403.
5. Restart the API service.
6. Restore the previous session and confirm that the database survived.
7. Confirm that `/version.txt` equals the public tag SHA.
8. Search the built `dist/` for `localhost`, `192.168`, and the private domain.
9. Configure one external HTTPS uptime check for `/api/v1/health`.

## Freeze operations

Disable automatic deployment before the submission freeze.
After the freeze, allow only service restart and availability checks.
Do not change the release tag, database schema, configuration, or static files.
Record every restart with UTC time and reason.
