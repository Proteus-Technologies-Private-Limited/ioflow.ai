"""
Enhanced Cost Tracking Finalization Patch
This patch ensures cost tracking is finalized when flows complete
"""
import logging
import json
from typing import Dict, Any
from datetime import datetime

from services.cost_tracking_service import cost_tracking_service
from db.database import get_db, get_tenant_db
from db.models import Flow

logger = logging.getLogger(__name__)


def apply_cost_finalization_patch():
    """Apply cost tracking finalization patch to ExecutionEngine"""
    from services.execution_engine import ExecutionEngine

    # Store original methods
    original_execute_flow_definition = ExecutionEngine._execute_flow_definition
    original_execute_service = ExecutionEngine._execute_service_with_type
    original_execute_action = ExecutionEngine._execute_action_node

    async def patched_execute_flow_definition(self, execution_id: str, flow_definition: Dict,
                                             trigger_data: Dict[str, Any], trigger_type: str):
        """Execute flow definition with cost tracking finalization"""
        try:
            # Get flow info for cost tracking initialization
            tenant_id = self.tenant_id or self.tenant_schema
            flow_id = None
            flow_name = None

            with get_tenant_db(self.tenant_schema) as db:
                from db.models import FlowExecution
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == execution_id
                ).first()
                if execution:
                    flow_id = execution.flow_id
                    flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
                    if flow:
                        flow_name = flow.flow_name

            # Initialize cost tracking for this execution
            if execution_id not in cost_tracking_service.execution_costs:
                cost_tracking_service.start_execution(
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    flow_id=flow_id,
                    flow_name=flow_name or flow_id,
                    trigger_type=trigger_type
                )
                logger.info(f"Cost tracking initialized for execution {execution_id}")

            # Execute the original flow definition
            result = await original_execute_flow_definition(self, execution_id, flow_definition,
                                                          trigger_data, trigger_type)

            # After flow completes, finalize cost tracking
            logger.info(f"Flow definition execution completed for {execution_id}, finalizing cost tracking")
            cost_log = cost_tracking_service.finalize_execution(execution_id)
            if cost_log:
                logger.info(f"✅ Cost tracking finalized for execution {execution_id}")
            else:
                logger.info(f"⚠️ No cost log created for execution {execution_id} (may be free or no services)")

            return result

        except Exception as e:
            logger.error(f"Error in cost-tracked flow definition execution: {str(e)}")
            # Try to finalize on error
            try:
                cost_tracking_service.finalize_execution(execution_id)
            except:
                pass
            raise

    async def patched_execute_action(self, node_data, context):
        """Execute action node with cost tracking initialization"""
        # Ensure cost tracking is initialized
        execution_id = context.get('execution_id')
        if execution_id and execution_id not in cost_tracking_service.execution_costs:
            flow_id = context.get('flow_id')
            flow_name = context.get('flow_name', flow_id)
            trigger_type = context.get('trigger_type', 'manual')
            tenant_id = self.tenant_id or self.tenant_schema

            cost_tracking_service.start_execution(
                execution_id=execution_id,
                tenant_id=tenant_id,
                flow_id=flow_id,
                flow_name=flow_name,
                trigger_type=trigger_type
            )
            logger.info(f"Cost tracking initialized in action for execution {execution_id}")

        # Execute the original action
        return await original_execute_action(self, node_data, context)

    async def patched_execute_service(self, service_obj, subscription, parameters, context, is_simulation=False):
        """Execute service with cost tracking"""
        try:
            # Execute the original service
            result = await original_execute_service(self, service_obj, subscription, parameters,
                                                   context, is_simulation)

            # Track the service call if not simulated
            if not is_simulation and 'execution_id' in context:
                execution_id = context['execution_id']

                # Ensure cost tracking is initialized
                if execution_id not in cost_tracking_service.execution_costs:
                    flow_id = context.get('flow_id')
                    flow_name = context.get('flow_name', flow_id)
                    trigger_type = context.get('trigger_type', 'manual')
                    tenant_id = self.tenant_id or self.tenant_schema

                    cost_tracking_service.start_execution(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        flow_id=flow_id,
                        flow_name=flow_name,
                        trigger_type=trigger_type
                    )

                # Track the service call
                app_id = service_obj.app_id
                service_id = service_obj.service_id
                service_name = service_obj.service_name

                cost_tracking_service.track_service_call(
                    execution_id=execution_id,
                    app_id=app_id,
                    service_id=service_id,
                    service_name=service_name,
                    request_data=parameters,
                    response_data=result
                )

                logger.info(f"Tracked service: {app_id}/{service_name} for execution {execution_id}")

            return result

        except Exception as e:
            logger.error(f"Error in cost-tracked service execution: {str(e)}")
            raise

    # Apply patches
    ExecutionEngine._execute_flow_definition = patched_execute_flow_definition
    ExecutionEngine._execute_service_with_type = patched_execute_service
    ExecutionEngine._execute_action_node = patched_execute_action

    logger.info("ExecutionEngine patched with cost tracking finalization")


def remove_cost_finalization_patch():
    """Remove the cost tracking patch (for testing)"""
    from services.execution_engine import ExecutionEngine

    # Restore original methods if they exist
    if hasattr(ExecutionEngine._execute_flow_definition, '__wrapped__'):
        ExecutionEngine._execute_flow_definition = ExecutionEngine._execute_flow_definition.__wrapped__
    if hasattr(ExecutionEngine._execute_service_with_type, '__wrapped__'):
        ExecutionEngine._execute_service_with_type = ExecutionEngine._execute_service_with_type.__wrapped__
    if hasattr(ExecutionEngine._execute_action_node, '__wrapped__'):
        ExecutionEngine._execute_action_node = ExecutionEngine._execute_action_node.__wrapped__

    logger.info("Cost tracking patch removed")