#!/bin/bash

echo "Starting IOFlow Backend (Fast Mode)..."

# Set Oracle Instant Client environment variables
export ORACLE_HOME=/opt/oracle/instantclient_23_3
export LD_LIBRARY_PATH=$ORACLE_HOME:$LD_LIBRARY_PATH
export DYLD_LIBRARY_PATH=$ORACLE_HOME:$DYLD_LIBRARY_PATH  # For macOS
export PATH=$ORACLE_HOME:$PATH

echo "Oracle Instant Client configured:"
echo "  ORACLE_HOME: $ORACLE_HOME"
echo "  Library paths updated"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Smart dependency installation - only when needed
cd backend

# Create a marker file to track requirements.txt changes
REQUIREMENTS_HASH_FILE="../.requirements_hash"
CURRENT_HASH=$(shasum -a 256 requirements.txt | cut -d' ' -f1)

if [ -f "$REQUIREMENTS_HASH_FILE" ]; then
    STORED_HASH=$(cat "$REQUIREMENTS_HASH_FILE")
    if [ "$CURRENT_HASH" = "$STORED_HASH" ]; then
        echo "Dependencies are up to date (skipping pip install)"
    else
        echo "requirements.txt has changed, updating dependencies..."
        pip install -r requirements.txt
        echo "$CURRENT_HASH" > "$REQUIREMENTS_HASH_FILE"
    fi
else
    echo "First run - installing backend dependencies..."
    pip install -r requirements.txt
    echo "$CURRENT_HASH" > "$REQUIREMENTS_HASH_FILE"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please update .env file with your database credentials!"
fi

# Set database URL to use SQLite with absolute path
export DATABASE_URL="sqlite:///$(pwd)/ioflow.db"

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."

    # Source the .env file to load all variables
    set -a  # Mark all new variables for export
    source .env
    set +a  # Turn off export mode

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

# Run with output to both console and log file
# Use the multi-worker script if available, otherwise fall back to single worker
if [ -f "run_multiworker.py" ]; then
    echo "Running with multiple workers to prevent blocking during database operations..."
    python run_multiworker.py 2>&1 | tee ../logs/ioflow.log
else
    echo "Warning: Running with single worker (may become unresponsive during heavy operations)"
    python run.py 2>&1 | tee ../logs/ioflow.log
fi