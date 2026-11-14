# IOFlow Health Monitoring (502 watchdog + email alerts)

A lightweight external watchdog that detects backend outages, auto-recovers them,
and emails alerts — built to eliminate the random **502 Bad Gateway** errors seen
on the live server **without introducing downtime**.

## Why this exists / why 502s happen

The backend runs as a **single uvicorn worker** (`backend/run.py`) behind nginx
(`/etc/nginx/sites-enabled/ioflow.conf`, proxying to `127.0.0.1:7001`). nginx
returns **502** whenever it can't get a response from that worker:

| Cause | Already handled? |
|-------|------------------|
| Process crashes / exits | ✅ `ioflow.service` has `Restart=always` (but ~10s 502 gap) |
| Process **alive but hung** (blocked event loop / deadlock) | ❌ systemd can't see this — process never exits |
| Worker overloaded / slow | ❌ |
| nginx/TLS misconfig | ❌ |

This watchdog covers the gaps systemd cannot: it actively probes the HTTP
endpoint, so a *hung-but-alive* worker is detected and force-restarted, and a
human is emailed every time the service goes down and again when it recovers.

## Components

| File | Role |
|------|------|
| `scripts/health_monitor.sh` | One health-check pass: probe → count failures → restart on threshold → alert. State persisted in `logs/.health_*`. |
| `scripts/send_alert.py` | Stdlib-only SMTP mailer. Reads `backend/.env` (`MAIL_SERVER`/`EMAIL_USER`/`EMAIL_PASS`/`FROM_EMAIL`, port 587 STARTTLS), same mailbox the app uses. |
| `scripts/healthcheck.env.example` | Tunable config (thresholds, recipients, URLs). |
| `deploy/systemd/ioflow-healthcheck.service` | oneshot unit that runs the monitor (as root, so it can `systemctl restart ioflow`). |
| `deploy/systemd/ioflow-healthcheck.timer` | Fires the check every **30s**; `Persistent=true`, autostarts on boot. |
| `scripts/install_healthcheck.sh` | Idempotent installer. **Never touches `ioflow.service`, nginx, or the running backend.** |

## Install (on the live server — zero downtime)

```bash
cd /opt/ioflow        # the deployed path (NOT IOFlow-V2)
git pull                              # bring in scripts/ + deploy/
sudo bash scripts/install_healthcheck.sh
```

The installer:
1. Copies `scripts/healthcheck.env.example` → `/etc/ioflow-healthcheck.env`
   (only if it doesn't already exist) and points `PROJECT_DIR` at the deploy path.
2. Installs the systemd `.service` + `.timer` with the real project path.
3. `daemon-reload`, `enable --now ioflow-healthcheck.timer`.

It installs **only** the watchdog units. The backend keeps running untouched.

### Then configure alerts

```bash
sudo nano /etc/ioflow-healthcheck.env     # set ALERT_RECIPIENTS=you@company.com
sudo systemctl start ioflow-healthcheck.service   # run one check immediately
```

## Verify

```bash
systemctl list-timers ioflow-healthcheck.timer        # next/last fire time
sudo systemctl start ioflow-healthcheck.service       # run a check now
tail -f /opt/ioflow/logs/health_monitor.log

# end-to-end email test (sends a real mail using backend/.env SMTP):
echo "test alert body" | PROJECT_DIR=/opt/ioflow \
  python3 scripts/send_alert.py --subject "[IOFlow] test alert" --to you@company.com
```

## Tuning (`/etc/ioflow-healthcheck.env`)

| Key | Default | Notes |
|-----|---------|-------|
| `FAILURE_THRESHOLD` | `3` | Consecutive 30s failures before declaring DOWN (≈90s) before restart. |
| `RESTART_ENABLED` | `true` | Set `false` to alert-only without auto-restart. |
| `RESTART_COOLDOWN` | `120` | Min seconds between auto-restarts; prevents restart storms in a crash loop. |
| `ALERT_MIN_INTERVAL` | `900` | Min seconds between repeated DOWN alerts while still down. |
| `PUBLIC_HEALTH_URL` | empty | Optionally also probe through nginx (e.g. `http://localhost:7001/health`); a failure here while local is OK alerts as an **nginx/TLS** issue and does **not** restart the backend. |
| `CURL_TIMEOUT` | `10` | A hung worker that doesn't answer within this counts as a failure. |

Changing the cadence: edit `OnUnitActiveSec` in the timer, then
`sudo systemctl daemon-reload && sudo systemctl restart ioflow-healthcheck.timer`.

## Behaviour summary

- **Healthy** → resets failure counter; if previously DOWN, emails `[RECOVERED]`.
- **Transient failure** (< threshold) → logged, no action (avoids flapping).
- **Threshold reached** → mark DOWN, capture the failure classification and the
  backend's logs **before** restarting, restart (respecting cooldown + boot grace),
  poll until healthy, then email. The alert contains:
  - **WHY IT FAILED** — connection refused (process **down**) vs. timed out
    (process **hung** — the classic 502 cause) vs. non-200.
  - the backend's **logs at the time of failure** (so the traceback/error that
    caused it is visible, not the fresh-boot logs).
  - current status + recovery outcome.
- The monitor script always exits 0 so the timer unit never shows as failed.

## Uninstall

```bash
sudo systemctl disable --now ioflow-healthcheck.timer
sudo rm /etc/systemd/system/ioflow-healthcheck.{service,timer}
sudo systemctl daemon-reload
# optional: sudo rm /etc/ioflow-healthcheck.env
```

## Recommended follow-up (separate change, not included here)

The deeper fix for 502s is to stop running a **single** worker so one slow/blocked
request can't take down the whole service. In `backend/run.py` the production
branch caps workers at `min(cpu_count, 1)`. Raising that to 2–4 workers (the
commit history shows it was intentionally pinned to 1) would let nginx fail over
to another worker instead of returning 502. This watchdog is the safety net;
multi-worker is the structural fix.
