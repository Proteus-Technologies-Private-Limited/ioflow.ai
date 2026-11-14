#!/bin/bash

echo "Starting IOFlow Backend..."

# Auto-detect Oracle Instant Client or use environment variable
if [ -z "$ORACLE_HOME" ]; then
    # Try to auto-detect Oracle Instant Client (picks the latest version)
    ORACLE_HOME=$(ls -d /opt/oracle/instantclient_* 2>/dev/null | sort -V | tail -1)
    if [ -z "$ORACLE_HOME" ]; then
        echo "Warning: Oracle Instant Client not found and ORACLE_HOME not set"
        echo "Set ORACLE_HOME environment variable or install Oracle Instant Client to /opt/oracle/"
    fi
fi

# Configure Oracle environment if ORACLE_HOME is set and directory exists
if [ -n "$ORACLE_HOME" ] && [ -d "$ORACLE_HOME" ]; then
    export ORACLE_HOME
    export LD_LIBRARY_PATH=$ORACLE_HOME:$LD_LIBRARY_PATH
    export DYLD_LIBRARY_PATH=$ORACLE_HOME:$DYLD_LIBRARY_PATH  # For macOS
    export PATH=$ORACLE_HOME:$PATH
    echo "Oracle Instant Client configured:"
    echo "  ORACLE_HOME: $ORACLE_HOME"
    echo "  Library paths updated"
else
    echo "Oracle Instant Client not configured - Oracle database features will not be available"
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies (with smart detection)
cd backend

# Check if this is a fresh installation or if critical packages are missing
echo "Checking dependencies..."
if ! python -c "import fastapi, sqlalchemy, uvicorn, razorpay, httpx, pydantic" 2>/dev/null; then
    echo "⚠️  Missing critical packages detected!"

    # Check if user wants to skip installation
    if [[ "$1" == "--skip-deps" ]]; then
        echo "Skipping dependency installation (--skip-deps flag provided)"
        echo "Warning: Server may fail to start if dependencies are missing!"
    else
        echo "Installing backend dependencies..."
        pip install --quiet --disable-pip-version-check -r requirements.txt

        if [ $? -ne 0 ]; then
            echo "❌ Failed to install dependencies"
            echo "Try running manually: pip install -r backend/requirements.txt"
            exit 1
        fi
        echo "✅ Dependencies installed successfully"
    fi
elif [[ "$1" == "--install-deps" ]]; then
    # Force install if explicitly requested
    echo "Installing backend dependencies (--install-deps flag provided)..."
    pip install --quiet --disable-pip-version-check -r requirements.txt
else
    echo "✅ All critical dependencies found"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please update .env file with your database credentials!"
fi

# Database URL is configured via .env file (PostgreSQL)
# Remove hardcoded SQLite path - use DATABASE_URL from .env instead

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    
    # Source the .env file to load all variables
    set -a  # Mark all new variables for export
    source .env
    set +a  # Turn off export mode
    
    # Override with production values to ensure they're set correctly
    # Commented out to use values from .env file
    # export BASE_URL="http://localhost:7001"
    # export SERVER_URL="http://localhost:7001"
    # export base_url="http://localhost:7001"
    # export server_url="http://localhost:7001"
    # export OAUTH_CALLBACK_BASE_URL="http://localhost:7001/api/v1/oauth2/callback"
    
    echo "Using BASE_URL: $BASE_URL"
    echo "Using SERVER_URL: $SERVER_URL"
    echo "Using OAUTH_CALLBACK_BASE_URL: $OAUTH_CALLBACK_BASE_URL"
fi

# Create logs directory if it doesn't exist
mkdir -p ../logs

# Run the backend with logging
echo "Starting backend server on http://localhost:7001"
echo "Using database: $DATABASE_URL"
echo "Logs will be saved to: $(dirname $(pwd))/logs/ioflow.log"

# Detect the number of CPU cores for optimal worker count
WORKER_COUNT=$(python3 -c "import multiprocessing; print(min(multiprocessing.cpu_count(), 4))")
echo "Starting with $WORKER_COUNT worker processes for better concurrency..."

# Raise the open-file-descriptor soft limit before launching the workers.
# The default soft limit is often 1024; long-running flows (many sequential
# Gemini/API calls) plus the shared worker's DB pools, MQTT and WebSocket
# connections can exceed that and fail with "[Errno 24] Too many open files".
# We only ever RAISE the soft limit (never lower it), capped at the hard limit.
DESIRED_NOFILE=65536
CURRENT_SOFT_NOFILE=$(ulimit -Sn)
HARD_NOFILE=$(ulimit -Hn)
if [ "$HARD_NOFILE" = "unlimited" ]; then
    TARGET_NOFILE=$DESIRED_NOFILE
elif [ "$DESIRED_NOFILE" -le "$HARD_NOFILE" ] 2>/dev/null; then
    TARGET_NOFILE=$DESIRED_NOFILE
else
    TARGET_NOFILE=$HARD_NOFILE
fi
if [ "$CURRENT_SOFT_NOFILE" = "unlimited" ] || { [ "$TARGET_NOFILE" -le "$CURRENT_SOFT_NOFILE" ] 2>/dev/null; }; then
    echo "File descriptor soft limit already $CURRENT_SOFT_NOFILE (>= target $TARGET_NOFILE), leaving unchanged"
elif ulimit -n "$TARGET_NOFILE" 2>/dev/null; then
    echo "File descriptor soft limit raised from $CURRENT_SOFT_NOFILE to $(ulimit -Sn)"
else
    echo "Warning: could not raise file descriptor soft limit (still $(ulimit -Sn)); long runs may hit 'Too many open files'"
fi

# Run the backend - log rotation is handled by Python's RotatingFileHandler in run.py
# Logs are written to logs/ioflow.log (50MB per file, 5 backups, ~300MB max)
python run.py