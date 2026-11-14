#!/bin/bash
#
# IOFlow backend health monitor / watchdog.
#
# Runs one health-check pass and exits (driven by ioflow-healthcheck.timer).
# Complements systemd's Restart=always on ioflow.service:
#   - systemd restarts the backend when the PROCESS exits (crash).
#   - this watchdog restarts it when the process is ALIVE BUT NOT RESPONDING
#     (blocked event loop / deadlock) -- the case that surfaces as random 502s --
#     and emails an alert when the backend goes down and again when it recovers.
#
# State is persisted between runs in $STATE_DIR so consecutive-failure counting,
# restart cooldown and alert rate-limiting survive across timer invocations.
#
# Exit status is always 0 (a failed health check is an expected, handled event;
# we don't want systemd to mark the timer unit as failed).

set -uo pipefail

# --- Resolve config -----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load env file if present (CLI/systemd may point HEALTHCHECK_ENV at it).
HEALTHCHECK_ENV="${HEALTHCHECK_ENV:-/etc/ioflow-healthcheck.env}"
if [ -f "$HEALTHCHECK_ENV" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$HEALTHCHECK_ENV"
    set +a
fi

PROJECT_DIR="${PROJECT_DIR:-$DEFAULT_PROJECT_DIR}"
SERVICE_NAME="${SERVICE_NAME:-ioflow}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:7001/health}"
PUBLIC_HEALTH_URL="${PUBLIC_HEALTH_URL:-}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-5}"
CURL_TIMEOUT="${CURL_TIMEOUT:-10}"
FAILURE_THRESHOLD="${FAILURE_THRESHOLD:-3}"
RESTART_ENABLED="${RESTART_ENABLED:-true}"
RESTART_COOLDOWN="${RESTART_COOLDOWN:-120}"
# After a (re)start, give the backend this long to boot before any health failure
# counts toward another restart. start_backend.sh + uvicorn boot can take 30-60s;
# without this grace the watchdog would kill a backend that is still starting.
BOOT_GRACE_SECONDS="${BOOT_GRACE_SECONDS:-60}"
# After issuing a restart, poll the health endpoint up to this many seconds before
# deciding the restart did/didn't recover the backend.
RESTART_VERIFY_TIMEOUT="${RESTART_VERIFY_TIMEOUT:-45}"

# Command used to restart the backend. If the env file didn't set it, pick a sane
# default for THIS host: systemctl on a real systemd host, otherwise the
# container restart script. This way a missing/mis-set RESTART_COMMAND never
# falls back to systemctl on a container (where it always fails).
if [ -z "${RESTART_COMMAND:-}" ]; then
    if command -v systemctl >/dev/null 2>&1 && systemctl is-system-running >/dev/null 2>&1; then
        RESTART_COMMAND="systemctl restart $SERVICE_NAME"
    else
        RESTART_COMMAND="bash $SCRIPT_DIR/restart_backend.sh"
    fi
fi
ALERT_RECIPIENTS="${ALERT_RECIPIENTS:-}"
ALERT_MIN_INTERVAL="${ALERT_MIN_INTERVAL:-900}"
ALERT_HOSTNAME="${ALERT_HOSTNAME:-$(hostname -f 2>/dev/null || hostname)}"

STATE_DIR="${STATE_DIR:-$PROJECT_DIR/logs}"
LOG_FILE="${LOG_FILE:-$STATE_DIR/health_monitor.log}"
ALERT_SCRIPT="$SCRIPT_DIR/send_alert.py"

mkdir -p "$STATE_DIR" 2>/dev/null

FAIL_COUNT_FILE="$STATE_DIR/.health_fail_count"
STATUS_FILE="$STATE_DIR/.health_status"            # UP | DOWN
LAST_RESTART_FILE="$STATE_DIR/.health_last_restart" # epoch seconds
LAST_ALERT_FILE="$STATE_DIR/.health_last_alert"     # epoch seconds

now() { date +%s; }
ts()  { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    echo "$(ts) [health-monitor] $*" >> "$LOG_FILE"
}

read_state() { cat "$1" 2>/dev/null; }

# --- Health check -------------------------------------------------------------
# Echoes "<http_code> <body-first-line>"; returns 0 on a healthy 200 response.
check_url() {
    local url="$1" body code
    body="$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$CURL_TIMEOUT" \
                 -w $'\n%{http_code}' "$url" 2>/dev/null)"
    code="${body##*$'\n'}"
    body="${body%$'\n'*}"
    echo "${code:-000} ${body:0:200}"
    [ "$code" = "200" ]
}

send_alert() {
    local subject="$1" body="$2"
    if [ -z "$ALERT_RECIPIENTS" ]; then
        log "ALERT (not emailed, no ALERT_RECIPIENTS set): $subject"
        return
    fi
    local py
    py="$(command -v python3 || echo python3)"
    if PROJECT_DIR="$PROJECT_DIR" ALERT_RECIPIENTS="$ALERT_RECIPIENTS" \
        "$py" "$ALERT_SCRIPT" --subject "$subject" --body-file <(printf '%s\n' "$body") \
        >> "$LOG_FILE" 2>&1; then
        log "alert emailed: $subject"
    else
        log "alert FAILED to email: $subject (see send_alert output above)"
    fi
}

have_systemd() {
    command -v systemctl >/dev/null 2>&1 && systemctl is-system-running >/dev/null 2>&1
}

# Short current-state block (process/service status as of NOW).
current_status() {
    echo "Host:        $ALERT_HOSTNAME"
    echo "Time:        $(ts)"
    echo "Service:     $SERVICE_NAME"
    echo "Health URL:  $HEALTH_URL"
    if have_systemd; then
        echo "systemctl is-active: $(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo unknown)"
    else
        local procs
        procs="$(pgrep -af 'run\.py' 2>/dev/null | head -3)"
        echo "Backend process: ${procs:-none found}"
    fi
}

# Classify WHY the health check failed -- the single most useful line for triage.
# curl exit 7 = connection refused (process down); 28 = timeout (process hung).
classify_failure() {
    local url="$1" out rc code dur
    out="$(curl -s -o /dev/null --connect-timeout "$CONNECT_TIMEOUT" --max-time "$CURL_TIMEOUT" \
                -w '%{http_code} %{time_total}' "$url" 2>/dev/null)"
    rc=$?
    code="${out%% *}"; dur="${out##* }"
    case "$rc" in
        7)  echo "CONNECTION REFUSED after ${dur}s -- backend is DOWN (not listening on the port). Likely a crash/exit; see the traceback below." ;;
        28) echo "TIMED OUT after ${dur}s (>=${CURL_TIMEOUT}s) -- backend is HUNG (listening but not responding: blocked event loop / deadlock / overload). This is the classic cause of intermittent 502s." ;;
        6)  echo "DNS/HOST resolution failed (curl exit 6) for $url." ;;
        0)  echo "HTTP $code returned in ${dur}s -- backend responded but not healthy (expected 200)." ;;
        *)  echo "No usable response (curl exit $rc, http $code) after ${dur}s." ;;
    esac
}

# Capture the backend's OWN logs as of NOW (call this BEFORE restarting so the
# alert shows what was happening when it failed, not the fresh-boot logs).
capture_failure_logs() {
    echo "--- logs/ioflow.log (last 50 lines, at time of failure) ---"
    if have_systemd; then
        journalctl -u "$SERVICE_NAME" -n 50 --no-pager 2>/dev/null \
            || tail -n 50 "$PROJECT_DIR/logs/ioflow.log" 2>/dev/null \
            || echo "(no logs available)"
    else
        tail -n 50 "$PROJECT_DIR/logs/ioflow.log" 2>/dev/null || echo "(no logs available)"
    fi
    # nohup.out captures startup banners and any stderr/crash output (e.g. a
    # segfault or import error) that never reached the rotating app log.
    if [ -s "$PROJECT_DIR/logs/ioflow_nohup.out" ]; then
        echo ""
        echo "--- logs/ioflow_nohup.out (last 20 lines: stdout/stderr) ---"
        tail -n 20 "$PROJECT_DIR/logs/ioflow_nohup.out" 2>/dev/null
    fi
}

maybe_restart() {
    [ "$RESTART_ENABLED" = "true" ] || { log "restart disabled; not restarting"; return 1; }
    local last_restart elapsed
    last_restart="$(read_state "$LAST_RESTART_FILE")"; last_restart="${last_restart:-0}"
    elapsed=$(( $(now) - last_restart ))
    if [ "$elapsed" -lt "$RESTART_COOLDOWN" ]; then
        log "within restart cooldown (${elapsed}s < ${RESTART_COOLDOWN}s); skipping restart"
        return 1
    fi
    # Record the ATTEMPT time up front so the cooldown engages even if the restart
    # command itself fails -- otherwise a persistently-failing command would be
    # retried every cycle (a restart storm).
    now > "$LAST_RESTART_FILE"
    log "restarting backend via: $RESTART_COMMAND"
    if bash -c "$RESTART_COMMAND" >> "$LOG_FILE" 2>&1; then
        log "restart command issued successfully"
        return 0
    else
        local rc=$?
        log "ERROR: restart command failed (exit $rc)"
        return 2
    fi
}

# --- Main ---------------------------------------------------------------------
prev_status="$(read_state "$STATUS_FILE")"; prev_status="${prev_status:-UP}"
fail_count="$(read_state "$FAIL_COUNT_FILE")"; fail_count="${fail_count:-0}"

result="$(check_url "$HEALTH_URL")"
local_ok=$?

if [ "$local_ok" -eq 0 ]; then
    # Backend is healthy locally.
    if [ "$prev_status" = "DOWN" ]; then
        log "RECOVERED: backend healthy again ($result)"
        send_alert "[IOFlow][RECOVERED] $ALERT_HOSTNAME backend is back up" \
"The IOFlow backend on $ALERT_HOSTNAME is responding normally again (it recovered on its own, without a watchdog restart).

$(current_status)"
    fi
    echo 0 > "$FAIL_COUNT_FILE"
    echo "UP" > "$STATUS_FILE"

    # Optional through-nginx check: alert only (do not restart backend for this).
    if [ -n "$PUBLIC_HEALTH_URL" ]; then
        pub="$(check_url "$PUBLIC_HEALTH_URL")"
        if [ $? -ne 0 ]; then
            log "WARN: public health check failed while local is healthy ($pub) -- likely nginx/TLS"
            last_alert="$(read_state "$LAST_ALERT_FILE")"; last_alert="${last_alert:-0}"
            if [ $(( $(now) - last_alert )) -ge "$ALERT_MIN_INTERVAL" ]; then
                send_alert "[IOFlow][WARN] $ALERT_HOSTNAME public endpoint failing (backend OK)" \
"Local backend health is OK but the public endpoint failed:
  PUBLIC_HEALTH_URL=$PUBLIC_HEALTH_URL -> $pub
This usually indicates an nginx or TLS problem rather than the application.

$(current_status)"
                now > "$LAST_ALERT_FILE"
            fi
        fi
    fi
    exit 0
fi

# Local health check failed.
# Boot grace: if we restarted very recently, the backend is probably still
# booting -- don't count this as a failure and don't restart again yet.
last_restart="$(read_state "$LAST_RESTART_FILE")"; last_restart="${last_restart:-0}"
since_restart=$(( $(now) - last_restart ))
if [ "$last_restart" -gt 0 ] && [ "$since_restart" -lt "$BOOT_GRACE_SECONDS" ]; then
    log "health check failed but within boot grace (${since_restart}s < ${BOOT_GRACE_SECONDS}s); waiting for boot ($result)"
    exit 0
fi

fail_count=$(( fail_count + 1 ))
echo "$fail_count" > "$FAIL_COUNT_FILE"
log "health check FAILED ($fail_count/$FAILURE_THRESHOLD): $result"

if [ "$fail_count" -lt "$FAILURE_THRESHOLD" ]; then
    exit 0   # transient blip; wait for confirmation before acting
fi

# Threshold reached -> declare DOWN.
echo "DOWN" > "$STATUS_FILE"

# Capture WHY it failed and the backend's own logs NOW, BEFORE restarting --
# otherwise the alert would only show the fresh backend booting, not the failure.
failure_class="$(classify_failure "$HEALTH_URL")"
failure_logs="$(capture_failure_logs)"
log "failure classified: $failure_class"

restart_note="restart not attempted"
if maybe_restart; then
    # Poll while the backend boots (start_backend.sh + uvicorn can take 10-30s).
    waited=0
    recheck=""
    recovered=false
    while [ "$waited" -lt "$RESTART_VERIFY_TIMEOUT" ]; do
        sleep 5
        waited=$(( waited + 5 ))
        recheck="$(check_url "$HEALTH_URL")"
        if [ $? -eq 0 ]; then
            recovered=true
            break
        fi
    done
    if [ "$recovered" = true ]; then
        log "RECOVERED via restart after ${waited}s ($recheck)"
        echo 0 > "$FAIL_COUNT_FILE"
        echo "UP" > "$STATUS_FILE"
        restart_note="restart issued; backend healthy again after ${waited}s ($recheck)"
    else
        restart_note="restart issued; backend STILL not healthy after ${waited}s ($recheck)"
    fi
fi

# If the watchdog restarted the backend and it came back, this is a recovery
# event worth reporting every time (not rate-limited): the operator wants to
# know an outage happened and was auto-healed. Otherwise it's a DOWN alert,
# rate-limited to avoid spamming while the backend stays down.
if [ "$(read_state "$STATUS_FILE")" = "UP" ]; then
    send_alert "[IOFlow][AUTO-RECOVERED] $ALERT_HOSTNAME backend was restarted" \
"The IOFlow backend on $ALERT_HOSTNAME failed its health check $fail_count time(s) in a row and was automatically restarted by the watchdog.

WHY IT FAILED: $failure_class
Last result:   $result
Recovery:      $restart_note

=== Current status (after restart) ===
$(current_status)

=== Backend logs AT TIME OF FAILURE (before the restart) ===
$failure_logs"
    now > "$LAST_ALERT_FILE"
else
    last_alert="$(read_state "$LAST_ALERT_FILE")"; last_alert="${last_alert:-0}"
    if [ "$prev_status" != "DOWN" ] || [ $(( $(now) - last_alert )) -ge "$ALERT_MIN_INTERVAL" ]; then
        send_alert "[IOFlow][DOWN] $ALERT_HOSTNAME backend unhealthy" \
"The IOFlow backend on $ALERT_HOSTNAME failed its health check $fail_count time(s) in a row and is STILL DOWN.

WHY IT FAILED: $failure_class
Last result:   $result
Action:        $restart_note

=== Current status ===
$(current_status)

=== Backend logs AT TIME OF FAILURE ===
$failure_logs"
        now > "$LAST_ALERT_FILE"
    else
        log "DOWN alert suppressed (within ALERT_MIN_INTERVAL=${ALERT_MIN_INTERVAL}s)"
    fi
fi

exit 0
