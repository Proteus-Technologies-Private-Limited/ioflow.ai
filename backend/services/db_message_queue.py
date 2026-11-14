"""
Message queue for cross-worker WebSocket communication.
Uses Redis pub/sub when available (ws_message_queue_backend setting),
falling back to a database-backed queue polled by subscribers.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, String, Text, DateTime, Integer, Index
from sqlalchemy.orm import Session
from db.database import Base, get_tenant_db, is_sqlite
import uuid

import redis.asyncio as aioredis

from core.config import settings

logger = logging.getLogger(__name__)


class ExecutionMessage(Base):
    """Model for storing execution update messages across workers"""
    __tablename__ = "execution_messages"

    message_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), nullable=False, index=True)
    tenant_id = Column(String(36), nullable=False, index=True)
    message_type = Column(String(50), nullable=False)
    message_data = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    consumed = Column(Integer, default=0)  # 0 = not consumed, 1 = consumed

    # Composite index for efficient queries. In PostgreSQL the table lives in
    # the shared 'ioflow' schema (like all main models); SQLite has no schemas.
    __table_args__ = (
        Index('idx_execution_tenant', 'execution_id', 'tenant_id'),
        Index('idx_tenant_consumed_created', 'tenant_id', 'consumed', 'created_at'),
    ) if is_sqlite else (
        Index('idx_execution_tenant', 'execution_id', 'tenant_id'),
        Index('idx_tenant_consumed_created', 'tenant_id', 'consumed', 'created_at'),
        {'schema': 'ioflow'},
    )


class DatabaseMessageQueue:
    """Message queue for WebSocket execution events.

    Transport is chosen once at startup (ws_message_queue_backend):
    Redis pub/sub when reachable, otherwise the execution_messages table
    polled by subscribers.
    """

    def __init__(self):
        self.polling_interval = 0.1  # Poll every 100ms (database backend only)
        self.message_ttl = 3600  # Keep messages for 1 hour (supports long-running flows)
        self._cleanup_task = None
        self.redis_client: Optional[aioredis.Redis] = None
        # Separate client for pub/sub consumers: subscriptions block waiting
        # for messages, so this client must not have a socket read timeout
        self.redis_pubsub_client: Optional[aioredis.Redis] = None
        self.use_redis = False

    async def start(self):
        """Pick the transport backend and start the cleanup task"""
        await self._init_redis()
        # Cleanup runs in both modes: it also drains rows left over from
        # earlier database-mode runs or per-message fallbacks
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_old_messages())
            logger.info("Database message queue cleanup task started")

    async def stop(self):
        """Stop the cleanup task and close the Redis connection"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Database message queue cleanup task stopped")

        for attr in ('redis_client', 'redis_pubsub_client'):
            client = getattr(self, attr)
            if client:
                try:
                    await client.aclose()
                except Exception as e:
                    logger.warning(f"Error closing Redis connection ({attr}): {e}")
                setattr(self, attr, None)
        self.use_redis = False

    async def _init_redis(self):
        """Try Redis for pub/sub transport; fall back to the database queue"""
        backend = (getattr(settings, 'ws_message_queue_backend', 'auto') or 'auto').lower()
        if backend == 'database':
            logger.info("WebSocket message queue: database backend (forced by ws_message_queue_backend)")
            return

        redis_url = getattr(settings, 'redis_url', None)
        if not redis_url:
            logger.warning("WebSocket message queue: no redis_url configured, using database backend")
            return

        try:
            self.redis_client = aioredis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=5
            )
            await self.redis_client.ping()
            # No socket_timeout here: pub/sub reads block indefinitely between
            # messages and a read timeout would kill idle subscriptions
            self.redis_pubsub_client = aioredis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=2
            )
            self.use_redis = True
            logger.info(f"WebSocket message queue using Redis pub/sub at {redis_url}")
        except Exception as e:
            self.redis_client = None
            self.redis_pubsub_client = None
            self.use_redis = False
            message = f"Redis not available for WebSocket message queue ({e}), falling back to database queue"
            if backend == 'redis':
                logger.error(message)
            else:
                logger.warning(message)

    @staticmethod
    def _channel(tenant_id: str, execution_id: str) -> str:
        return f"ioflow:execmsg:{tenant_id}:{execution_id}"

    async def publish(self, execution_id: str, tenant_id: str, message_type: str, message_data: Dict[str, Any], schema_name: str = "main"):
        """
        Publish a message to the queue

        Args:
            execution_id: ID of the execution
            tenant_id: ID of the tenant
            message_type: Type of message (e.g., 'execution_update', 'execution_log')
            message_data: Message data as dictionary
            schema_name: Database schema name
        """
        if self.use_redis:
            try:
                payload = json.dumps({
                    "type": message_type,
                    "execution_id": execution_id,
                    "data": message_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
                await self.redis_client.publish(self._channel(tenant_id, execution_id), payload)
                logger.debug(f"Published message via Redis: {message_type} for execution {execution_id}")
                return
            except Exception as e:
                logger.error(f"Redis publish failed ({e}), falling back to database for this message")

        try:
            with get_tenant_db(schema_name) as db:
                message = ExecutionMessage(
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    message_type=message_type,
                    message_data=json.dumps(message_data),
                    created_at=datetime.utcnow(),
                    consumed=0
                )
                db.add(message)
                db.commit()
                logger.debug(f"Published message: {message_type} for execution {execution_id}")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")

    async def subscribe(self, tenant_id: str, execution_id: Optional[str], callback, schema_name: str = "main"):
        """
        Subscribe to messages for a tenant or specific execution

        Args:
            tenant_id: ID of the tenant to subscribe to
            execution_id: Optional specific execution ID (None for all tenant executions)
            callback: Async callback function to handle messages
            schema_name: Database schema name
        """
        if self.use_redis:
            await self._subscribe_redis(tenant_id, execution_id, callback)
        else:
            await self._subscribe_database(tenant_id, execution_id, callback, schema_name)

    async def _subscribe_redis(self, tenant_id: str, execution_id: Optional[str], callback):
        """Consume messages for a tenant/execution via Redis pub/sub.

        Transient errors (broker restart, dropped connection) resubscribe
        after a short delay; only task cancellation ends the subscription.
        """
        logger.info(f"Starting Redis subscription: tenant={tenant_id}, execution={execution_id}")

        while True:
            pubsub = self.redis_pubsub_client.pubsub(ignore_subscribe_messages=True)
            try:
                if execution_id:
                    await pubsub.subscribe(self._channel(tenant_id, execution_id))
                else:
                    await pubsub.psubscribe(f"ioflow:execmsg:{tenant_id}:*")

                async for message in pubsub.listen():
                    if message.get('type') not in ('message', 'pmessage'):
                        continue
                    try:
                        formatted_message = json.loads(message['data'])
                        await callback(formatted_message)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode Redis message data: {e}")
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")

            except asyncio.CancelledError:
                logger.info(f"Redis subscription cancelled: tenant={tenant_id}, execution={execution_id}")
                raise
            except Exception as e:
                logger.error(
                    f"Redis subscription error (tenant={tenant_id}, execution={execution_id}): {e}; "
                    f"resubscribing in 1s"
                )
                await asyncio.sleep(1.0)
            finally:
                try:
                    await pubsub.aclose()
                except Exception as e:
                    logger.warning(f"Error closing Redis pubsub: {e}")

    async def _subscribe_database(self, tenant_id: str, execution_id: Optional[str], callback, schema_name: str = "main"):
        """Consume messages for a tenant/execution by polling the database queue"""
        logger.info(f"Starting subscription: tenant={tenant_id}, execution={execution_id}")
        last_check = datetime.utcnow()

        try:
            while True:
                try:
                    # Fetch new messages
                    with get_tenant_db(schema_name) as db:
                        query = db.query(ExecutionMessage).filter(
                            ExecutionMessage.tenant_id == tenant_id,
                            ExecutionMessage.consumed == 0,
                            ExecutionMessage.created_at >= last_check
                        )

                        # Filter by execution_id if specified
                        if execution_id:
                            query = query.filter(ExecutionMessage.execution_id == execution_id)

                        messages = query.order_by(ExecutionMessage.created_at).all()

                        # Process messages
                        for msg in messages:
                            try:
                                message_data = json.loads(msg.message_data)

                                # Format message for WebSocket
                                formatted_message = {
                                    "type": msg.message_type,
                                    "execution_id": msg.execution_id,
                                    "data": message_data,
                                    "timestamp": msg.created_at.isoformat()
                                }

                                # Call the callback
                                await callback(formatted_message)

                                # Mark as consumed
                                msg.consumed = 1

                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to decode message data: {e}")
                                msg.consumed = 1  # Mark as consumed to avoid reprocessing
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")

                        # Commit consumed status updates
                        if messages:
                            db.commit()
                            logger.debug(f"Processed {len(messages)} messages")

                        # Update last check time
                        last_check = datetime.utcnow()

                except Exception as e:
                    logger.error(f"Error in subscription loop: {e}")

                # Wait before next poll
                await asyncio.sleep(self.polling_interval)

        except asyncio.CancelledError:
            logger.info(f"Subscription cancelled: tenant={tenant_id}, execution={execution_id}")
            raise

    async def _cleanup_old_messages(self):
        """Periodically clean up old consumed messages"""
        while True:
            try:
                await asyncio.sleep(60)  # Run cleanup every minute

                cutoff_time = datetime.utcnow() - timedelta(seconds=self.message_ttl)

                with get_tenant_db("main") as db:
                    # Delete expired messages regardless of consumed status:
                    # events of unwatched executions are never consumed and
                    # would otherwise accumulate forever
                    deleted = db.query(ExecutionMessage).filter(
                        ExecutionMessage.created_at < cutoff_time
                    ).delete()

                    if deleted > 0:
                        db.commit()
                        logger.info(f"Cleaned up {deleted} old messages")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")


# Global instance
db_message_queue = DatabaseMessageQueue()
