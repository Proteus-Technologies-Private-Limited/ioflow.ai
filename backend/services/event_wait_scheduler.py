"""
Event Wait Timeout Scheduler - Background task that checks for timed-out event waits
and handles timeout actions (fail, continue_with_defaults, skip).
"""
import asyncio
import logging
from datetime import datetime

from db.models import EventWait, FlowExecution, Flow, ExecutionStatus
from db.database import get_tenant_db, get_db
from core.config import settings

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


async def check_event_wait_timeouts():
    """Check for expired event waits and handle timeout actions."""
    try:
        is_sqlite = settings.database_url.startswith("sqlite") if hasattr(settings, 'database_url') else False

        if is_sqlite:
            schemas = ['default']
        else:
            db = next(get_db())
            try:
                from db.models import Tenant
                tenants = db.query(Tenant).filter(Tenant.status == 'active').all()
                schemas = [t.schema_name for t in tenants]
            finally:
                db.close()

        now = datetime.utcnow()

        for schema_name in schemas:
            try:
                with get_tenant_db(schema_name) as db:
                    expired_waits = db.query(EventWait).filter(
                        EventWait.status == 'waiting',
                        EventWait.timeout_at != None,
                        EventWait.timeout_at < now,
                    ).all()

                    for event_wait in expired_waits:
                        try:
                            await _handle_wait_timeout(event_wait, schema_name, db)
                        except Exception as e:
                            logger.error(f"Error handling timeout for event wait {event_wait.wait_id}: {e}")

                    if expired_waits:
                        db.commit()

            except Exception as e:
                logger.error(f"Error checking event wait timeouts for schema {schema_name}: {e}")

    except Exception as e:
        logger.error(f"Error in event wait timeout check: {e}")


async def _handle_wait_timeout(event_wait: EventWait, schema_name: str, db):
    """Handle a single timed-out event wait based on its timeout_action."""
    timeout_action = event_wait.timeout_action or 'fail'

    logger.info(f"EventWait {event_wait.wait_id} timed out. Action: {timeout_action}")

    if timeout_action == 'fail':
        _fail_wait(event_wait, db)

    elif timeout_action == 'continue_with_defaults':
        await _continue_with_defaults(event_wait, schema_name, db)

    elif timeout_action == 'skip':
        await _continue_with_skip(event_wait, schema_name, db)

    else:
        logger.warning(f"Unknown timeout action '{timeout_action}' for event wait {event_wait.wait_id}, failing")
        _fail_wait(event_wait, db)


def _fail_wait(event_wait: EventWait, db):
    """Fail an event wait and its associated execution."""
    event_wait.status = 'timed_out'
    event_wait.matched_at = datetime.utcnow()

    execution = db.query(FlowExecution).filter(
        FlowExecution.execution_id == event_wait.execution_id
    ).first()
    if execution and execution.status == ExecutionStatus.PAUSED:
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = datetime.utcnow()

    logger.info(f"EventWait {event_wait.wait_id} timed out, execution {event_wait.execution_id} marked as failed")


async def _continue_with_defaults(event_wait: EventWait, schema_name: str, db):
    """Resume flow with default data on timeout."""
    import json

    event_wait.status = 'timed_out'
    event_wait.matched_at = datetime.utcnow()

    default_data = event_wait.default_data
    if isinstance(default_data, str):
        try:
            default_data = json.loads(default_data)
        except (json.JSONDecodeError, TypeError):
            default_data = {}
    default_data = default_data or {}

    event_wait.event_data = default_data
    db.flush()

    event_output = {
        'event_data': default_data,
        'callback_token': event_wait.callback_token,
        'matched_at': event_wait.matched_at.isoformat(),
        'app_id': event_wait.app_id,
        'event_name': event_wait.event_name,
        '_timed_out': True,
        '_timeout_action': 'continue_with_defaults',
    }

    try:
        flow = db.query(Flow).filter(Flow.flow_id == event_wait.flow_id).first()
        if flow:
            from services.execution_engine import ExecutionEngine
            engine = ExecutionEngine(schema_name)
            await engine.resume_after_event(
                wait_id=event_wait.wait_id,
                event_output=event_output,
                flow_definition=flow.flow_definition,
                tenant_schema=schema_name,
            )
    except Exception as e:
        logger.error(f"Error resuming flow after timeout (continue_with_defaults) for wait {event_wait.wait_id}: {e}")


async def _continue_with_skip(event_wait: EventWait, schema_name: str, db):
    """Resume flow with empty data and skip marker on timeout."""
    event_wait.status = 'timed_out'
    event_wait.matched_at = datetime.utcnow()
    event_wait.event_data = {}
    db.flush()

    event_output = {
        'event_data': {},
        'callback_token': event_wait.callback_token,
        'matched_at': event_wait.matched_at.isoformat(),
        'app_id': event_wait.app_id,
        'event_name': event_wait.event_name,
        '_timed_out': True,
        '_timeout_action': 'skip',
        '_skipped': True,
    }

    try:
        flow = db.query(Flow).filter(Flow.flow_id == event_wait.flow_id).first()
        if flow:
            from services.execution_engine import ExecutionEngine
            engine = ExecutionEngine(schema_name)
            await engine.resume_after_event(
                wait_id=event_wait.wait_id,
                event_output=event_output,
                flow_definition=flow.flow_definition,
                tenant_schema=schema_name,
            )
    except Exception as e:
        logger.error(f"Error resuming flow after timeout (skip) for wait {event_wait.wait_id}: {e}")


async def start_scheduler():
    """Start the event wait timeout scheduler as a background loop."""
    logger.info("Event wait timeout scheduler started")
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        try:
            await check_event_wait_timeouts()
        except Exception as e:
            logger.error(f"Event wait timeout scheduler error: {e}")
