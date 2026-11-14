# How Database Connection Works in IOFlow

## Overview
The IOFlow application uses SQLite as its database, and all components find the database through a consistent mechanism.

## Configuration Flow

### 1. Base Configuration (`backend/core/config.py`)
```python
database_url: str = "postgresql://ioflow:password@localhost:5432/ioflow"  # Default
```
- This is the default in the Settings class
- Gets overridden by environment variables

### 2. Environment File (`backend/.env`)
```
DATABASE_URL=sqlite:///ioflow.db
```
- Uses relative path with three slashes (`///`)
- Relative to current working directory

### 3. Startup Script Override (`start_backend.sh`)
```bash
cd backend
export DATABASE_URL="sqlite:///$(pwd)/ioflow.db"
```
- **KEY**: Converts relative path to absolute path
- Results in: `sqlite:////path/to/ioflow/backend/ioflow.db`
- This environment variable override takes precedence

## How Different Components Access the Database

### 1. API Endpoints (FastAPI)
- Use `get_db()` dependency injection
- Path: `api/*.py` → `db.database.get_db()` → `SessionLocal` → `engine` → `DATABASE_URL`

### 2. Flow Execution Engine
- Uses `get_tenant_db()` for tenant-specific operations
- For SQLite, falls back to main database
- Path: `ExecutionEngine` → `get_tenant_db()` → `SessionLocal` → same database

### 3. Polling Service
- Uses `get_db_context()` context manager
- Path: `generic_polling_service.py` → `get_db_context()` → `SessionLocal` → same database

### 4. Background Services (Scheduler, File Watcher)
- Use `get_db_context()` for database operations
- All use the same `SessionLocal` factory

## Why It Works

### When Using `start_backend.sh`:
1. Script changes to `backend/` directory
2. Sets `DATABASE_URL` with absolute path: `/path/to/ioflow/backend/ioflow.db`
3. All Python modules import `settings.database_url` which reads this environment variable
4. Every component uses the same absolute path

### The SQLite Connection Chain:
```
Environment Variable (DATABASE_URL with absolute path)
    ↓
settings.database_url (reads from environment)
    ↓
db/database.py creates engine with this URL
    ↓
SessionLocal factory bound to this engine
    ↓
All components use SessionLocal for database access
```

## Key Points

1. **Single Source of Truth**: The `DATABASE_URL` environment variable
2. **Absolute Path Critical**: `start_backend.sh` converts relative to absolute path
3. **SQLite Simplicity**: No schema/tenant separation in SQLite, all tables in one file
4. **Consistent Access**: All components use the same `SessionLocal` factory

## Common Issues and Solutions

### Issue: "no such table" errors
**Cause**: Running from wrong directory or DATABASE_URL not set correctly
**Solution**: Always use `start_backend.sh` which ensures correct working directory and absolute path

### Issue: Polling service can't find subscriptions
**Cause**: Same as above - incorrect database path
**Solution**: Ensure backend started with `start_backend.sh`

### Issue: Different components seeing different data
**Cause**: Multiple database files due to relative paths
**Solution**: Use absolute path via `start_backend.sh`

## Testing Database Connection

To verify all components use the same database:

```python
from core.config import settings
print(f"Database URL: {settings.database_url}")

from db.database import engine
print(f"Engine URL: {engine.url}")

# Should show absolute path:
# sqlite:////path/to/ioflow/backend/ioflow.db
```

## Summary

The entire application finds the database through:
1. `start_backend.sh` sets absolute path in `DATABASE_URL` environment variable
2. All Python code reads this via `settings.database_url`
3. Single `engine` and `SessionLocal` factory ensures consistent access
4. SQLite's single-file nature means no complex schema management

This is why sending emails works (API endpoints), flow designer works (API + WebSocket), but polling might fail if the backend isn't started correctly - they all need the same absolute path to the database file.