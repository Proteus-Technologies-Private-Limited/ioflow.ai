#!/usr/bin/env bash
#
# IOFlow live deploy via git.
#
# Pulls the latest code from origin/<branch>, applies any pending migrations,
# rebuilds the frontend, and restarts the backend.
#
# SAFETY: the live SQLite database and .env are gitignored, so `git pull` and
# `git reset` never touch them. This script ALSO snapshots the DB before doing
# anything, so a bad migration can be rolled back by restoring the snapshot.
#
# Usage:
#   ./deploy.sh                 # deploy origin/main
#   ./deploy.sh --branch main   # explicit branch
#   ./deploy.sh --no-frontend   # skip the npm build (backend-only change)
#   ./deploy.sh --dry-run       # show what would happen, change nothing
#
set -euo pipefail

BRANCH="main"
BUILD_FRONTEND=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) BRANCH="$2"; shift 2 ;;
    --no-frontend) BUILD_FRONTEND=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"

# --- resolve the live SQLite path from backend/.env ---------------------------
DB_URL="$(grep -E '^DATABASE_URL=' backend/.env | head -1 | cut -d= -f2-)"
DB_PATH=""
if [[ "$DB_URL" == sqlite:* ]]; then
  # sqlite:////abs/path -> /abs/path ; sqlite:///rel/path -> rel/path
  DB_PATH="${DB_URL#sqlite://}"
  DB_PATH="/${DB_PATH#/}"           # ensure single leading slash for the 4-slash absolute form
  DB_PATH="${DB_PATH//\/\//\/}"
fi

run() { if [[ $DRY_RUN -eq 1 ]]; then echo "DRY: $*"; else eval "$*"; fi; }

echo "==> IOFlow deploy  branch=$BRANCH  root=$PROJECT_ROOT  ts=$TS"

# --- 1. snapshot the live DB (data safety net) --------------------------------
if [[ -n "$DB_PATH" && -f "$DB_PATH" ]]; then
  BACKUP_DIR="$PROJECT_ROOT/backup-files/db"
  run "mkdir -p '$BACKUP_DIR'"
  # use sqlite .backup for a consistent copy even with WAL active; fall back to cp
  if command -v sqlite3 >/dev/null 2>&1; then
    run "sqlite3 '$DB_PATH' \".backup '$BACKUP_DIR/ioflow.db.$TS'\""
  else
    run "cp '$DB_PATH' '$BACKUP_DIR/ioflow.db.$TS'"
  fi
  echo "    DB snapshot -> backup-files/db/ioflow.db.$TS"
else
  echo "    WARNING: could not resolve a live SQLite file from DATABASE_URL ($DB_URL); skipping DB snapshot"
fi

# --- 2. pull code (DB & .env are gitignored => untouched) ---------------------
run "git fetch origin"
echo "    incoming commits:"
git --no-pager log --oneline "HEAD..origin/$BRANCH" 2>/dev/null | sed 's/^/      /' || true
run "git checkout '$BRANCH'"
run "git reset --hard 'origin/$BRANCH'"

# --- 3. backend deps ----------------------------------------------------------
# venv lives in project root per project convention
run "source venv/bin/activate"
run "pip install -q -r backend/requirements.txt"

# --- 4. migrations ------------------------------------------------------------
# This project uses ad-hoc migration scripts (alembic is scaffolded but unused).
# List the scripts to run for THIS deploy here, newest last. Each must be
# idempotent (safe to re-run). Track applied ones in backup-files/db/applied_migrations.log
APPLIED_LOG="$PROJECT_ROOT/backup-files/db/applied_migrations.log"
run "touch '$APPLIED_LOG'"
PENDING_MIGRATIONS=(
  # "migrations/update_wati_message_received_mappings.py --apply"
  # add new migration invocations here, one per line, in order
)
for m in "${PENDING_MIGRATIONS[@]}"; do
  key="$(echo "$m" | md5sum | cut -d' ' -f1)"
  if grep -q "$key" "$APPLIED_LOG" 2>/dev/null; then
    echo "    [skip] already applied: $m"
    continue
  fi
  echo "    [migrate] $m"
  run "python3 $m"
  run "echo '$TS  $key  $m' >> '$APPLIED_LOG'"
done

# If/when you adopt alembic properly, replace the block above with:
#   run "cd backend && alembic upgrade head && cd .."

# --- 5. frontend build (static assets are gitignored, must build on live) -----
if [[ $BUILD_FRONTEND -eq 1 ]]; then
  run "cd frontend && npm ci && npm run build && cd '$PROJECT_ROOT'"
  # Vite builds to frontend/dist, but the backend serves from backend/static.
  # backend/static/index.html and backend/static/assets/ are gitignored, so the
  # freshly built bundle MUST be copied over or the live UI stays stale.
  if [[ ! -d frontend/dist ]]; then
    echo "    ERROR: frontend/dist not found after build; aborting before restart" >&2
    exit 1
  fi
  echo "    copying frontend/dist -> backend/static"
  run "rm -rf backend/static/assets backend/static/index.html"
  run "cp -r frontend/dist/* backend/static/"
fi

# --- 6. restart backend (no hot-reload) ---------------------------------------
run "./start_backend.sh"

echo "==> Deploy complete. Snapshot: backup-files/db/ioflow.db.$TS"
echo "    If anything is wrong, restore with:"
echo "      cp backup-files/db/ioflow.db.$TS '$DB_PATH' && ./start_backend.sh"
