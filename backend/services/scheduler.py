from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text
import logging
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Any, List

from db.database import get_db, get_tenant_db, get_db_context
from db.db_compat import table_ref, is_sqlite
from db.models import Flow, FlowStatus, Tenant
from .execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)

class FlowScheduler:
    """Manages scheduled flow executions."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.active_jobs = {}  # flow_id -> job_id mapping
        self.lock_manager = None  # Will be injected by BackgroundServiceManager
        self.sync_task = None  # Background task for periodic sync
        self.sync_interval = 60  # Sync every 60 seconds to pick up new activations
    
    async def start(self):
        """Start the scheduler and load all active scheduled flows."""
        self.scheduler.start()
        logger.info("Flow scheduler started")

        # Load existing scheduled flows
        await self.reload_all_schedules()

        # Start periodic sync task to handle multi-worker scenarios
        self.sync_task = asyncio.create_task(self._periodic_sync())
    
    async def stop(self):
        """Stop the scheduler."""
        # Cancel periodic sync task
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass

        self.scheduler.shutdown()
        logger.info("Flow scheduler stopped")
    
    async def reload_all_schedules(self):
        """Reload all scheduled flows from database."""
        try:
            with get_db_context() as db:
                if is_sqlite:
                    # SQLite: Use ORM query since all data is in one schema
                    tenants = db.query(Tenant).filter(Tenant.status == 'active').all()
                    for tenant in tenants:
                        await self.reload_tenant_schedules(tenant.tenant_id, 'default')
                else:
                    # PostgreSQL: Each tenant has its own schema
                    tenants = db.execute(
                        text(f"SELECT tenant_id, schema_name FROM {table_ref('tenants')} WHERE status = 'active'")
                    ).fetchall()

                    for tenant_id, schema_name in tenants:
                        await self.reload_tenant_schedules(tenant_id, schema_name)

        except Exception as e:
            logger.error(f"Failed to reload schedules: {str(e)}")
    
    async def reload_tenant_schedules(self, tenant_id: str, schema_name: str):
        """Reload schedules for a specific tenant."""
        try:
            with get_tenant_db(schema_name) as tenant_db:
                # Find all active flows with schedule triggers for this specific tenant
                # Both SQLite and PostgreSQL: Filter by tenant_id to avoid scheduling
                # the same flow multiple times across different tenant iterations
                flows = tenant_db.query(Flow).filter(
                    Flow.tenant_id == tenant_id,
                    Flow.status == FlowStatus.ACTIVE
                ).all()
                
                for flow in flows:
                    trigger_config = flow.trigger_config or {}
                    if trigger_config.get('type') == 'schedule':
                        # Don't execute immediately on reload (server restart)
                        await self.schedule_flow(tenant_id, schema_name, flow, execute_immediately=False)
        
        except Exception as e:
            logger.error(f"Failed to reload schedules for tenant {tenant_id}: {str(e)}")
    
    async def schedule_flow(self, tenant_id: str, schema_name: str, flow: Flow, execute_immediately: bool = True):
        """Schedule a single flow.
        
        Args:
            tenant_id: The tenant ID
            schema_name: The tenant schema name
            flow: The flow to schedule
            execute_immediately: Whether to execute the flow immediately on schedule (default: True)
        """
        flow_id = flow.flow_id
        job_id = f"{tenant_id}_{flow_id}"
        
        # Remove existing job if any
        if job_id in self.active_jobs:
            try:
                self.scheduler.remove_job(self.active_jobs[job_id])
            except Exception:
                pass  # Job may have already been removed from APScheduler
            del self.active_jobs[job_id]
        
        trigger_config = flow.trigger_config or {}
        schedule_config = trigger_config.get('schedule', {})
        
        logger.info(f"Scheduling flow {flow_id} with trigger_config: {trigger_config}")
        logger.info(f"Schedule config: {schedule_config}")
        
        # Handle if schedule_config is None or not a dict
        if not isinstance(schedule_config, dict):
            logger.error(f"Invalid schedule config type: {type(schedule_config)}, value: {schedule_config}")
            return
            
        schedule_type = schedule_config.get('type')
        # Wall-clock schedules (cron/daily/weekly/monthly) fire in the zone the
        # schedule names; without one, the server's zone as before.
        tz = self._schedule_timezone(schedule_config, trigger_config, flow_id)
        
        try:
            if schedule_type == 'interval':
                # Interval-based schedule
                interval_value = schedule_config.get('interval_value', 1)
                interval_unit = schedule_config.get('interval_unit', 'hours')
                
                if interval_unit == 'minutes':
                    trigger = IntervalTrigger(minutes=interval_value)
                elif interval_unit == 'hours':
                    trigger = IntervalTrigger(hours=interval_value)
                elif interval_unit == 'days':
                    trigger = IntervalTrigger(days=interval_value)
                else:
                    logger.error(f"Unknown interval unit: {interval_unit}")
                    return
            
            elif schedule_type == 'cron':
                # Cron-based schedule
                cron_expression = schedule_config.get('cron_expression')
                
                logger.info(f"Cron expression type: {type(cron_expression)}, value: {cron_expression}")
                
                # Handle if cron_expression is a dict (shouldn't happen but let's be safe)
                if isinstance(cron_expression, dict):
                    logger.error(f"Cron expression is a dict: {cron_expression}")
                    # Try to extract from nested structure
                    if 'cron_expression' in cron_expression:
                        cron_expression = cron_expression.get('cron_expression', '')
                    else:
                        logger.error(f"Cannot find cron_expression in dict: {cron_expression}")
                        return
                
                if cron_expression and isinstance(cron_expression, str):
                    # Parse cron expression
                    parts = cron_expression.split()
                    if len(parts) == 5:
                        trigger = CronTrigger(
                            minute=parts[0],
                            hour=parts[1],
                            day=parts[2],
                            month=parts[3],
                            day_of_week=parts[4],
                            timezone=tz
                        )
                    else:
                        logger.error(f"Invalid cron expression: {cron_expression}")
                        return
                else:
                    # Build cron from individual fields
                    trigger = self._build_cron_trigger(schedule_config, tz)
            
            elif schedule_type == 'daily':
                # Daily at specific time
                time_str = schedule_config.get('time', '00:00')
                hour, minute = map(int, time_str.split(':'))
                trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
            
            elif schedule_type == 'weekly':
                # Weekly on specific days
                days = schedule_config.get('days', [])
                time_str = schedule_config.get('time', '00:00')
                hour, minute = map(int, time_str.split(':'))
                
                if days:
                    day_of_week = ','.join(str(d) for d in days)
                    trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute,
                                          timezone=tz)
                else:
                    logger.error("No days specified for weekly schedule")
                    return
            
            elif schedule_type == 'monthly':
                # Monthly on specific day
                day = schedule_config.get('day', 1)
                time_str = schedule_config.get('time', '00:00')
                hour, minute = map(int, time_str.split(':'))
                
                if day == 'last':
                    trigger = CronTrigger(day='last', hour=hour, minute=minute, timezone=tz)
                else:
                    trigger = CronTrigger(day=day, hour=hour, minute=minute, timezone=tz)
            
            else:
                logger.error(f"Unknown schedule type: {schedule_type}")
                return
            
            # Add job to scheduler
            job = self.scheduler.add_job(
                func=self._execute_scheduled_flow,
                trigger=trigger,
                args=[tenant_id, schema_name, flow_id],
                id=job_id,
                name=f"Flow: {flow.flow_name}",
                misfire_grace_time=300  # 5 minutes grace time
            )
            
            self.active_jobs[job_id] = job.id
            logger.info(f"Scheduled flow {flow_id} for tenant {tenant_id}")
            
            # Execute immediately on first schedule (if not a specific time-based schedule)
            # Don't execute immediately for time-specific schedules (daily, weekly, monthly)
            # Check trigger_config for execute_immediately flag (default to True if not specified)
            should_execute_immediately = trigger_config.get('execute_immediately', True)
            if execute_immediately and should_execute_immediately and schedule_type in ['interval', 'cron']:
                logger.info(f"Executing flow {flow_id} immediately on schedule activation")
                # Run the flow immediately in the background
                asyncio.create_task(self._execute_scheduled_flow(tenant_id, schema_name, flow_id))
        
        except Exception as e:
            logger.error(f"Failed to schedule flow {flow_id}: {str(e)}")
            raise  # Re-raise the exception so it can be caught by the caller
    
    async def unschedule_flow(self, tenant_id: str, flow_id: str):
        """Remove a flow from the schedule."""
        job_id = f"{tenant_id}_{flow_id}"
        
        if job_id in self.active_jobs:
            try:
                self.scheduler.remove_job(self.active_jobs[job_id])
                del self.active_jobs[job_id]
                logger.info(f"Unscheduled flow {flow_id} for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to unschedule flow {flow_id}: {str(e)}")
    
    @staticmethod
    def _schedule_timezone(schedule_config: Dict[str, Any], trigger_config: Dict[str, Any],
                           flow_id: str):
        """The IANA zone a schedule names (`schedule.timezone`, else the
        trigger's), or None for the server's zone. An unknown name is logged
        and ignored rather than failing the whole schedule."""
        name = (schedule_config.get('timezone') or trigger_config.get('timezone') or '').strip()
        if not name:
            return None
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception as e:  # noqa: BLE001 — ZoneInfoNotFoundError / bad key
            logger.warning(f"Flow {flow_id}: unknown schedule timezone {name!r} ({e}); "
                           f"using the server's timezone")
            return None

    def _build_cron_trigger(self, schedule_config: Dict[str, Any], tz=None) -> CronTrigger:
        """Build a cron trigger from individual configuration fields."""
        return CronTrigger(
            minute=schedule_config.get('minute', '*'),
            hour=schedule_config.get('hour', '*'),
            day=schedule_config.get('day', '*'),
            month=schedule_config.get('month', '*'),
            day_of_week=schedule_config.get('day_of_week', '*'),
            timezone=tz
        )
    
    async def _execute_scheduled_flow(self, tenant_id: str, schema_name: str, flow_id: str):
        """Execute a scheduled flow with distributed lock for deduplication."""
        try:
            logger.info(f"Executing scheduled flow {flow_id} for tenant {tenant_id} in schema {schema_name}")

            # Check if flow is still active in database before execution
            # This handles multi-worker scenarios where a non-leader worker may have deactivated the flow
            with get_tenant_db(schema_name) as tenant_db:
                flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()

                if not flow:
                    logger.warning(f"Flow {flow_id} not found in database, unscheduling")
                    await self.unschedule_flow(tenant_id, flow_id)
                    return

                if flow.status != FlowStatus.ACTIVE:
                    logger.info(f"Flow {flow_id} is not active (status: {flow.status.value}), skipping execution and unscheduling")
                    await self.unschedule_flow(tenant_id, flow_id)
                    return

            # Create trigger data with schedule information
            trigger_data = {
                'triggered_at': datetime.utcnow().isoformat(),
                'trigger_source': 'scheduler'
            }

            # If lock manager is available, use it for deduplication
            if self.lock_manager:
                from services.distributed_lock import DistributedLockManager

                # Generate unique lock key for this execution
                lock_key = DistributedLockManager.get_execution_lock_key(
                    flow_id,
                    trigger_data
                )

                # Try to acquire lock (don't retry, skip if already processing)
                acquired = await self.lock_manager.acquire_lock(
                    lock_key,
                    ttl=300,  # 5 minutes should be enough for most flows
                    retry_count=0
                )

                if acquired:
                    try:
                        # Execute the flow
                        engine = ExecutionEngine(schema_name, tenant_id)
                        try:
                            await engine.execute_flow(
                                flow_id=flow_id,
                                trigger_data=trigger_data,
                                trigger_type='schedule'
                            )
                        finally:
                            await engine.close()
                    finally:
                        # Release lock after execution
                        await self.lock_manager.release_lock(lock_key)
                else:
                    # Another worker is already executing this scheduled flow
                    logger.debug(
                        f"Skipping duplicate execution for scheduled flow {flow_id}, "
                        f"already being processed by another worker"
                    )
            else:
                # Fallback to direct execution (backward compatibility)
                engine = ExecutionEngine(schema_name, tenant_id)
                try:
                    await engine.execute_flow(
                        flow_id=flow_id,
                        trigger_data=trigger_data,
                        trigger_type='schedule'
                    )
                finally:
                    await engine.close()

        except Exception as e:
            logger.error(f"Failed to execute scheduled flow {flow_id}: {str(e)}")
    
    def get_next_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get information about upcoming scheduled runs."""
        next_runs = []

        for job in self.scheduler.get_jobs():
            if job.next_run_time:
                flow_info = {
                    'job_id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat(),
                    'trigger': str(job.trigger)
                }
                next_runs.append(flow_info)

        # Sort by next run time and limit
        next_runs.sort(key=lambda x: x['next_run'])
        return next_runs[:limit]

    async def _periodic_sync(self):
        """
        Periodically sync schedules from database.
        This handles multi-worker scenarios where API calls to activate/deactivate
        flows may go to non-leader workers.
        """
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                logger.debug("Performing periodic schedule sync")
                await self.reload_all_schedules()
            except asyncio.CancelledError:
                logger.debug("Periodic sync task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic schedule sync: {str(e)}")
                # Continue despite errors

# Global scheduler instance
flow_scheduler = FlowScheduler()