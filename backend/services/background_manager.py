"""
Background Service Manager for IOFlow
Manages leader election and coordination of background services across multiple workers
"""

import asyncio
import logging
import uuid
from typing import Dict, Set, Optional
from datetime import datetime

from services.distributed_lock import DistributedLockManager
# Services are imported when needed to use global instances

logger = logging.getLogger(__name__)


class BackgroundServiceManager:
    """
    Manages background services with leader election.
    Ensures only one instance of each service runs across all workers/servers.
    """

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.lock_manager = DistributedLockManager(self.worker_id)

        # Services that need leader election
        self.services = {
            'api_polling': None,  # Will be initialized when becoming leader
            'service_polling': None,  # Service-based polling (Gmail OAuth, etc)
            'email_polling': None,  # Direct IMAP/POP3 email polling
            'scheduler': None,
            'file_watcher': None,
            'mqtt_listener': None
        }

        # Track which services we're currently leading
        self.active_services: Set[str] = set()

        # Leadership management task
        self.leadership_task: Optional[asyncio.Task] = None

        # Service heartbeat intervals (in seconds)
        self.heartbeat_interval = 10
        self.lock_ttl = 30  # Lock TTL should be > heartbeat interval

        self.running = False

        logger.info(f"Background Service Manager initialized for worker: {self.worker_id}")

    async def start(self):
        """Start the background service manager."""
        if self.running:
            logger.warning("Background Service Manager already running")
            return

        logger.info(f"Starting Background Service Manager on {self.worker_id}")

        # Initialize lock manager
        await self.lock_manager.initialize()

        self.running = True

        # Start leadership management loop
        self.leadership_task = asyncio.create_task(self._manage_leadership())

        logger.info("Background Service Manager started")

    async def stop(self):
        """Stop the background service manager and all services."""
        logger.info(f"Stopping Background Service Manager on {self.worker_id}")

        self.running = False

        # Cancel leadership task
        if self.leadership_task:
            self.leadership_task.cancel()
            try:
                await self.leadership_task
            except asyncio.CancelledError:
                pass

        # Stop all active services
        for service_name in list(self.active_services):
            await self._stop_service(service_name)

        # Clean up locks
        await self.lock_manager.cleanup()

        logger.info("Background Service Manager stopped")

    async def _manage_leadership(self):
        """
        Main loop for managing service leadership.
        Continuously tries to acquire/maintain leadership for each service.
        """
        while self.running:
            try:
                # Try to acquire or maintain leadership for each service
                for service_name in self.services.keys():
                    await self._check_service_leadership(service_name)

                # Wait before next check
                await asyncio.sleep(self.heartbeat_interval)

            except asyncio.CancelledError:
                logger.debug("Leadership management task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in leadership management: {e}", exc_info=True)
                await asyncio.sleep(self.heartbeat_interval)

    async def _check_service_leadership(self, service_name: str):
        """Check and manage leadership for a specific service."""
        lock_key = f"leader:{service_name}"

        try:
            if service_name in self.active_services:
                # We're currently the leader, try to extend our lock
                extended = await self.lock_manager.extend_lock(lock_key, self.lock_ttl)

                if not extended:
                    # Lost leadership
                    logger.info(f"Lost leadership for {service_name} on {self.worker_id}")
                    await self._stop_service(service_name)
                    self.active_services.discard(service_name)
                else:
                    logger.debug(f"Maintained leadership for {service_name} on {self.worker_id}")
            else:
                # Try to acquire leadership
                acquired = await self.lock_manager.acquire_lock(
                    lock_key,
                    ttl=self.lock_ttl,
                    retry_count=0  # Don't retry, we'll try again on next cycle
                )

                if acquired:
                    # Became the leader
                    logger.info(f"Acquired leadership for {service_name} on {self.worker_id}")
                    await self._start_service(service_name)
                    self.active_services.add(service_name)

        except Exception as e:
            logger.error(f"Error managing leadership for {service_name}: {e}")
            # On error, stop the service if we were running it
            if service_name in self.active_services:
                await self._stop_service(service_name)
                self.active_services.discard(service_name)

    async def _start_service(self, service_name: str):
        """Start a specific background service."""
        try:
            logger.info(f"Starting {service_name} service on {self.worker_id}")

            if service_name == 'api_polling':
                # Use the global API polling instance
                from services.polling_service import api_polling_service
                if not self.services['api_polling']:
                    self.services['api_polling'] = api_polling_service
                    # Pass the lock manager to the service
                    self.services['api_polling'].lock_manager = self.lock_manager
                await self.services['api_polling'].start()

            elif service_name == 'service_polling':
                # Use the global service polling instance
                from services.generic_polling_service import service_polling_service
                if not self.services['service_polling']:
                    self.services['service_polling'] = service_polling_service
                    # Pass the lock manager to the service
                    self.services['service_polling'].lock_manager = self.lock_manager
                await self.services['service_polling'].start()

            elif service_name == 'email_polling':
                # Use the global email polling instance
                from services.email_polling_service import email_polling_service
                if not self.services['email_polling']:
                    self.services['email_polling'] = email_polling_service
                    # Pass the lock manager to the service
                    self.services['email_polling'].lock_manager = self.lock_manager
                await self.services['email_polling'].start()

            elif service_name == 'scheduler':
                # Use the global scheduler instance instead of creating a new one
                from services.scheduler import flow_scheduler
                if not self.services['scheduler']:
                    self.services['scheduler'] = flow_scheduler
                    # Pass the lock manager to the service
                    self.services['scheduler'].lock_manager = self.lock_manager
                await self.services['scheduler'].start()

            elif service_name == 'file_watcher':
                # Use the global file watcher instance instead of creating a new one
                from services.file_watcher import file_watcher_service
                if not self.services['file_watcher']:
                    self.services['file_watcher'] = file_watcher_service
                    # Pass the lock manager to the service
                    self.services['file_watcher'].lock_manager = self.lock_manager
                await self.services['file_watcher'].start()

            elif service_name == 'mqtt_listener':
                # Use the global MQTT listener instance instead of creating a new one
                from services.mqtt_listener_service import mqtt_listener_service
                if not self.services['mqtt_listener']:
                    self.services['mqtt_listener'] = mqtt_listener_service
                    # Pass the lock manager to the service
                    self.services['mqtt_listener'].lock_manager = self.lock_manager
                await self.services['mqtt_listener'].start()

            logger.info(f"Successfully started {service_name} service on {self.worker_id}")

        except Exception as e:
            logger.error(f"Failed to start {service_name} service: {e}", exc_info=True)
            raise

    async def _stop_service(self, service_name: str):
        """Stop a specific background service."""
        try:
            logger.info(f"Stopping {service_name} service on {self.worker_id}")

            service = self.services.get(service_name)
            if service:
                # All services have a stop() method
                await service.stop()

                # Don't clear the service instance, we might become leader again
                # self.services[service_name] = None

            logger.info(f"Successfully stopped {service_name} service on {self.worker_id}")

        except Exception as e:
            logger.error(f"Error stopping {service_name} service: {e}", exc_info=True)

    def get_status(self) -> Dict:
        """Get the current status of the service manager."""
        return {
            'worker_id': self.worker_id,
            'running': self.running,
            'active_services': list(self.active_services),
            'is_api_polling_leader': 'api_polling' in self.active_services,
            'is_service_polling_leader': 'service_polling' in self.active_services,
            'is_email_polling_leader': 'email_polling' in self.active_services,
            'is_scheduler_leader': 'scheduler' in self.active_services,
            'is_file_watcher_leader': 'file_watcher' in self.active_services,
            'is_mqtt_listener_leader': 'mqtt_listener' in self.active_services,
            'timestamp': datetime.utcnow().isoformat()
        }

    def is_leader_for(self, service_name: str) -> bool:
        """Check if this worker is the leader for a specific service."""
        return service_name in self.active_services


# Global instance for easy access
_background_manager: Optional[BackgroundServiceManager] = None


def get_background_manager() -> Optional[BackgroundServiceManager]:
    """Get the global background manager instance."""
    return _background_manager


def set_background_manager(manager: BackgroundServiceManager):
    """Set the global background manager instance."""
    global _background_manager
    _background_manager = manager