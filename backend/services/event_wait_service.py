"""
Event Wait Service - Core business logic for wait_for_event node completion and flow resumption.
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from db.models import EventWait, FlowExecution, Flow, ExecutionStatus
from db.database import get_tenant_db
from services.execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)


def _deserialize_json(value):
    """Deserialize JSON field for SQLite compatibility."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


class EventWaitService:
    """Core service for event wait management."""

    async def complete_wait(self, wait_id: str, event_data: Dict[str, Any],
                            schema_name: str, tenant_id: str) -> EventWait:
        """Complete an event wait and resume flow execution."""
        with get_tenant_db(schema_name) as db:
            event_wait = db.query(EventWait).filter(
                EventWait.wait_id == wait_id,
                EventWait.tenant_id == tenant_id,
            ).with_for_update().first()

            if not event_wait:
                raise ValueError(f"EventWait {wait_id} not found")

            if event_wait.status != 'waiting':
                raise ValueError(f"EventWait {wait_id} is already {event_wait.status}")

            # Update the wait record
            event_wait.status = 'matched'
            event_wait.event_data = event_data
            event_wait.matched_at = datetime.utcnow()
            db.commit()

            # Build event output for the flow
            event_output = {
                'event_data': event_data,
                'callback_token': event_wait.callback_token,
                'matched_at': event_wait.matched_at.isoformat(),
                'app_id': event_wait.app_id,
                'event_name': event_wait.event_name,
                '_timed_out': False,
            }

            # Get flow definition
            flow = db.query(Flow).filter(Flow.flow_id == event_wait.flow_id).first()
            if not flow:
                raise ValueError(f"Flow {event_wait.flow_id} not found")
            flow_definition = flow.flow_definition

        # Check if this is a debug execution
        is_debug = False
        with get_tenant_db(schema_name) as db:
            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == event_wait.execution_id
            ).first()
            if execution and execution.execution_data:
                exec_data = _deserialize_json(execution.execution_data) if isinstance(execution.execution_data, str) else execution.execution_data
                is_debug = exec_data.get('debug_mode', False) if exec_data else False

        if is_debug:
            await self._handle_debug_completion(event_wait, event_output, schema_name, tenant_id)
            return event_wait

        # Normal mode: Resume flow execution in the background
        async def _resume_flow():
            try:
                engine = ExecutionEngine(schema_name, tenant_id=tenant_id)
                await engine.resume_after_event(
                    wait_id=wait_id,
                    event_output=event_output,
                    flow_definition=flow_definition,
                    tenant_schema=schema_name,
                )
            except Exception as e:
                logger.error(f"Flow resumption failed for event wait {wait_id}: {e}", exc_info=True)

        asyncio.ensure_future(_resume_flow())
        return event_wait

    async def _handle_debug_completion(self, event_wait: EventWait,
                                        event_output: Dict[str, Any],
                                        schema_name: str, tenant_id: str):
        """Handle event wait completion in debug mode."""
        from services.debug_execution_manager import DebugExecutionManager
        from services.websocket_manager import manager as ws_manager

        debug_state = DebugExecutionManager.get_debug_state(
            schema_name, event_wait.execution_id, tenant_id)
        if debug_state:
            # Inject event output as the node's output
            debug_state['node_outputs'][event_wait.node_id] = event_output
            debug_state['context_data'] = event_output

            # Find next node
            edges = debug_state.get('flow_definition', {}).get('edges', [])
            next_nodes = [e['target'] for e in edges if e['source'] == event_wait.node_id]

            if next_nodes:
                debug_state['current_node'] = next_nodes[0]
                debug_state['status'] = 'waiting_for_step'
            else:
                debug_state['status'] = 'completed'
                debug_state['current_node'] = None

            # Clear event wait tracking fields
            debug_state.pop('event_wait_id', None)
            debug_state.pop('event_wait_node_id', None)

            # Update execution status back to RUNNING
            with get_tenant_db(schema_name) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == event_wait.execution_id
                ).first()
                if execution:
                    execution.status = ExecutionStatus.RUNNING
                    db.commit()

            # Save updated debug state
            DebugExecutionManager.save_debug_state(
                schema_name, event_wait.execution_id, debug_state, tenant_id)

            # Send WebSocket events
            await ws_manager.send_execution_update(
                execution_id=event_wait.execution_id,
                tenant_id=tenant_id,
                update_data={
                    'type': 'event_wait_completed',
                    'node_id': event_wait.node_id,
                    'wait_id': event_wait.wait_id,
                }
            )

            if debug_state['status'] == 'waiting_for_step':
                await ws_manager.send_execution_update(
                    execution_id=event_wait.execution_id,
                    tenant_id=tenant_id,
                    update_data={
                        'type': 'waiting_for_step',
                        'node_id': debug_state['current_node'],
                        'executed_nodes': debug_state['executed_nodes'],
                    }
                )
            elif debug_state['status'] == 'completed':
                await ws_manager.send_execution_update(
                    execution_id=event_wait.execution_id,
                    tenant_id=tenant_id,
                    update_data={
                        'type': 'execution_complete',
                        'status': 'completed',
                    }
                )

    async def complete_wait_by_token(self, callback_token: str,
                                      event_data: Dict[str, Any],
                                      schema_name: str) -> EventWait:
        """Complete an event wait using a callback token."""
        with get_tenant_db(schema_name) as db:
            event_wait = db.query(EventWait).filter(
                EventWait.callback_token == callback_token,
            ).first()

            if not event_wait:
                raise ValueError("Invalid callback token")

            if event_wait.status != 'waiting':
                raise ValueError(f"EventWait is already {event_wait.status}")

        return await self.complete_wait(
            wait_id=event_wait.wait_id,
            event_data=event_data,
            schema_name=schema_name,
            tenant_id=event_wait.tenant_id,
        )

    async def complete_wait_by_correlation(self, app_id: str, event_name: str,
                                            event_data: Dict[str, Any],
                                            schema_name: str, tenant_id: str) -> List[EventWait]:
        """Find and complete all matching event waits by correlation."""
        matched_waits = []

        with get_tenant_db(schema_name) as db:
            # Query all waiting records for this app+event in this tenant
            waiting_records = db.query(EventWait).filter(
                EventWait.app_id == app_id,
                EventWait.status == 'waiting',
                EventWait.tenant_id == tenant_id,
            ).all()

            if not waiting_records:
                return []

            # Filter by event name (normalized comparison)
            normalized_event = event_name.lower().replace(' ', '_').replace('-', '_')
            candidates = []
            for record in waiting_records:
                record_event = (record.event_name or '').lower().replace(' ', '_').replace('-', '_')
                if record_event == normalized_event:
                    candidates.append(record)

            if not candidates:
                return []

            # For each candidate, check correlation match
            for record in candidates:
                if record.match_mode == 'token':
                    # Token mode waits are not matched by correlation
                    continue

                correlation = _deserialize_json(record.correlation_config) if isinstance(record.correlation_config, str) else record.correlation_config
                if not correlation:
                    # No correlation config - match any event of this type
                    matched_waits.append(record)
                    continue

                event_field = correlation.get('event_field', '')
                flow_value = correlation.get('flow_value')

                if not event_field:
                    matched_waits.append(record)
                    continue

                # Extract the field value from event data (supports dot notation)
                event_value = self._get_nested_value(event_data, event_field)

                # Compare values (string comparison for robustness)
                if str(event_value) == str(flow_value):
                    matched_waits.append(record)

        # Complete all matched waits
        completed = []
        for record in matched_waits:
            try:
                result = await self.complete_wait(
                    wait_id=record.wait_id,
                    event_data=event_data,
                    schema_name=schema_name,
                    tenant_id=tenant_id,
                )
                completed.append(result)
            except Exception as e:
                logger.error(f"Failed to complete event wait {record.wait_id}: {e}")

        return completed

    def _get_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get a nested value from a dict using dot notation (e.g., 'order.id')."""
        if not data or not field_path:
            return None
        parts = field_path.split('.')
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def get_pending_waits(self, tenant_id: str, schema_name: str,
                          limit: int = 50, offset: int = 0) -> tuple:
        """Get pending event waits for monitoring. Returns (waits, total_count)."""
        with get_tenant_db(schema_name) as db:
            query = db.query(EventWait).filter(
                EventWait.tenant_id == tenant_id,
                EventWait.status == 'waiting',
            )
            total = query.count()
            waits = query.order_by(EventWait.created_at.desc()).offset(offset).limit(limit).all()
            return waits, total

    def get_waits_by_execution(self, execution_id: str, schema_name: str) -> List[EventWait]:
        """Get all event waits for a specific execution."""
        with get_tenant_db(schema_name) as db:
            return db.query(EventWait).filter(
                EventWait.execution_id == execution_id,
            ).order_by(EventWait.created_at.desc()).all()

    def get_wait_detail(self, wait_id: str, tenant_id: str, schema_name: str) -> Optional[EventWait]:
        """Get a specific event wait."""
        with get_tenant_db(schema_name) as db:
            return db.query(EventWait).filter(
                EventWait.wait_id == wait_id,
                EventWait.tenant_id == tenant_id,
            ).first()

    def cancel_wait(self, wait_id: str, tenant_id: str, schema_name: str) -> EventWait:
        """Cancel an event wait and fail the associated execution."""
        with get_tenant_db(schema_name) as db:
            event_wait = db.query(EventWait).filter(
                EventWait.wait_id == wait_id,
                EventWait.tenant_id == tenant_id,
            ).first()

            if not event_wait:
                raise ValueError(f"EventWait {wait_id} not found")

            if event_wait.status != 'waiting':
                raise ValueError(f"EventWait {wait_id} is already {event_wait.status}")

            event_wait.status = 'cancelled'
            event_wait.matched_at = datetime.utcnow()

            # Also cancel the execution
            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == event_wait.execution_id
            ).first()
            if execution and execution.status == ExecutionStatus.PAUSED:
                execution.status = ExecutionStatus.CANCELLED
                execution.completed_at = datetime.utcnow()

            db.commit()
            return event_wait


# Singleton instance
event_wait_service = EventWaitService()
