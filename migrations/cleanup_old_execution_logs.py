"""
Cleanup execution logs and flow executions older than 2 weeks.

This script:
1. Deletes orphan execution_logs (no parent flow_execution)
2. Deletes execution_logs linked to flow_executions older than 14 days
3. Deletes flow_executions older than 14 days
4. Runs VACUUM to reclaim disk space

All deletions are done in batches to avoid locking the database.

Usage:
    cd backend && python -m migrations.cleanup_old_execution_logs

    Or from project root:
    cd backend && ../venv/bin/python -c "from migrations.cleanup_old_execution_logs import run_cleanup; run_cleanup()"
"""

import sys
import os
import sqlite3
import logging
from datetime import datetime, timedelta

# Add backend to path so we can import settings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RETENTION_DAYS = 14
BATCH_SIZE = 1000


def run_cleanup(retention_days=RETENTION_DAYS, batch_size=BATCH_SIZE):
    """Delete execution logs and flow executions older than retention_days."""

    try:
        from core.config import settings
        db_url = settings.database_url
    except ImportError:
        # Fallback: read from .env
        env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
        db_url = None
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        db_url = line.strip().split('=', 1)[1]
                        break
        if not db_url:
            logger.error("Could not determine DATABASE_URL")
            return

    if db_url.startswith("sqlite"):
        _cleanup_sqlite(db_url, retention_days, batch_size)
    elif db_url.startswith("postgresql"):
        _cleanup_postgresql(db_url, retention_days, batch_size)
    else:
        logger.error(f"Unsupported database type: {db_url}")


def _cleanup_sqlite(db_url, retention_days, batch_size):
    """Cleanup for SQLite database."""
    db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")

    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return

    cutoff_date = (datetime.utcnow() - timedelta(days=retention_days)).strftime('%Y-%m-%d %H:%M:%S')

    logger.info(f"=== Execution Log Cleanup ===")
    logger.info(f"Database: {db_path}")
    logger.info(f"Retention: {retention_days} days")
    logger.info(f"Cutoff date: {cutoff_date}")
    logger.info(f"Batch size: {batch_size}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get pre-cleanup counts
        cursor.execute("SELECT COUNT(*) FROM flow_executions")
        total_executions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM execution_logs")
        total_logs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM flow_executions WHERE started_at < ?", (cutoff_date,))
        old_executions = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM execution_logs
            WHERE execution_id IN (SELECT execution_id FROM flow_executions WHERE started_at < ?)
        """, (cutoff_date,))
        old_logs = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM execution_logs
            WHERE execution_id NOT IN (SELECT execution_id FROM flow_executions)
        """)
        orphan_logs = cursor.fetchone()[0]

        logger.info(f"")
        logger.info(f"Pre-cleanup state:")
        logger.info(f"  Total executions: {total_executions}")
        logger.info(f"  Total logs: {total_logs}")
        logger.info(f"  Executions to delete (older than {retention_days} days): {old_executions}")
        logger.info(f"  Logs to delete (linked to old executions): {old_logs}")
        logger.info(f"  Orphan logs to delete (no parent execution): {orphan_logs}")
        logger.info(f"  Total rows to delete: {old_executions + old_logs + orphan_logs}")
        logger.info(f"")

        if old_executions == 0 and orphan_logs == 0:
            logger.info("Nothing to clean up.")
            return

        # Step 1: Delete orphan execution_logs in batches
        if orphan_logs > 0:
            logger.info("Step 1: Deleting orphan execution logs...")
            total_deleted = 0
            while True:
                cursor.execute("""
                    DELETE FROM execution_logs
                    WHERE log_id IN (
                        SELECT log_id FROM execution_logs
                        WHERE execution_id NOT IN (SELECT execution_id FROM flow_executions)
                        LIMIT ?
                    )
                """, (batch_size,))
                deleted = cursor.rowcount
                conn.commit()
                total_deleted += deleted
                if deleted > 0:
                    logger.info(f"  Deleted {total_deleted}/{orphan_logs} orphan logs...")
                if deleted < batch_size:
                    break
            logger.info(f"  Done. Deleted {total_deleted} orphan logs.")
        else:
            logger.info("Step 1: No orphan logs to delete.")

        # Step 2: Delete execution_logs linked to old executions in batches
        if old_logs > 0:
            logger.info("Step 2: Deleting old execution logs...")
            total_deleted = 0
            while True:
                cursor.execute("""
                    DELETE FROM execution_logs
                    WHERE log_id IN (
                        SELECT el.log_id FROM execution_logs el
                        INNER JOIN flow_executions fe ON el.execution_id = fe.execution_id
                        WHERE fe.started_at < ?
                        LIMIT ?
                    )
                """, (cutoff_date, batch_size))
                deleted = cursor.rowcount
                conn.commit()
                total_deleted += deleted
                if deleted > 0:
                    logger.info(f"  Deleted {total_deleted}/{old_logs} old logs...")
                if deleted < batch_size:
                    break
            logger.info(f"  Done. Deleted {total_deleted} old execution logs.")
        else:
            logger.info("Step 2: No old execution logs to delete.")

        # Step 3: Delete old flow_executions in batches
        if old_executions > 0:
            logger.info("Step 3: Deleting old flow executions...")
            total_deleted = 0
            while True:
                cursor.execute("""
                    DELETE FROM flow_executions
                    WHERE execution_id IN (
                        SELECT execution_id FROM flow_executions
                        WHERE started_at < ?
                        LIMIT ?
                    )
                """, (cutoff_date, batch_size))
                deleted = cursor.rowcount
                conn.commit()
                total_deleted += deleted
                if deleted > 0:
                    logger.info(f"  Deleted {total_deleted}/{old_executions} old executions...")
                if deleted < batch_size:
                    break
            logger.info(f"  Done. Deleted {total_deleted} old flow executions.")
        else:
            logger.info("Step 3: No old executions to delete.")

        # Step 4: Verify post-cleanup state
        cursor.execute("SELECT COUNT(*) FROM flow_executions")
        remaining_executions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM execution_logs")
        remaining_logs = cursor.fetchone()[0]

        logger.info(f"")
        logger.info(f"Post-cleanup state:")
        logger.info(f"  Remaining executions: {remaining_executions}")
        logger.info(f"  Remaining logs: {remaining_logs}")

        # Step 5: VACUUM to reclaim disk space
        logger.info(f"")
        logger.info("Step 4: Running VACUUM to reclaim disk space...")
        db_size_before = os.path.getsize(db_path)
        conn.execute("VACUUM")
        db_size_after = os.path.getsize(db_path)

        saved_mb = (db_size_before - db_size_after) / (1024 * 1024)
        logger.info(f"  Size before: {db_size_before / (1024*1024):.1f} MB")
        logger.info(f"  Size after:  {db_size_after / (1024*1024):.1f} MB")
        logger.info(f"  Space saved: {saved_mb:.1f} MB")

        logger.info(f"")
        logger.info("=== Cleanup complete ===")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error during cleanup: {e}")
        raise
    finally:
        conn.close()


def _cleanup_postgresql(db_url, retention_days, batch_size):
    """Cleanup for PostgreSQL database (handles multi-tenant schemas)."""
    try:
        import psycopg2
    except ImportError:
        logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
        return

    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    logger.info(f"=== Execution Log Cleanup (PostgreSQL) ===")
    logger.info(f"Retention: {retention_days} days")
    logger.info(f"Cutoff date: {cutoff_date}")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # Get all tenant schemas
        cursor.execute("SELECT schema_name FROM ioflow.tenants WHERE schema_name IS NOT NULL")
        schemas = [row[0] for row in cursor.fetchall()]

        if not schemas:
            logger.info("No tenant schemas found.")
            return

        logger.info(f"Found {len(schemas)} tenant schema(s): {schemas}")

        for schema in schemas:
            logger.info(f"")
            logger.info(f"--- Processing schema: {schema} ---")

            # Count records to delete
            cursor.execute(f"SELECT COUNT(*) FROM {schema}.flow_executions WHERE started_at < %s", (cutoff_date,))
            old_executions = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT COUNT(*) FROM {schema}.execution_logs
                WHERE execution_id IN (
                    SELECT execution_id FROM {schema}.flow_executions WHERE started_at < %s
                )
            """, (cutoff_date,))
            old_logs = cursor.fetchone()[0]

            logger.info(f"  Executions to delete: {old_executions}")
            logger.info(f"  Logs to delete: {old_logs}")

            if old_executions == 0:
                logger.info(f"  Nothing to clean up in {schema}.")
                continue

            # Delete logs in batches
            total_deleted_logs = 0
            while True:
                cursor.execute(f"""
                    DELETE FROM {schema}.execution_logs
                    WHERE log_id IN (
                        SELECT el.log_id FROM {schema}.execution_logs el
                        INNER JOIN {schema}.flow_executions fe ON el.execution_id = fe.execution_id
                        WHERE fe.started_at < %s
                        LIMIT %s
                    )
                """, (cutoff_date, batch_size))
                deleted = cursor.rowcount
                conn.commit()
                total_deleted_logs += deleted
                if deleted > 0:
                    logger.info(f"  Deleted {total_deleted_logs}/{old_logs} logs...")
                if deleted < batch_size:
                    break

            # Delete executions in batches
            total_deleted_execs = 0
            while True:
                cursor.execute(f"""
                    DELETE FROM {schema}.flow_executions
                    WHERE execution_id IN (
                        SELECT execution_id FROM {schema}.flow_executions
                        WHERE started_at < %s
                        LIMIT %s
                    )
                """, (cutoff_date, batch_size))
                deleted = cursor.rowcount
                conn.commit()
                total_deleted_execs += deleted
                if deleted > 0:
                    logger.info(f"  Deleted {total_deleted_execs}/{old_executions} executions...")
                if deleted < batch_size:
                    break

            logger.info(f"  Done. Deleted {total_deleted_logs} logs, {total_deleted_execs} executions from {schema}.")

        logger.info(f"")
        logger.info("=== Cleanup complete ===")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error during cleanup: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_cleanup()
