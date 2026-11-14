"""
Flow Execution Bridge Service

Bridges the gap between application service calls and flow execution,
allowing published flow-based applications to work seamlessly like traditional applications.
"""

import json
import uuid
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from .parameter_mapper import ParameterMapper, ParameterMapping, MappingResult
from .execution_engine import ExecutionEngine
from db.application_models import (
    PublishedApplication, FlowExecutionBridge, ParameterMapping as DBParameterMapping,
    Application, ApplicationService
)
from db.models import Flow, FlowExecution, ExecutionStatus
from db.db_compat import parse_json_field
from core.config import settings

logger = logging.getLogger(__name__)


class ExecutionBridgeError(Exception):
    """Custom exception for execution bridge errors"""
    pass


class FlowExecutionBridgeService:
    """Bridges application service calls to flow execution"""

    def __init__(self):
        self.parameter_mapper = ParameterMapper()
        # ExecutionEngine requires tenant_schema, so we create it per-request
        self.pending_executions = {}  # Cache for async executions

    def _get_execution_engine(self, tenant_schema: str = 'default') -> ExecutionEngine:
        """Get an execution engine for the given tenant schema"""
        return ExecutionEngine(tenant_schema=tenant_schema)
    
    async def execute_flow_service(self,
                                 db: Session,
                                 app_key: str,
                                 service_name: str,
                                 parameters: Dict[str, Any],
                                 user_id: str = None,
                                 tenant_id: str = None,
                                 sync_mode: bool = False,
                                 timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Execute a flow-based service
        
        Args:
            db: Database session
            app_key: Application key
            service_name: Service name to execute
            parameters: Service parameters
            user_id: User ID for execution context
            tenant_id: Tenant ID for execution context
            sync_mode: Whether to execute synchronously
            timeout_seconds: Timeout for synchronous execution
            
        Returns:
            Dictionary with execution result
        """
        logger.info(f"Executing flow service: {app_key}.{service_name}")
        
        try:
            # 1. Get published application
            published_app = self._get_published_application(db, app_key)
            if not published_app:
                raise ExecutionBridgeError(f"Published application '{app_key}' not found")
            
            # 2. Get service configuration
            service_config = self._get_service_config(db, published_app.app_id, service_name)
            if not service_config:
                raise ExecutionBridgeError(f"Service '{service_name}' not found in application '{app_key}'")
            
            # 3. Get parameter mappings
            parameter_mappings = self._get_parameter_mappings(db, published_app.published_app_id, service_name)
            
            # 4. Map service parameters to flow variables
            mapping_result = self._map_service_parameters_to_flow(
                parameters, parameter_mappings, published_app.flow_analysis
            )
            
            if not mapping_result.success:
                raise ExecutionBridgeError(f"Parameter mapping failed: {mapping_result.errors}")
            
            # 5. Generate unique service call ID
            service_call_id = str(uuid.uuid4())
            
            # 6. Create execution bridge record
            bridge_record = self._create_bridge_record(
                db=db,
                published_app_id=published_app.published_app_id,
                service_call_id=service_call_id,
                input_parameters=parameters,
                mapped_parameters=mapping_result.mapped_parameters
            )
            
            # 7. Execute the flow
            if sync_mode or published_app.application.flow_based_config.get('force_sync', False):
                result = await self._execute_flow_sync(
                    db=db,
                    flow_id=published_app.flow_id,
                    mapped_parameters=mapping_result.mapped_parameters,
                    bridge_record=bridge_record,
                    timeout_seconds=timeout_seconds,
                    user_id=user_id,
                    tenant_id=tenant_id
                )
            else:
                result = await self._execute_flow_async(
                    db=db,
                    flow_id=published_app.flow_id,
                    mapped_parameters=mapping_result.mapped_parameters,
                    bridge_record=bridge_record,
                    user_id=user_id,
                    tenant_id=tenant_id
                )
            
            # 8. Update usage count
            published_app.usage_count += 1
            db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing flow service {app_key}.{service_name}: {str(e)}")
            db.rollback()
            raise ExecutionBridgeError(f"Flow service execution failed: {str(e)}")
    
    async def _execute_flow_sync(self,
                               db: Session,
                               flow_id: str,
                               mapped_parameters: Dict[str, Any],
                               bridge_record: FlowExecutionBridge,
                               timeout_seconds: int,
                               user_id: str = None,
                               tenant_id: str = None) -> Dict[str, Any]:
        """Execute flow synchronously and return result"""
        start_time = datetime.now()
        
        try:
            # Update bridge record status
            bridge_record.execution_status = 'running'
            db.commit()
            
            # Execute flow with timeout
            execution_engine = self._get_execution_engine()
            execution_result = await asyncio.wait_for(
                execution_engine.execute_flow_sync(
                    flow_id=flow_id,
                    input_variables=mapped_parameters,
                    user_id=user_id,
                    tenant_id=tenant_id
                ),
                timeout=timeout_seconds
            )
            
            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update bridge record with success
            bridge_record.execution_status = 'completed'
            bridge_record.execution_result = json.dumps(execution_result)
            bridge_record.completed_at = end_time
            bridge_record.execution_time_ms = execution_time_ms
            
            # Handle both string and dict execution results
            execution_id = None
            if isinstance(execution_result, dict):
                execution_id = execution_result.get('execution_id')
            elif isinstance(execution_result, str):
                # For text format flows, we don't have an execution_id in the response
                # We can try to get it from the context or generate one if needed
                execution_id = None
            
            bridge_record.execution_id = execution_id
            
            db.commit()
            
            # Format result for service response
            formatted_result = self._format_sync_result(execution_result)
            
            return {
                "success": True,
                "data": formatted_result,
                "execution_id": execution_id,
                "execution_time_ms": execution_time_ms,
                "service_call_id": bridge_record.service_call_id
            }
            
        except asyncio.TimeoutError:
            # Handle timeout
            bridge_record.execution_status = 'failed'
            bridge_record.error_details = json.dumps({
                "error": "timeout",
                "message": f"Execution timed out after {timeout_seconds} seconds"
            })
            bridge_record.completed_at = datetime.now()
            db.commit()
            
            raise ExecutionBridgeError(f"Flow execution timed out after {timeout_seconds} seconds")
            
        except Exception as e:
            # Handle execution error
            bridge_record.execution_status = 'failed'
            bridge_record.error_details = json.dumps({
                "error": "execution_error",
                "message": str(e)
            })
            bridge_record.completed_at = datetime.now()
            db.commit()
            
            raise ExecutionBridgeError(f"Flow execution failed: {str(e)}")
    
    async def _execute_flow_async(self,
                                db: Session,
                                flow_id: str,
                                mapped_parameters: Dict[str, Any],
                                bridge_record: FlowExecutionBridge,
                                user_id: str = None,
                                tenant_id: str = None) -> Dict[str, Any]:
        """Execute flow asynchronously and return execution ID"""
        try:
            # Update bridge record status
            bridge_record.execution_status = 'running'
            db.commit()
            
            # Start async execution
            execution_engine = self._get_execution_engine()
            execution_result = await execution_engine.execute_flow_async(
                flow_id=flow_id,
                input_variables=mapped_parameters,
                user_id=user_id,
                tenant_id=tenant_id
            )
            
            # Handle both string and dict execution results
            execution_id = None
            if isinstance(execution_result, dict):
                execution_id = execution_result.get('execution_id')
            elif isinstance(execution_result, str):
                # For text format flows, we don't have an execution_id in the response
                execution_id = None
            
            # Update bridge record with execution ID
            bridge_record.execution_id = execution_id
            db.commit()
            
            # Store in pending executions for status tracking
            self.pending_executions[bridge_record.service_call_id] = {
                "execution_id": execution_id,
                "bridge_id": bridge_record.bridge_id,
                "started_at": datetime.now()
            }
            
            return {
                "success": True,
                "execution_id": execution_id,
                "service_call_id": bridge_record.service_call_id,
                "status": "running",
                "message": "Flow execution started"
            }
            
        except Exception as e:
            # Handle execution error
            bridge_record.execution_status = 'failed'
            bridge_record.error_details = json.dumps({
                "error": "start_error",
                "message": str(e)
            })
            bridge_record.completed_at = datetime.now()
            db.commit()
            
            raise ExecutionBridgeError(f"Failed to start flow execution: {str(e)}")
    
    def get_execution_status(self,
                           db: Session,
                           service_call_id: str) -> Dict[str, Any]:
        """Get execution status for a service call"""
        try:
            bridge_record = db.query(FlowExecutionBridge).filter(
                FlowExecutionBridge.service_call_id == service_call_id
            ).first()
            
            if not bridge_record:
                return {
                    "success": False,
                    "error": f"Service call '{service_call_id}' not found"
                }
            
            result = {
                "success": True,
                "service_call_id": service_call_id,
                "execution_id": bridge_record.execution_id,
                "status": bridge_record.execution_status,
                "started_at": bridge_record.started_at.isoformat(),
                "completed_at": bridge_record.completed_at.isoformat() if bridge_record.completed_at else None,
                "execution_time_ms": bridge_record.execution_time_ms
            }
            
            if bridge_record.execution_status == 'completed':
                result["data"] = parse_json_field(bridge_record.execution_result)
            elif bridge_record.execution_status == 'failed':
                result["error_details"] = parse_json_field(bridge_record.error_details)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting execution status for {service_call_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get execution status: {str(e)}"
            }
    
    def get_execution_result(self,
                           db: Session,
                           service_call_id: str) -> Dict[str, Any]:
        """Get execution result for a completed service call"""
        try:
            bridge_record = db.query(FlowExecutionBridge).filter(
                FlowExecutionBridge.service_call_id == service_call_id
            ).first()
            
            if not bridge_record:
                return {
                    "success": False,
                    "error": f"Service call '{service_call_id}' not found"
                }
            
            if bridge_record.execution_status != 'completed':
                return {
                    "success": False,
                    "error": f"Execution not completed. Current status: {bridge_record.execution_status}"
                }
            
            result_data = parse_json_field(bridge_record.execution_result) or {}
            
            return {
                "success": True,
                "data": result_data,
                "execution_time_ms": bridge_record.execution_time_ms,
                "completed_at": bridge_record.completed_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting execution result for {service_call_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get execution result: {str(e)}"
            }
    
    async def execute_transform_service(self,
                                      db: Session,
                                      app_key: str,
                                      transform_node_id: str,
                                      parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific transformation from a flow"""
        try:
            # Get published application
            published_app = self._get_published_application(db, app_key)
            if not published_app:
                raise ExecutionBridgeError(f"Published application '{app_key}' not found")
            
            # Parse flow analysis to get transformation info
            flow_analysis = parse_json_field(published_app.flow_analysis) or {}
            transformations = flow_analysis.get('transformations', [])
            
            # Find the specific transformation
            target_transform = None
            for transform in transformations:
                if transform.get('node_id') == transform_node_id:
                    target_transform = transform
                    break
            
            if not target_transform:
                raise ExecutionBridgeError(f"Transform node '{transform_node_id}' not found")
            
            # Execute the transformation
            result = await self._execute_single_transform(target_transform, parameters)
            
            return {
                "success": True,
                "data": result,
                "transform_node_id": transform_node_id
            }
            
        except Exception as e:
            logger.error(f"Error executing transform service: {str(e)}")
            raise ExecutionBridgeError(f"Transform service execution failed: {str(e)}")
    
    async def _execute_single_transform(self,
                                      transform_config: Dict[str, Any],
                                      input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single transformation"""
        try:
            # Get transformation code
            transform_code = transform_config.get('transformation_code', '')
            
            # Prepare execution context
            context = {
                'input': input_params,
                'output': {},
                'node_outputs': {},
                'global': {},
                'local': {}
            }
            
            # Execute the transformation code
            exec_globals = {
                '__builtins__': {
                    'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
                    'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
                    'min': min, 'max': max, 'sum': sum, 'abs': abs, 'round': round
                }
            }
            
            exec(transform_code, exec_globals, context)
            
            return context.get('output', {})
            
        except Exception as e:
            logger.error(f"Transform execution error: {str(e)}")
            raise ExecutionBridgeError(f"Transform execution failed: {str(e)}")
    
    def cleanup_expired_executions(self, db: Session, max_age_hours: int = 24) -> int:
        """Clean up old execution bridge records"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            # Delete old completed/failed executions
            deleted_count = db.query(FlowExecutionBridge).filter(
                and_(
                    FlowExecutionBridge.started_at < cutoff_time,
                    FlowExecutionBridge.execution_status.in_(['completed', 'failed'])
                )
            ).delete()
            
            db.commit()
            
            logger.info(f"Cleaned up {deleted_count} expired execution bridge records")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up execution bridge records: {str(e)}")
            db.rollback()
            return 0
    
    # Private helper methods
    
    def _get_published_application(self, db: Session, app_key: str) -> Optional[PublishedApplication]:
        """Get published application by key"""
        return db.query(PublishedApplication).filter(
            PublishedApplication.app_key == app_key
        ).first()
    
    def _get_service_config(self, db: Session, app_id: str, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service configuration"""
        service = db.query(ApplicationService).filter(
            and_(
                ApplicationService.app_id == app_id,
                ApplicationService.service_name == service_name
            )
        ).first()
        
        if service:
            return parse_json_field(service.service_config)

        return None
    
    def _get_parameter_mappings(self, db: Session, published_app_id: str, service_name: str) -> List[ParameterMapping]:
        """Get parameter mappings for a service"""
        db_mappings = db.query(DBParameterMapping).filter(
            DBParameterMapping.published_app_id == published_app_id
        ).all()
        
        mappings = []
        for db_mapping in db_mappings:
            mapping = ParameterMapping(
                source_path=db_mapping.flow_variable_path,
                target_parameter=db_mapping.service_parameter_name,
                mapping_type=db_mapping.parameter_type,
                transformation_rule=parse_json_field(db_mapping.transformation_rule),
                default_value=parse_json_field(db_mapping.default_value),
                required=db_mapping.is_required,
                validation_schema=parse_json_field(db_mapping.validation_schema),
                description=db_mapping.description
            )
            mappings.append(mapping)
        
        return mappings
    
    def _map_service_parameters_to_flow(self,
                                      service_params: Dict[str, Any],
                                      parameter_mappings: List[ParameterMapping],
                                      flow_analysis: str) -> MappingResult:
        """Map service parameters to flow variables"""
        # Create input context from service parameters
        input_context = service_params
        
        # Apply parameter mappings
        return self.parameter_mapper.apply_mappings(
            input_data=input_context,
            mappings=parameter_mappings
        )
    
    def _create_bridge_record(self,
                            db: Session,
                            published_app_id: str,
                            service_call_id: str,
                            input_parameters: Dict[str, Any],
                            mapped_parameters: Dict[str, Any]) -> FlowExecutionBridge:
        """Create execution bridge record"""
        bridge_record = FlowExecutionBridge(
            bridge_id=str(uuid.uuid4()),
            published_app_id=published_app_id,
            service_call_id=service_call_id,
            input_parameters=json.dumps(input_parameters),
            mapped_parameters=json.dumps(mapped_parameters),
            execution_status='pending'
        )
        
        db.add(bridge_record)
        db.flush()
        
        return bridge_record
    
    def _format_sync_result(self, execution_result) -> Any:
        """Format synchronous execution result for service response"""
        # Handle string results (from text format flows)
        if isinstance(execution_result, str):
            return execution_result
        
        # Handle dict results (from JSON format flows)
        if isinstance(execution_result, dict):
            # Extract the actual result data from flow execution
            # Published flows should return only the data content, not the HTTP wrapper structure
            if 'data' in execution_result:
                return execution_result['data']
            elif 'result' in execution_result:
                return execution_result['result']
            else:
                return execution_result
        
        # For any other type, return as-is
        return execution_result
    
    async def check_and_update_async_executions(self, db: Session) -> int:
        """Check and update status of async executions"""
        updated_count = 0
        
        try:
            # Get all running executions
            running_bridges = db.query(FlowExecutionBridge).filter(
                FlowExecutionBridge.execution_status == 'running'
            ).all()
            
            for bridge in running_bridges:
                if bridge.execution_id:
                    # Check execution status
                    execution = db.query(FlowExecution).filter(
                        FlowExecution.execution_id == bridge.execution_id
                    ).first()
                    
                    if execution:
                        if execution.status == ExecutionStatus.COMPLETED:
                            # Update bridge record
                            bridge.execution_status = 'completed'
                            bridge.execution_result = execution.result
                            bridge.completed_at = execution.completed_at
                            if execution.completed_at and bridge.started_at:
                                bridge.execution_time_ms = int(
                                    (execution.completed_at - bridge.started_at).total_seconds() * 1000
                                )
                            updated_count += 1
                            
                        elif execution.status == ExecutionStatus.FAILED:
                            # Update bridge record
                            bridge.execution_status = 'failed'
                            bridge.error_details = json.dumps({
                                "error": "flow_execution_failed",
                                "message": execution.error_message or "Flow execution failed"
                            })
                            bridge.completed_at = execution.completed_at or datetime.now()
                            updated_count += 1
            
            if updated_count > 0:
                db.commit()
                logger.info(f"Updated {updated_count} async execution statuses")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error checking async executions: {str(e)}")
            db.rollback()
            return 0


# Create singleton instance
flow_execution_bridge = FlowExecutionBridgeService()