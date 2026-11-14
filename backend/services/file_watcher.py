from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import asyncio
import logging
import fnmatch
import os
import threading
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import and_
from db.database import get_tenant_db
from core.config import settings

# Import models - PostgreSQL Only
from db.models import Flow, FlowStatus

logger = logging.getLogger(__name__)


class FlowFileEventHandler(FileSystemEventHandler):
    """Handles file system events and triggers flows."""

    def __init__(self, tenant_id: str, schema_name: str, flow_id: str,
                 file_pattern: str, listener_types: List[str],
                 recursive: bool, debounce_seconds: int,
                 loop: asyncio.AbstractEventLoop, user_id: str = None,
                 lock_manager = None):
        self.tenant_id = tenant_id
        self.schema_name = schema_name
        self.flow_id = flow_id
        self.file_pattern = file_pattern
        self.listener_types = listener_types
        self.recursive = recursive
        self.debounce_seconds = debounce_seconds
        self.last_triggered = {}  # Track last trigger time per file
        self.loop = loop  # Store the event loop
        self.user_id = user_id  # Store the flow creator's user_id for execution context
        self.lock_manager = lock_manager  # Store the lock manager for deduplication
        
    def should_process_event(self, event_path: str, event_type: str) -> bool:
        """Check if event should be processed based on configuration."""
        # Check if event type is enabled
        if event_type not in self.listener_types:
            logger.debug(f"Event type {event_type} not in listener types {self.listener_types}")
            return False
            
        # Check file pattern
        file_name = os.path.basename(event_path)
        if not fnmatch.fnmatch(file_name, self.file_pattern):
            logger.debug(f"File {file_name} doesn't match pattern {self.file_pattern}")
            return False
            
        # Check debouncing
        if self.debounce_seconds > 0:
            key = f"{event_path}:{event_type}"
            now = datetime.now()
            if key in self.last_triggered:
                if now - self.last_triggered[key] < timedelta(seconds=self.debounce_seconds):
                    logger.debug(f"Debouncing event for {event_path} ({event_type})")
                    return False
            self.last_triggered[key] = now
            
        return True
        
    def on_created(self, event):
        if not event.is_directory:
            logger.info(f"File created event received: {event.src_path}")
            if self.should_process_event(event.src_path, 'create'):
                logger.info(f"Processing create event for {event.src_path}")
                try:
                    # Run in the main event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.trigger_flow(event.src_path, 'create'), self.loop
                    )
                    logger.info(f"Scheduled flow trigger for create event")
                except Exception as e:
                    logger.error(f"Error scheduling flow trigger for create event: {e}", exc_info=True)
            else:
                logger.info(f"Event not processed for {event.src_path}")
            
    def on_modified(self, event):
        if not event.is_directory:
            logger.debug(f"File modified event: {event.src_path}")
            if self.should_process_event(event.src_path, 'modify'):
                logger.info(f"Processing modify event for {event.src_path}")
                try:
                    # Run in the main event loop
                    asyncio.run_coroutine_threadsafe(
                        self.trigger_flow(event.src_path, 'modify'), self.loop
                    )
                except Exception as e:
                    logger.error(f"Error scheduling flow trigger for modify event: {e}")
            
    def on_deleted(self, event):
        if not event.is_directory:
            logger.debug(f"File deleted event: {event.src_path}")
            if self.should_process_event(event.src_path, 'delete'):
                logger.info(f"Processing delete event for {event.src_path}")
                try:
                    # Run in the main event loop
                    asyncio.run_coroutine_threadsafe(
                        self.trigger_flow(event.src_path, 'delete'), self.loop
                    )
                except Exception as e:
                    logger.error(f"Error scheduling flow trigger for delete event: {e}")
            
    async def trigger_flow(self, file_path: str, event_type: str):
        """Trigger the associated flow with file information and distributed lock for deduplication."""
        try:
            logger.info(f"Triggering flow {self.flow_id} for {event_type} event on {file_path}")

            # Prepare variables with file information (using input. prefix for consistency)
            variables = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'event_type': event_type,
                'timestamp': datetime.now().isoformat()
            }

            # Add file size if file exists
            if event_type != 'delete' and os.path.exists(file_path):
                try:
                    variables['file_size'] = os.path.getsize(file_path)
                except Exception:
                    pass

            # Prepare trigger data with variables
            trigger_data = {
                'trigger_source': 'file_watcher',
                'variables': variables
            }

            # If lock manager is available, use it for deduplication
            if self.lock_manager:
                from services.distributed_lock import DistributedLockManager

                # Generate unique lock key for this execution
                lock_key = DistributedLockManager.get_execution_lock_key(
                    self.flow_id,
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
                        # Import here to avoid circular dependency
                        from services.execution_engine import ExecutionEngine

                        # Execute the flow with the correct schema, tenant_id, and user_id
                        # Use the flow creator's user_id for proper subscription context
                        execution_engine = ExecutionEngine(
                            self.schema_name,
                            tenant_id=self.tenant_id,
                            user_id=self.user_id
                        )
                        await execution_engine.execute_flow(
                            flow_id=self.flow_id,
                            trigger_data=trigger_data,
                            trigger_type='file_change'
                        )
                    finally:
                        # Release lock after execution
                        await self.lock_manager.release_lock(lock_key)
                else:
                    # Another worker is already processing this file event
                    logger.debug(
                        f"Skipping duplicate execution for flow {self.flow_id}, "
                        f"file event already being processed by another worker"
                    )
            else:
                # Fallback to direct execution (backward compatibility)
                from services.execution_engine import ExecutionEngine

                execution_engine = ExecutionEngine(
                    self.schema_name,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id
                )
                await execution_engine.execute_flow(
                    flow_id=self.flow_id,
                    trigger_data=trigger_data,
                    trigger_type='file_change'
                )

        except Exception as e:
            logger.error(f"Failed to trigger flow {self.flow_id} for file event: {str(e)}")


class FileWatcherService:
    """Manages file system watchers for flows."""

    def __init__(self):
        self.observers: Dict[str, Observer] = {}  # key: f"{tenant_id}:{flow_id}"
        self.handlers: Dict[str, FlowFileEventHandler] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.lock_manager = None  # Will be injected by BackgroundServiceManager
        
    async def start(self):
        """Start the file watcher service and load all active file watchers."""
        # Store the main event loop
        self.loop = asyncio.get_running_loop()
        logger.info("File watcher service started")
        
        # Load existing file watchers
        await self.reload_all_watchers()
        
    async def stop(self):
        """Stop all file watchers."""
        for observer_key, observer in self.observers.items():
            if observer.is_alive():
                observer.stop()
                observer.join()
                logger.info(f"Stopped file watcher for {observer_key}")
                
        self.observers.clear()
        self.handlers.clear()
        logger.info("File watcher service stopped")
        
    async def reload_all_watchers(self):
        """Reload all file watchers from database."""
        try:
            # PostgreSQL multi-tenant mode
            from db.database import get_db
            from db.models import Tenant

            main_db = next(get_db())
            try:
                tenants = main_db.query(Tenant).filter(Tenant.status == 'active').all()
                for tenant in tenants:
                    tenant_id = str(tenant.tenant_id)
                    schema_name = f"tenant_{tenant_id.replace('-', '_')}"
                    await self.reload_tenant_watchers(tenant_id, schema_name)
            finally:
                main_db.close()
                    
        except Exception as e:
            logger.error(f"Failed to reload file watchers: {str(e)}")
            
    async def reload_tenant_watchers(self, tenant_id: str, schema_name: str):
        """Reload file watchers for a specific tenant."""
        try:
            with get_tenant_db(schema_name) as db:
                # Flows live in the shared ioflow.flows table (models are
                # schema-qualified, so the tenant search_path does not isolate
                # them) — filter by tenant_id or every tenant's pass would
                # attach watchers for all tenants' flows.
                flows = db.query(Flow).filter(
                    Flow.tenant_id == tenant_id,
                    Flow.status == FlowStatus.ACTIVE
                ).all()
                for flow in flows:
                    trigger_config = flow.trigger_config or {}
                    if trigger_config.get('type') == 'file_change':
                        # Start watching for this flow
                        # Note: tenant_id here is the actual tenant_id from the database
                        await self.watch_flow(tenant_id, schema_name, flow)
                
        except Exception as e:
            logger.error(f"Failed to reload watchers for tenant {tenant_id}: {str(e)}")
            
    async def watch_flow(self, tenant_id: str, schema_name: str, flow: Flow):
        """Start watching files for a specific flow.
        
        Args:
            tenant_id: The tenant ID
            schema_name: The database schema name
            flow: The flow to watch for
        """
        flow_id = str(flow.flow_id)
        watcher_key = f"{tenant_id}:{flow_id}"
        
        # Stop existing watcher if any
        if watcher_key in self.observers:
            self.observers[watcher_key].stop()
            del self.observers[watcher_key]
            del self.handlers[watcher_key]
            
        trigger_config = flow.trigger_config or {}
        
        # Extract configuration
        folder_path = trigger_config.get('folder_path')
        if not folder_path:
            logger.error(f"No folder_path specified for flow {flow_id}")
            return
            
        # Validate folder exists
        if not os.path.exists(folder_path):
            logger.error(f"Folder does not exist: {folder_path} for flow {flow_id}")
            return
            
        if not os.path.isdir(folder_path):
            logger.error(f"Path is not a directory: {folder_path} for flow {flow_id}")
            return
            
        listener_types = trigger_config.get('listener_type', ['create', 'modify', 'delete'])
        file_pattern = trigger_config.get('file_pattern', '*')
        recursive = trigger_config.get('recursive', False)
        debounce_seconds = trigger_config.get('debounce_seconds', 5)
        
        # Ensure we have an event loop
        if not self.loop:
            logger.error(f"No event loop available for flow {flow_id}")
            return
            
        try:
            # Create event handler with the event loop and flow creator's user_id
            handler = FlowFileEventHandler(
                tenant_id=tenant_id,
                schema_name=schema_name,
                flow_id=flow_id,
                file_pattern=file_pattern,
                listener_types=listener_types,
                recursive=recursive,
                debounce_seconds=debounce_seconds,
                loop=self.loop,
                user_id=flow.created_by,  # Pass the flow creator's user_id
                lock_manager=self.lock_manager  # Pass the lock manager for deduplication
            )
            
            # Create and start observer
            observer = Observer()
            observer.schedule(handler, folder_path, recursive=recursive)
            observer.start()
            
            # Verify observer is running
            if not observer.is_alive():
                logger.error(f"Observer failed to start for flow {flow_id}")
                return
            
            # Store references
            self.observers[watcher_key] = observer
            self.handlers[watcher_key] = handler
            
            logger.info(f"Started file watcher for flow {flow_id} monitoring {folder_path} "
                       f"(pattern: {file_pattern}, recursive: {recursive}, observer_alive: {observer.is_alive()})")
                       
        except Exception as e:
            logger.error(f"Failed to start file watcher for flow {flow_id}: {str(e)}")
            
    async def unwatch_flow(self, tenant_id: str, flow_id: str):
        """Stop watching files for a specific flow."""
        watcher_key = f"{tenant_id}:{flow_id}"
        
        if watcher_key in self.observers:
            try:
                observer = self.observers[watcher_key]
                if observer.is_alive():
                    observer.stop()
                    observer.join()
                del self.observers[watcher_key]
                del self.handlers[watcher_key]
                logger.info(f"Stopped file watcher for flow {flow_id}")
            except Exception as e:
                logger.error(f"Failed to stop file watcher for flow {flow_id}: {str(e)}")
                
    def get_active_watchers(self) -> List[Dict]:
        """Get information about active file watchers."""
        watchers = []
        for watcher_key, handler in self.handlers.items():
            tenant_id, flow_id = watcher_key.split(':', 1)
            watchers.append({
                'tenant_id': tenant_id,
                'flow_id': flow_id,
                'file_pattern': handler.file_pattern,
                'listener_types': handler.listener_types,
                'recursive': handler.recursive,
                'debounce_seconds': handler.debounce_seconds
            })
        return watchers


# Global file watcher instance
file_watcher_service = FileWatcherService()