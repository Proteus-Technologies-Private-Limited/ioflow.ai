"""
Patch for ExecutionEngine to add cost tracking functionality
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from db.models import Flow, FlowExecution
from db.application_models import Application
from services.cost_calculator import cost_calculator
from db.database import get_db

logger = logging.getLogger(__name__)


class CostTrackingMixin:
    """Mixin to add cost tracking capabilities to ExecutionEngine"""
    
    def __init__(self):
        # Cost tracking counters
        self.cost_metrics = {
            'incoming_events': 0,
            'outgoing_services': 0,
            'data_transfer_kb': 0,
            'token_count': 0,
            'app_id': None,
            'tenant_id': None
        }
    
    def reset_cost_metrics(self):
        """Reset cost metrics for new execution"""
        self.cost_metrics = {
            'incoming_events': 0,
            'outgoing_services': 0,
            'data_transfer_kb': 0,
            'token_count': 0,
            'app_id': None,
            'tenant_id': None
        }
    
    def track_incoming_event(self, app_id: str, tenant_id: str, data: Dict[str, Any]):
        """Track an incoming event for cost calculation"""
        self.cost_metrics['incoming_events'] += 1
        self.cost_metrics['app_id'] = app_id
        self.cost_metrics['tenant_id'] = tenant_id
        
        # Estimate data size
        if data:
            self.cost_metrics['data_transfer_kb'] += cost_calculator.estimate_data_transfer_kb(data)
    
    def track_outgoing_service(self, app_id: str, request_data: Dict[str, Any], response_data: Dict[str, Any]):
        """Track an outgoing service call for cost calculation"""
        self.cost_metrics['outgoing_services'] += 1
        
        # Track data transfer
        if request_data:
            self.cost_metrics['data_transfer_kb'] += cost_calculator.estimate_data_transfer_kb(request_data)
        if response_data:
            self.cost_metrics['data_transfer_kb'] += cost_calculator.estimate_data_transfer_kb(response_data)
    
    def track_llm_usage(self, prompt: str, response: str, model: str = "gpt-3.5"):
        """Track LLM token usage"""
        if prompt:
            self.cost_metrics['token_count'] += cost_calculator.count_llm_tokens(prompt, model)
        if response:
            self.cost_metrics['token_count'] += cost_calculator.count_llm_tokens(response, model)
    
    def finalize_cost_tracking(self, execution_id: str, flow_id: str, flow_name: str, 
                             trigger_type: str, tenant_schema: str):
        """Finalize cost tracking and create cost log"""
        try:
            # Only track if we have an app_id and actual usage
            if (self.cost_metrics['app_id'] and 
                (self.cost_metrics['incoming_events'] > 0 or 
                 self.cost_metrics['outgoing_services'] > 0)):
                
                # Get main database session for cost tracking
                with next(get_db()) as db:
                    # Check if cost tracking is enabled
                    if not cost_calculator.should_track_cost(self.cost_metrics['app_id'], db):
                        logger.info(f"Cost tracking not enabled for app {self.cost_metrics['app_id']}")
                        return
                    
                    # Create cost log
                    cost_log = cost_calculator.create_cost_log(
                        execution_id=execution_id,
                        app_id=self.cost_metrics['app_id'],
                        tenant_id=self.cost_metrics['tenant_id'],
                        flow_id=flow_id,
                        flow_name=flow_name,
                        trigger_type=trigger_type,
                        incoming_events=self.cost_metrics['incoming_events'],
                        outgoing_services=self.cost_metrics['outgoing_services'],
                        data_transfer_kb=self.cost_metrics['data_transfer_kb'],
                        token_count=self.cost_metrics['token_count'],
                        db=db
                    )
                    
                    if cost_log:
                        logger.info(f"Created cost log for execution {execution_id}: "
                                  f"{cost_log.total_cost} {cost_log.currency}")
        
        except Exception as e:
            logger.error(f"Error finalizing cost tracking: {str(e)}")
        finally:
            # Reset metrics for next execution
            self.reset_cost_metrics()


def patch_execution_engine():
    """
    Patch the ExecutionEngine class to add cost tracking
    This should be called during application startup
    """
    from services.execution_engine import ExecutionEngine
    
    # Store original methods
    original_init = ExecutionEngine.__init__
    original_execute_flow = ExecutionEngine.execute_flow
    original_execute_action = ExecutionEngine._execute_action_node
    
    # Create cost tracking instance
    cost_tracker = CostTrackingMixin()
    
    def new_init(self, tenant_schema: str, tenant_id: str = None, user_id: str = None):
        # Call original init with all parameters
        original_init(self, tenant_schema=tenant_schema, tenant_id=tenant_id, user_id=user_id)
        self.cost_tracker = CostTrackingMixin()
    
    async def new_execute_flow(self, flow_id: str, trigger_data: Dict[str, Any], trigger_type: str = "manual"):
        """Execute flow with cost tracking"""
        # Reset cost metrics
        self.cost_tracker.reset_cost_metrics()
        
        try:
            # Get flow info for cost tracking
            flow_name = None
            tenant_id = None
            
            from db.database import get_tenant_db
            with get_tenant_db(self.tenant_schema) as db:
                flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
                if flow:
                    flow_name = flow.flow_name
                    # Get tenant_id from schema name or from trigger data
                    # This is a simplified approach - adjust based on your tenant structure
                    tenant_id = trigger_data.get('tenant_id')
            
            # Track incoming event if from an application trigger
            if trigger_type in ['webhook', 'api_call', 'email', 'form']:
                app_id = trigger_data.get('app_id')
                if app_id and tenant_id:
                    self.cost_tracker.track_incoming_event(app_id, tenant_id, trigger_data)
            
            # Call original method
            result = await original_execute_flow(self, flow_id, trigger_data, trigger_type)
            
            # Get execution_id from the last execution
            execution_id = None
            with get_tenant_db(self.tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.flow_id == flow_id
                ).order_by(FlowExecution.started_at.desc()).first()
                if execution:
                    execution_id = execution.execution_id
            
            # Finalize cost tracking
            if execution_id:
                self.cost_tracker.finalize_cost_tracking(
                    execution_id=execution_id,
                    flow_id=flow_id,
                    flow_name=flow_name or flow_id,
                    trigger_type=trigger_type,
                    tenant_schema=self.tenant_schema
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in cost-tracked flow execution: {str(e)}")
            raise
    
    async def new_execute_action(self, node_data: Dict[str, Any], context: Dict[str, Any]):
        """Execute action with cost tracking"""
        result = await original_execute_action(self, node_data, context)
        
        # Track outgoing service call
        app_id = node_data.get('appId') or node_data.get('app_id')
        if app_id and hasattr(self, 'cost_tracker'):
            # Extract request/response data from context
            request_data = node_data.get('parameters', {})
            self.cost_tracker.track_outgoing_service(app_id, request_data, result)
        
        return result
    
    # Apply patches
    ExecutionEngine.__init__ = new_init
    ExecutionEngine.execute_flow = new_execute_flow
    ExecutionEngine._execute_action_node = new_execute_action
    
    logger.info("ExecutionEngine patched with cost tracking capabilities")