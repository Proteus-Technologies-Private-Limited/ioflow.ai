"""
Polling Service for IOFlow
Periodically checks external APIs for changes and triggers flows
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_

from db.database import get_db_context, get_tenant_db
from db.models import Flow, FlowStatus
from db.application_models import (
    ApplicationSubscription, 
    ApplicationEvent,
    Application
)
from services.execution_engine import ExecutionEngine
from core.config import settings

logger = logging.getLogger(__name__)


class ApiPollingService:
    """Service to handle direct API polling triggers"""

    def __init__(self):
        self.polling_tasks: Dict[str, asyncio.Task] = {}
        self.execution_engine = ExecutionEngine  # Store the class, not an instance
        self.running = False
        self.http_client = None
        self.lock_manager = None  # Will be injected by BackgroundServiceManager
        
    async def start(self):
        """Start the polling service"""
        logger.info("Starting polling service...")
        self.running = True
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Load all active flows with polling triggers
        await self._load_polling_flows()
        
        # Start monitoring task
        asyncio.create_task(self._monitor_flows())
        
        logger.info("Polling service started")
        
    async def stop(self):
        """Stop the polling service"""
        logger.info("Stopping polling service...")
        self.running = False
        
        # Cancel all polling tasks
        for task_id, task in self.polling_tasks.items():
            task.cancel()
            
        self.polling_tasks.clear()
        
        if self.http_client:
            await self.http_client.aclose()
            
        logger.info("Polling service stopped")
        
    async def _monitor_flows(self):
        """Monitor for changes in flows and update polling tasks"""
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
                tenants = db.execute(text("SELECT DISTINCT tenant_id FROM users WHERE tenant_id IS NOT NULL")).fetchall()
                
                for tenant_row in tenants:
                    tenant_id = tenant_row[0]
                    await self._load_tenant_polling_flows(db, tenant_id)
                    
        except Exception as e:
            logger.error(f"Error loading polling flows: {str(e)}")
            
    async def _load_tenant_polling_flows(self, db: Session, tenant_id: str):
        """Load polling flows for a specific tenant"""
        try:
            # Get tenant schema
            from api.flows import get_tenant_schema
            from db.models import User
            
            # Get a user from this tenant to get schema
            user = db.query(User).filter(User.tenant_id == tenant_id).first()
            if not user:
                return
                
            schema_name = get_tenant_schema(user, db)
            
            with get_tenant_db(schema_name) as tenant_db:
                # Get active flows with polling triggers
                # First get all active flows, then filter by trigger type.
                # Flows live in the shared ioflow.flows table (models are
                # schema-qualified, so the tenant search_path does not isolate
                # them) — without the tenant_id filter every tenant's pass
                # would start a duplicate polling task for every flow.
                flows = tenant_db.query(Flow).filter(
                    Flow.tenant_id == tenant_id,
                    Flow.status == FlowStatus.ACTIVE
                ).all()
                
                # Filter flows with polling triggers
                flows = [f for f in flows if f.trigger_config and f.trigger_config.get('type') == 'polling']
                
                for flow in flows:
                    task_id = f"{tenant_id}:{flow.flow_id}"
                    
                    # Check if task already exists
                    if task_id in self.polling_tasks:
                        if not self.polling_tasks[task_id].done():
                            continue
                            
                    # Create new polling task
                    task = asyncio.create_task(
                        self._poll_flow(tenant_id, schema_name, flow)
                    )
                    self.polling_tasks[task_id] = task
                    
        except Exception as e:
            logger.error(f"Error loading tenant polling flows: {str(e)}")
            
    async def _poll_flow(self, tenant_id: str, schema_name: str, flow: Flow):
        """Poll for a specific flow"""
        task_id = f"{tenant_id}:{flow.flow_id}"
        logger.info(f"Starting polling for flow {flow.flow_name} (ID: {flow.flow_id})")
        
        try:
            trigger_config = flow.trigger_config
            app_id = trigger_config.get('app_id')
            event_name = trigger_config.get('event_name')
            poll_interval = trigger_config.get('poll_interval', 300)  # Default 5 minutes
            
            if not app_id or not event_name:
                logger.error(f"Invalid polling config for flow {flow.flow_id}")
                return
                
            # Get last poll state
            last_poll_state = await self._get_last_poll_state(flow.flow_id)
            
            while self.running and task_id in self.polling_tasks:
                try:
                    # Poll the external API
                    new_data = await self._poll_external_api(
                        tenant_id, app_id, event_name, last_poll_state
                    )
                    
                    if new_data:
                        # Process each item with deduplication lock if available
                        if self.lock_manager:
                            # Process with distributed lock for deduplication
                            await self._process_polled_data_with_lock(
                                tenant_id, flow, new_data
                            )
                        else:
                            # Fallback to direct execution (backward compatibility)
                            await self._trigger_flow_execution(
                                tenant_id, flow, new_data
                            )

                        # Update last poll state
                        last_poll_state = await self._update_poll_state(
                            flow.flow_id, new_data
                        )
                        
                except Exception as e:
                    logger.error(f"Error polling flow {flow.flow_id}: {str(e)}")
                    
                # Wait for next poll
                await asyncio.sleep(poll_interval)
                
        except Exception as e:
            logger.error(f"Fatal error in polling task for flow {flow.flow_id}: {str(e)}")
        finally:
            # Remove task from tracking
            if task_id in self.polling_tasks:
                del self.polling_tasks[task_id]
                
    async def _poll_external_api(
        self, 
        tenant_id: str, 
        app_id: str, 
        event_name: str,
        last_poll_state: Optional[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Poll external API for changes"""
        try:
            with get_db_context() as db:
                # Get application subscription
                subscription = db.query(ApplicationSubscription).filter(
                    and_(
                        ApplicationSubscription.tenant_id == tenant_id,
                        ApplicationSubscription.app_id == app_id,
                        ApplicationSubscription.status == 'active'
                    )
                ).first()
                
                if not subscription:
                    logger.error(f"No active subscription found for app {app_id}")
                    return None
                    
                # Get application and event details
                app = db.query(Application).filter(
                    Application.app_id == app_id
                ).first()
                
                event = db.query(ApplicationEvent).filter(
                    and_(
                        ApplicationEvent.app_id == app_id,
                        ApplicationEvent.event_name == event_name
                    )
                ).first()
                
                if not app or not event:
                    logger.error(f"Application or event not found")
                    return None
                    
                # Build polling request
                poll_config = event.trigger_config or {}
                endpoint = poll_config.get('endpoint')
                
                if not endpoint:
                    logger.error(f"No polling endpoint configured for event {event_name}")
                    return None
                    
                # Prepare authentication
                headers = self._prepare_auth_headers(app, subscription)
                
                # Add polling parameters
                params = {}
                if last_poll_state:
                    # Use last modified timestamp or ID for incremental polling
                    if 'last_modified' in last_poll_state:
                        params['since'] = last_poll_state['last_modified']
                    elif 'last_id' in last_poll_state:
                        params['after_id'] = last_poll_state['last_id']
                        
                # Make polling request
                response = await self.http_client.get(
                    endpoint,
                    headers=headers,
                    params=params
                )
                
                if response.status_code != 200:
                    logger.error(f"Polling failed with status {response.status_code}")
                    return None
                    
                # Parse response
                data = response.json()
                
                # Extract items based on poll config
                items_path = poll_config.get('items_path', '')
                if items_path:
                    # Navigate to items in response
                    items = data
                    for key in items_path.split('.'):
                        items = items.get(key, [])
                else:
                    # Assume response is array or has standard structure
                    items = data if isinstance(data, list) else data.get('items', [])
                    
                # Filter for new items only
                if last_poll_state and items:
                    # Implement change detection logic
                    new_items = self._detect_changes(items, last_poll_state, poll_config)
                    return new_items if new_items else None
                    
                return items if items else None
                
        except Exception as e:
            logger.error(f"Error polling external API: {str(e)}")
            return None
            
    def _prepare_auth_headers(
        self, 
        app: Application, 
        subscription: ApplicationSubscription
    ) -> Dict[str, str]:
        """Prepare authentication headers"""
        headers = {}
        auth_type = app.auth_type
        auth_config = app.auth_config or {}
        credentials = subscription.auth_credentials or {}
        
        if auth_type == 'api_key':
            api_key = credentials.get('api_key')
            if api_key:
                header_name = auth_config.get('api_key_header', 'X-API-Key')
                prefix = auth_config.get('api_key_prefix', '')
                headers[header_name] = f"{prefix} {api_key}".strip()
                
        elif auth_type == 'oauth2':
            access_token = credentials.get('access_token')
            if access_token:
                headers['Authorization'] = f"Bearer {access_token}"
                
        elif auth_type == 'basic':
            username = credentials.get('username')
            password = credentials.get('password')
            if username and password:
                import base64
                auth_str = f"{username}:{password}"
                encoded = base64.b64encode(auth_str.encode()).decode()
                headers['Authorization'] = f"Basic {encoded}"
                
        return headers
        
    def _detect_changes(
        self, 
        items: List[Dict[str, Any]], 
        last_poll_state: Dict[str, Any],
        poll_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect new or changed items"""
        new_items = []
        
        # Get comparison field from config
        id_field = poll_config.get('id_field', 'id')
        modified_field = poll_config.get('modified_field', 'updated_at')
        
        last_ids = set(last_poll_state.get('seen_ids', []))
        last_modified = last_poll_state.get('last_modified')
        
        for item in items:
            item_id = item.get(id_field)
            
            # Check if this is a new item
            if item_id and item_id not in last_ids:
                new_items.append(item)
                continue
                
            # Check if item was modified
            if last_modified and modified_field in item:
                item_modified = item[modified_field]
                if isinstance(item_modified, str):
                    # Parse ISO timestamp
                    item_modified = datetime.fromisoformat(
                        item_modified.replace('Z', '+00:00')
                    )
                    last_mod_dt = datetime.fromisoformat(last_modified)
                    if item_modified > last_mod_dt:
                        new_items.append(item)
                        
        return new_items
        
    async def _get_last_poll_state(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """Get last poll state from storage"""
        # TODO: Implement persistent storage for poll state
        # For now, return None (poll everything)
        return None
        
    async def _update_poll_state(
        self, 
        flow_id: str, 
        new_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update poll state after successful poll"""
        # Extract state from new data
        state = {
            'last_poll': datetime.utcnow().isoformat(),
            'seen_ids': [],
            'last_modified': None
        }
        
        # TODO: Implement based on actual data structure
        # Store IDs and latest modification timestamp
        
        return state
        
    async def _process_polled_data_with_lock(
        self,
        tenant_id: str,
        flow: Flow,
        poll_data: List[Dict[str, Any]]
    ):
        """Process polled data with distributed lock for deduplication."""
        from services.distributed_lock import DistributedLockManager

        for item in poll_data:
            # Generate unique lock key for this specific data item
            lock_key = DistributedLockManager.get_execution_lock_key(
                flow.flow_id,
                item
            )

            try:
                # Try to acquire lock for this specific execution
                # TTL of 300 seconds should be enough for most flows
                acquired = await self.lock_manager.acquire_lock(
                    lock_key,
                    ttl=300,
                    retry_count=0  # Don't retry, skip if already processing
                )

                if acquired:
                    try:
                        # Execute flow for this item
                        await self._execute_single_item(tenant_id, flow, item)
                    finally:
                        # Release lock after execution
                        await self.lock_manager.release_lock(lock_key)
                else:
                    # Another worker is already processing this item
                    logger.debug(
                        f"Skipping duplicate execution for flow {flow.flow_id}, "
                        f"item already being processed"
                    )

            except Exception as e:
                logger.error(
                    f"Error processing polled item for flow {flow.flow_id}: {e}"
                )

    async def _trigger_flow_execution(
        self,
        tenant_id: str,
        flow: Flow,
        poll_data: List[Dict[str, Any]]
    ):
        """Trigger flow execution for polled data (backward compatibility)"""
        try:
            # Execute for each item
            for item in poll_data:
                await self._execute_single_item(tenant_id, flow, item)

        except Exception as e:
            logger.error(f"Error triggering flow execution: {str(e)}")

    async def _execute_single_item(self, tenant_id: str, flow: Flow, item: Dict[str, Any]):
        """Execute flow for a single polled item."""
        try:
            trigger_data = {
                'type': 'polling',
                'timestamp': datetime.utcnow().isoformat(),
                'data': item
            }

            # Get tenant schema
            from api.flows import get_tenant_schema
            from db.models import User

            with get_db_context() as db:
                user = db.query(User).filter(User.tenant_id == tenant_id).first()
                if not user:
                    logger.error(f"No user found for tenant {tenant_id}")
                    return
                schema_name = get_tenant_schema(user)

            # Start flow execution
            engine = self.execution_engine(schema_name)
            try:
                await engine.execute_flow(
                    flow_id=flow.flow_id,
                    trigger_data=trigger_data,
                    trigger_type='polling'
                )
                logger.info(f"Started execution for flow {flow.flow_id} with polled data")
            finally:
                await engine.close()

        except Exception as e:
            logger.error(f"Error executing single item for flow {flow.flow_id}: {str(e)}")


# Global API polling service instance
api_polling_service = ApiPollingService()

# Legacy alias for backward compatibility
polling_service = api_polling_service


async def start_polling_service():
    """Start the global polling service"""
    await polling_service.start()
    
    
async def stop_polling_service():
    """Stop the global polling service"""
    await polling_service.stop()