"""
HITL Escalation Scheduler - Background task that checks for timed-out HITL tasks
and handles escalation actions.
"""
import asyncio
import uuid
import logging
from datetime import datetime, timedelta

from db.models import HITLTask, HITLTaskAssignment, FlowExecution, ExecutionStatus
from db.database import get_tenant_db, get_db
from core.config import settings

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


async def check_hitl_timeouts():
    """Check for expired HITL tasks and handle escalation."""
    try:
        # Determine schema to query
        is_sqlite = settings.database_url.startswith("sqlite") if hasattr(settings, 'database_url') else False

        if is_sqlite:
            schemas = ['default']
        else:
            # Get all tenant schemas
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
                    # Find tasks that have timed out
                    expired_tasks = db.query(HITLTask).filter(
                        HITLTask.status == 'pending',
                        HITLTask.timeout_at != None,
                        HITLTask.timeout_at < now,
                    ).all()

                    for task in expired_tasks:
                        try:
                            await _handle_task_timeout(task, schema_name, db)
                        except Exception as e:
                            logger.error(f"Error handling timeout for task {task.task_id}: {e}")

                    if expired_tasks:
                        db.commit()

            except Exception as e:
                logger.error(f"Error checking HITL timeouts for schema {schema_name}: {e}")

    except Exception as e:
        logger.error(f"Error in HITL escalation check: {e}")


async def _handle_task_timeout(task: HITLTask, schema_name: str, db):
    """Handle a single timed-out HITL task based on its escalation config."""
    escalation_config = task.escalation_config or {}
    on_timeout = escalation_config.get('on_timeout', 'fail')
    max_escalations = escalation_config.get('max_escalations', 3)

    logger.info(f"HITL task {task.task_id} timed out. Action: {on_timeout}, level: {task.escalation_level}")

    if on_timeout == 'auto_approve':
        await _auto_complete_task(task, 'approved', schema_name, db)

    elif on_timeout == 'auto_reject':
        await _auto_complete_task(task, 'rejected', schema_name, db)

    elif on_timeout == 'escalate':
        if task.escalation_level >= max_escalations:
            logger.info(f"Task {task.task_id} reached max escalation level ({max_escalations}), failing")
            _fail_task(task, db)
        else:
            await _escalate_task(task, escalation_config, schema_name, db)

    elif on_timeout == 'fail':
        _fail_task(task, db)

    else:
        logger.warning(f"Unknown timeout action '{on_timeout}' for task {task.task_id}, failing")
        _fail_task(task, db)


async def _auto_complete_task(task: HITLTask, action: str, schema_name: str, db):
    """Auto-complete a task with a given action and resume the flow."""
    from services.hitl_service import hitl_service

    task.response_action = action
    task.response_data = {'_auto_completed': True, '_reason': 'timeout'}
    task.completed_by = 'system_escalation'
    task.completed_at = datetime.utcnow()
    task.status = 'completed'
    db.flush()

    # Resume the flow
    try:
        from services.execution_engine import ExecutionEngine
        from db.models import Flow

        flow = db.query(Flow).filter(Flow.flow_id == task.flow_id).first()
        if flow:
            hitl_output = {
                'response_action': action,
                'response_data': task.response_data,
                'completed_by': 'system_escalation',
                'completed_at': task.completed_at.isoformat(),
                'task_type': task.task_type,
                'input_data': task.input_data,
                'task_id': task.task_id,
            }
            engine = ExecutionEngine(schema_name)
            await engine.resume_after_hitl(
                task_id=task.task_id,
                hitl_output=hitl_output,
                flow_definition=flow.flow_definition,
                tenant_schema=schema_name,
            )
    except Exception as e:
        logger.error(f"Error resuming flow after auto-{action} for task {task.task_id}: {e}")


async def _escalate_task(task: HITLTask, escalation_config: dict, schema_name: str, db):
    """Escalate a task to new assignees and reset the timeout."""
    escalate_to = escalation_config.get('escalate_to', {})
    escalation_timeout = escalation_config.get('escalation_timeout_minutes', 30)

    if not escalate_to:
        logger.warning(f"No escalation target for task {task.task_id}, failing")
        _fail_task(task, db)
        return

    # Remove existing assignments
    db.query(HITLTaskAssignment).filter(
        HITLTaskAssignment.task_id == task.task_id
    ).delete()

    # Create new assignment
    new_assignment = HITLTaskAssignment(
        id=str(uuid.uuid4()),
        task_id=task.task_id,
        assignee_type=escalate_to.get('type', 'user'),
        assignee_id=escalate_to.get('id', ''),
        tenant_id=task.tenant_id,
    )
    db.add(new_assignment)

    # Update task
    task.escalation_level += 1
    task.status = 'escalated'
    task.timeout_at = datetime.utcnow() + timedelta(minutes=escalation_timeout)
    # Reset status back to pending so it can be acted on
    task.status = 'pending'
    db.flush()

    # Send notifications to new assignees
    try:
        from services.hitl_notification_service import hitl_notification_service
        await hitl_notification_service.notify_assignees(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            schema_name=schema_name,
        )
    except Exception as e:
        logger.warning(f"Failed to send escalation notifications for task {task.task_id}: {e}")

    logger.info(f"Task {task.task_id} escalated to level {task.escalation_level}")


def _fail_task(task: HITLTask, db):
    """Fail a task and its associated execution."""
    task.status = 'expired'
    task.completed_at = datetime.utcnow()

    # Fail the execution
    execution = db.query(FlowExecution).filter(
        FlowExecution.execution_id == task.execution_id
    ).first()
    if execution and execution.status == ExecutionStatus.PAUSED:
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = datetime.utcnow()

    logger.info(f"Task {task.task_id} expired, execution {task.execution_id} marked as failed")


async def start_scheduler():
    """Start the HITL escalation scheduler as a background loop."""
    logger.info("HITL escalation scheduler started")
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        try:
            await check_hitl_timeouts()
        except Exception as e:
            logger.error(f"HITL escalation scheduler error: {e}")
