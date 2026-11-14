"""
Enhanced Cost Tracking Patch for ExecutionEngine
This patch integrates cost tracking into the flow execution process
"""
import logging
import json
from typing import Dict, Any
from datetime import datetime

from services.cost_tracking_service import cost_tracking_service
from db.database import get_db, get_tenant_db
from db.models import Flow

logger = logging.getLogger(__name__)


def apply_cost_tracking_patch():
    """Apply cost tracking patch to ExecutionEngine"""
    from services.execution_engine import ExecutionEngine

    # Store original methods
    original_execute_flow = ExecutionEngine.execute_flow
    original_execute_service = ExecutionEngine._execute_service_with_type
    original_execute_action = ExecutionEngine._execute_action_node

    async def patched_execute_flow(self, flow_id: str, trigger_data: Dict[str, Any], trigger_type: str = "manual"):
        """Execute flow with cost tracking"""
        from db.models import FlowExecution
        execution_id = None
        tenant_id = None
        flow_name = None

        try:
            # Get flow info
            with get_tenant_db(self.tenant_schema) as db:
                flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
                if flow:
                    flow_name = flow.flow_name
                    # Get tenant_id - for SQLite, it's the same as tenant_schema
                    tenant_id = self.tenant_id or self.tenant_schema

            # Call original method (doesn't return execution_id)
            await original_execute_flow(self, flow_id, trigger_data, trigger_type)

            # Get the execution_id from the database
            # The execution was just created, so get the latest one for this flow
            with get_tenant_db(self.tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.flow_id == flow_id
                ).order_by(FlowExecution.started_at.desc()).first()

                if execution:
                    execution_id = execution.execution_id
                    logger.info(f"Flow execution completed: {execution_id}")

                    # Finalize cost tracking
                    cost_log = cost_tracking_service.finalize_execution(execution_id)
                    if cost_log:
                        logger.info(f"Cost tracking finalized for execution {execution_id}")
                    else:
                        logger.info(f"No cost log created for execution {execution_id}")
                else:
                    logger.warning(f"Could not find execution for flow {flow_id}")

        except Exception as e:
            logger.error(f"Error in cost-tracked flow execution: {str(e)}")
            # Clean up cost tracking on error
            if execution_id:
                try:
                    cost_tracking_service.finalize_execution(execution_id)
                except:
                    pass
            raise

    async def patched_execute_service(self, service_obj, subscription, parameters, context, is_simulation=False):
        """Execute service with cost tracking"""
        result = None
        try:
            # Execute the original service
            result = await original_execute_service(self, service_obj, subscription, parameters, context, is_simulation)

            # Track the service call if not simulated
            if not is_simulation and 'execution_id' in context:
                execution_id = context['execution_id']
                app_id = service_obj.app_id
                service_id = service_obj.service_id
                service_name = service_obj.service_name

                # Track the service call
                cost_tracking_service.track_service_call(
                    execution_id=execution_id,
                    app_id=app_id,
                    service_id=service_id,
                    service_name=service_name,
                    request_data=parameters,
                    response_data=result
                )

                logger.info(f"Tracked service call: {app_id}/{service_name} for execution {execution_id}")

            return result

        except Exception as e:
            logger.error(f"Error in cost-tracked service execution: {str(e)}")
            raise

    async def patched_execute_action(self, node_data, context):
        """Execute action node with cost tracking initialization"""
        # Initialize cost tracking if this is the first node
        execution_id = context.get('execution_id')
        if execution_id and execution_id not in cost_tracking_service.execution_costs:
            flow_id = context.get('flow_id')
            flow_name = context.get('flow_name', flow_id)
            trigger_type = context.get('trigger_type', 'manual')
            tenant_id = self.tenant_id or self.tenant_schema

            # Initialize cost tracking for this execution
            cost_tracking_service.start_execution(
                execution_id=execution_id,
                tenant_id=tenant_id,
                flow_id=flow_id,
                flow_name=flow_name,
                trigger_type=trigger_type
            )
            logger.info(f"Initialized cost tracking for execution {execution_id}")

        # Execute the original action
        result = await original_execute_action(self, node_data, context)

        return result

    # Apply patches
    ExecutionEngine.execute_flow = patched_execute_flow
    ExecutionEngine._execute_service_with_type = patched_execute_service
    ExecutionEngine._execute_action_node = patched_execute_action

    logger.info("ExecutionEngine patched with enhanced cost tracking")


def remove_cost_tracking_patch():
    """Remove the cost tracking patch (for testing)"""
    from services.execution_engine import ExecutionEngine

    # Restore original methods if they exist
    if hasattr(ExecutionEngine.execute_flow, '__wrapped__'):
        ExecutionEngine.execute_flow = ExecutionEngine.execute_flow.__wrapped__
    if hasattr(ExecutionEngine._execute_service_with_type, '__wrapped__'):
        ExecutionEngine._execute_service_with_type = ExecutionEngine._execute_service_with_type.__wrapped__
    if hasattr(ExecutionEngine._execute_action_node, '__wrapped__'):
        ExecutionEngine._execute_action_node = ExecutionEngine._execute_action_node.__wrapped__

    logger.info("Cost tracking patch removed")