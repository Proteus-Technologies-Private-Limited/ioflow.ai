#!/usr/bin/env python
"""Script to run the backend server"""
import uvicorn
import multiprocessing
import os
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "ioflow.log")
MAX_LOG_SIZE = 50 * 1024 * 1024  # 50 MB per file
BACKUP_COUNT = 5  # Keep 5 rotated files (total ~300 MB max)


def setup_logging():
    """Configure rotating file logging for uvicorn and application loggers."""
    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )

    # Apply to root logger so all app + uvicorn logs are captured
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Ensure uvicorn loggers use our handlers instead of their defaults
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [file_handler, console_handler]
        uv_logger.propagate = False


if __name__ == "__main__":
    setup_logging()

    # Check if we want multi-worker mode (default) or single-worker with reload
    use_reload = os.environ.get("IOFLOW_DEV_MODE", "false").lower() == "true"
    port = int(os.environ.get("IOFLOW_PORT", "7001"))

    if use_reload:
        # Development mode with hot reload (single worker only)
        logging.getLogger().info("Running in development mode with hot reload (single worker)...")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            log_config=None,
        )
    else:
        # Production mode with multiple workers
        # NOTE: Now supports multi-worker WebSocket via database message queue
        workers = min(multiprocessing.cpu_count(), 1)
        logging.getLogger().info(f"Running with {workers} worker processes (multi-worker WebSocket supported via DB queue)...")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            workers=workers,
            reload=False,
            log_level="info",
            access_log=True,
            loop="auto",
            limit_concurrency=1000,
            timeout_keep_alive=5,
            log_config=None,
        )