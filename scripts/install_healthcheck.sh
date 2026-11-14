#!/bin/bash
#
# Idempotent installer for the IOFlow health monitor.
#
# Auto-detects the host:
#   * systemd host  -> installs a .service + .timer (runs every 30s, autostarts on boot)
#   * non-systemd   -> configures the container restart command and runs the
#     watchdog as a detached nohup daemon (scripts/health_monitor_daemon.sh)
#
# ZERO DOWNTIME: never touches the running backend, nginx, or how the app is
# started. Safe to run on the live server/container.
#
# Usage (as a user with sufficient privileges):
#     sudo bash scripts/install_healthcheck.sh [PROJECT_DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SYSTEMD_DIR="/etc/systemd/system"
ENV_TARGET="/etc/ioflow-healthcheck.env"

echo "==> Installing IOFlow health monitor"
echo "    PROJECT_DIR = $PROJECT_DIR"

for f in scripts/health_monitor.sh scripts/send_alert.py scripts/restart_backend.sh \
         scripts/health_monitor_daemon.sh; do
    [ -f "$PROJECT_DIR/$f" ] || { echo "ERROR: missing $PROJECT_DIR/$f" >&2; exit 1; }
done
chmod +x "$PROJECT_DIR"/scripts/health_monitor.sh "$PROJECT_DIR"/scripts/send_alert.py \
         "$PROJECT_DIR"/scripts/restart_backend.sh "$PROJECT_DIR"/scripts/health_monitor_daemon.sh

# Detect a usable systemd.
HAVE_SYSTEMD=false
if command -v systemctl >/dev/null 2>&1 && systemctl is-system-running >/dev/null 2>&1; then
    HAVE_SYSTEMD=true
fi
echo "    systemd available = $HAVE_SYSTEMD"

# --- Config file: install once, never clobber an edited copy -------------------
if [ -f "$ENV_TARGET" ]; then
    echo "==> Keeping existing $ENV_TARGET (not overwritten)"
else
    cp "$PROJECT_DIR/scripts/healthcheck.env.example" "$ENV_TARGET"
    sed -i "s|^PROJECT_DIR=.*|PROJECT_DIR=$PROJECT_DIR|" "$ENV_TARGET"
    chmod 600 "$ENV_TARGET"
    echo "==> Installed $ENV_TARGET (edit it to set ALERT_RECIPIENTS)"
fi

if [ "$HAVE_SYSTEMD" = true ]; then
    # --- systemd path ---------------------------------------------------------
    [ "$(id -u)" -eq 0 ] || { echo "ERROR: run as root (sudo) for systemd install." >&2; exit 1; }
    sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
        "$PROJECT_DIR/deploy/systemd/ioflow-healthcheck.service" \
        > "$SYSTEMD_DIR/ioflow-healthcheck.service"
    cp "$PROJECT_DIR/deploy/systemd/ioflow-healthcheck.timer" \
       "$SYSTEMD_DIR/ioflow-healthcheck.timer"
    systemctl daemon-reload
    systemctl enable --now ioflow-healthcheck.timer
    echo "==> systemd timer enabled and started"
    echo ""
    echo "Verify:  systemctl list-timers ioflow-healthcheck.timer"
    echo "         tail -f $PROJECT_DIR/logs/health_monitor.log"
else
    # --- non-systemd (container) path -----------------------------------------
    # Ensure the restart command targets the container restart script, not systemctl.
    # The value MUST be quoted: an unquoted `RESTART_COMMAND=bash /path/script.sh`
    # would, when the env file is sourced, run that script and leave the variable
    # unset (the cause of the earlier restart-thrash). Quoting makes it a plain
    # string assignment.
    RC_VALUE="bash $PROJECT_DIR/scripts/restart_backend.sh"
    if grep -q '^RESTART_COMMAND=' "$ENV_TARGET"; then
        sed -i "s|^RESTART_COMMAND=.*|RESTART_COMMAND=\"$RC_VALUE\"|" "$ENV_TARGET"
    else
        printf '\n# Auto-set by installer (non-systemd host):\nRESTART_COMMAND="%s"\n' \
            "$RC_VALUE" >> "$ENV_TARGET"
    fi
    echo "==> Configured container restart command in $ENV_TARGET"

    # Remove any dead systemd unit files left by a previous (failed) systemd run.
    rm -f "$SYSTEMD_DIR/ioflow-healthcheck.service" "$SYSTEMD_DIR/ioflow-healthcheck.timer" 2>/dev/null || true

    # Start (or restart) the watchdog daemon.
    bash "$PROJECT_DIR/scripts/health_monitor_daemon.sh" stop >/dev/null 2>&1 || true
    bash "$PROJECT_DIR/scripts/health_monitor_daemon.sh" start
    echo ""
    echo "==> Watchdog daemon running (no systemd/cron on this host)."
    echo ""
    echo "IMPORTANT for autostart across container restarts:"
    echo "  Add this line to the container entrypoint that launches start_backend.sh,"
    echo "  AFTER the backend is started:"
    echo "      bash $PROJECT_DIR/scripts/health_monitor_daemon.sh start"
    echo ""
    echo "Verify:  bash $PROJECT_DIR/scripts/health_monitor_daemon.sh status"
    echo "         tail -f $PROJECT_DIR/logs/health_monitor.log"
fi

echo ""
echo "Next: edit $ENV_TARGET -> set ALERT_RECIPIENTS, then test email:"
echo "  echo test | PROJECT_DIR=$PROJECT_DIR python3 $PROJECT_DIR/scripts/send_alert.py \\"
echo "    --subject '[IOFlow] test alert' --to you@company.com"
