"""
Generic Polling Service for IOFlow
Allows any API service to be used as a polling event source
"""
import asyncio
import logging
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from db.database import get_db_context, get_tenant_db
from db.models import Flow, FlowStatus, User
from db.application_models import (
    ApplicationSubscription, 
    ApplicationEvent,
    Application,
    ApplicationService
)
from db.polling_models import PollingState
from services.execution_engine import ExecutionEngine
from services.service_executors import ServiceExecutor
from core.config import settings
from api.flows import get_tenant_schema

logger = logging.getLogger(__name__)


class ChangeDetectionStrategy:
    """Base class for change detection strategies"""
    
    @staticmethod
    def detect_changes(new_data: Any, polling_state: PollingState, config: Dict) -> List[Dict]:
        """Detect changes in the data"""
        raise NotImplementedError


class NewItemsStrategy(ChangeDetectionStrategy):
    """Detect new items based on an identifier field"""
    
    @staticmethod
    def detect_changes(new_data: Any, polling_state: PollingState, config: Dict) -> List[Dict]:
        """Detect new items that haven't been processed before"""
        identifier_field = config.get('identifier_field', 'id')
        
        # Handle different response structures
        if isinstance(new_data, dict):
            # Check for common API response patterns
            if 'messages' in new_data:
                items = new_data['messages']
            elif 'items' in new_data:
                items = new_data['items']
            elif 'data' in new_data and isinstance(new_data['data'], list):
                items = new_data['data']
            elif 'results' in new_data:
                items = new_data['results']
            else:
                # Treat the dict as a single item
                items = [new_data]
        elif isinstance(new_data, list):
            items = new_data
        else:
            items = []
        
        new_items = []
        
        for item in items:
            if isinstance(item, dict):
                item_id = item.get(identifier_field)
                if item_id and not polling_state.has_processed_item(item_id):
                    new_items.append(item)
        
        return new_items


class ModifiedSinceStrategy(ChangeDetectionStrategy):
    """Detect items modified since last poll"""
    
    @staticmethod
    def detect_changes(new_data: Any, polling_state: PollingState, config: Dict) -> List[Dict]:
        """Detect items modified since last poll timestamp"""
        timestamp_field = config.get('timestamp_field', 'updated_at')
        last_timestamp = polling_state.get_state_value('last_timestamp')
        
        items = new_data if isinstance(new_data, list) else [new_data]
        modified_items = []
        max_timestamp = last_timestamp
        
        for item in items:
            if isinstance(item, dict):
                item_timestamp = item.get(timestamp_field)
                if item_timestamp:
                    # Convert to comparable format if needed
                    if isinstance(item_timestamp, str):
                        try:
                            item_timestamp = datetime.fromisoformat(item_timestamp.replace('Z', '+00:00'))
                        except:
                            pass
                    
                    if not last_timestamp or item_timestamp > last_timestamp:
                        modified_items.append(item)
                        if not max_timestamp or item_timestamp > max_timestamp:
                            max_timestamp = item_timestamp
        
        # Update state with new max timestamp
        if max_timestamp != last_timestamp:
            polling_state.update_state({'last_timestamp': max_timestamp})
        
        return modified_items


class HashComparisonStrategy(ChangeDetectionStrategy):
    """Detect changes by comparing content hash"""
    
    @staticmethod
    def detect_changes(new_data: Any, polling_state: PollingState, config: Dict) -> List[Dict]:
        """Detect changes by comparing hash of the data"""
        # Calculate hash of new data
        data_str = json.dumps(new_data, sort_keys=True)
        new_hash = hashlib.sha256(data_str.encode()).hexdigest()
        
        last_hash = polling_state.get_state_value('last_hash')
        
        if last_hash != new_hash:
            polling_state.update_state({'last_hash': new_hash})
            return new_data if isinstance(new_data, list) else [new_data]
        
        return []


class CountChangeStrategy(ChangeDetectionStrategy):
    """Detect when count of items changes"""
    
    @staticmethod
    def detect_changes(new_data: Any, polling_state: PollingState, config: Dict) -> List[Dict]:
        """Detect when the count of items changes"""
        items = new_data if isinstance(new_data, list) else [new_data]
        new_count = len(items)
        
        last_count = polling_state.get_state_value('last_count', 0)
        
        if new_count != last_count:
            polling_state.update_state({'last_count': new_count})
            # Return only the difference (new items if count increased)
            if new_count > last_count:
                return items[last_count:] if isinstance(new_data, list) else items
        
        return []


class ServicePollingService:
    """Service to handle application service-based polling with OAuth/API authentication"""

    STRATEGY_MAP = {
        'new_items': NewItemsStrategy,
        'modified_since': ModifiedSinceStrategy,
        'hash_comparison': HashComparisonStrategy,
        'count_change': CountChangeStrategy,
    }

    def __init__(self):
        self.polling_tasks: Dict[str, asyncio.Task] = {}
        self.execution_engine = ExecutionEngine
        self.service_executor = None  # Will be initialized per service call
        self.running = False
        self.http_client = None
        self.lock_manager = None  # Will be injected by BackgroundServiceManager
        
    async def start(self):
        """Start the service polling service"""
        logger.info("Starting service polling service...")
        self.running = True
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Start monitoring task (will load flows on first iteration)
        # We don't load flows immediately to allow lock_manager to be injected
        asyncio.create_task(self._monitor_flows())

        logger.info("Service polling service started")
        
    async def stop(self):
        """Stop the polling service"""
        logger.info("Stopping service polling service...")
        self.running = False
        
        # Cancel all polling tasks
        for task_id, task in self.polling_tasks.items():
            task.cancel()
            
        self.polling_tasks.clear()
        
        if self.http_client:
            await self.http_client.aclose()
            
        logger.info("Service polling service stopped")
        
    async def _monitor_flows(self):
        """Monitor for changes in flows and update polling tasks"""
        # Small delay to ensure lock_manager is injected by BackgroundServiceManager
        await asyncio.sleep(0.1)

        while self.running:
            try:
                await self._load_polling_flows()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in flow monitor: {str(e)}")
                await asyncio.sleep(60)
                
    async def _load_polling_flows(self):
        """Load all active flows with polling triggers"""
        try:
            with get_db_context() as db:
                # Get all tenants
                from sqlalchemy import text
                tenants = db.execute(
                    text("SELECT DISTINCT tenant_id FROM users WHERE tenant_id IS NOT NULL")
                ).fetchall()
                
                for tenant_row in tenants:
                    tenant_id = tenant_row[0]
                    await self._load_tenant_polling_flows(db, tenant_id)
                    
        except Exception as e:
            logger.error(f"Error loading polling flows: {str(e)}")
            
    async def _load_tenant_polling_flows(self, db: Session, tenant_id: str):
        """Load polling flows for a specific tenant"""
        try:
            # Get a user from this tenant to get schema
            user = db.query(User).filter(User.tenant_id == tenant_id).first()
            if not user:
                return

            schema_name = get_tenant_schema(user, db)

            with get_tenant_db(schema_name) as tenant_db:
                # Get active flows for this specific tenant
                # In SQLite mode, we need to filter by tenant_id since all tenants share the same DB
                # In PostgreSQL mode, each tenant has its own schema, so no tenant_id filter needed
                from core.config import settings

                if settings.database_url.startswith('sqlite'):
                    # SQLite: All tenants in same DB, filter by tenant_id
                    flows = tenant_db.query(Flow).filter(
                        and_(
                            Flow.status == FlowStatus.ACTIVE,
                            Flow.tenant_id == tenant_id  # Filter by tenant_id to avoid cross-tenant pollution
                        )
                    ).all()
                else:
                    # PostgreSQL/Other: Each tenant has its own schema, no tenant_id filter needed
                    flows = tenant_db.query(Flow).filter(
                        Flow.status == FlowStatus.ACTIVE
                    ).all()

                # Track flows we've already processed to avoid duplicates
                processed_flows = set()

                for flow in flows:
                    trigger_config = flow.trigger_config or {}

                    # Check if this is an application event trigger with polling
                    # Match the execution engine: type == 'event' means application event
                    if trigger_config.get('type') == 'event':
                        app_id = trigger_config.get('app_id')
                        event_name = trigger_config.get('event_name')

                        if app_id and event_name:
                            # Create a unique identifier for this flow
                            flow_key = f"{flow.flow_id}:{app_id}:{event_name}"

                            # Skip if we've already processed this flow in this load cycle
                            if flow_key in processed_flows:
                                continue
                            processed_flows.add(flow_key)

                            # Check if this event is a polling event
                            # In SQLite, application events are in the same database
                            event = tenant_db.query(ApplicationEvent).filter(
                                and_(
                                    ApplicationEvent.app_id == app_id,
                                    ApplicationEvent.event_name == event_name,
                                    ApplicationEvent.event_type == 'polling'
                                )
                            ).first()

                            if event:
                                task_id = f"{tenant_id}:{flow.flow_id}:{app_id}:{event_name}"

                                # Check if task already exists and is running
                                if task_id in self.polling_tasks:
                                    if not self.polling_tasks[task_id].done():
                                        logger.debug(f"Polling task already running for flow {flow.flow_name}")
                                        continue

                                # Use a lock to prevent duplicate task creation during startup
                                # This prevents race conditions when multiple threads check at the same time
                                task_lock_key = f"polling_task:{task_id}"

                                # Try to acquire lock for creating this specific polling task
                                if self.lock_manager:
                                    from services.distributed_lock import DistributedLockManager
                                    acquired = await self.lock_manager.acquire_lock(
                                        task_lock_key,
                                        ttl=10,  # Short TTL just for task creation
                                        retry_count=0  # Don't retry - if someone else is creating it, skip
                                    )

                                    if not acquired:
                                        logger.debug(f"Another worker is creating polling task for flow {flow.flow_name}")
                                        continue

                                    try:
                                        # Double-check after acquiring lock
                                        if task_id in self.polling_tasks and not self.polling_tasks[task_id].done():
                                            logger.debug(f"Polling task already running for flow {flow.flow_name} (after lock)")
                                            continue

                                        # Create new polling task
                                        logger.info(f"Creating polling task for flow {flow.flow_name} (ID: {flow.flow_id})")
                                        task = asyncio.create_task(
                                            self._poll_flow(tenant_id, schema_name, flow, event)
                                        )
                                        self.polling_tasks[task_id] = task
                                        logger.info(f"Started polling task for flow {flow.flow_name}")
                                    finally:
                                        # Release the lock after task creation
                                        await self.lock_manager.release_lock(task_lock_key)
                                else:
                                    # Fallback if no lock manager (shouldn't happen but safety)
                                    # Create new polling task
                                    logger.info(f"Creating polling task for flow {flow.flow_name} (ID: {flow.flow_id})")
                                    task = asyncio.create_task(
                                        self._poll_flow(tenant_id, schema_name, flow, event)
                                    )
                                    self.polling_tasks[task_id] = task
                                    logger.info(f"Started polling task for flow {flow.flow_name}")
                    
        except Exception as e:
            logger.error(f"Error loading tenant polling flows: {str(e)}")
            
    async def _poll_flow(
        self, 
        tenant_id: str, 
        schema_name: str, 
        flow: Flow, 
        event: ApplicationEvent
    ):
        """Poll for a specific flow"""
        task_id = f"{tenant_id}:{flow.flow_id}:{event.app_id}:{event.event_name}"
        logger.info(f"Starting polling for flow {flow.flow_name} with event {event.event_name}")
        
        try:
            # Get event configuration
            # Handle case where event_configuration might be a JSON string (SQLite)
            event_config = event.event_configuration
            if isinstance(event_config, str):
                import json
                event_config = json.loads(event_config)
            event_config = self._normalize_event_config(event_config or {})
            # Seed applications declare the interval as `interval_seconds`; older
            # events used `polling_interval`. Default 5 minutes.
            polling_interval = int(
                event_config.get('polling_interval')
                or event_config.get('interval_seconds')
                or 300
            )
            polling_service = event_config.get('polling_service')
            
            # Layer 1: Event default parameters
            polling_parameters = event_config.get('polling_parameters', {})
            
            # Layer 2: Flow-specific overrides from trigger_config
            # Handle case where trigger_config might be a JSON string (SQLite)
            trigger_config = flow.trigger_config
            if isinstance(trigger_config, str):
                import json
                trigger_config = json.loads(trigger_config)
            flow_overrides = trigger_config.get('polling_overrides', {}) if trigger_config else {}
            if flow_overrides:
                logger.info(f"Applying flow overrides: {flow_overrides}")
                polling_parameters = self._merge_parameters(polling_parameters, flow_overrides)
            
            change_detection = event_config.get('change_detection', {})
            # Optional: follow the API's "next page" token inside one poll, so a
            # burst larger than one page is not silently dropped.
            #   {"token_path": "meta.next_token", "param": "next_token",
            #    "max_pages": 5}
            pagination = event_config.get('pagination') or {}
            
            if not polling_service:
                logger.error(f"No polling service configured for event {event.event_name}")
                return
            
            # Get or create polling state
            polling_state = await self._get_or_create_polling_state(
                tenant_id, flow.flow_id, event.app_id, event.event_name
            )
            
            while self.running and task_id in self.polling_tasks:
                try:
                    # Execute the polling service
                    poll_result = await self._execute_polling_service(
                        tenant_id,
                        event.app_id,
                        polling_service,
                        polling_parameters,
                        polling_state,
                        flow,
                        event
                    )
                    
                    if poll_result and poll_result.get('success', True) and pagination:
                        poll_result = await self._follow_pages(
                            poll_result, pagination, tenant_id, event.app_id,
                            polling_service, polling_parameters, polling_state,
                            flow, event)

                    if poll_result and poll_result.get('success', True):
                        # Log the poll result for debugging
                        logger.info(f"Poll result for {flow.flow_name}: {type(poll_result)}, Keys: {poll_result.keys() if isinstance(poll_result, dict) else 'Not a dict'}")
                        
                        # Extract data from poll result
                        poll_data = poll_result.get('data') if 'data' in poll_result else poll_result
                        logger.info(f"Poll data type: {type(poll_data)}, Has messages: {'messages' in poll_data if isinstance(poll_data, dict) else False}")
                        
                        # Detect changes
                        changes = await self._detect_changes(
                            poll_data,
                            polling_state,
                            change_detection
                        )
                        
                        # Remember the newest id seen, so the next poll asks only
                        # for what came after it (the `since_id` the executor
                        # already injects from state `last_id`).
                        self._advance_cursor(poll_data, polling_state, change_detection)

                        if changes:
                            logger.info(f"Detected {len(changes)} changes for flow {flow.flow_name}")
                            
                            if change_detection.get('dispatch') == 'batch':
                                # One flow run per batch of new items, carrying the
                                # response's side data (e.g. X `includes.users`,
                                # where an author's location lives) — so a flow can
                                # classify and bulk-write many items in one go.
                                for batch in self._batches(changes, change_detection):
                                    await self._trigger_flow_execution(
                                        tenant_id,
                                        schema_name,
                                        flow,
                                        self._batch_payload(batch, poll_data)
                                    )
                            else:
                                # Trigger flow execution for each change
                                for change_data in changes:
                                    await self._trigger_flow_execution(
                                        tenant_id,
                                        schema_name,
                                        flow,
                                        change_data
                                    )
                            
                            # Update processed items
                            if change_detection.get('method') == 'new_items':
                                identifier_field = change_detection.get('identifier_field', 'id')
                                item_ids = [
                                    item.get(identifier_field) 
                                    for item in changes 
                                    if item.get(identifier_field)
                                ]
                                if item_ids:
                                    polling_state.add_processed_items(item_ids)
                            
                            # Reset error count on success
                            polling_state.reset_error_count()
                            
                            # Save state
                            await self._save_polling_state(polling_state)
                        elif change_detection.get('cursor_field'):
                            # No new items, but the cursor may still have moved.
                            await self._save_polling_state(polling_state)
                    else:
                        # Record error
                        error_msg = poll_result.get('error', 'Unknown error') if poll_result else 'Service execution failed'
                        polling_state.record_error(error_msg)
                        await self._save_polling_state(polling_state)
                        
                        # Implement exponential backoff for errors
                        if polling_state.consecutive_errors > 3:
                            await asyncio.sleep(min(polling_interval * 2, 3600))  # Max 1 hour
                        
                except Exception as e:
                    logger.error(f"Error polling flow {flow.flow_id}: {str(e)}")
                    polling_state.record_error(str(e))
                    await self._save_polling_state(polling_state)
                    
                # Wait for next poll
                await asyncio.sleep(polling_interval)
                
        except Exception as e:
            logger.error(f"Fatal error in polling task for flow {flow.flow_id}: {str(e)}")
        finally:
            # Remove task from tracking
            if task_id in self.polling_tasks:
                del self.polling_tasks[task_id]
                
    async def _execute_polling_service(
        self,
        tenant_id: str,
        app_id: str,
        service_name: str,
        parameters: Dict,
        polling_state: PollingState,
        flow: Flow = None,
        event: ApplicationEvent = None
    ) -> Dict:
        """Execute the polling service with enhanced parameter handling"""
        try:
            with get_db_context() as db:
                # Get the service - application tables are in master DB for SQLite
                service = db.query(ApplicationService).filter(
                    and_(
                        ApplicationService.app_id == app_id,
                        ApplicationService.service_name == service_name
                    )
                ).first()
                
                if not service:
                    return {'success': False, 'error': f'Service {service_name} not found'}
                
                # Get subscription - also in master DB for SQLite
                subscription = db.query(ApplicationSubscription).filter(
                    and_(
                        ApplicationSubscription.tenant_id == tenant_id,
                        ApplicationSubscription.app_id == app_id,
                        ApplicationSubscription.status == 'active'
                    )
                ).first()
                
                if not subscription:
                    # Log more details for debugging
                    logger.error(f"No active subscription found - tenant_id: {tenant_id}, app_id: {app_id}")
                    # Check if any subscription exists at all
                    any_sub = db.query(ApplicationSubscription).filter(
                        and_(
                            ApplicationSubscription.app_id == app_id,
                            ApplicationSubscription.tenant_id == tenant_id
                        )
                    ).first()
                    if any_sub:
                        logger.error(f"Found subscription but status is: {any_sub.status}")
                    return {'success': False, 'error': 'No active subscription'}
                
                # Layer 3: Add dynamic state-based parameters
                enhanced_params = parameters.copy()
                
                # Add timestamp for modified_since strategy
                if polling_state.last_poll_timestamp:
                    enhanced_params['since'] = polling_state.last_poll_timestamp.isoformat()
                    enhanced_params['modified_since'] = polling_state.last_poll_timestamp.isoformat()
                    enhanced_params['last_poll_timestamp'] = polling_state.last_poll_timestamp.isoformat()
                
                # Add last processed ID if available
                last_id = polling_state.get_state_value('last_id')
                if last_id:
                    enhanced_params['after_id'] = last_id
                    enhanced_params['since_id'] = last_id
                
                # Add pagination support
                next_page = polling_state.get_state_value('next_page')
                if next_page:
                    enhanced_params['page'] = next_page
                    enhanced_params['page_token'] = next_page
                
                # Apply parameter mapping if configured
                if event and event.event_configuration:
                    # Handle case where event_configuration might be a JSON string (SQLite)
                    event_config = event.event_configuration
                    if isinstance(event_config, str):
                        import json
                        event_config = json.loads(event_config)
                    param_mapping = event_config.get('parameter_mapping', {})
                    enhanced_params = self._apply_parameter_mapping(
                        enhanced_params, param_mapping, polling_state, flow
                    )
                
                # Resolve any template variables
                enhanced_params = self._resolve_templates(enhanced_params, {
                    'state': polling_state.last_poll_state or {},
                    'flow': {'id': flow.flow_id, 'name': flow.flow_name} if flow else {},
                    'last_poll': polling_state.last_poll_timestamp.isoformat() if polling_state.last_poll_timestamp else None
                })
                
                logger.debug(f"Final polling parameters: {enhanced_params}")
                
                # Execute the service using ExecutionEngine
                # Get user for this tenant
                from db.models import User
                user = db.query(User).filter(User.tenant_id == tenant_id).first()
                if not user:
                    return {'success': False, 'error': 'No user found for tenant'}
                
                # Use ExecutionEngine to execute the service
                from api.flows import get_tenant_schema
                schema_name = get_tenant_schema(user, db)
                
                # Create a minimal context for service execution
                execution_context = {
                    'execution_id': f"poll_{flow.flow_id if flow else 'manual'}_{datetime.utcnow().isoformat()}",
                    'trigger_data': enhanced_params,
                    'is_polling': True
                }
                
                # Use the execution engine's service execution method
                engine = self.execution_engine(user, tenant_id, schema_name)
                result = await engine._execute_service_with_type(
                    service_obj=service,
                    subscription=subscription,
                    parameters=enhanced_params,
                    context=execution_context,
                    is_simulation=False
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Error executing polling service: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _normalize_event_config(cfg: Dict) -> Dict:
        """Accept the older polling-event shape as well as the current one.

        The event guide used to describe `service_name` / `service_params` /
        `comparison_field` / `comparison_type`, and seed applications were
        written that way, but this poller reads `polling_service` /
        `polling_parameters` / `change_detection` — so those events never
        fired. Map the old keys onto the new ones; a current key always wins."""
        if not isinstance(cfg, dict):
            return {}
        out = dict(cfg)
        if not out.get('polling_service') and out.get('service_name'):
            out['polling_service'] = out['service_name']
        if 'polling_parameters' not in out and isinstance(out.get('service_params'), dict):
            out['polling_parameters'] = out['service_params']
        if 'change_detection' not in out and (out.get('comparison_field')
                                              or out.get('comparison_type')):
            out['change_detection'] = {
                'method': out.get('comparison_type') or 'new_items',
                'identifier_field': out.get('comparison_field') or 'id',
            }
        return out

    @staticmethod
    def _page_items(page: Any) -> Optional[list]:
        """The list of items inside one page of a polling response (the same
        shapes NewItemsStrategy understands), or None."""
        if isinstance(page, list):
            return page
        if isinstance(page, dict):
            for key in ('data', 'items', 'results', 'messages'):
                if isinstance(page.get(key), list):
                    return page[key]
        return None

    async def _follow_pages(self, poll_result: Dict, pagination: Dict,
                            tenant_id: str, app_id: str, polling_service: str,
                            polling_parameters: Dict, polling_state: PollingState,
                            flow: Flow, event: ApplicationEvent) -> Dict:
        """Fetch the following pages of one poll and merge them into the first.

        Items lists are concatenated, and so are the lists inside an
        `includes`-style side object (X returns each page's authors there).
        A page that fails ends the walk; what was already fetched is kept."""
        token_path = [p for p in str(pagination.get('token_path') or '').split('.') if p]
        param = pagination.get('param')
        try:
            max_pages = max(1, int(pagination.get('max_pages') or 1))
        except (TypeError, ValueError):
            max_pages = 1
        if not token_path or not param or max_pages <= 1:
            return poll_result

        merged = poll_result.get('data') if 'data' in poll_result else poll_result
        if not isinstance(merged, dict) or self._page_items(merged) is None:
            return poll_result
        page = merged
        for page_no in range(2, max_pages + 1):
            token = self._get_nested_value(page, token_path) if isinstance(page, dict) else None
            if not token:
                break
            params = dict(polling_parameters or {})
            params[param] = token
            try:
                result = await self._execute_polling_service(
                    tenant_id, app_id, polling_service, params,
                    polling_state, flow, event)
            except Exception as e:  # noqa: BLE001 — keep what we have
                logger.warning(f"Polling page {page_no} failed for {polling_service}: {e}")
                break
            if not result or not result.get('success', True):
                logger.warning(f"Polling page {page_no} failed for {polling_service}: "
                               f"{(result or {}).get('error')}")
                break
            page = result.get('data') if 'data' in result else result
            items = self._page_items(page)
            if not items:
                break
            self._page_items(merged).extend(items)
            side = page.get('includes') if isinstance(page, dict) else None
            if isinstance(side, dict):
                acc = merged.setdefault('includes', {})
                for key, values in side.items():
                    if isinstance(values, list):
                        acc.setdefault(key, [])
                        if isinstance(acc[key], list):
                            acc[key].extend(values)
        logger.info(f"Polling {polling_service}: merged pages, "
                    f"{len(self._page_items(merged) or [])} items")
        if 'data' in poll_result:
            poll_result = dict(poll_result)
            poll_result['data'] = merged
            return poll_result
        return merged

    def _advance_cursor(self, poll_data: Any, polling_state: PollingState,
                        change_detection: Dict) -> None:
        """Store the highest `cursor_field` value seen as state `last_id`.

        Opt-in (`change_detection.cursor_field`), because only an API whose ids
        grow monotonically (X tweet ids) can be asked "since this id"."""
        field = change_detection.get('cursor_field')
        if not field:
            return
        items = self._page_items(poll_data) or []
        best = polling_state.get_state_value('last_id')
        for item in items:
            if not isinstance(item, dict) or item.get(field) in (None, ''):
                continue
            value = str(item.get(field))
            try:
                if best is None or int(value) > int(best):
                    best = value
            except (TypeError, ValueError):
                logger.debug(f"cursor_field {field!r} is not numeric: {value!r}")
                return
        if best is not None and best != polling_state.get_state_value('last_id'):
            # Assign a new dict: an in-place change to the JSON column is not
            # tracked by the ORM and would never be saved.
            polling_state.last_poll_state = {**(polling_state.last_poll_state or {}),
                                             'last_id': best}

    @staticmethod
    def _batches(changes: List[Dict], change_detection: Dict) -> List[List[Dict]]:
        try:
            size = int(change_detection.get('batch_size') or 0)
        except (TypeError, ValueError):
            size = 0
        if size <= 0:
            return [changes]
        return [changes[i:i + size] for i in range(0, len(changes), size)]

    def _batch_payload(self, batch: List[Dict], poll_data: Any) -> Dict:
        payload: Dict[str, Any] = {'items': batch, 'count': len(batch)}
        if isinstance(poll_data, dict):
            for key in ('includes', 'meta'):
                if key in poll_data:
                    payload[key] = poll_data[key]
        return payload

    async def _detect_changes(
        self,
        new_data: Any,
        polling_state: PollingState,
        config: Dict
    ) -> List[Dict]:
        """Detect changes based on configured strategy"""
        method = config.get('method', 'new_items')
        
        # Get the appropriate strategy
        strategy_class = self.STRATEGY_MAP.get(method)
        
        if not strategy_class:
            logger.warning(f"Unknown change detection method: {method}, using new_items")
            strategy_class = NewItemsStrategy
        
        # Detect changes
        changes = strategy_class.detect_changes(new_data, polling_state, config)
        
        return changes
    
    async def _get_or_create_polling_state(
        self,
        tenant_id: str,
        flow_id: str,
        app_id: str,
        event_name: str
    ) -> PollingState:
        """Get or create polling state for a flow/event combination"""
        with get_db_context() as db:
            state = db.query(PollingState).filter(
                and_(
                    PollingState.flow_id == flow_id,
                    PollingState.app_id == app_id,
                    PollingState.event_name == event_name
                )
            ).first()
            
            if not state:
                state = PollingState(
                    flow_id=flow_id,
                    app_id=app_id,
                    event_name=event_name,
                    tenant_id=tenant_id,
                    last_poll_state={},
                    items_processed=[]
                )
                db.add(state)
                db.commit()
            
            return state
    
    async def _save_polling_state(self, polling_state: PollingState):
        """Save polling state to database"""
        try:
            with get_db_context() as db:
                # Merge the state object to ensure it's attached to this session
                db.merge(polling_state)
                db.commit()
        except Exception as e:
            logger.error(f"Error saving polling state: {str(e)}")
    
    async def _trigger_flow_execution(
        self,
        tenant_id: str,
        schema_name: str,
        flow: Flow,
        trigger_data: Dict
    ):
        """Trigger flow execution with the polling data and distributed lock for deduplication"""
        try:
            # Use distributed lock if available to prevent duplicate execution
            if self.lock_manager:
                from services.distributed_lock import DistributedLockManager

                # Generate unique lock key for this polling data
                lock_key = DistributedLockManager.get_execution_lock_key(
                    flow.flow_id,
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
                        # Execute the flow - pass required parameters to ExecutionEngine
                        engine = self.execution_engine(
                            tenant_schema=schema_name,
                            tenant_id=tenant_id
                        )
                        await engine.execute_flow(
                            flow_id=flow.flow_id,
                            trigger_data=trigger_data,
                            trigger_type='polling'
                        )
                    finally:
                        # Release lock after execution
                        await self.lock_manager.release_lock(lock_key)
                else:
                    # Another worker is already processing this data
                    logger.debug(
                        f"Skipping duplicate execution for flow {flow.flow_id}, "
                        f"polling data already being processed by another worker"
                    )
            else:
                # Fallback to direct execution (backward compatibility)
                engine = self.execution_engine(
                    tenant_schema=schema_name,
                    tenant_id=tenant_id
                )
                await engine.execute_flow(
                    flow_id=flow.flow_id,
                    trigger_data=trigger_data,
                    trigger_type='polling'
                )

        except Exception as e:
            logger.error(f"Error triggering flow execution: {str(e)}")
    
    def _merge_parameters(self, base_params: Dict, overrides: Dict) -> Dict:
        """Merge parameter dictionaries, with overrides taking precedence"""
        result = base_params.copy()
        
        for key, value in overrides.items():
            if value is None:
                # None value means remove the parameter
                result.pop(key, None)
            else:
                result[key] = value
        
        return result
    
    def _apply_parameter_mapping(
        self,
        params: Dict,
        mapping: Dict,
        polling_state: PollingState,
        flow: Flow
    ) -> Dict:
        """Apply parameter mapping configuration"""
        result = params.copy()
        
        # Apply state field mappings
        state_fields = mapping.get('state_fields', {})
        for param_name, state_key in state_fields.items():
            state_value = polling_state.get_state_value(state_key)
            if state_value is not None:
                result[param_name] = state_value
        
        # Apply computed fields
        computed_fields = mapping.get('computed_fields', {})
        for param_name, computation in computed_fields.items():
            if computation == 'current_timestamp':
                result[param_name] = datetime.utcnow().isoformat()
            elif computation == 'flow_id':
                result[param_name] = flow.flow_id if flow else None
            # Add more computed field types as needed
        
        return result
    
    def _resolve_templates(self, params: Dict, context: Dict) -> Dict:
        """Resolve template variables in parameter values
        
        Supports {{variable.path}} syntax for nested values
        Example: {{state.last_id}} or {{flow.name}}
        """
        result = {}
        
        for key, value in params.items():
            if isinstance(value, str):
                # Find all template variables
                template_pattern = r'\{\{([^}]+)\}\}'
                matches = re.findall(template_pattern, value)
                
                resolved_value = value
                for match in matches:
                    # Handle the entire match including || operator
                    if '||' in match:
                        # Split by || to handle defaults
                        parts = match.split('||')
                        primary = parts[0].strip()
                        default = parts[1].strip().strip("'\"")
                        
                        # Try to resolve the primary path
                        path_parts = primary.split('.')
                        replacement = self._get_nested_value(context, path_parts)
                        
                        # Use default if primary is None
                        if replacement is None:
                            replacement = default
                    else:
                        # Parse the variable path (e.g., "state.last_id")
                        path_parts = match.strip().split('.')
                        replacement = self._get_nested_value(context, path_parts)
                    
                    if replacement is not None:
                        # Replace the template with the actual value
                        resolved_value = resolved_value.replace(
                            f'{{{{{match}}}}}',
                            str(replacement)
                        )
                
                # Check if entire value was a template and resolve to proper type
                if len(matches) == 1 and value.strip() == f'{{{{{matches[0]}}}}}':
                    # Entire value is a single template, preserve type
                    if '||' in matches[0]:
                        parts = matches[0].split('||')
                        primary = parts[0].strip()
                        default = parts[1].strip().strip("'\"")
                        path_parts = primary.split('.')
                        replacement = self._get_nested_value(context, path_parts)
                        # Try to convert default to appropriate type
                        if replacement is None:
                            try:
                                # Try to parse as number
                                result[key] = int(default)
                            except ValueError:
                                try:
                                    result[key] = float(default)
                                except ValueError:
                                    result[key] = default
                        else:
                            result[key] = replacement
                    else:
                        result[key] = self._get_nested_value(context, matches[0].strip().split('.'))
                else:
                    result[key] = resolved_value
            elif isinstance(value, dict):
                # Recursively resolve nested dictionaries
                result[key] = self._resolve_templates(value, context)
            elif isinstance(value, list):
                # Resolve templates in list items
                result[key] = [
                    self._resolve_templates({'_': item}, context).get('_', item)
                    if isinstance(item, (str, dict)) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    def _get_nested_value(self, obj: Dict, path: List[str]) -> Any:
        """Get a nested value from an object using a path"""
        current = obj
        
        # First check if the entire path contains default syntax
        full_path = '.'.join(path)
        if '||' in full_path:
            parts = full_path.split('||')
            primary_path = parts[0].strip().split('.')
            default_value = parts[1].strip().strip("'\"")
            
            # Try to get the primary value
            temp_current = obj
            for part in primary_path:
                if temp_current is None or not isinstance(temp_current, dict):
                    return default_value
                temp_current = temp_current.get(part)
            
            # Return the found value or default
            return temp_current if temp_current is not None else default_value
        
        # Standard path resolution
        for part in path:
            if current is None:
                return None
            
            # Handle optional chaining (e.g., "user?.email")
            if part.endswith('?'):
                part = part[:-1]
                if not isinstance(current, dict) or part not in current:
                    return None
            
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current


# Global service polling instance
service_polling_service = ServicePollingService()

# Legacy alias for backward compatibility
GenericPollingService = ServicePollingService