#!/bin/bash
#
# Long-running driver for health_monitor.sh on hosts WITHOUT systemd/cron
# (e.g. the live Docker container). Runs one check every CHECK_INTERVAL seconds.
#
# Usage:
#   scripts/health_monitor_daemon.sh start    # launch detached (nohup) and return
#   scripts/health_monitor_daemon.sh run      # run in the foreground (for entrypoint / debugging)
#   scripts/health_monitor_daemon.sh stop     # stop the running daemon
#   scripts/health_monitor_daemon.sh status   # show whether it's running
#
# Single-instance: guarded by a pidfile so repeated `start` calls are safe.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

HEALTHCHECK_ENV="${HEALTHCHECK_ENV:-/etc/ioflow-healthcheck.env}"
if [ -f "$HEALTHCHECK_ENV" ]; then
    set -a; source "$HEALTHCHECK_ENV"; set +a
fi

PROJECT_DIR="${PROJECT_DIR:-$DEFAULT_PROJECT_DIR}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
STATE_DIR="${STATE_DIR:-$PROJECT_DIR/logs}"
LOG_FILE="${LOG_FILE:-$STATE_DIR/health_monitor.log}"
PID_FILE="${PID_FILE:-$STATE_DIR/.health_daemon.pid}"
MONITOR="$SCRIPT_DIR/health_monitor.sh"

mkdir -p "$STATE_DIR" 2>/dev/null
ts() { date '+%Y-%m-%d %H:%M:%S'; }

is_running() {
    [ -f "$PID_FILE" ] || return 1
    local pid; pid="$(cat "$PID_FILE" 2>/dev/null)"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

run_loop() {
    echo "$$" > "$PID_FILE"
    echo "$(ts) [daemon] started (pid $$), interval=${CHECK_INTERVAL}s, env=$HEALTHCHECK_ENV" >> "$LOG_FILE"
    trap 'echo "$(ts) [daemon] stopping (pid $$)" >> "$LOG_FILE"; rm -f "$PID_FILE"; exit 0' TERM INT
    while true; do
        HEALTHCHECK_ENV="$HEALTHCHECK_ENV" bash "$MONITOR" || true
        sleep "$CHECK_INTERVAL"
    done
}

case "${1:-start}" in
    run)
        if is_running; then echo "already running (pid $(cat "$PID_FILE"))"; exit 0; fi
        run_loop
        ;;
    start)
        if is_running; then echo "already running (pid $(cat "$PID_FILE"))"; exit 0; fi
        setsid nohup bash "$0" run < /dev/null >> "$LOG_FILE" 2>&1 &
        disown 2>/dev/null || true
        sleep 1
        if is_running; then echo "started (pid $(cat "$PID_FILE")); logging to $LOG_FILE"; else
            echo "ERROR: failed to start; check $LOG_FILE"; exit 1; fi
        ;;
    stop)
        if is_running; then
            kill -TERM "$(cat "$PID_FILE")" 2>/dev/null && echo "stopped"
        else echo "not running"; fi
        rm -f "$PID_FILE"
        ;;
    status)
        if is_running; then echo "running (pid $(cat "$PID_FILE"))"; else echo "not running"; fi
        ;;
    *)
        echo "usage: $0 {start|run|stop|status}"; exit 2
        ;;
esac
