#!/bin/bash
#
# Restart the IOFlow backend WITHOUT systemd -- for container / non-systemd hosts
# where the backend runs as a plain process tree:
#     start_backend.sh  ->  python run.py   (listening on :7001)
#
# Strategy: terminate the existing backend tree, wait for the port to free, then
# relaunch start_backend.sh fully detached (setsid + nohup) so it survives this
# script and the watchdog.
#
# SAFETY:
#   * refuses to kill PID 1 (in the live container PID 1 is nginx).
#   * the process pattern is boundary-anchored so it never matches THIS script
#     (restart_backend.sh contains the substring "start_backend.sh").
#   * a lock prevents two restarts from running (and stacking) at once.
#
# Used by health_monitor.sh via RESTART_COMMAND. Can also be run by hand.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

# Pattern identifying the backend process(es). The leading [ /] boundary ensures
# "start_backend.sh" matches "/bin/bash ./start_backend.sh" but NOT this script's
# own "restart_backend.sh" cmdline.
BACKEND_PROCESS_PATTERN="${BACKEND_PROCESS_PATTERN:-run\.py|[ /]start_backend\.sh}"
START_CMD="${BACKEND_START_CMD:-bash start_backend.sh}"
HEALTH_PORT="${HEALTH_PORT:-7001}"
NOHUP_OUT="${PROJECT_DIR}/logs/ioflow_nohup.out"
LOCK_FILE="${PROJECT_DIR}/logs/.restart_backend.lock"
SELF_PID=$$

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [restart-backend] $*"; }

mkdir -p "$PROJECT_DIR/logs" 2>/dev/null

# --- Single-instance lock -----------------------------------------------------
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "another restart is already in progress; skipping"
    exit 0
fi

# --- Identify processes to stop -----------------------------------------------
collect_pids() {
    local p
    for p in $(pgrep -f "$BACKEND_PROCESS_PATTERN" 2>/dev/null); do
        [ -z "$p" ] && continue
        [ "$p" = "1" ] && continue
        [ "$p" = "$SELF_PID" ] && continue
        [ "$p" = "$PPID" ] && continue
        # Never match the watchdog/monitor/alert helpers.
        if ps -p "$p" -o args= 2>/dev/null | grep -qE 'health_monitor|restart_backend|send_alert'; then
            continue
        fi
        echo "$p"
    done
}

mapfile -t pids < <(collect_pids)

if [ "${#pids[@]}" -gt 0 ]; then
    log "stopping backend pids: ${pids[*]}"
    # Also target children (uvicorn worker processes) so nothing is orphaned.
    for pid in "${pids[@]}"; do
        pkill -TERM -P "$pid" 2>/dev/null || true
    done
    kill -TERM "${pids[@]}" 2>/dev/null || true

    # Wait up to 10s for graceful shutdown.
    for _ in $(seq 1 10); do
        mapfile -t still < <(collect_pids)
        [ "${#still[@]}" -eq 0 ] && break
        sleep 1
    done
    # Force-kill stragglers.
    mapfile -t still < <(collect_pids)
    if [ "${#still[@]}" -gt 0 ]; then
        log "force killing: ${still[*]}"
        for pid in "${still[@]}"; do
            pkill -9 -P "$pid" 2>/dev/null || true
        done
        kill -9 "${still[@]}" 2>/dev/null || true
    fi
else
    log "no running backend process found (will start fresh)"
fi

# --- Wait for the port to be released -----------------------------------------
for _ in $(seq 1 10); do
    if command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | grep -q ":$HEALTH_PORT " || break
    elif command -v netstat >/dev/null 2>&1; then
        netstat -ltn 2>/dev/null | grep -q ":$HEALTH_PORT " || break
    else
        break
    fi
    sleep 1
done

# --- Relaunch detached --------------------------------------------------------
cd "$PROJECT_DIR" || { log "ERROR: cannot cd to $PROJECT_DIR"; exit 1; }
log "relaunching backend: $START_CMD (output -> $NOHUP_OUT)"
setsid nohup $START_CMD > "$NOHUP_OUT" 2>&1 < /dev/null &
disown 2>/dev/null || true
log "backend relaunch issued (pid $!)"
exit 0
