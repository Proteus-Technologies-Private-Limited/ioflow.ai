"""
WebSocket Manager for real-time execution updates
Supports multi-worker deployment using database-based message queue
"""
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
from datetime import datetime
import json
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Import database message queue
from services.db_message_queue import db_message_queue
from core.config import settings


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Maps tenant_id -> set of WebSocket connections
        self._tenant_connections: Dict[str, Set[WebSocket]] = defaultdict(set)

        # Maps connection -> user info
        self._connection_info: Dict[WebSocket, dict] = {}

        # Maps connection -> subscribed execution IDs
        self._execution_subscriptions: Dict[WebSocket, Set[str]] = defaultdict(set)

        # Maps connection -> subscribed tenant (for tenant-wide updates)
        self._tenant_subscriptions: Dict[WebSocket, bool] = {}

        # Maps connection -> database subscription tasks (one per execution ID)
        # Structure: WebSocket -> {execution_id: Task}
        self._db_subscription_tasks: Dict[WebSocket, Dict[str, asyncio.Task]] = defaultdict(dict)

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str, user_id: str, user_email: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        async with self._lock:
            # Store connection info
            self._connection_info[websocket] = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "user_email": user_email,
                "connected_at": datetime.utcnow()
            }
            
            # Add to tenant connections
            self._tenant_connections[tenant_id].add(websocket)
            
        logger.info(f"WebSocket connected: user={user_email}, tenant={tenant_id}")
        
        # Send initial connection message
        await self.send_personal_message(
            websocket,
            {
                "type": "connection",
                "status": "connected",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        async with self._lock:
            # Get connection info before removing
            info = self._connection_info.get(websocket, {})
            tenant_id = info.get("tenant_id")
            user_email = info.get("user_email", "unknown")

            # Cancel all database subscription tasks for this WebSocket
            tasks_dict = self._db_subscription_tasks.pop(websocket, {})
            for execution_id, task in tasks_dict.items():
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    logger.info(f"Cancelled database subscription task for execution {execution_id}, user {user_email}")

            # Remove from all tracking structures
            if tenant_id:
                self._tenant_connections[tenant_id].discard(websocket)
                if not self._tenant_connections[tenant_id]:
                    del self._tenant_connections[tenant_id]

            self._connection_info.pop(websocket, None)
            self._execution_subscriptions.pop(websocket, None)
            self._tenant_subscriptions.pop(websocket, None)

        logger.info(f"WebSocket disconnected: user={user_email}, tenant={tenant_id}")

    async def subscribe_to_execution(self, websocket: WebSocket, execution_id: str):
        """Subscribe a connection to specific execution updates using database queue"""
        async with self._lock:
            self._execution_subscriptions[websocket].add(execution_id)

        info = self._connection_info.get(websocket, {})
        tenant_id = info.get('tenant_id', 'main')
        logger.info(f"User {info.get('user_email')} subscribed to execution {execution_id}")

        # Create database subscription task for this specific execution
        # Each execution gets its own task to maintain execution-level privacy
        async with self._lock:
            if execution_id not in self._db_subscription_tasks[websocket]:
                async def db_callback(message):
                    """Callback to forward database messages to WebSocket"""
                    await self.send_personal_message(websocket, message)

                # Create subscription task for this specific execution only
                # This maintains privacy by only retrieving messages for this execution
                task = asyncio.create_task(
                    db_message_queue.subscribe(
                        tenant_id=tenant_id,
                        execution_id=execution_id,  # Subscribe to specific execution only
                        callback=db_callback,
                        schema_name="main"
                    )
                )

                self._db_subscription_tasks[websocket][execution_id] = task
                logger.info(f"Started database queue subscription for execution {execution_id}")
            else:
                logger.info(f"Already subscribed to execution {execution_id}")

        # Send subscription confirmation
        await self.send_personal_message(
            websocket,
            {
                "type": "subscription",
                "action": "subscribed",
                "execution_id": execution_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def unsubscribe_from_execution(self, websocket: WebSocket, execution_id: str):
        """Unsubscribe a connection from specific execution updates"""
        async with self._lock:
            self._execution_subscriptions[websocket].discard(execution_id)

            # Cancel the database subscription task for this execution
            task = self._db_subscription_tasks.get(websocket, {}).pop(execution_id, None)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"Cancelled database subscription task for execution {execution_id}")

        info = self._connection_info.get(websocket, {})
        logger.info(f"User {info.get('user_email')} unsubscribed from execution {execution_id}")

        # Send unsubscription confirmation
        await self.send_personal_message(
            websocket,
            {
                "type": "subscription",
                "action": "unsubscribed",
                "execution_id": execution_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def subscribe_to_tenant(self, websocket: WebSocket, tenant_id: str):
        """
        Mark connection as subscribed to tenant (for backward compatibility).

        NOTE: For security, we do NOT stream all tenant executions to all users.
        Users must explicitly subscribe to specific execution IDs using subscribe_to_execution().
        This prevents users from seeing other users' execution progress.
        """
        async with self._lock:
            self._tenant_subscriptions[websocket] = True

        info = self._connection_info.get(websocket, {})
        logger.info(f"User {info.get('user_email')} marked as tenant subscriber (no automatic streaming)")

        # Send subscription confirmation
        await self.send_personal_message(
            websocket,
            {
                "type": "subscription",
                "action": "subscribed_tenant",
                "tenant_id": tenant_id,
                "timestamp": datetime.utcnow().isoformat(),
                "note": "Tenant subscription confirmed. Subscribe to specific execution IDs to receive updates."
            }
        )

    async def unsubscribe_from_tenant(self, websocket: WebSocket, tenant_id: str):
        """Unsubscribe a connection from tenant-wide updates"""
        async with self._lock:
            self._tenant_subscriptions[websocket] = False
            
        info = self._connection_info.get(websocket, {})
        logger.info(f"User {info.get('user_email')} unsubscribed from tenant executions")
        
        # Send unsubscription confirmation
        await self.send_personal_message(
            websocket,
            {
                "type": "subscription",
                "action": "unsubscribed_tenant",
                "tenant_id": tenant_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket connection"""
        try:
            # Check if WebSocket is still open before sending
            if websocket.client_state.value <= 1:  # CONNECTING=0, CONNECTED=1
                await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            # Only disconnect if the WebSocket isn't already closing/closed
            if websocket.client_state.value <= 1:
                await self.disconnect(websocket)

    async def send_to_user(self, user_id: str, tenant_id: str, message: dict):
        """Send a message to all WebSocket connections of a specific user within a tenant."""
        async with self._lock:
            connections = list(self._tenant_connections.get(tenant_id, []))

        sent_count = 0
        for conn in connections:
            info = self._connection_info.get(conn, {})
            if info.get('user_id') == user_id and info.get('tenant_id') == tenant_id:
                await self.send_personal_message(conn, message)
                sent_count += 1

        if sent_count > 0:
            logger.info(f"Sent HITL notification to user {user_id}: {sent_count} connection(s)")
        return sent_count

    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        """Broadcast a message to all connections in a tenant"""
        async with self._lock:
            connections = list(self._tenant_connections.get(tenant_id, []))
        
        if connections:
            logger.info(f"Broadcasting to {len(connections)} connections in tenant {tenant_id}")
            
            # Send to all connections concurrently
            tasks = [
                self.send_personal_message(conn, message)
                for conn in connections
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    def has_execution_audience(self, execution_id: str) -> bool:
        """True if any connected client on this worker is subscribed to the execution."""
        try:
            return any(
                execution_id in subscriptions
                for subscriptions in self._execution_subscriptions.values()
            )
        except Exception as e:
            # On any unexpected error, err on the side of publishing
            logger.error(f"Audience check failed for execution {execution_id}: {e}")
            return True

    def _should_publish(self, execution_id: str) -> bool:
        """Decide whether an execution event is worth publishing to the queue.

        Backend-triggered executions (MQTT, schedules) usually have no viewer;
        writing their events to the queue is pure overhead.
        """
        if not settings.ws_skip_unwatched_publish:
            return True
        if self.has_execution_audience(execution_id):
            return True
        logger.debug(f"Skipping WebSocket publish (no subscribers): execution={execution_id}")
        return False

    async def send_execution_update(self, execution_id: str, tenant_id: str, update_data: dict):
        """
        Send execution update via database queue (works across multiple workers)

        This publishes the message to the database, where it will be picked up
        by all workers with WebSocket connections subscribed to this tenant/execution.
        """
        if not self._should_publish(execution_id):
            return
        logger.debug(f"Publishing execution update to database queue: execution={execution_id}, tenant={tenant_id}")

        try:
            # Publish to database queue instead of direct WebSocket send
            await db_message_queue.publish(
                execution_id=execution_id,
                tenant_id=tenant_id,
                message_type="execution_update",
                message_data=update_data,
                schema_name="main"
            )
            logger.debug(f"✓ Execution update published to database queue")
        except Exception as e:
            logger.error(f"Failed to publish execution update to database queue: {e}")

    async def send_execution_log(self, execution_id: str, tenant_id: str, log_entry: dict):
        """Send execution log entry via database queue (works across multiple workers)"""
        if not self._should_publish(execution_id):
            return
        logger.debug(f"Publishing execution log to database queue: execution={execution_id}, tenant={tenant_id}")

        try:
            # Publish to database queue instead of direct WebSocket send
            await db_message_queue.publish(
                execution_id=execution_id,
                tenant_id=tenant_id,
                message_type="execution_log",
                message_data=log_entry,
                schema_name="main"
            )
            logger.debug(f"✓ Execution log published to database queue")
        except Exception as e:
            logger.error(f"Failed to publish execution log to database queue: {e}")

    async def send_execution_progress(self, execution_id: str, tenant_id: str, progress_data: dict):
        """Send execution progress update via database queue (works across multiple workers)"""
        if not self._should_publish(execution_id):
            return
        logger.debug(f"Publishing execution progress to database queue: execution={execution_id}, tenant={tenant_id}")

        try:
            # Publish to database queue instead of direct WebSocket send
            await db_message_queue.publish(
                execution_id=execution_id,
                tenant_id=tenant_id,
                message_type="execution_progress",
                message_data=progress_data,
                schema_name="main"
            )
            logger.debug(f"✓ Execution progress published to database queue")
        except Exception as e:
            logger.error(f"Failed to publish execution progress to database queue: {e}")

    def get_connection_stats(self) -> dict:
        """Get statistics about current connections"""
        stats = {
            "total_connections": len(self._connection_info),
            "tenants": {},
            "subscriptions": {}
        }
        
        # Count connections per tenant
        for conn, info in self._connection_info.items():
            tenant_id = info.get("tenant_id")
            if tenant_id:
                if tenant_id not in stats["tenants"]:
                    stats["tenants"][tenant_id] = 0
                stats["tenants"][tenant_id] += 1
        
        # Count subscriptions
        total_subscriptions = 0
        for subscriptions in self._execution_subscriptions.values():
            total_subscriptions += len(subscriptions)
        
        stats["subscriptions"]["total"] = total_subscriptions
        stats["subscriptions"]["connections_with_subscriptions"] = len(self._execution_subscriptions)
        
        return stats


# Global instance
manager = ConnectionManager()