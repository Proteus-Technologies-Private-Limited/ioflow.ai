"""
Human in the Loop (HITL) Service - Core business logic for task completion and flow resumption.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from db.models import (
    HITLTask, HITLTaskAssignment, HITLRole, HITLUserRole,
    FlowExecution, Flow, ExecutionStatus, User
)
from db.database import get_tenant_db
from services.execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)


class HITLService:
    """Core service for HITL task management."""

    def is_user_assigned(self, task: HITLTask, user_id: str, db: Session) -> bool:
        """Check if a user is assigned to a task (directly or via HITL role).

        When no assignments exist, any tenant user can complete the task
        (fallback for HITL nodes with no user/role configured).
        """
        assignments = db.query(HITLTaskAssignment).filter(
            HITLTaskAssignment.task_id == task.task_id
        ).all()

        # No assignments configured — allow the executing user to complete
        if not assignments:
            return True

        for assignment in assignments:
            if assignment.assignee_type == 'user' and assignment.assignee_id == user_id:
                return True
            elif assignment.assignee_type == 'hitl_role':
                # Check if user has this HITL role
                user_role = db.query(HITLUserRole).filter(
                    HITLUserRole.user_id == user_id,
                    HITLUserRole.hitl_role_id == assignment.assignee_id
                ).first()
                if user_role:
                    return True
        return False

    def get_user_hitl_role_ids(self, user_id: str, tenant_id: str, db: Session) -> List[str]:
        """Get all HITL role IDs for a user."""
        user_roles = db.query(HITLUserRole).filter(
            HITLUserRole.user_id == user_id,
            HITLUserRole.tenant_id == tenant_id
        ).all()
        return [ur.hitl_role_id for ur in user_roles]

    def get_user_tasks(self, user_id: str, tenant_id: str, db: Session,
                       status: Optional[str] = None,
                       limit: int = 50, offset: int = 0) -> tuple:
        """Get tasks assigned to a user (directly or via roles). Returns (tasks, total_count)."""
        user_role_ids = self.get_user_hitl_role_ids(user_id, tenant_id, db)

        query = db.query(HITLTask).join(HITLTaskAssignment).filter(
            HITLTask.tenant_id == tenant_id,
            or_(
                and_(
                    HITLTaskAssignment.assignee_type == 'user',
                    HITLTaskAssignment.assignee_id == user_id
                ),
                and_(
                    HITLTaskAssignment.assignee_type == 'hitl_role',
                    HITLTaskAssignment.assignee_id.in_(user_role_ids)
                ) if user_role_ids else False
            )
        ).distinct()

        if status:
            query = query.filter(HITLTask.status == status)

        total = query.count()
        tasks = query.order_by(HITLTask.created_at.desc()).offset(offset).limit(limit).all()
        return tasks, total

    def get_task_stats(self, user_id: str, tenant_id: str, db: Session) -> Dict[str, int]:
        """Get task statistics for a user."""
        user_role_ids = self.get_user_hitl_role_ids(user_id, tenant_id, db)

        base_query = db.query(HITLTask).join(HITLTaskAssignment).filter(
            HITLTask.tenant_id == tenant_id,
            or_(
                and_(
                    HITLTaskAssignment.assignee_type == 'user',
                    HITLTaskAssignment.assignee_id == user_id
                ),
                and_(
                    HITLTaskAssignment.assignee_type == 'hitl_role',
                    HITLTaskAssignment.assignee_id.in_(user_role_ids)
                ) if user_role_ids else False
            )
        ).distinct()

        pending = base_query.filter(HITLTask.status == 'pending').count()
        completed = base_query.filter(HITLTask.status == 'completed').count()
        expired = base_query.filter(HITLTask.status == 'expired').count()
        escalated = base_query.filter(HITLTask.status == 'escalated').count()
        cancelled = base_query.filter(HITLTask.status == 'cancelled').count()
        urgent = base_query.filter(
            HITLTask.status == 'pending',
            HITLTask.priority.in_(['high', 'critical'])
        ).count()

        return {
            'pending': pending,
            'completed': completed,
            'expired': expired,
            'escalated': escalated,
            'cancelled': cancelled,
            'urgent': urgent,
        }

    async def complete_task(self, task_id: str, user_id: str,
                            response_action: str,
                            response_data: Optional[Dict[str, Any]],
                            comment: Optional[str],
                            tenant_id: str,
                            schema_name: str) -> HITLTask:
        """Complete a HITL task and resume flow execution."""
        with get_tenant_db(schema_name) as db:
            # Lock the task row to prevent concurrent completion
            task = db.query(HITLTask).filter(
                HITLTask.task_id == task_id,
                HITLTask.tenant_id == tenant_id,
            ).with_for_update().first()

            if not task:
                raise ValueError(f"Task {task_id} not found")

            if task.status != 'pending':
                raise ValueError(f"Task {task_id} is already {task.status}")

            # Verify user is assigned
            if not self.is_user_assigned(task, user_id, db):
                raise PermissionError(f"User {user_id} is not assigned to task {task_id}")

            # Update the task
            if comment and response_data:
                response_data['_comment'] = comment
            elif comment:
                response_data = {'_comment': comment}

            # Store response data on the task but keep status as pending until flow resumes
            task.response_action = response_action
            task.response_data = response_data
            task.completed_by = user_id
            db.commit()

            # Build HITL output for the flow
            completed_at = datetime.utcnow()
            hitl_output = {
                'response_action': response_action,
                'response_data': response_data or {},
                'completed_by': user_id,
                'completed_at': completed_at.isoformat(),
                'task_type': task.task_type,
                'input_data': task.input_data,
                'task_id': task_id,
            }

            # Get flow definition to resume execution
            flow = db.query(Flow).filter(Flow.flow_id == task.flow_id).first()
            if not flow:
                raise ValueError(f"Flow {task.flow_id} not found")

            flow_definition = flow.flow_definition

        # Mark task as completed immediately so the API can respond
        with get_tenant_db(schema_name) as db:
            task = db.query(HITLTask).filter(HITLTask.task_id == task_id).first()
            if task:
                task.status = 'completed'
                task.completed_at = completed_at
                db.commit()

        # Check if this is a debug execution
        is_debug = False
        with get_tenant_db(schema_name) as db:
            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == task.execution_id
            ).first()
            if execution and execution.execution_data:
                is_debug = execution.execution_data.get('debug_mode', False)

        if is_debug:
            # Debug mode: update debug state and let debug stepping continue
            from services.debug_execution_manager import DebugExecutionManager
            from services.websocket_manager import manager as ws_manager

            debug_state = DebugExecutionManager.get_debug_state(schema_name, task.execution_id, tenant_id)
            if debug_state:
                # Inject HITL output as the node's output
                debug_state['node_outputs'][task.node_id] = hitl_output
                debug_state['context_data'] = hitl_output

                # Find next node from the HITL node
                edges = debug_state.get('flow_definition', {}).get('edges', [])
                next_nodes = [e['target'] for e in edges if e['source'] == task.node_id]

                if next_nodes:
                    debug_state['current_node'] = next_nodes[0]
                    debug_state['status'] = 'waiting_for_step'
                else:
                    debug_state['status'] = 'completed'
                    debug_state['current_node'] = None

                # Clear HITL tracking fields
                debug_state.pop('hitl_task_id', None)
                debug_state.pop('hitl_node_id', None)

                # Update execution status back to RUNNING
                with get_tenant_db(schema_name) as db:
                    execution = db.query(FlowExecution).filter(
                        FlowExecution.execution_id == task.execution_id
                    ).first()
                    if execution:
                        execution.status = ExecutionStatus.RUNNING
                        db.commit()

                # Save updated debug state
                DebugExecutionManager.save_debug_state(schema_name, task.execution_id, debug_state, tenant_id)

                # Send WebSocket events
                await ws_manager.send_execution_update(
                    execution_id=task.execution_id,
                    tenant_id=tenant_id,
                    update_data={
                        'type': 'hitl_task_completed',
                        'node_id': task.node_id,
                        'task_id': task_id,
                        'response_action': hitl_output.get('response_action'),
                        'completed_by': hitl_output.get('completed_by'),
                    }
                )

                if debug_state['status'] == 'waiting_for_step':
                    await ws_manager.send_execution_update(
                        execution_id=task.execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'waiting_for_step',
                            'node_id': debug_state['current_node'],
                            'executed_nodes': debug_state['executed_nodes'],
                        }
                    )
                elif debug_state['status'] == 'completed':
                    await ws_manager.send_execution_update(
                        execution_id=task.execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'execution_complete',
                            'status': 'completed',
                        }
                    )

            return task

        # Normal (non-debug) mode: Resume flow execution in the background
        import asyncio

        async def _resume_flow():
            try:
                engine = ExecutionEngine(schema_name, tenant_id=tenant_id, user_id=user_id)
                await engine.resume_after_hitl(
                    task_id=task_id,
                    hitl_output=hitl_output,
                    flow_definition=flow_definition,
                    tenant_schema=schema_name,
                )
            except Exception as e:
                logger.error(f"Flow resumption failed for task {task_id}: {e}", exc_info=True)

        asyncio.ensure_future(_resume_flow())

        return task

    async def complete_task_by_token(self, task_token: str,
                                      response_action: str,
                                      response_data: Optional[Dict[str, Any]],
                                      schema_name: str) -> HITLTask:
        """Complete a HITL task using a secure token (for email-based actions)."""
        with get_tenant_db(schema_name) as db:
            task = db.query(HITLTask).filter(
                HITLTask.task_token == task_token,
            ).first()

            if not task:
                raise ValueError("Invalid task token")

            if task.status != 'pending':
                raise ValueError(f"Task is already {task.status}")

        # Use a system user ID for token-based completion
        return await self.complete_task(
            task_id=task.task_id,
            user_id='system_token',
            response_action=response_action,
            response_data=response_data,
            comment=None,
            tenant_id=task.tenant_id,
            schema_name=schema_name,
        )

    def cancel_task(self, task_id: str, tenant_id: str, db: Session) -> HITLTask:
        """Cancel a HITL task and fail the associated execution."""
        task = db.query(HITLTask).filter(
            HITLTask.task_id == task_id,
            HITLTask.tenant_id == tenant_id,
        ).first()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status != 'pending':
            raise ValueError(f"Task {task_id} is already {task.status}")

        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()

        # Also cancel the execution
        execution = db.query(FlowExecution).filter(
            FlowExecution.execution_id == task.execution_id
        ).first()
        if execution and execution.status == ExecutionStatus.PAUSED:
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.utcnow()

        db.commit()
        return task

    def reassign_task(self, task_id: str, tenant_id: str,
                      assignee_type: str, assignee_ids: List[str],
                      db: Session) -> HITLTask:
        """Reassign a HITL task to different users/roles."""
        import uuid

        task = db.query(HITLTask).filter(
            HITLTask.task_id == task_id,
            HITLTask.tenant_id == tenant_id,
        ).first()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status != 'pending':
            raise ValueError(f"Task {task_id} is already {task.status}")

        # Remove existing assignments
        db.query(HITLTaskAssignment).filter(
            HITLTaskAssignment.task_id == task_id
        ).delete()

        # Create new assignments
        for aid in assignee_ids:
            assignment = HITLTaskAssignment(
                id=str(uuid.uuid4()),
                task_id=task_id,
                assignee_type=assignee_type,
                assignee_id=aid,
                tenant_id=tenant_id,
            )
            db.add(assignment)

        db.commit()
        return task


# Singleton instance
hitl_service = HITLService()
