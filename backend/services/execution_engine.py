import asyncio
import json
import random
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
import logging

# Import models - PostgreSQL Only
from db.models import (
    Flow, FlowExecution, ExecutionLog, AsyncCallback,
    ExecutionStatus, User,
    HITLTask, HITLTaskAssignment, HITLRole, HITLUserRole,
    EventWait
)
from db.application_models import Application, ApplicationSubscription, ApplicationService
from core.config import settings
from db.database import get_tenant_db
from utils.crypto_utils import decrypt_credentials, mask_sensitive_data, redact_secrets, redact_text
from utils.json_utils import ensure_dict
from services.service_executors import get_service_executor
from utils.retry_utils import retry_async, with_retry, RetryConfig, NETWORK_RETRY_CONFIG, DATABASE_RETRY_CONFIG
from core.config import settings
from services.variable_manager import FlowVariableManager
from services.transform_executor import TransformExecutor
from services.flow_cache import flow_cache
from services.websocket_manager import manager as ws_manager
from services.debug_coordinator import debug_coordinator
from services.balance_enforcer import balance_enforcer
from services.node_error_handling import (
    ErrorPolicy, ServiceExecutionError, ON_ERROR_BRANCH, ERROR_HANDLE,
    FATAL_ERROR_TYPES, classify_exception, is_control_flow_exception,
    unsuccessful_result_error, build_error_object, build_handled_output,
    mark_skip_policy, should_skip_policy,
)
from services.cost_calculator import cost_calculator
from exceptions.billing_exceptions import (
    InsufficientBalanceError,
    ServiceAccessDeniedError,
    PricingNotConfiguredError,
    BalanceReservationError
)

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """Core execution engine for running flows."""

    # Shared HTTP client — one connection pool for all engine instances
    # instead of a fresh pool per execution (MQTT triggers create one engine
    # per message, so per-instance pools were pure overhead)
    _shared_http_client: Optional[httpx.AsyncClient] = None

    # Per-execution log policies (flow-level execution logging: 'node_summary'
    # and 'errors_only' levels). Keyed by execution_id; absent = 'full'.
    _log_policies: Dict[str, Dict[str, Any]] = {}

    # Log verbosity ordering used to apply the operator floor
    _LOG_LEVEL_VERBOSITY = {'errors_only': 0, 'node_summary': 1, 'full': 2}

    # Main event loop, captured at execution start so log writes running in
    # worker threads (asyncio.to_thread) can still schedule WS notifications
    _main_loop: Optional[asyncio.AbstractEventLoop] = None

    # Fire-and-forget tasks (e.g. error handler flows) kept alive until done
    _background_tasks: set = set()

    def __init__(self, tenant_schema: str, tenant_id: str = None, user_id: str = None):
        self.tenant_schema = tenant_schema
        # For WebSocket notifications, we need the tenant_id
        self.tenant_id = tenant_id or tenant_schema
        self.user_id = user_id  # Store user_id for subscription access
        self.http_client = self._get_shared_http_client()
        self.variable_manager = FlowVariableManager()

    @classmethod
    def _get_shared_http_client(cls) -> httpx.AsyncClient:
        if cls._shared_http_client is None or cls._shared_http_client.is_closed:
            cls._shared_http_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            )
        return cls._shared_http_client

    @classmethod
    def _capture_main_loop(cls):
        try:
            cls._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    def _load_flow_info(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """Load the flow fields needed for execution, served from the flow
        definition cache when possible. The cache is invalidated automatically
        whenever a flow is saved (SQLAlchemy commit hooks in services/flow_cache),
        so design changes take effect on the very next execution."""
        cached = flow_cache.get(self.tenant_schema, flow_id)
        if cached is not None:
            return cached
        with get_tenant_db(self.tenant_schema) as db:
            flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
            if not flow:
                return None
            entry = {
                'flow_definition': flow.flow_definition,
                'flow_name': flow.flow_name,
                'trigger_config': flow.trigger_config,
                'is_synchronous': bool(flow.is_synchronous),
                'sync_timeout': flow.sync_timeout,
            }
            flow_cache.set(self.tenant_schema, flow_id, entry)
            return entry

    async def execute_flow(self, flow_id: str, trigger_data: Dict[str, Any], trigger_type: str = "manual"):
        """Execute a flow asynchronously."""
        try:
            self._capture_main_loop()
            is_simulation = trigger_data.get('is_simulation', False)

            # Load the flow off the event loop — synchronous SQLAlchemy calls
            # would otherwise freeze the loop that serves all API traffic
            flow_info = await asyncio.to_thread(self._load_flow_info, flow_id)
            if not flow_info:
                raise ValueError(f"Flow {flow_id} not found")
            flow_definition = flow_info['flow_definition']

            # PRE-EXECUTION BALANCE CHECK
            # Check balance BEFORE creating execution record
            with get_tenant_db(self.tenant_schema) as db:
                await self._check_flow_balance_before_execution(flow_id, flow_definition, trigger_data, db)

            # Create execution record + start log off the event loop
            mode_text = " (SIMULATION MODE)" if is_simulation else ""

            def _create_execution():
                with get_tenant_db(self.tenant_schema) as db:
                    execution = FlowExecution(
                        flow_id=flow_id,
                        trigger_type=trigger_type,
                        trigger_data=trigger_data,
                        status=ExecutionStatus.RUNNING,
                        execution_data={'is_simulation': is_simulation}
                    )
                    db.add(execution)
                    db.commit()

                    # Register the flow-level log policy BEFORE the first log write
                    self._init_log_policy(execution.execution_id, flow_definition)

                    self._log_execution(db, execution.execution_id, None, "info",
                                      f"⚡ Flow execution starting - trigger: {trigger_type}{mode_text}",
                                      {"execution_stage": "execution_start", "trigger_type": trigger_type})
                    started_at = execution.started_at.isoformat() if execution.started_at else None
                    return execution.execution_id, started_at

            execution_id, started_at = await asyncio.to_thread(_create_execution)

            # Send immediate execution start notification
            await self._send_status_notification(execution_id, {
                'type': 'execution_start',
                'status': 'running',
                'started_at': started_at,
                'flow_id': flow_id,
                'flow_name': flow_info['flow_name'],
                'trigger_type': trigger_type,
                'message': f'Flow execution starting{mode_text}'
            })

            # Execute flow steps with extracted flow definition
            await self._execute_flow_definition(execution_id, flow_definition, trigger_data, trigger_type)

        except Exception as e:
            # Error is already handled and logged in _execute_flow_definition
            logger.error(f"Flow execution failed: {str(e)}", exc_info=False)
    
    async def execute_flow_with_id(self, flow_id: str, execution_id: str, trigger_data: Dict[str, Any], trigger_type: str = "manual"):
        """Execute a flow with a pre-created execution ID."""
        try:
            self._capture_main_loop()

            # Flow fields come from the cache (invalidated on save)
            flow_info = await asyncio.to_thread(self._load_flow_info, flow_id)
            if not flow_info:
                raise ValueError(f"Flow {flow_id} not found")
            flow_definition = flow_info['flow_definition']

            with get_tenant_db(self.tenant_schema) as db:
                # PRE-EXECUTION BALANCE CHECK
                # Check balance BEFORE updating execution status to RUNNING
                # If this raises InsufficientBalanceError, the execution stays in its current state
                await self._check_flow_balance_before_execution(flow_id, flow_definition, trigger_data, db)

                # Update execution record to running (only after balance check passes)
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == execution_id
                ).first()

                if not execution:
                    raise ValueError(f"Execution {execution_id} not found")

                execution.status = ExecutionStatus.RUNNING
                execution.started_at = datetime.utcnow()
                db.commit()

                # Register the flow-level log policy BEFORE the first log write
                self._init_log_policy(execution_id, flow_definition)

                # Check if this is a simulation
                is_simulation = trigger_data.get('is_simulation', False)
                
                # Check if this is a debug execution
                debug_mode = trigger_data.get('debug_mode', False)
                logger.info(f"Debug mode: {debug_mode}, execution_id: {execution_id}")
                
                if debug_mode:
                    logger.info(f"Creating debug session for {execution_id}")
                    debug_coordinator.create_session(execution_id)
                
                # Log start with immediate execution start notification
                mode_text = " (SIMULATION MODE)" if is_simulation else ""
                self._log_execution(db, execution_id, None, "info", 
                                  f"⚡ Flow execution starting - trigger: {trigger_type}{mode_text}",
                                  {"execution_stage": "execution_start", "trigger_type": trigger_type})
                
                # Send immediate execution start notification
                await self._send_status_notification(execution_id, {
                    'type': 'execution_start',
                    'status': 'running',
                    'started_at': execution.started_at.isoformat() if execution.started_at else None,
                    'flow_id': flow_id,
                    'flow_name': flow_info['flow_name'],
                    'trigger_type': trigger_type,
                    'message': f'Flow execution starting{mode_text}'
                })

            # Execute flow steps with extracted flow definition
            await self._execute_flow_definition(execution_id, flow_definition, trigger_data, trigger_type)

        except Exception as e:
            # Error is already handled and logged in _execute_flow_definition
            logger.error(f"Flow execution failed: {str(e)}", exc_info=False)

    async def execute_flow_sync(self, flow_id: str, trigger_data: Dict[str, Any],
                               trigger_type: str = "manual", timeout: int = 30) -> Dict[str, Any]:
        """Execute a flow synchronously and return the result."""
        import asyncio

        self._capture_main_loop()

        # Flow fields come from the cache (invalidated on save)
        flow_info = await asyncio.to_thread(self._load_flow_info, flow_id)
        if not flow_info:
            raise ValueError(f"Flow {flow_id} not found")

        # For direct execution, allow synchronous execution even if flow is not marked as synchronous
        is_direct_execution = trigger_data.get('direct_execution', False)
        if not flow_info['is_synchronous'] and not is_direct_execution:
            raise ValueError(f"Flow {flow_id} is not marked as synchronous")

        # Extract flow definition and timeout
        flow_definition = flow_info['flow_definition']
        timeout = flow_info['sync_timeout'] or timeout

        execution_id = None

        with get_tenant_db(self.tenant_schema) as db:
            # PRE-EXECUTION BALANCE CHECK
            # Check balance BEFORE creating execution record
            await self._check_flow_balance_before_execution(flow_id, flow_definition, trigger_data, db)

            # Create execution record
            execution_data = {'is_synchronous': True}
            if is_direct_execution:
                execution_data.update({
                    'direct_execution': True,
                    'bypass_application_trigger': trigger_data.get('bypass_application_trigger', False)
                })
            
            execution = FlowExecution(
                flow_id=flow_id,
                trigger_type=trigger_type,
                trigger_data=trigger_data,
                status=ExecutionStatus.RUNNING,
                execution_data=execution_data
            )
            db.add(execution)
            db.commit()

            execution_id = execution.execution_id

            # Register the flow-level log policy BEFORE the first log write
            self._init_log_policy(execution_id, flow_definition)

            self._log_execution(db, execution_id, None, "info",
                              f"Synchronous flow execution started - trigger: {trigger_type}")
            
            # Send WebSocket notification for status update
            await self._send_status_notification(execution_id, {
                'status': 'running',
                'started_at': execution.started_at.isoformat() if execution.started_at else None,
                'flow_id': flow_id,
                'flow_name': flow_info['flow_name'],
                'trigger_type': trigger_type
            })
        
        try:
            # Execute flow with timeout
            await asyncio.wait_for(
                self._execute_flow_definition(execution_id, flow_definition, trigger_data, trigger_type),
                timeout=timeout
            )
            
            # Retrieve result
            with get_tenant_db(self.tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == execution_id
                ).first()
                
                if execution.result_data is None:
                    # Check if the flow is designed to have response nodes
                    nodes = flow_definition.get('nodes', [])
                    has_response_nodes = any(node.get('type') == 'response' for node in nodes)
                    
                    if has_response_nodes:
                        # Flow has response nodes but no result data - this is an error
                        raise ValueError("Flow completed but no response data was set. Ensure flow has a response node.")
                    else:
                        # Flow is designed without response nodes - this is not an error
                        # Log as info instead of error and return a success message
                        self._log_execution(db, execution_id, None, "info", 
                                          "Flow completed successfully without response node as designed")
                        
                        # Return a generic success response for flows without response nodes
                        return {
                            "status": "completed", 
                            "message": "Flow executed successfully",
                            "execution_id": execution_id
                        }
                
                # Check output format to determine response structure
                output_format = "text"  # default from node configuration
                if execution.response_headers:
                    output_format = execution.response_headers.get('X-Output-Format', 'text')
                
                # Handle different output formats according to requirements
                if output_format == "text":
                    # Text format: return raw text only
                    return execution.result_data
                elif output_format == "json":
                    # JSON format: return full metadata structure
                    return {
                        "status": execution.response_status or 200,
                        "headers": execution.response_headers or {},
                        "data": execution.result_data,
                        "execution_id": execution_id
                    }
                elif output_format == "html":
                    # HTML format: return with HTTP headers/status and HTML body
                    return {
                        "status": execution.response_status or 200,
                        "headers": execution.response_headers or {},
                        "body": execution.result_data,
                        "execution_id": execution_id
                    }
                elif output_format == "xml":
                    # XML format: return XML-style structure
                    import xml.etree.ElementTree as ET
                    
                    # Create XML structure
                    root = ET.Element("response")
                    
                    # Add status
                    status_elem = ET.SubElement(root, "status")
                    status_elem.text = str(execution.response_status or 200)
                    
                    # Add headers
                    if execution.response_headers:
                        headers_elem = ET.SubElement(root, "headers")
                        for key, value in execution.response_headers.items():
                            header_elem = ET.SubElement(headers_elem, "header")
                            header_elem.set("name", key)
                            header_elem.text = str(value)
                    
                    # Add data
                    data_elem = ET.SubElement(root, "data")
                    data_elem.text = str(execution.result_data)
                    
                    # Add execution_id
                    exec_id_elem = ET.SubElement(root, "execution_id")
                    exec_id_elem.text = execution_id
                    
                    # Convert to string
                    xml_string = ET.tostring(root, encoding='unicode')
                    return xml_string
                else:
                    # Default fallback to JSON format
                    return {
                        "status": execution.response_status or 200,
                        "headers": execution.response_headers or {},
                        "data": execution.result_data,
                        "execution_id": execution_id
                    }
                
        except asyncio.TimeoutError:
            with get_tenant_db(self.tenant_schema) as db:
                self._mark_execution_failed(db, execution_id, f"Flow execution timed out after {timeout} seconds", None)
            raise ValueError(f"Flow execution timed out after {timeout} seconds")

        except Exception as e:
            # Error is already handled and logged in _execute_flow_definition
            logger.error(f"Synchronous flow execution failed: {str(e)}", exc_info=False)
            raise

    async def _check_flow_balance_before_execution(self, flow_id: str, flow_definition: Dict[str, Any],
                                                   trigger_data: Dict[str, Any], db: Session):
        """
        Check if tenant has sufficient balance before starting flow execution.

        This is a pre-execution check that happens BEFORE the flow starts executing.
        It finds the first action node (service call) in the flow and estimates the cost.

        Args:
            flow_id: Flow identifier
            flow_definition: Flow definition with nodes and edges
            trigger_data: Trigger data to estimate data transfer size
            db: Database session

        Raises:
            InsufficientBalanceError: If balance is insufficient for prepaid billing

        Returns:
            None (or raises exception)
        """
        # Skip balance check for simulation mode
        is_simulation = trigger_data.get('is_simulation', False)
        if is_simulation:
            logger.info(f"Skipping balance check for simulation mode execution of flow {flow_id}")
            return

        # Find the first action node (service call) in the flow
        nodes = flow_definition.get('nodes', [])
        first_action_node = None

        for node in nodes:
            node_type = node.get('type', '')
            if node_type == 'action':
                first_action_node = node
                break

        # If no action nodes, no services to bill for - return early
        if not first_action_node:
            logger.info(f"Flow {flow_id} has no action nodes - skipping balance check")
            return

        # Extract app_id and service_id from the first action node
        app_id = first_action_node.get('app_id') or first_action_node.get('appId')
        service_id = first_action_node.get('service_id') or first_action_node.get('serviceId')

        if not app_id or not service_id:
            logger.warning(f"First action node in flow {flow_id} missing app_id or service_id - skipping balance check")
            return

        # Get application and service details
        app = db.query(Application).filter(Application.app_id == app_id).first()
        if not app:
            logger.warning(f"Application {app_id} not found - skipping balance check")
            return

        service = db.query(ApplicationService).filter(ApplicationService.service_id == service_id).first()
        if not service:
            logger.warning(f"Service {service_id} not found - skipping balance check")
            return

        # Estimate data transfer size from trigger_data
        # Similar to how it's done in _execute_action_node
        try:
            trigger_data_json = json.dumps(trigger_data)
            estimated_data_kb = len(trigger_data_json.encode('utf-8')) / 1024.0
        except Exception as e:
            logger.warning(f"Could not estimate data size: {e}, using 0")
            estimated_data_kb = 0

        # Check balance using balance_enforcer
        logger.info(f"Checking balance before executing flow {flow_id} - app: {app.app_name}, service: {service.service_name}")

        try:
            can_execute, estimated_cost, billing_mode = balance_enforcer.check_balance_for_service(
                tenant_id=self.tenant_id,
                app_id=app_id,
                service_id=service_id,
                estimated_data_kb=estimated_data_kb,
                db=db
            )

            logger.info(f"Pre-execution balance check passed - can_execute: {can_execute}, "
                       f"estimated_cost: ${estimated_cost:.4f if estimated_cost else 0}, "
                       f"billing_mode: {billing_mode}")

        except InsufficientBalanceError as e:
            # Re-raise with service context for better error message
            logger.error(f"Pre-execution balance check failed for flow {flow_id}: {str(e)}")
            raise

    async def _execute_flow_definition(self, execution_id: str, flow_definition: Dict[str, Any],
                                     initial_data: Dict[str, Any], trigger_type: str = "manual"):
        """Execute the flow based on its definition."""
        logger.info(f"=== Starting _execute_flow_definition for execution {execution_id} ===")
        logger.info(f"Initial data keys: {list(initial_data.keys())}")
        logger.info(f"Debug flags: debug_mode={initial_data.get('debug_mode')}, debug_step_mode={initial_data.get('debug_step_mode')}")

        failed_node_id = None  # Track which node failed for proper error handling

        try:
            nodes = flow_definition.get('nodes', [])
            edges = flow_definition.get('edges', [])

            # Build adjacency list and reverse adjacency (incoming edges)
            adjacency = self._build_adjacency_list(edges)
            reverse_adjacency = self._build_reverse_adjacency_list(edges)

            # Find start node (trigger node)
            start_node = None
            for node in nodes:
                if node['type'] == 'trigger':
                    start_node = node
                    break

            if not start_node:
                raise ValueError("No trigger node found in flow")

            # Execute from start node
            # Extract variables based on trigger type and configuration
            variables = {}

            # Check if this is a polling trigger
            if trigger_type == 'polling':
                # For polling triggers, the initial_data contains the polling data directly
                # (e.g., {'id': 'message_id', 'threadId': 'thread_id'})
                variables = initial_data.copy()
                # Remove any system fields that shouldn't be exposed as variables
                variables.pop('is_simulation', None)
                variables.pop('debug_mode', None)
                variables.pop('debug_step_mode', None)
                logger.info(f"Polling trigger - extracted variables: {list(variables.keys())}")
            # For webhook/event triggers, use unified parameter extraction
            elif 'webhook_data' in initial_data:
                webhook_data = initial_data.get('webhook_data', {})

                # Get flow and event information from execution record
                with get_tenant_db(self.tenant_schema) as db:
                    execution = db.query(FlowExecution).filter(
                        FlowExecution.execution_id == execution_id
                    ).first()
                    if execution:
                        flow_id = execution.flow_id
                        flow = self._get_flow_from_db(flow_id)

                        # Get event configuration for unified parameter extraction
                        event_config = await self._get_event_configuration_for_flow(db, flow)
                    else:
                        flow = None
                        event_config = None

                # Use unified parameter extraction if event configuration is available
                if event_config:
                    variables = await self._extract_parameters_unified(webhook_data, event_config, execution_id)

                    # Also check for manual variables in the trigger configuration
                    if flow and flow.trigger_config:
                        trigger_variables = await self._extract_parameters_legacy(webhook_data, flow.trigger_config)
                        # Merge trigger variables, giving precedence to trigger-defined variables
                        variables.update(trigger_variables)

                elif flow and flow.trigger_config:
                    # Fallback to legacy extraction for backward compatibility
                    variables = await self._extract_parameters_legacy(webhook_data, flow.trigger_config)
                else:
                    # Fallback: use entire webhook_data as variables
                    variables = webhook_data
            else:
                # For other triggers (manual, etc.), use provided variables
                variables = initial_data.get('variables', {})
        
            execution_context = {
                'data': initial_data,
                'execution_id': execution_id,
                'variables': variables,  # Initialize with extracted variables
                'node_outputs': {},  # Store node outputs separately to avoid circular refs
                'webhook_data': initial_data.get('webhook_data', {}),  # Store webhook data in context
                'global_vars': self.variable_manager.global_vars,  # Add global variables
                'tenant_id': self.tenant_id,  # Add tenant_id for proper filtering
                'user_id': self.user_id or initial_data.get('user_id'),  # Add user_id for subscription access
                'is_simulation': initial_data.get('is_simulation', False),  # Pass simulation flag
                '_reverse_adjacency': reverse_adjacency,  # For fork-join synchronization
                '_completed_nodes': set(),  # Track completed nodes
                '_pending_executions': {},   # Track nodes waiting for all incoming edges
                '_all_nodes': nodes,  # Store all nodes for reference
                # Chat session context for agent session continuity
                'chat_session_id': initial_data.get('chat_session_id'),
                'flow_id': flow_id if 'flow_id' in dir() else None,
                'schema_name': self.tenant_schema
            }

            # Log extracted variables for debugging (off the event loop — DB
            # writes must not freeze the loop that serves all API traffic)
            for var_name, var_value in variables.items():
                if isinstance(var_value, dict) and 'filename' in var_value and 'content' in var_value:
                    logger.info(f"File variable '{var_name}': filename={var_value.get('filename')}, "
                              f"content_length={len(var_value.get('content', ''))}, "
                              f"size={var_value.get('size')}")

            def _log_extracted_variables():
                with get_tenant_db(self.tenant_schema) as db:
                    self._log_execution(db, execution_id, None, "debug",
                                      f"Extracted variables from trigger data",
                                      {"variables": variables, "trigger_type": trigger_type})

            await asyncio.to_thread(_log_extracted_variables)

            # Every run knows its flow (only the webhook branch above used to set
            # it): usage metering and the daily budget are per flow.
            if not execution_context.get('flow_id'):
                def _flow_of_execution():
                    with get_tenant_db(self.tenant_schema) as db:
                        row = db.query(FlowExecution.flow_id).filter(
                            FlowExecution.execution_id == execution_id).first()
                        return row[0] if row else None
                execution_context['flow_id'] = await asyncio.to_thread(_flow_of_execution)

            # Daily budget (flow_definition.settings.budget): refuse the run once
            # today's metered cost has reached it. Re-checked before each metered
            # call (_execute_service_with_type), so a long run stops part-way.
            from services import flow_usage
            _budget = flow_usage.budget_of(flow_definition)
            if _budget and not execution_context.get('is_simulation'):
                execution_context['_budget'] = _budget
                await asyncio.to_thread(flow_usage.check_budget, self.tenant_schema,
                                        execution_context.get('flow_id'), _budget)

            await self._execute_node(start_node, nodes, edges, adjacency, execution_context)

            # Completion bookkeeping runs off the event loop
            def _finalize_completion():
                with get_tenant_db(self.tenant_schema) as db:
                    execution = db.query(FlowExecution).filter(
                        FlowExecution.execution_id == execution_id
                    ).first()
                    # Check if execution was paused by HITL - don't mark as completed
                    if execution.status == ExecutionStatus.PAUSED:
                        return {'paused': True}

                    # Mark execution as completed
                    execution.status = ExecutionStatus.COMPLETED
                    execution.completed_at = datetime.utcnow()

                    # Save node outputs from execution context to database
                    node_outputs = execution_context.get('node_outputs', {})
                    if node_outputs:
                        from api.applications import serialize_json_field
                        execution.node_outputs = serialize_json_field(node_outputs)
                        logger.info(f"Saved {len(node_outputs)} node outputs to database: {list(node_outputs.keys())}")

                    db.commit()

                    self._log_execution(db, execution_id, None, "info",
                                      "Flow execution completed successfully",
                                      {"execution_stage": "execution_complete"})

                    # Refresh execution object to get latest data (including result_data from response node)
                    db.refresh(execution)
                    return {
                        'paused': False,
                        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
                        'result_data': execution.result_data,
                        'response_headers': execution.response_headers,
                        'response_status': execution.response_status,
                    }

            completion = await asyncio.to_thread(_finalize_completion)
            if completion['paused']:
                logger.info(f"Execution {execution_id} is paused (HITL) - not marking as completed")
                return

            # Send WebSocket notification for status update
            await self._send_status_notification(execution_id, {
                'status': 'completed',
                'completed_at': completion['completed_at'],
                'type': 'execution_complete',
                'execution_id': execution_id,
                'final_status': 'success',
                'result': completion['result_data'],  # Include the final result
                'response_headers': completion['response_headers'],  # Include headers for format detection
                'response_status': completion['response_status']  # Include status code
            })

            # Send debug completion event
            debug_mode = initial_data.get('debug_mode', False)
            if debug_mode:
                await self._send_debug_event(execution_id, {
                    'type': 'execution_complete',
                    'status': 'completed'
                })
                # Clean up debug session — we're done debugging
                debug_coordinator.remove_session(execution_id)
                logger.info(f"Debug session ended for execution {execution_id}")

        except Exception as e:
            # Extract the failed node ID from the exception if it has been marked
            if hasattr(e, '_logged_nodes') and len(getattr(e, '_logged_nodes', set())) > 0:
                # The first node in _logged_nodes is the actual failing node
                failed_node_id = list(e._logged_nodes)[0] if e._logged_nodes else None
                logger.info(f"Flow execution failed at node: {failed_node_id}")
            else:
                failed_node_id = None
                logger.info(f"Flow execution failed without specific node context")

            # Mark the execution as failed but pass the failed_node_id to avoid duplicate logging
            with get_tenant_db(self.tenant_schema) as db:
                self._mark_execution_failed(db, execution_id, str(e), failed_node_id)

            # Flow-level error handler: start the configured error flow
            await self._trigger_error_handler_flow(execution_id, flow_definition, initial_data,
                                                   e, failed_node_id)

            # Send execution error notification via WebSocket for all executions
            try:
                await self._send_status_notification(execution_id, {
                    'type': 'execution_error',
                    'status': 'failed',
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'failed_node_id': failed_node_id
                })
            except Exception as ws_error:
                logger.warning(f"Failed to send execution error WebSocket notification: {ws_error}")

            # Send debug error event if in debug mode
            debug_mode = initial_data.get('debug_mode', False)
            if debug_mode:
                await self._send_debug_event(execution_id, {
                    'type': 'execution_error',
                    'status': 'failed',
                    'error': str(e),
                    'failed_node_id': failed_node_id
                })

            # Re-raise the exception to propagate to caller
            raise
        finally:
            # Release any flow-scoped DB transaction still pinned to this
            # execution. Runs on success, failure, and the HITL paused return
            # (which is inside the try): an uncommitted transaction is rolled
            # back and its connection returned to the pool, so a transaction can
            # never silently span a flow boundary or a HITL/event-wait pause.
            try:
                from services import db_transaction_manager
                await db_transaction_manager.release_all(execution_id)
            except Exception as _txn_release_err:
                logger.warning(f"Error releasing DB transactions for execution {execution_id}: {_txn_release_err}")

            # Drop the flow-level log policy (and any never-flushed buffer)
            self._finalize_log_policy(execution_id)

    async def _execute_node(self, node: Dict[str, Any], all_nodes: List[Dict[str, Any]], 
                          edges: List[Dict[str, Any]], adjacency: Dict[str, List[str]], 
                          context: Dict[str, Any]):
        """Execute a single node in the flow."""
        node_id = node['id']
        node_type = node['type']
        node_data = node.get('data', {})
        
        # Check for updated node configuration in debug mode
        execution_id = context.get('execution_id')
        if execution_id and debug_coordinator.session_exists(execution_id):
            updated_config = debug_coordinator.get_updated_node_config(execution_id, node_id)
            if updated_config:
                logger.info(f"Using updated configuration for node {node_id}")
                # For transform nodes, handle both 'script' and 'code' fields
                if node_type == 'transform' and 'code' in updated_config and 'script' not in updated_config:
                    updated_config['script'] = updated_config['code']
                # Merge updated config with existing node data
                node_data = {**node_data, **updated_config}
                node['data'] = node_data
            
            # Apply any updated variables
            updated_vars = debug_coordinator.get_updated_variables(execution_id)
            if updated_vars:
                logger.info(f"Applying updated variables: {updated_vars}")
                context.setdefault('variables', {}).update(updated_vars)
        
        logger.info(f"=== Executing node {node_id} (type: {node_type}) ===")
        logger.info(f"Context data type: {type(context.get('data'))}")
        
        # Check if we're in debug mode
        debug_mode = context.get('data', {}).get('debug_mode', False)
        debug_step_mode = context.get('data', {}).get('debug_step_mode', False)
        
        # Log debug flags for troubleshooting
        logger.info(f"Debug flags in _execute_node: debug_mode={debug_mode}, debug_step_mode={debug_step_mode}")
        logger.info(f"Context data keys: {list(context.get('data', {}).keys())}")
        
        # Log debug mode status and context data
        if node_type != 'trigger':
            logger.info(f"Node {node_id}: debug_mode={debug_mode}, debug_step_mode={debug_step_mode}, node_type={node_type}")
            logger.info(f"Context data keys: {list(context.get('data', {}).keys())}")
            logger.info(f"Full debug flags in data: debug_mode={context.get('data', {}).get('debug_mode')}, debug_step_mode={context.get('data', {}).get('debug_step_mode')}")
        
        # Send debug event for node start
        if debug_mode:
            # Collect all variable types for debugging
            all_variables = {
                'input': dict(context.get('variables', {})),
                'global': dict(context.get('global_vars', {})),
                'output': {},  # Node hasn't produced output yet
                'loop': dict(context.get('loop', {})) if context.get('_in_loop') else {},
                'node_outputs': dict(context.get('node_outputs', {}))
            }
            
            await self._send_debug_event(context['execution_id'], {
                'type': 'node_start',
                'node_id': node_id,
                'node_type': node_type,
                'node_label': node_data.get('label', node_id),
                'variables': all_variables
            })
            
            # If in step mode, wait for user to continue
            if debug_step_mode and node_type != 'trigger':
                logger.info(f"[STEP] Node {node_id} (type: {node_type}) - Waiting for step")
                logger.info(f"[STEP] Execution ID: {context['execution_id']}")
                await self._wait_for_debug_step(context['execution_id'], node_id)
                logger.info(f"[STEP] Node {node_id} - Step continue received, proceeding with execution")
                
                # Re-check for updated configuration after waiting
                updated_config = debug_coordinator.get_updated_node_config(execution_id, node_id)
                if updated_config:
                    logger.info(f"Applying updated configuration after step for node {node_id}")
                    # For transform nodes, handle both 'script' and 'code' fields
                    if node_type == 'transform' and 'code' in updated_config and 'script' not in updated_config:
                        updated_config['script'] = updated_config['code']
                    node_data = {**node_data, **updated_config}
                    node['data'] = node_data
                
                # Re-apply updated variables after waiting
                updated_vars = debug_coordinator.get_updated_variables(execution_id)
                if updated_vars:
                    logger.info(f"Re-applying updated variables after step: {updated_vars}")
                    context.setdefault('variables', {}).update(updated_vars)
        
        # Ensure node_data is a dictionary
        if isinstance(node_data, str):
            try:
                node_data = json.loads(node_data)
                logger.info(f"Converted node_data from string to dict for node {node_id}")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse node_data string for node {node_id}: {node_data}")
                node_data = {}
        elif not isinstance(node_data, dict):
            logger.error(f"node_data is not a dict for node {node_id}: {type(node_data)}")
            node_data = {}
        
        # Set current node ID in context
        context['current_node_id'] = node_id
        
        # Add log callback to context for service executors
        def log_callback(execution_id, node_id, level, message, data=None):
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, execution_id, node_id, level, message, data, context)
        
        context['log_callback'] = log_callback
        
        # Log node execution with more details
        node_info = {
            'node_type': node_type,
            'label': node_data.get('label', node_id),
            'description': node_data.get('description', ''),
        }

        # Add node-specific info
        if node_type == 'action':
            node_info['app_id'] = node_data.get('appId') or node_data.get('app_id')
            node_info['service'] = node_data.get('service') or node_data.get('serviceName')
            node_info['app_name'] = node_data.get('appName', '')
            node_info['service_name'] = node_data.get('serviceName', '')
        elif node_type == 'trigger':
            node_info['trigger_type'] = node_data.get('triggerType', 'manual')

        # Add loop iteration info if inside a loop
        log_message = f"Executing {node_type} node: {node_data.get('label', node_id)}"
        if context.get('_in_loop') and context.get('loop'):
            loop_info = context.get('loop', {})
            iteration = loop_info.get('count', loop_info.get('index', 0))
            log_message += f" (iteration {iteration})"
            node_info['loop_iteration'] = iteration
            node_info['loop_node_id'] = context.get('_loop_node_id')

        # Update current step + write the node start logs off the event loop
        def _record_node_start():
            with get_tenant_db(self.tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == context['execution_id']
                ).first()
                execution.current_step = node_id
                db.commit()

                self._log_execution(db, context['execution_id'], node_id, "info",
                                  log_message,
                                  node_info, context)
                self._log_execution(db, context['execution_id'], node_id, "info",
                                  f"🚀 {node_type.title()} node execution started",
                                  {"execution_stage": "node_start", "node_type": node_type})

        await asyncio.to_thread(_record_node_start)

        try:
            # Send immediate node start notification for frontend feedback
            try:
                await self._send_status_notification(context['execution_id'], {
                    'type': 'node_start',
                    'node_id': node_id,
                    'node_type': node_type,
                    'node_label': node_data.get('label', node_id),
                    'status': 'executing'
                })
            except Exception as ws_error:
                logger.warning(f"Failed to send WebSocket notification: {ws_error}")
            
            # Execute based on node type — dispatch via plugin registry
            from plugins.registry import PluginRegistry
            from plugins.base import NodeExecutionContext

            handler = PluginRegistry.get_node_handler(node_type)
            if not handler:
                raise ValueError(f"Unknown node type: {node_type}")
            engine_ctx = NodeExecutionContext(
                self, context['execution_id'], context,
                all_nodes, edges, adjacency
            )

            # Run the handler under the node's error policy (retry / continue /
            # error branch). node_error is set only when a failure was handled.
            error_policy = ErrorPolicy.from_node(node_type, node_data)
            result, node_error = await self._run_node_with_error_policy(
                node_id, node_type, node_data, handler, engine_ctx, context, error_policy
            )

            # Update context with result, but preserve debug flags
            # Store debug flags before updating
            debug_flags = {}
            if context.get('data'):
                if 'debug_mode' in context['data']:
                    debug_flags['debug_mode'] = context['data']['debug_mode']
                if 'debug_step_mode' in context['data']:
                    debug_flags['debug_step_mode'] = context['data']['debug_step_mode']
            
            # Update data with result
            context['data'] = result
            
            # Restore debug flags
            if debug_flags:
                if isinstance(context['data'], dict):
                    context['data'].update(debug_flags)
                else:
                    # If result is not a dict, wrap it
                    context['data'] = {
                        'result': context['data'],
                        **debug_flags
                    }
            
            # Store node output separately to avoid circular references in variables
            # Note: We keep AttrDict in context for dot notation access but will convert when needed for storage

            # Store node outputs with special handling for different node types
            # IMPORTANT: Preserve nested data structures for backward compatibility
            if isinstance(result, dict):
                # For action nodes that have 'data' field, we need special handling
                if node_type == 'action' and 'data' in result:
                    # Action nodes often have nested data.data structure (e.g., DALL-E responses)
                    # We need to be careful not to flatten these nested structures

                    # Create a wrapper that allows both access patterns without breaking nested data
                    wrapped_result = result.copy()

                    # Only merge top-level keys from data if it's a dict AND doesn't contain another 'data'
                    if isinstance(result.get('data'), dict):
                        # Check if this is a nested data.data structure (common in API responses)
                        inner_data = result.get('data', {})
                        if 'data' not in inner_data:
                            # Safe to merge - no nested data.data structure
                            for key, value in inner_data.items():
                                if key not in wrapped_result:
                                    wrapped_result[key] = value
                        # If there IS nested data.data, we preserve the structure as-is
                        # This ensures node_outputs.node_id.data.data[0].url still works

                    context['node_outputs'][node_id] = wrapped_result
                    self.variable_manager.set_node_output(node_id, wrapped_result)
                else:
                    # For transform nodes and other non-action nodes
                    # Simply store the result as-is
                    context['node_outputs'][node_id] = result
                    self.variable_manager.set_node_output(node_id, result)
            else:
                # For non-dict results (e.g., strings, lists), wrap in a structure
                # This ensures consistent access patterns
                wrapped_output = {'data': result, 'value': result}
                context['node_outputs'][node_id] = wrapped_output
                self.variable_manager.set_node_output(node_id, wrapped_output)

            # For trigger nodes, also store under 'trigger' alias for easier access
            if node_type == 'trigger':
                context['node_outputs']['trigger'] = context['node_outputs'][node_id]
                self.variable_manager.set_node_output('trigger', context['node_outputs'][node_id])
            
            # A handled failure: expose the error as {{error.*}} and route it.
            # "error_branch" follows only the node's error-handle edges;
            # "continue" falls through to the normal traversal below.
            if node_error is not None:
                context['last_error'] = node_error
                await self._report_handled_error(node_id, node_type, node_data, node_error,
                                                 error_policy, context, debug_mode)
                if error_policy.on_error == ON_ERROR_BRANCH:
                    # The normal outgoing paths are skipped: mark them dead first
                    # so joins that also receive the error branch don't wait on them
                    for next_node_id in adjacency.get(node_id, []):
                        await self._propagate_dead_path(node_id, next_node_id, all_nodes,
                                                        edges, adjacency, context)
                    await self._follow_error_branch(node_id, all_nodes, edges, adjacency, context)
                    return
                if node_type == 'loop':
                    # The loop never reached its own continue handling; run it here
                    await self._follow_handle_edges(node_id, 'continue', all_nodes, edges,
                                                    adjacency, context)
                    return

            # Check if HITL pause was triggered - stop graph traversal before logging completion
            if isinstance(result, dict) and result.get('_hitl_paused'):
                logger.info(f"HITL pause at node {node_id} - stopping graph traversal")
                return

            # Check if event wait pause was triggered - stop graph traversal
            if isinstance(result, dict) and result.get('_event_wait_paused'):
                logger.info(f"Event wait pause at node {node_id} - stopping graph traversal")
                return

            # Success bookkeeping (a handled failure reported its own logs/events)
            if node_error is None:
                # Log successful node completion
                logger.info(f"Node {node_id} ({node_type}) execution complete")

                completion_data = {
                    'node_type': node_type,
                    'label': node_data.get('label', node_id),
                    'output_keys': list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                    'execution_stage': 'node_complete'
                }

                # Provide specific completion messages based on node type
                if node_type == 'trigger':
                    trigger_type = node_data.get('triggerType', 'manual')
                    result_count = len(result) if isinstance(result, dict) else 0
                    completion_msg = f"✅ {trigger_type.title()} trigger completed - extracted {result_count} parameters"
                    completion_data['trigger_type'] = trigger_type
                    completion_data['extracted_params'] = result_count
                elif node_type == 'transform':
                    completion_msg = f"✅ Transform node completed - {node_data.get('label', node_id)}"
                elif node_type == 'action':
                    service_name = node_data.get('serviceName', node_data.get('service', 'Unknown'))
                    completion_msg = f"✅ Action completed - {service_name}"
                    completion_data['service_name'] = service_name
                else:
                    completion_msg = f"✅ {node_type.title()} node completed - {node_data.get('label', node_id)}"

                # Write the completion log off the event loop
                def _record_node_complete():
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], node_id, "info",
                                          completion_msg, completion_data, context)

                await asyncio.to_thread(_record_node_complete)

                # Send WebSocket notification for node completion
                try:
                    await self._send_status_notification(context['execution_id'], {
                        'type': 'node_complete',
                        'node_id': node_id,
                        'node_type': node_type,
                        'node_label': node_data.get('label', node_id),
                        'status': 'completed',
                        'completion_message': completion_msg
                    })
                except Exception as ws_error:
                    logger.warning(f"Failed to send completion WebSocket notification: {ws_error}")

                # Send debug event for node completion
                if debug_mode:
                    # Collect all variable types for debugging
                    all_variables = {
                        'input': dict(context.get('variables', {})),
                        'global': dict(context.get('global_vars', {})),
                        'output': dict(context.get('node_outputs', {}).get(node_id, {})),
                        'loop': dict(context.get('loop', {})) if context.get('_in_loop') else {},
                        'node_outputs': dict(context.get('node_outputs', {}))
                    }

                    await self._send_debug_event(context['execution_id'], {
                        'type': 'node_complete',
                        'node_id': node_id,
                        'node_type': node_type,
                        'node_label': node_data.get('label', node_id),
                        'variables': all_variables,
                        'result': result
                    })

            # Execute next nodes based on node type
            if node_type == 'condition':
                # For condition nodes, check the edge source handle
                condition_result = result.get('_condition_result', False)
                for edge in edges:
                    if edge['source'] == node_id:
                        # Check if this edge matches the condition result
                        source_handle = edge.get('sourceHandle', 'true')
                        if (condition_result and source_handle == 'true') or (not condition_result and source_handle == 'false'):
                            next_node = self._find_node_by_id(edge['target'], all_nodes)
                            if next_node:
                                await self._execute_node(next_node, all_nodes, edges, adjacency, context)
            elif node_type == 'loop':
                # Loop nodes handle their own internal execution (loop-body and continue outputs)
                # The loop execution method already handles executing the continue node
                # We don't need to execute next nodes here as they were handled in _execute_loop_node
                # Just return to avoid double execution
                return
            else:
                # For other nodes, check if we're in a loop and hitting a loop-back point
                if (context.get('_in_loop') and 
                    node_id in context.get('_loop_back_nodes', [])):
                    # This node connects back to the loop, don't continue to next nodes
                    # Mark that we returned to the loop
                    context['_returned_to_loop'] = True
                    # The loop will handle the next iteration
                    return
                
                
                # For other nodes, execute all connected nodes
                next_node_ids = adjacency.get(node_id, [])
                
                # If we're in a loop and there are no next nodes, the path ends here
                if context.get('_in_loop') and not next_node_ids:
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], node_id, "debug",
                                          f"End of execution path in loop - no outgoing connections")
                    # Don't set _returned_to_loop, so the loop will break
                    return
                
                for next_node_id in next_node_ids:
                    next_node = self._find_node_by_id(next_node_id, all_nodes)
                    if next_node:
                        # Check if this node should wait for other incoming edges (fork-join synchronization)
                        if await self._can_execute_node(node_id, next_node_id, context):
                            await self._execute_node(next_node, all_nodes, edges, adjacency, context)
        
        except Exception as e:
            # Mark this as the first node where the error occurred
            if not hasattr(e, '_logged_nodes'):
                e._logged_nodes = set()

                # Only log error for the first node where it occurs
                logger.error(f"Node execution failed at {node_id}: {str(e)}", exc_info=True)
                error_category, error_status_code = classify_exception(e)
                with get_tenant_db(self.tenant_schema) as db:
                    error_data = {
                        'error_type': type(e).__name__,
                        'error_category': error_category,
                        'status_code': error_status_code,
                        'attempts': getattr(e, '_ioflow_attempts', 1),
                        'error_message': str(e),
                        'node_type': node_type,
                        'node_label': node_data.get('label', node_id),
                        'node_id': node_id
                    }
                    self._log_execution(db, context['execution_id'], node_id, "error",
                                      f"Node execution failed: {str(e)}",
                                      error_data)

                # Send node error notification via WebSocket for all executions
                try:
                    await self._send_status_notification(context['execution_id'], {
                        'type': 'node_error',
                        'node_id': node_id,
                        'node_type': node_type,
                        'node_label': node_data.get('label', node_id),
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'error_category': error_category,
                        'status': 'error'
                    })
                except Exception as ws_error:
                    logger.warning(f"Failed to send node error WebSocket notification: {ws_error}")

                # Send debug error event if in debug mode
                if debug_mode:
                    await self._send_debug_event(context['execution_id'], {
                        'type': 'node_error',
                        'node_id': node_id,
                        'node_type': node_type,
                        'node_label': node_data.get('label', node_id),
                        'error': str(e),
                        'error_type': type(e).__name__
                    })

                # Mark that we've logged for this node
                e._logged_nodes.add(node_id)

            raise

    async def _trigger_error_handler_flow(self, execution_id: str, flow_definition: Dict[str, Any],
                                          initial_data: Dict[str, Any], exc: BaseException,
                                          failed_node_id: Optional[str]):
        """Start the flow configured in ``settings.error_handler_flow_id`` when an
        execution fails with an unhandled error. The handler flow receives the
        failure as input variables: ``{{input.error.*}}``, ``{{input.execution.*}}``
        and ``{{input.flow.*}}``. Never raises."""
        try:
            flow_settings = (flow_definition or {}).get('settings') or {}
            handler_flow_id = flow_settings.get('error_handler_flow_id')
            if not handler_flow_id:
                return
            if initial_data.get('is_simulation'):
                logger.info(f"Skipping error handler flow for simulated execution {execution_id}")
                return
            if initial_data.get('_error_handler_source'):
                # The failing execution is itself an error handler run: stop the chain
                logger.warning(f"Error handler flow execution {execution_id} failed; "
                               f"not triggering another error handler")
                return

            def _load_source():
                with get_tenant_db(self.tenant_schema) as db:
                    execution = db.query(FlowExecution).filter(
                        FlowExecution.execution_id == execution_id
                    ).first()
                    if not execution:
                        return None
                    flow = db.query(Flow).filter(Flow.flow_id == execution.flow_id).first()
                    handler = db.query(Flow).filter(Flow.flow_id == handler_flow_id).first()
                    return {
                        'flow_id': execution.flow_id,
                        'flow_name': flow.flow_name if flow else None,
                        'trigger_type': execution.trigger_type,
                        'started_at': execution.started_at.isoformat() if execution.started_at else None,
                        'handler_exists': handler is not None,
                    }

            source = await asyncio.to_thread(_load_source)
            if not source:
                return
            if handler_flow_id == source['flow_id']:
                logger.warning(f"Flow {source['flow_id']} lists itself as its error handler; skipping")
                return
            if not source['handler_exists']:
                with get_tenant_db(self.tenant_schema) as db:
                    self._log_execution(db, execution_id, None, "warning",
                                      f"Error handler flow {handler_flow_id} not found — it may have been deleted")
                return

            error_type, status_code = classify_exception(exc)
            failed_node = self._find_node_by_id(failed_node_id, flow_definition.get('nodes', [])) \
                if failed_node_id else None
            failed_label = ((failed_node or {}).get('data') or {}).get('label') if failed_node else None
            trigger_data = {
                'variables': {
                    'error': {
                        'message': str(exc),
                        'type': error_type,
                        'status_code': status_code,
                        'exception': type(exc).__name__,
                        'node_id': failed_node_id,
                        'node_label': failed_label,
                        'attempts': getattr(exc, '_ioflow_attempts', 1),
                    },
                    'execution': {
                        'execution_id': execution_id,
                        'trigger_type': source['trigger_type'],
                        'started_at': source['started_at'],
                        'failed_at': datetime.utcnow().isoformat() + 'Z',
                    },
                    'flow': {
                        'flow_id': source['flow_id'],
                        'flow_name': source['flow_name'],
                    },
                },
                '_error_handler_source': execution_id,
                'user_id': self.user_id or initial_data.get('user_id'),
            }

            handler_engine = ExecutionEngine(self.tenant_schema, self.tenant_id, self.user_id)
            task = asyncio.create_task(
                handler_engine.execute_flow(handler_flow_id, trigger_data, trigger_type='error_handler'))
            # Hold a reference so the fire-and-forget task is not garbage collected
            ExecutionEngine._background_tasks.add(task)
            task.add_done_callback(ExecutionEngine._background_tasks.discard)

            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, execution_id, None, "info",
                                  f"🚨 Started error handler flow {handler_flow_id}",
                                  {"error_handler_flow_id": handler_flow_id, "error_category": error_type})
        except Exception as handler_error:
            logger.error(f"Failed to trigger error handler flow for execution {execution_id}: {handler_error}",
                         exc_info=True)

    async def _run_node_with_error_policy(self, node_id: str, node_type: str, node_data: Dict[str, Any],
                                          handler, engine_ctx, context: Dict[str, Any],
                                          policy: ErrorPolicy):
        """Execute a node handler under its error policy.

        Returns ``(result, None)`` on success, or ``(handled_output, error)``
        when the failure was handled by ``continue`` / ``error_branch``.
        Unhandled failures (policy ``stop``, fatal error types, exhausted
        retries without a handler) are re-raised unchanged.
        """
        node_label = node_data.get('label', node_id)
        attempt = 0
        while True:
            attempt += 1
            try:
                result = await handler.execute(node_data, context, engine_ctx)
                if policy.fail_on_unsuccessful_response:
                    soft_error = unsuccessful_result_error(result)
                    if soft_error is not None:
                        raise soft_error
                if attempt > 1:
                    def _log_recovered():
                        with get_tenant_db(self.tenant_schema) as db:
                            self._log_execution(db, context['execution_id'], node_id, "info",
                                              f"🔁 Node succeeded on attempt {attempt}/{policy.retry.max_attempts}",
                                              {"execution_stage": "node_retry_succeeded", "attempt": attempt})
                    await asyncio.to_thread(_log_recovered)
                return result, None
            except Exception as e:
                # Engine flow-control signals and failures of nodes downstream
                # of this one are not this node's failure
                if is_control_flow_exception(e) or should_skip_policy(e, node_id):
                    raise

                error_type, status_code = classify_exception(e)

                if policy.should_retry(error_type, attempt):
                    delay = policy.retry.delay_seconds(attempt)
                    retry_msg = (f"⚠️ Attempt {attempt}/{policy.retry.max_attempts} failed "
                                 f"({error_type}): {str(e)[:300]} — retrying in {delay:.1f}s")
                    logger.warning(f"Node {node_id}: {retry_msg}")

                    def _log_retry():
                        with get_tenant_db(self.tenant_schema) as db:
                            self._log_execution(db, context['execution_id'], node_id, "warning", retry_msg, {
                                "execution_stage": "node_retry",
                                "attempt": attempt,
                                "max_attempts": policy.retry.max_attempts,
                                "delay_seconds": round(delay, 3),
                                "error_category": error_type,
                                "status_code": status_code,
                                "error_message": str(e),
                            })
                    await asyncio.to_thread(_log_retry)
                    try:
                        await self._send_status_notification(context['execution_id'], {
                            'type': 'node_retry',
                            'node_id': node_id,
                            'node_type': node_type,
                            'node_label': node_label,
                            'attempt': attempt,
                            'max_attempts': policy.retry.max_attempts,
                            'delay_seconds': round(delay, 3),
                            'error': str(e),
                            'error_category': error_type,
                            'status': 'retrying'
                        })
                    except Exception as ws_error:
                        logger.warning(f"Failed to send node retry WebSocket notification: {ws_error}")
                    await asyncio.sleep(delay)
                    continue

                try:
                    e._ioflow_attempts = attempt
                except Exception:
                    pass

                if error_type in FATAL_ERROR_TYPES or not policy.handles_errors:
                    raise

                error = build_error_object(e, node_id=node_id, node_type=node_type,
                                           node_label=node_label, attempts=attempt,
                                           handled_by=policy.on_error)
                logger.info(f"Node {node_id} failed after {attempt} attempt(s); "
                            f"handled by on-error '{policy.on_error}': {error['message']}")
                return build_handled_output(policy, error), error

    async def _report_handled_error(self, node_id: str, node_type: str, node_data: Dict[str, Any],
                                    error: Dict[str, Any], policy: ErrorPolicy,
                                    context: Dict[str, Any], debug_mode: bool):
        """Log and broadcast a node failure that the node's policy handled.

        Reported as a (warning) node completion so the execution keeps going in
        every UI; the ``handled_error`` field carries the details.
        """
        node_label = node_data.get('label', node_id)
        route = 'error branch' if policy.on_error == ON_ERROR_BRANCH else 'continue'
        message = f"⚠️ {node_type.title()} node failed — handled ({route}): {error['message']}"
        log_data = {
            'execution_stage': 'node_error_handled',
            'node_type': node_type,
            'label': node_label,
            'on_error': policy.on_error,
            'error': mask_sensitive_data(error),
        }

        def _log_handled():
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], node_id, "warning",
                                  message, log_data, context)
        await asyncio.to_thread(_log_handled)

        try:
            await self._send_status_notification(context['execution_id'], {
                'type': 'node_complete',
                'node_id': node_id,
                'node_type': node_type,
                'node_label': node_label,
                'status': 'completed',
                'completion_message': message,
                'handled_error': {
                    'message': error['message'],
                    'type': error['type'],
                    'status_code': error.get('status_code'),
                    'attempts': error.get('attempts'),
                    'on_error': policy.on_error,
                },
            })
        except Exception as ws_error:
            logger.warning(f"Failed to send handled-error WebSocket notification: {ws_error}")

        if debug_mode:
            await self._send_debug_event(context['execution_id'], {
                'type': 'node_complete',
                'node_id': node_id,
                'node_type': node_type,
                'node_label': node_label,
                'variables': {
                    'input': dict(context.get('variables', {})),
                    'global': dict(context.get('global_vars', {})),
                    'output': dict(context.get('node_outputs', {}).get(node_id, {})),
                    'loop': dict(context.get('loop', {})) if context.get('_in_loop') else {},
                    'node_outputs': dict(context.get('node_outputs', {}))
                },
                'result': context.get('node_outputs', {}).get(node_id),
                'handled_error': error,
            })

    async def _propagate_dead_path(self, source_id: str, target_id: str,
                                   all_nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]],
                                   adjacency: Dict[str, List[str]], context: Dict[str, Any]):
        """Dead-path elimination for fork-join.

        Marks the edge ``source_id -> target_id`` as never going to fire (its
        source took another route, e.g. its error branch). If every join input
        of the target is dead, the target can never run and its own outgoing
        edges die too. If the target was waiting only on inputs that are now
        all completed or dead, it runs now.
        """
        reverse_adjacency = context.get('_reverse_adjacency', {})
        incoming = reverse_adjacency.get(target_id, [])
        if source_id not in incoming:
            return  # not a join input (e.g. loop-internal edge)
        dead_edges = context.setdefault('_dead_edges', set())
        if (source_id, target_id) in dead_edges:
            return
        dead_edges.add((source_id, target_id))

        if all((src, target_id) in dead_edges for src in incoming):
            for next_id in adjacency.get(target_id, []):
                await self._propagate_dead_path(target_id, next_id, all_nodes, edges, adjacency, context)
            return

        completed = context.setdefault('_completed_nodes', set())
        if target_id in completed:
            return
        if all(src in completed or (src, target_id) in dead_edges for src in incoming):
            target_node = self._find_node_by_id(target_id, all_nodes)
            if target_node:
                def _log_join():
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], target_id, "info",
                                          "Fork-join synchronization: remaining inputs were skipped, executing node")
                await asyncio.to_thread(_log_join)
                await self._execute_node(target_node, all_nodes, edges, adjacency, context)

    async def _follow_handle_edges(self, node_id: str, source_handle: str,
                                   all_nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]],
                                   adjacency: Dict[str, List[str]], context: Dict[str, Any]) -> int:
        """Execute the targets of the edges leaving ``node_id`` through
        ``source_handle``. Returns the number of targets executed."""
        context.setdefault('_completed_nodes', set()).add(node_id)
        executed = 0
        for edge in edges:
            if edge.get('source') == node_id and edge.get('sourceHandle') == source_handle:
                next_node = self._find_node_by_id(edge.get('target'), all_nodes)
                if next_node:
                    await self._execute_node(next_node, all_nodes, edges, adjacency, context)
                    executed += 1
        return executed

    async def _follow_error_branch(self, node_id: str, all_nodes: List[Dict[str, Any]],
                                   edges: List[Dict[str, Any]], adjacency: Dict[str, List[str]],
                                   context: Dict[str, Any]):
        """Run the nodes connected to a failed node's error handle."""
        executed = await self._follow_handle_edges(node_id, ERROR_HANDLE, all_nodes, edges,
                                                   adjacency, context)
        if not executed:
            def _log_no_branch():
                with get_tenant_db(self.tenant_schema) as db:
                    self._log_execution(db, context['execution_id'], node_id, "warning",
                                      "Node is set to route errors to its error branch, but no node is "
                                      "connected to its error output — this path ends here")
            await asyncio.to_thread(_log_no_branch)

    async def _execute_trigger_node(self, node_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trigger node - extract parameters from event schema."""
        node_id = context.get('current_node_id', '')

        # Send specific trigger execution notification
        with get_tenant_db(self.tenant_schema) as db:
            trigger_type = node_data.get('triggerType', 'manual')
            self._log_execution(db, context['execution_id'], node_id, "info",
                              f"Processing {trigger_type} trigger with input data...",
                              {"execution_stage": "trigger_processing", "trigger_type": trigger_type})

        # Trigger nodes return extracted parameters from event schema
        # Use the variables extracted during flow setup phase
        result = dict(context.get('variables', {}))

        # Also include original data for backward compatibility
        result.update({
            'webhook_data': context.get('webhook_data', {}),
            'trigger_type': context.get('data', {}).get('trigger_type', 'event'),
            'execution_id': context.get('execution_id')
        })

        # Log the extracted parameters with more detail
        with get_tenant_db(self.tenant_schema) as db:
            extracted_params = {k: v for k, v in result.items()
                             if k not in ['webhook_data', 'trigger_type', 'execution_id']}

            # Show file attachment info if present
            file_info = ""
            if 'file_attach' in extracted_params:
                file_attach = extracted_params['file_attach']
                if isinstance(file_attach, dict) and 'size' in file_attach:
                    file_size_mb = file_attach.get('size', 0) / (1024 * 1024)
                    file_info = f" (includes file: {file_attach.get('name', 'unnamed')} - {file_size_mb:.1f}MB)"
                elif isinstance(file_attach, list):
                    file_count = len(file_attach)
                    total_size = sum(f.get('size', 0) for f in file_attach if isinstance(f, dict))
                    total_mb = total_size / (1024 * 1024)
                    file_info = f" (includes {file_count} files - {total_mb:.1f}MB total)"

            self._log_execution(db, context['execution_id'], node_id, "info",
                              f"📊 Trigger extracted {len(extracted_params)} parameters{file_info}",
                              {"extracted_parameters": list(extracted_params.keys()),
                               "execution_stage": "trigger_complete"})

        return result

    async def _execute_action_node(self, node_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action node (API call)."""
        # Check if this is a simulation
        is_simulation = context.get('data', {}).get('is_simulation', False)
        
        # Handle both snake_case and camelCase from frontend
        app_id = node_data.get('app_id') or node_data.get('appId')
        service_id = node_data.get('service_id') or node_data.get('serviceId')
        service_name = node_data.get('service') or node_data.get('serviceName')
        
        # Check if parameterMapping exists and has values
        parameter_mapping = node_data.get('parameterMapping', {})
        
        # Use parameterMapping if it has actual values
        if parameter_mapping:
            # Resolve any source/value structures in parameterMapping
            # This format is used by newer versions of the flow designer
            resolved_params = {}
            for key, value in parameter_mapping.items():
                if isinstance(value, dict) and 'source' in value and 'value' in value:
                    # New flow designer format: {'source': 'static'|'variable', 'value': ...}
                    source = value.get('source')
                    param_value = value.get('value')
                    
                    if source == 'static':
                        # Static value - use directly
                        resolved_params[key] = param_value
                        logger.debug(f"Resolved static parameter {key}: {param_value}")
                    elif source == 'variable':
                        # Variable reference - convert to template format for later resolution
                        if isinstance(param_value, str):
                            # Ensure it's in template format for _map_parameters to resolve
                            if not param_value.startswith('{{'):
                                resolved_params[key] = f"{{{{{param_value}}}}}"
                            else:
                                resolved_params[key] = param_value
                            logger.debug(f"Converted variable parameter {key}: {param_value} -> {resolved_params[key]}")
                        else:
                            resolved_params[key] = param_value
                    else:
                        # Unknown source type - use value as fallback
                        resolved_params[key] = param_value
                        logger.warning(f"Unknown parameter source '{source}' for {key}, using value directly")
                else:
                    # Not a source/value structure - use as-is (older flow format)
                    resolved_params[key] = value
            
            parameters = resolved_params
            logger.info(f"Using resolved parameterMapping from node_data: {redact_secrets(parameters)}")
        else:
            parameters = node_data.get('parameters', {})
            logger.info(f"Using standard parameters from node_data: {redact_secrets(parameters)}")
        
        # Log the received node data for debugging
        logger.info(f"_execute_action_node received: app_id={app_id}, service_id={service_id}, service_name={service_name}")
        logger.info(f"Raw parameters from node_data: {redact_secrets(parameters)}")
        
        # Debug logging for context
        logger.info(f"Action node context - In loop: {context.get('_in_loop', False)}")
        if context.get('_in_loop'):
            logger.info(f"Loop variables available: {list(context.get('loop', {}).keys())}")
            logger.info(f"Loop data: {context.get('loop', {})}")
        logger.info(f"Context data keys: {list(context.get('data', {}).keys()) if isinstance(context.get('data'), dict) else 'not a dict'}")
        logger.info(f"Available node_outputs: {list(context.get('node_outputs', {}).keys())}")
        
        # Ensure parameters is a dictionary
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
                logger.info(f"Converted parameters from string in _execute_action_node")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse parameters string in _execute_action_node: {parameters}")
                parameters = {}
        elif not isinstance(parameters, dict):
            logger.error(f"Parameters is not a dict or string in _execute_action_node: {type(parameters)}")
            parameters = {}
        is_async = node_data.get('async', False)
        
        # Check for simulated response
        simulate_response = node_data.get('simulateResponse')
        if simulate_response and is_simulation:
            logger.info(f"Using simulated response for action node")
            # Map any variables in the simulated response
            if isinstance(simulate_response, dict):
                mapped_response = self._map_parameters(simulate_response, context)
                return {"data": mapped_response, "simulated": True}
            else:
                return {"data": simulate_response, "simulated": True}
        
        with get_tenant_db(self.tenant_schema) as db:
            # First check if this is a Debug application
            app = db.query(Application).filter(Application.app_id == app_id).first()
            if not app:
                raise ValueError(f"Application {app_id} not found")
            
            # Handle Debug application specially
            if app.app_name == "Debug":
                # For debug app, always use service_id to get the correct service name
                if service_id:
                    # Query the service to get its name
                    debug_service = db.query(ApplicationService).filter(
                        ApplicationService.service_id == service_id
                    ).first()
                    if debug_service:
                        service_name = debug_service.service_name
                    else:
                        raise ValueError(f"Debug service with ID {service_id} not found")
                return await self._execute_debug_action(app, service_name or 'print', parameters, context, db)
            
            # Check if this is a published flow application - they don't require subscriptions
            from db.application_models import PublishedApplication
                
            published_app = db.query(PublishedApplication).filter(
                PublishedApplication.app_id == app_id,
                PublishedApplication.status == 'active'
            ).first()
            
            subscription = None  # Initialize subscription variable
            
            if published_app:
                # Published flow applications are automatically available, no subscription required
                # Continue with execution using the app we already have
                pass
            else:
                # For regular applications, check subscription
                # Get tenant_id and user_id from context
                tenant_id = context.get('tenant_id', self.tenant_id)
                user_id = context.get('user_id', self.user_id)
                
                # Log the context being used for subscription lookup
                logger.info(f"Looking up subscription for app {app_id} with context: tenant_id={tenant_id}, user_id={user_id}")
                
                subscription = db.query(ApplicationSubscription).options(
                    joinedload(ApplicationSubscription.application)
                ).filter(
                    ApplicationSubscription.app_id == app_id,
                    ApplicationSubscription.tenant_id == tenant_id,
                    ApplicationSubscription.status == 'active'
                ).first()
                
                if not subscription:
                    raise ValueError(f"Application {app_id} not subscribed or inactive")
                
                app = subscription.application
            
            # Check if application is in draft status - force simulation mode
            if app.status == 'draft':
                is_simulation = True
                self._log_execution(db, context['execution_id'], context.get('current_node_id'), "info",
                                  f"Application {app.app_name} is in draft status - forcing simulation mode",
                                  {})
            
            # Find service definition - first try by service_id if available
            service = None
            service_obj = None
            
            logger.info(f"Looking for service - service_id: {service_id}, service_name: {service_name}")
            
            if service_id:
                # Query the actual service from database
                service_obj = db.query(ApplicationService).options(
                    joinedload(ApplicationService.application)
                ).filter(
                    ApplicationService.service_id == service_id
                ).first()
                
                # If service_id lookup failed and we have a service_name, try fallback lookup by name in the same app
                if not service_obj and service_name:
                    logger.info(f"Service ID {service_id} not found, trying fallback lookup by name '{service_name}' in app {app_id}")
                    service_obj = db.query(ApplicationService).options(
                        joinedload(ApplicationService.application)
                    ).filter(
                        ApplicationService.app_id == app_id,
                        ApplicationService.service_name == service_name
                    ).first()
                    
                    if service_obj:
                        logger.info(f"Found service by name fallback: {service_obj.service_name} (ID: {service_obj.service_id})")
                
                if service_obj:
                    logger.info(f"Found service_obj: {service_obj.service_name}, type: {service_obj.service_type}")

                    # ===== BILLING ENFORCEMENT =====
                    # Check balance and enforce prepaid billing for non-simulation executions
                    if not is_simulation and not published_app:
                        try:
                            # Get tenant_id for billing check
                            tenant_id = context.get('tenant_id', self.tenant_id)

                            # Estimate data size for cost calculation
                            # We'll use a conservative estimate based on parameters
                            estimated_data_kb = 1.0  # Default 1KB
                            if parameters:
                                try:
                                    params_json = json.dumps(parameters)
                                    estimated_data_kb = len(params_json.encode('utf-8')) / 1024.0
                                except:
                                    estimated_data_kb = 1.0

                            # Check balance (will raise InsufficientBalanceError if insufficient)
                            can_execute, estimated_cost, billing_mode = balance_enforcer.check_balance_for_service(
                                tenant_id=tenant_id,
                                app_id=app.app_id,
                                service_id=service_obj.service_id,
                                estimated_data_kb=estimated_data_kb,
                                db=db
                            )

                            logger.info(f"Balance check passed - billing_mode: {billing_mode}, estimated_cost: {estimated_cost}")

                            # Reserve funds if prepaid
                            if billing_mode == 'prepaid' and estimated_cost > 0:
                                balance_enforcer.reserve_funds(
                                    tenant_id=tenant_id,
                                    amount=estimated_cost,
                                    execution_id=context.get('execution_id'),
                                    app_id=app.app_id,
                                    service_name=service_obj.service_name,
                                    db=db
                                )
                                logger.info(f"Reserved funds: {estimated_cost} for execution {context.get('execution_id')}")

                                # Store billing info in context for later commit/release
                                context['billing_mode'] = billing_mode
                                context['billing_estimated_cost'] = estimated_cost

                        except InsufficientBalanceError as e:
                            logger.error(f"Insufficient balance for service execution: {str(e)}")
                            # Log the billing error
                            self._log_execution(
                                db,
                                context['execution_id'],
                                context.get('current_node_id'),
                                "error",
                                f"Insufficient balance to execute service '{service_obj.service_name}': {str(e)}",
                                {"error_type": "InsufficientBalanceError", "service_id": service_obj.service_id}
                            )
                            raise
                        except (ServiceAccessDeniedError, PricingNotConfiguredError) as e:
                            logger.error(f"Billing check failed: {str(e)}")
                            self._log_execution(
                                db,
                                context['execution_id'],
                                context.get('current_node_id'),
                                "error",
                                f"Service access denied for '{service_obj.service_name}': {str(e)}",
                                {"error_type": type(e).__name__, "service_id": service_obj.service_id}
                            )
                            raise
                    # ===== END BILLING ENFORCEMENT =====

                    # Wrap service execution with billing error handling
                    try:
                        # Check if service uses new service_config or legacy fields
                        # file_protocol and file_operation services must always use the new executor regardless of service_config content
                        if service_obj.service_type in ['file_protocol', 'file_operation']:
                            logger.info(f"Service type is {service_obj.service_type}, routing to FileProtocolExecutor")
                            result = await self._execute_service_with_type(service_obj, subscription, parameters, context, is_simulation)
                            # Commit billing after successful execution
                            await self._commit_billing(context, db)
                            return result
                        elif service_obj.service_type == 'ai_agent_execute':
                            logger.info(f"Service type is {service_obj.service_type}, routing to FlowAgentExecutor")
                            result = await self._execute_service_with_type(service_obj, subscription, parameters, context, is_simulation)
                            # Commit billing after successful execution
                            await self._commit_billing(context, db)
                            return result
                        elif service_obj.service_config and service_obj.service_type in ['api_call', 'webhook', 'email_send', 'smtp_send', 'pop3_receive', 'imap_receive', 'llm_api_call', 'mcp_call', 'database_query', 'graphql', 'ssh_command']:
                            logger.info(f"Service type {service_obj.service_type} with config, routing to executor")
                            result = await self._execute_service_with_type(service_obj, subscription, parameters, context, is_simulation)
                            # Commit billing after successful execution
                            await self._commit_billing(context, db)
                            return result
                        else:
                            logger.warning(f"Service {service_obj.service_name} (type: {service_obj.service_type}) falling through to legacy HTTP path")
                    except Exception as e:
                        # Release reserved funds on execution failure
                        await self._release_billing(context, db)
                        raise

                    # Get method and endpoint from service_config
                    method = 'GET'  # Default
                    endpoint_template = ''  # Default
                    if service_obj.service_config:
                        try:
                            service_config = json.loads(service_obj.service_config) if isinstance(service_obj.service_config, str) else service_obj.service_config
                            request_config = service_config.get('request_config', {})
                            method = request_config.get('method', 'GET')
                            # Get endpoint from service_config
                            endpoint_template = service_config.get('endpoint_template', '') or service_config.get('endpoint_url', '')
                        except Exception as e:
                            logger.error(f"Failed to extract method/endpoint from service_config: {e}")
                    
                    service = {
                        'name': service_obj.service_name,
                        'method': method,
                        'endpoint': endpoint_template,
                        'callback_required': service_obj.is_async
                    }
            elif service_name:
                # Fallback to searching by name in app.services
                logger.info(f"No service_obj found, searching in app.services for '{service_name}'")
                for svc in app.services:
                    if svc['name'] == service_name:
                        service = svc
                        logger.info(f"Found service in app.services: {service}")
                        
                        # Check if this is a file service from app.services
                        service_type = svc.get('service_type') or svc.get('type')
                        if service_type in ['file_protocol', 'file_operation']:
                            logger.error(f"Found {service_type} service in app.services - this should have been in database!")
                            # For file operations, we need to prevent HTTP requests
                            raise ValueError(f"File operation service '{service_name}' (type: {service_type}) must be properly installed in database. Please install the 'File Systems' application.")
                        break
            
            if not service:
                raise ValueError(f"Service not found in application {app.app_name}")
            
            # Prepare request - PostgreSQL stores JSONB natively
            auth_creds_to_decrypt = subscription.auth_credentials if subscription else None
            auth_credentials = decrypt_credentials(auth_creds_to_decrypt) if auth_creds_to_decrypt else {}
            
            # Merge custom parameters from subscription_config
            from services.custom_params_patch import merge_custom_params_with_credentials

            # Ensure subscription_config is a dict (handles both PostgreSQL JSONB and SQLite TEXT/double-serialized)
            sub_config = ensure_dict(subscription.subscription_config if subscription else None, "subscription_config")

            # Merge custom params with auth credentials
            auth_credentials = merge_custom_params_with_credentials(auth_credentials, sub_config)

            # Map parameters
            mapped_params = self._map_parameters(parameters, context)

            # Build URL
            endpoint = service['endpoint']
            for param_name, param_value in mapped_params.items():
                endpoint = endpoint.replace(f"{{{param_name}}}", str(param_value))

            # Get base_url from subscription config (already parsed above)
            base_url = sub_config.get('base_url', '')
            url = f"{base_url}{endpoint}"
            
            # Safety check: Prevent non-HTTP protocols from reaching HTTP client
            # Only check if base_url looks like it has a protocol (contains ://)
            if base_url and '://' in base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
                logger.error(f"Invalid protocol for HTTP request. base_url: {base_url}, service: {service}")
                raise ValueError(f"Cannot make HTTP request to non-HTTP URL: {url}. Protocol services must use specialized executors.")
            
            # PostgreSQL stores JSONB natively
            auth_config = app.auth_config or {}
            
            # Prepare headers
            headers = self._build_auth_headers(auth_config, auth_credentials)
            
            # Execute request
            if is_async and service.get('callback_required'):
                # Create async callback
                callback = AsyncCallback(
                    execution_id=context['execution_id'],
                    step_id=node_data.get('id', 'unknown'),
                    status='pending'
                )
                db.add(callback)
                db.commit()
                
                # Add callback URL to parameters
                callback_url = f"https://api.ioflow.com/api/v1/executions/callback/{callback.callback_token}"
                mapped_params['callback_url'] = callback_url
                
                # Update execution status to paused
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == context['execution_id']
                ).first()
                execution.status = ExecutionStatus.PAUSED
                db.commit()
            
            # Log the API call details
            api_call_info = {
                'method': service['method'],
                'url': url,
                'app_name': app.app_name,
                'service_name': service['name'],
                'has_auth': bool(auth_credentials),
                'is_async': is_async,
                'is_simulation': is_simulation
            }
            
            if is_simulation:
                self._log_execution(db, context['execution_id'], node_data.get('id'), "info", 
                                  f"[SIMULATION] Would call {app.app_name} API: {service['method']} {url}",
                                  api_call_info)
            else:
                self._log_execution(db, context['execution_id'], node_data.get('id'), "info", 
                                  f"Calling {app.app_name} API: {service['method']} {url}",
                                  api_call_info)
        
        # In simulation mode, don't make actual HTTP request
        if is_simulation:
            # Return mock response
            return {
                'status': 200,
                'message': 'Simulated response',
                'simulation': True,
                'request_details': {
                    'method': service['method'],
                    'url': url,
                    'params': mapped_params,
                    'app': app.app_name,
                    'service': service['name']
                }
            }
        
        # Prepare query and body parameters
        query_params = None
        body_params = mapped_params
        
        # Extract custom query params from auth_credentials if present
        if 'query_params' in auth_credentials:
            query_params = auth_credentials['query_params'].copy()
            logger.info(f"Adding custom query params: {list(query_params.keys())}")
            
            # For GET/DELETE, also merge mapped params into query params
            if service['method'] in ['GET', 'DELETE']:
                query_params.update(mapped_params)
        elif service['method'] in ['GET', 'DELETE']:
            query_params = mapped_params
        
        # Extract custom body params from auth_credentials if present
        if 'body_params' in auth_credentials and service['method'] in ['POST', 'PUT', 'PATCH']:
            body_params = mapped_params.copy()
            body_params.update(auth_credentials['body_params'])
            logger.info(f"Adding custom body params: {list(auth_credentials['body_params'].keys())}")
        
        # Make HTTP request wrapped with billing handling
        try:
            response = await self._make_http_request(
                method=service['method'],
                url=url,
                headers=headers,
                json=body_params if service['method'] in ['POST', 'PUT', 'PATCH'] else None,
                params=query_params
            )

            # Commit billing after successful execution
            with get_tenant_db(self.tenant_schema) as db:
                await self._commit_billing(context, db)

            return response
        except Exception as e:
            # Release reserved funds on execution failure
            with get_tenant_db(self.tenant_schema) as db:
                await self._release_billing(context, db)
            raise
    
    async def _execute_condition_node(self, node_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a condition node."""
        # Get expression from node data
        expression = node_data.get('expression')
        
        # Log available variables for debugging - with more detail
        with get_tenant_db(self.tenant_schema) as db:
            # Log the full context data to see what we're receiving
            debug_info = {
                'variables': context.get('variables', {}),
                'data': context.get('data', {}),  # Add this to see what's in data
                'node_outputs': list(context.get('node_outputs', {}).keys()),
                'expression': expression,
                'in_loop': context.get('_in_loop', False),
                'loop_node_id': context.get('_loop_node_id', None),
                'loop_type': context.get('_loop_type', None)
            }
            self._log_execution(db, context['execution_id'], node_data.get('id'), "debug", 
                              f"Evaluating condition with full context",
                              debug_info)
        
        if not expression:
            # Fallback to old format
            condition = node_data.get('condition', {})
            if condition:
                field = condition.get('field')
                operator = condition.get('operator')
                value = condition.get('value')
                result = self._evaluate_simple_condition(field, operator, value, context)
            else:
                raise ValueError("No expression or condition defined for condition node")
        else:
            # Evaluate JavaScript-like expression
            result = self._evaluate_expression(expression, context)
        
        with get_tenant_db(self.tenant_schema) as db:
            # Log the evaluation context for debugging
            available_vars = {
                'input': list(context.get('variables', {}).keys()),
                'node_outputs': list(context.get('node_outputs', {}).keys()),
            }
            self._log_execution(db, context['execution_id'], node_data.get('id'), "info", 
                              f"Condition evaluated: {expression if expression else 'legacy condition'} = {result}",
                              {"expression": expression, "result": result, "available_variables": available_vars})
        
        
        # Return original data with condition result
        return {**context['data'], '_condition_result': result}
    
    async def _execute_parallel_node(self, node_data: Dict[str, Any], context: Dict[str, Any],
                                   all_nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], 
                                   adjacency: Dict[str, List[str]]) -> Dict[str, Any]:
        """Execute parallel branches."""
        node_id = node_data.get('id')
        branches = adjacency.get(node_id, [])
        
        if not branches:
            return context['data']
        
        with get_tenant_db(self.tenant_schema) as db:
            self._log_execution(db, context['execution_id'], node_id, "info", 
                              f"Executing {len(branches)} parallel branches")
        
        # Execute branches in parallel
        tasks = []
        for branch_node_id in branches:
            branch_node = self._find_node_by_id(branch_node_id, all_nodes)
            if branch_node:
                # Create separate context for each branch
                branch_context = {
                    'data': context['data'].copy(),
                    'execution_id': context['execution_id'],
                    'variables': context['variables'].copy(),
                    'node_outputs': context.get('node_outputs', {}).copy(),  # Copy existing node outputs so branches can access previous data
                    'global_vars': context.get('global_vars', {}).copy(),  # Also copy global variables
                    '_branch_id': branch_node_id,  # Add branch identification for debugging
                    '_parent_context': 'parallel',  # Mark as parallel branch context
                    '_reverse_adjacency': context.get('_reverse_adjacency', {}),  # Copy synchronization data
                    '_completed_nodes': context.get('_completed_nodes', set()),  # Share completed nodes tracking
                    '_pending_executions': context.get('_pending_executions', {}),  # Share pending executions
                    '_all_nodes': context.get('_all_nodes', [])  # Share all nodes reference
                }
                tasks.append(self._execute_node(branch_node, all_nodes, edges, adjacency, branch_context))
        
        # Wait for all branches to complete
        branch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Enhanced result merging with individual node outputs preservation
        merged_result = context['data'].copy()
        branch_node_outputs = {}
        successful_branches = 0
        
        with get_tenant_db(self.tenant_schema) as db:
            for i, (branch_id, result) in enumerate(zip(branches, branch_results)):
                if isinstance(result, Exception):
                    logger.error(f"Parallel branch {i} (node_id: {branch_id}) failed: {str(result)}")
                    self._log_execution(db, context['execution_id'], node_id, "error", 
                                      f"Branch {i} ({branch_id}) execution failed: {str(result)}")
                else:
                    successful_branches += 1
                    # Store branch result with branch identification
                    merged_result[f'branch_{i}'] = result
                    merged_result[f'branch_{branch_id}'] = result  # Also store by node ID for easier access
                    
                    # Collect node outputs from this branch for later merging
                    # Note: We would need to capture the branch context's node_outputs here
                    # For now, we'll enhance this in a future iteration
                    
                    self._log_execution(db, context['execution_id'], node_id, "info", 
                                      f"Branch {i} ({branch_id}) completed successfully")
            
            # Log overall parallel execution summary
            total_branches = len(branches)
            self._log_execution(db, context['execution_id'], node_id, "info", 
                              f"Parallel execution completed: {successful_branches}/{total_branches} branches successful")
        
        return merged_result
    
    async def _execute_response_node(self, node_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a response node - store the response data for synchronous flows."""
        variable_path = node_data.get('variable')
        status_code_value = node_data.get('statusCode', 200)
        
        # Process status code - it might be a template or a direct value
        if isinstance(status_code_value, str):
            if '{{' in status_code_value and '}}' in status_code_value:
                # It's a template - interpolate it
                interpolated = self._interpolate_template_string(status_code_value, context)
                try:
                    status_code = int(interpolated) if interpolated is not None else 200
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert interpolated status code '{interpolated}' to integer, using default 200")
                    status_code = 200
            else:
                # Try to convert string to integer
                try:
                    status_code = int(status_code_value)
                except ValueError:
                    logger.warning(f"Could not convert status code '{status_code_value}' to integer, using default 200")
                    status_code = 200
        else:
            # Direct integer or None
            status_code = status_code_value if isinstance(status_code_value, int) else 200
        
        headers_value = node_data.get('headers', {})
        output_format = node_data.get('outputFormat', 'text')
        
        # Parse headers if they're a string (JSON) or variable reference
        headers = {}
        if isinstance(headers_value, str) and headers_value:
            if headers_value.startswith('{{') and headers_value.endswith('}}'):
                # It's a variable reference
                headers_path = headers_value[2:-2]
                headers = self._get_field_value(headers_path, context) or {}
                # Convert AttrDict to regular dict if necessary
                headers = self._convert_attrdict_to_dict(headers)
            else:
                # Try to parse as JSON
                try:
                    headers = json.loads(headers_value)
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse headers as JSON: {headers_value}")
        elif isinstance(headers_value, dict):
            # Convert AttrDict to regular dict if necessary
            headers = self._convert_attrdict_to_dict(headers_value)
        
        # Check if there's a direct response value (hardcoded string)
        response_value = node_data.get('response') or node_data.get('value')
        
        # Handle variable path that might be wrapped in double curly braces
        if variable_path and variable_path.startswith('{{') and variable_path.endswith('}}'):
            variable_path = variable_path[2:-2]  # Remove {{ and }}
            logger.debug(f"Removed double curly braces from variable_path: {variable_path}")

        # Debug logging - log entire node_data to see what fields are available
        logger.debug(f"Response node configuration: {json.dumps(node_data, indent=2)}")
        logger.debug(f"Response node executing with variable_path: {variable_path}, direct response: {response_value}")
        logger.debug(f"Available node_outputs: {list(context.get('node_outputs', {}).keys())}")
        logger.debug(f"Context data keys: {list(context.get('data', {}).keys())}")
        logger.debug(f"Global variables available: {list(context.get('global_vars', {}).keys())}")
        
        # Determine the response data
        if response_value:
            # Check if the response value contains template variables
            if isinstance(response_value, str) and '{{' in response_value and '}}' in response_value:
                # Process template interpolation
                response_data = self._interpolate_template_string(response_value, context)
                logger.debug(f"Interpolated template string to response data")
            else:
                # If there's a direct response value (no templates), use it
                response_data = response_value
                logger.debug(f"Using direct response value")
        elif variable_path:
            # Check if variable_path is a string literal (enclosed in quotes)
            if (isinstance(variable_path, str) and
                ((variable_path.startswith('"') and variable_path.endswith('"')) or
                 (variable_path.startswith("'") and variable_path.endswith("'")))):
                # It's a string literal, remove the quotes and use it directly
                response_data = variable_path[1:-1]
                logger.debug(f"Using string literal as response")
            else:
                # Extract the variable value from context
                logger.debug(f"Resolving response from variable path: {variable_path}")
                response_data = self._get_field_value(variable_path, context)
                # Convert AttrDict to regular dict if necessary
                response_data = self._convert_attrdict_to_dict(response_data)
                logger.debug(f"Resolved response_data from path '{variable_path}'")
            
            # If response_data is None, try some fallback paths
            if response_data is None:
                logger.warning(f"Could not resolve path '{variable_path}', trying fallbacks")
                # Try without 'data' suffix if it's there
                if variable_path.endswith('.data'):
                    alt_path = variable_path[:-5]  # Remove '.data'
                    response_data = self._get_field_value(alt_path, context)
                    if response_data is not None:
                        logger.debug(f"Found data using alternate path '{alt_path}'")

                # If still None, try to get the last action node's output
                if response_data is None and context.get('node_outputs'):
                    # Find the most recent action node output
                    for node_id, output in context['node_outputs'].items():
                        if output is not None:
                            response_data = output
                            # Convert AttrDict to regular dict if necessary
                            response_data = self._convert_attrdict_to_dict(response_data)
                            logger.debug(f"Using output from node {node_id} as fallback")
                            break
        else:
            # If no variable or response value specified, return the current data
            response_data = context['data']
            # Convert AttrDict to regular dict if necessary
            response_data = self._convert_attrdict_to_dict(response_data)
            logger.debug(f"Using context data as response")
        
        # Store response in execution
        with get_tenant_db(self.tenant_schema) as db:
            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == context['execution_id']
            ).first()
            
            if execution:
                execution.result_data = response_data
                execution.response_status = status_code
                execution.response_headers = headers
                # Store output format in response headers for frontend access
                if headers is None:
                    headers = {}
                headers['X-Output-Format'] = output_format
                execution.response_headers = headers
                db.commit()
                
                self._log_execution(db, context['execution_id'], node_data.get('id'), "info",
                                  f"Response stored with status {status_code} and format {output_format}",
                                  {"status_code": status_code, "has_headers": bool(headers), "output_format": output_format, "response_data": response_data})
        
        # Return the response data to continue flow if needed
        return response_data

    async def _execute_human_in_loop_node(self, node_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a human_in_loop node - pause execution and create a task for human review."""
        import uuid as uuid_mod
        from datetime import timedelta

        node_id = node_data.get('id', context.get('current_node_id', 'unknown'))
        task_type = node_data.get('taskType', 'review')
        title = node_data.get('title', f'Human Review - {node_data.get("label", node_id)}')
        description = node_data.get('description', '')
        priority = node_data.get('priority', 'medium')
        assignment_config = node_data.get('assignmentConfig', {})
        display_config = node_data.get('displayConfig', {})
        timeout_minutes = node_data.get('timeoutMinutes', 0)
        escalation_config = node_data.get('escalationConfig', None)

        # Resolve input data to present to the user
        input_data_mapping = node_data.get('inputDataMapping', {})
        input_data = {}
        if input_data_mapping:
            for field_name, field_path in input_data_mapping.items():
                if isinstance(field_path, str) and '{{' in field_path and '}}' in field_path:
                    # Template variable - resolve it
                    clean_path = field_path.strip('{}').strip()
                    resolved = self._get_field_value(clean_path, context)
                    if resolved is not None:
                        resolved = self._convert_attrdict_to_dict(resolved)
                    input_data[field_name] = resolved
                else:
                    input_data[field_name] = field_path
        else:
            # Default: pass through all previous node outputs
            for nid, output in context.get('node_outputs', {}).items():
                if nid != 'trigger':
                    input_data[nid] = self._convert_attrdict_to_dict(output) if output else output

        # Interpolate title and description templates
        if '{{' in title:
            title = self._interpolate_template_string(title, context)
        if description and '{{' in description:
            description = self._interpolate_template_string(description, context)

        # Build execution snapshot for resume
        # Store only serializable parts of context
        snapshot_context = {
            'variables': self._convert_attrdict_to_dict(context.get('variables', {})),
            'node_outputs': {},
            'global_vars': self._convert_attrdict_to_dict(context.get('global_vars', {})),
            'execution_id': context.get('execution_id'),
            'tenant_id': context.get('tenant_id'),
            'user_id': context.get('user_id'),
            'schema_name': context.get('schema_name'),
        }
        # Serialize node_outputs
        for nid, output in context.get('node_outputs', {}).items():
            try:
                snapshot_context['node_outputs'][nid] = self._convert_attrdict_to_dict(output)
            except Exception:
                snapshot_context['node_outputs'][nid] = str(output)

        # Add loop context if in a loop
        if context.get('_in_loop'):
            snapshot_context['_in_loop'] = True
            snapshot_context['_loop_node_id'] = context.get('_loop_node_id')
            snapshot_context['_loop_type'] = context.get('_loop_type')
            snapshot_context['_loop_back_nodes'] = context.get('_loop_back_nodes', [])
            snapshot_context['loop'] = self._convert_attrdict_to_dict(context.get('loop', {}))

        # Calculate timeout
        timeout_at = None
        if timeout_minutes and timeout_minutes > 0:
            timeout_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)

        # Build escalation config with timeout info
        full_escalation_config = None
        if escalation_config or timeout_minutes > 0:
            full_escalation_config = escalation_config or {}
            full_escalation_config['timeout_minutes'] = timeout_minutes

        # Get flow_id and flow name for metadata
        flow_id = context.get('flow_id', '')
        flow_name = ''
        with get_tenant_db(self.tenant_schema) as db:
            # If flow_id not in context, get it from the execution record
            if not flow_id:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == context['execution_id']
                ).first()
                if execution:
                    flow_id = execution.flow_id
            flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
            if flow:
                flow_name = flow.flow_name

        task_id = str(uuid_mod.uuid4())
        task_token = str(uuid_mod.uuid4())

        # Create the HITL task
        with get_tenant_db(self.tenant_schema) as db:
            task = HITLTask(
                task_id=task_id,
                tenant_id=context.get('tenant_id', ''),
                execution_id=context['execution_id'],
                flow_id=flow_id,
                node_id=node_id,
                task_token=task_token,
                task_type=task_type,
                title=title,
                description=description,
                status='pending',
                priority=priority,
                input_data=input_data,
                display_config=display_config,
                response_data=None,
                response_action=None,
                timeout_at=timeout_at,
                escalation_config=full_escalation_config,
                escalation_level=0,
                execution_snapshot=snapshot_context,
                task_metadata={
                    'flow_name': flow_name,
                    'node_label': node_data.get('label', node_id),
                    'flow_id': flow_id,
                }
            )
            db.add(task)

            # Create task assignments
            assign_type = assignment_config.get('type', 'user')
            assignments_created = 0
            if assign_type == 'user':
                user_ids = assignment_config.get('users', [])
                for uid in user_ids:
                    assignment = HITLTaskAssignment(
                        id=str(uuid_mod.uuid4()),
                        task_id=task_id,
                        assignee_type='user',
                        assignee_id=uid,
                        tenant_id=context.get('tenant_id', ''),
                    )
                    db.add(assignment)
                    assignments_created += 1
            elif assign_type == 'role':
                role_ids = assignment_config.get('roles', [])
                for rid in role_ids:
                    assignment = HITLTaskAssignment(
                        id=str(uuid_mod.uuid4()),
                        task_id=task_id,
                        assignee_type='hitl_role',
                        assignee_id=rid,
                        tenant_id=context.get('tenant_id', ''),
                    )
                    db.add(assignment)
                    assignments_created += 1

            # Fallback: if no assignments were created, assign to the flow executor
            if assignments_created == 0 and context.get('user_id'):
                fallback_assignment = HITLTaskAssignment(
                    id=str(uuid_mod.uuid4()),
                    task_id=task_id,
                    assignee_type='user',
                    assignee_id=context['user_id'],
                    tenant_id=context.get('tenant_id', ''),
                )
                db.add(fallback_assignment)
                logger.info(f"HITL task {task_id}: No assignees configured, falling back to flow executor {context['user_id']}")

            # Pause the execution
            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == context['execution_id']
            ).first()
            if execution:
                execution.status = ExecutionStatus.PAUSED
                execution.current_step = node_id

            db.commit()

            # Resolve assignment details for display
            assignee_details = []
            assignments = db.query(HITLTaskAssignment).filter(
                HITLTaskAssignment.task_id == task_id
            ).all()
            for a in assignments:
                if a.assignee_type == 'user':
                    user = db.query(User).filter(User.user_id == a.assignee_id).first()
                    assignee_details.append({
                        'type': 'user',
                        'id': a.assignee_id,
                        'name': user.user_name if user else a.assignee_id,
                    })
                elif a.assignee_type == 'hitl_role':
                    role = db.query(HITLRole).filter(HITLRole.role_id == a.assignee_id).first()
                    assignee_details.append({
                        'type': 'role',
                        'id': a.assignee_id,
                        'name': role.role_name if role else a.assignee_id,
                    })

            assignee_summary = ', '.join(
                f"{a['name']} ({a['type']})" for a in assignee_details
            ) or 'Unassigned'

            # Determine if executing user can complete this task
            executing_user_id = self.user_id or context.get('user_id')
            can_complete = False
            if executing_user_id:
                for a in assignments:
                    if a.assignee_type == 'user' and a.assignee_id == executing_user_id:
                        can_complete = True
                        break
                    elif a.assignee_type == 'hitl_role':
                        user_role_match = db.query(HITLUserRole).filter(
                            HITLUserRole.user_id == executing_user_id,
                            HITLUserRole.hitl_role_id == a.assignee_id
                        ).first()
                        if user_role_match:
                            can_complete = True
                            break
            logger.info(f"HITL task {task_id}: can_complete={can_complete}, executing_user={executing_user_id}, assignments={[(a.assignee_type, a.assignee_id) for a in assignments]}")

            self._log_execution(db, context['execution_id'], node_id, "info",
                              f"⏸️ Flow paused - waiting for human {task_type}: {title}",
                              {
                                  'task_id': task_id,
                                  'task_type': task_type,
                                  'priority': priority,
                                  'assigned_to': assignee_summary,
                                  'assignees': assignee_details,
                                  'timeout_at': timeout_at.isoformat() if timeout_at else None,
                                  'paused_at': datetime.utcnow().isoformat(),
                              })

        # Send WebSocket notification
        try:
            await self._send_status_notification(context['execution_id'], {
                'type': 'hitl_task_created',
                'node_id': node_id,
                'node_type': 'human_in_loop',
                'node_label': node_data.get('label', node_id),
                'status': 'paused',
                'task_id': task_id,
                'task_type': task_type,
                'title': title,
                'priority': priority,
                'message': f'⏸️ Waiting for human {task_type}: {title}',
                'assigned_to': assignee_summary,
                'assignees': assignee_details,
                'can_complete': can_complete,
                'paused_at': datetime.utcnow().isoformat(),
                'timeout_at': timeout_at.isoformat() if timeout_at else None,
            })
        except Exception as ws_error:
            logger.warning(f"Failed to send HITL WebSocket notification: {ws_error}")

        # Send notifications to assigned users (async, non-blocking)
        try:
            from services.hitl_notification_service import hitl_notification_service
            await hitl_notification_service.notify_assignees(
                task_id=task_id,
                tenant_id=context.get('tenant_id', ''),
                schema_name=self.tenant_schema
            )
        except Exception as notify_error:
            logger.warning(f"Failed to send HITL notifications: {notify_error}")

        return {
            '_hitl_paused': True,
            'task_id': task_id,
            'task_token': task_token,
            'status': 'waiting_for_human',
            'task_type': task_type,
            'title': title,
            'priority': priority,
        }

    async def resume_after_hitl(self, task_id: str, hitl_output: Dict[str, Any],
                                 flow_definition: Dict[str, Any], tenant_schema: str):
        """Resume flow execution after a HITL task is completed."""
        with get_tenant_db(tenant_schema) as db:
            task = db.query(HITLTask).filter(HITLTask.task_id == task_id).first()
            if not task:
                raise ValueError(f"HITL task {task_id} not found")

            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == task.execution_id
            ).first()
            if not execution:
                raise ValueError(f"Execution {task.execution_id} not found")

            # Restore execution context from snapshot
            snapshot = task.execution_snapshot or {}
            context = {
                'data': hitl_output,
                'variables': snapshot.get('variables', {}),
                'node_outputs': snapshot.get('node_outputs', {}),
                'global_vars': snapshot.get('global_vars', {}),
                'execution_id': task.execution_id,
                'tenant_id': task.tenant_id,
                'user_id': snapshot.get('user_id', ''),
                'schema_name': snapshot.get('schema_name', tenant_schema),
                'flow_id': task.flow_id,
                '_completed_nodes': set(),
                '_pending_executions': {},
            }

            # Restore loop context if applicable
            # NOTE: Do NOT restore _loop_back_nodes here. After HITL resume, we want
            # the adjacency graph to naturally navigate to the loop node for re-evaluation.
            # Restoring _loop_back_nodes would cause the loop-back interception (line ~976)
            # to stop execution prematurely, since there's no synchronous while loop listening.
            if snapshot.get('_in_loop'):
                context['_in_loop'] = True
                context['_loop_node_id'] = snapshot.get('_loop_node_id')
                context['_loop_type'] = snapshot.get('_loop_type')
                context['loop'] = snapshot.get('loop', {})

            # Inject HITL output as the node's output
            context['node_outputs'][task.node_id] = hitl_output

            # Update execution status
            execution.status = ExecutionStatus.RUNNING
            db.commit()

        # Log HITL completion to database
        with get_tenant_db(tenant_schema) as db:
            self._log_execution(db, task.execution_id, task.node_id, "info",
                              f"✅ Human review completed - flow resuming",
                              {
                                  'task_id': task_id,
                                  'response_action': hitl_output.get('response_action'),
                                  'completed_by': hitl_output.get('completed_by'),
                                  'completed_at': hitl_output.get('completed_at'),
                                  'execution_stage': 'node_complete',
                              })

        # Send WebSocket notification for resume
        try:
            await self._send_status_notification(task.execution_id, {
                'type': 'hitl_task_completed',
                'node_id': task.node_id,
                'node_type': 'human_in_loop',
                'status': 'running',
                'task_id': task_id,
                'response_action': hitl_output.get('response_action'),
                'completed_by': hitl_output.get('completed_by'),
                'completed_at': hitl_output.get('completed_at'),
                'message': f'✅ Human review completed - flow resuming',
            })
        except Exception as ws_error:
            logger.warning(f"Failed to send HITL resume WebSocket notification: {ws_error}")

        # Build adjacency and find next nodes
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        adjacency = self._build_adjacency_list(edges)

        # Build reverse adjacency for fork-join
        reverse_adjacency = self._build_reverse_adjacency_list(edges)
        context['_reverse_adjacency'] = reverse_adjacency
        context['_all_nodes'] = nodes

        # Set up variable manager
        self.variable_manager = FlowVariableManager()
        for nid, output in context['node_outputs'].items():
            self.variable_manager.set_node_output(nid, output)
        for var_name, var_value in context.get('variables', {}).items():
            self.variable_manager.set_global(var_name, var_value)
        # Restore global variables from snapshot (set via set_global() in previous nodes)
        for var_name, var_value in context.get('global_vars', {}).items():
            self.variable_manager.set_global(var_name, var_value)

        # Set up log callback
        context['log_callback'] = lambda step_id, level, message, data=None: None

        try:
            # Execute next nodes from the HITL node
            next_node_ids = adjacency.get(task.node_id, [])
            for next_node_id in next_node_ids:
                next_node = self._find_node_by_id(next_node_id, nodes)
                if next_node:
                    await self._execute_node(next_node, nodes, edges, adjacency, context)

            # Mark execution as completed and collect result data for notification
            # Only send execution_complete if the flow actually finished (not paused at another HITL node)
            execution_actually_completed = False
            result_data = None
            response_headers = None
            response_status = None
            completed_at = None
            with get_tenant_db(tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == task.execution_id
                ).first()
                if execution and execution.status == ExecutionStatus.RUNNING:
                    execution.status = ExecutionStatus.COMPLETED
                    execution.completed_at = datetime.utcnow()
                    # Save final node_outputs
                    final_outputs = {}
                    for nid, output in context.get('node_outputs', {}).items():
                        try:
                            final_outputs[nid] = self._convert_attrdict_to_dict(output)
                        except Exception:
                            final_outputs[nid] = str(output)
                    execution.node_outputs = final_outputs
                    db.commit()

                    # Refresh to get latest data (including result_data from response node)
                    db.refresh(execution)
                    result_data = execution.result_data
                    response_headers = execution.response_headers
                    response_status = execution.response_status
                    completed_at = execution.completed_at.isoformat() if execution.completed_at else None
                    execution_actually_completed = True
                else:
                    logger.info(f"HITL resume: execution {task.execution_id} status is {execution.status if execution else 'not found'}, skipping completion notification")

            if execution_actually_completed:
                # Send completion notification with result data (matching normal completion path)
                await self._send_status_notification(task.execution_id, {
                    'type': 'execution_complete',
                    'execution_id': task.execution_id,
                    'status': 'completed',
                    'completed_at': completed_at,
                    'final_status': 'success',
                    'result': result_data,
                    'response_headers': response_headers,
                    'response_status': response_status,
                    'message': 'Flow execution completed',
                })
                logger.info(f"HITL resume: execution_complete sent for {task.execution_id}")

        except Exception as e:
            logger.error(f"Error resuming flow after HITL: {e}", exc_info=True)
            with get_tenant_db(tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == task.execution_id
                ).first()
                if execution:
                    execution.status = ExecutionStatus.FAILED
                    execution.completed_at = datetime.utcnow()
                    db.commit()

            await self._send_status_notification(task.execution_id, {
                'type': 'execution_error',
                'status': 'failed',
                'error': str(e),
                'message': f'Flow execution failed after HITL resume: {str(e)}',
            })
            raise
        finally:
            # Release any flow-scoped DB transaction pinned while resuming.
            try:
                from services import db_transaction_manager
                await db_transaction_manager.release_all(task.execution_id)
            except Exception as _txn_release_err:
                logger.warning(f"Error releasing DB transactions after HITL resume: {_txn_release_err}")

    async def _execute_wait_for_event_node(self, node_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a wait_for_event node - pause execution until an application event arrives."""
        import uuid as uuid_mod
        from datetime import timedelta

        node_id = node_data.get('id', context.get('current_node_id', 'unknown'))
        app_id = node_data.get('appId', '')
        event_name = node_data.get('eventName', '')
        event_id = node_data.get('eventId', '')
        match_mode = node_data.get('matchMode', 'token')
        correlation_config_raw = node_data.get('correlationConfig', {})
        timeout_minutes = node_data.get('timeoutMinutes', 0)
        timeout_action = node_data.get('timeoutAction', 'fail')
        default_data = node_data.get('defaultData', {})
        label = node_data.get('label', f'Wait for Event - {event_name}')

        # Resolve correlation config - replace template variables with actual values
        correlation_config = None
        if match_mode == 'correlation' and correlation_config_raw:
            event_field = correlation_config_raw.get('eventField', '')
            flow_field = correlation_config_raw.get('flowField', '')
            flow_value = None
            if flow_field and '{{' in flow_field and '}}' in flow_field:
                clean_path = flow_field.strip('{}').strip()
                flow_value = self._get_field_value(clean_path, context)
                if flow_value is not None:
                    flow_value = self._convert_attrdict_to_dict(flow_value) if hasattr(flow_value, '__getattr__') else flow_value
            elif flow_field:
                flow_value = flow_field
            correlation_config = {
                'event_field': event_field,
                'flow_value': flow_value,
            }

        # Interpolate label if it contains templates
        if '{{' in label:
            label = self._interpolate_template_string(label, context)

        # Build execution snapshot for resume (same pattern as HITL)
        snapshot_context = {
            'variables': self._convert_attrdict_to_dict(context.get('variables', {})),
            'node_outputs': {},
            'global_vars': self._convert_attrdict_to_dict(context.get('global_vars', {})),
            'execution_id': context.get('execution_id'),
            'tenant_id': context.get('tenant_id'),
            'user_id': context.get('user_id'),
            'schema_name': context.get('schema_name'),
        }
        for nid, output in context.get('node_outputs', {}).items():
            try:
                snapshot_context['node_outputs'][nid] = self._convert_attrdict_to_dict(output)
            except Exception:
                snapshot_context['node_outputs'][nid] = str(output)

        # Add loop context if in a loop
        if context.get('_in_loop'):
            snapshot_context['_in_loop'] = True
            snapshot_context['_loop_node_id'] = context.get('_loop_node_id')
            snapshot_context['_loop_type'] = context.get('_loop_type')
            snapshot_context['_loop_back_nodes'] = context.get('_loop_back_nodes', [])
            snapshot_context['loop'] = self._convert_attrdict_to_dict(context.get('loop', {}))

        # Calculate timeout
        timeout_at = None
        if timeout_minutes and timeout_minutes > 0:
            timeout_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)

        # Get flow_id and flow/app names for metadata
        flow_id = context.get('flow_id', '')
        flow_name = ''
        app_name = ''
        with get_tenant_db(self.tenant_schema) as db:
            if not flow_id:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == context['execution_id']
                ).first()
                if execution:
                    flow_id = execution.flow_id
            flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
            if flow:
                flow_name = flow.flow_name

            # Get app name
            try:
                app = db.query(Application).filter(Application.app_id == app_id).first()
                if app:
                    app_name = app.app_name
            except Exception:
                pass

        wait_id = str(uuid_mod.uuid4())
        callback_token = str(uuid_mod.uuid4())

        # Create the EventWait record
        with get_tenant_db(self.tenant_schema) as db:
            event_wait = EventWait(
                wait_id=wait_id,
                tenant_id=context.get('tenant_id', ''),
                execution_id=context['execution_id'],
                flow_id=flow_id,
                node_id=node_id,
                app_id=app_id,
                event_name=event_name,
                event_id=event_id or None,
                match_mode=match_mode,
                correlation_config=correlation_config,
                callback_token=callback_token,
                status='waiting',
                timeout_at=timeout_at,
                timeout_action=timeout_action,
                default_data=default_data if default_data else None,
                execution_snapshot=snapshot_context,
                wait_metadata={
                    'flow_name': flow_name,
                    'node_label': label,
                    'flow_id': flow_id,
                    'app_name': app_name,
                }
            )
            db.add(event_wait)

            # Pause the execution
            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == context['execution_id']
            ).first()
            if execution:
                execution.status = ExecutionStatus.PAUSED
                execution.current_step = node_id

            db.commit()

            self._log_execution(db, context['execution_id'], node_id, "info",
                              f"⏸️ Flow paused - waiting for event: {event_name} from {app_name or app_id}",
                              {
                                  'wait_id': wait_id,
                                  'app_id': app_id,
                                  'event_name': event_name,
                                  'match_mode': match_mode,
                                  'correlation_config': correlation_config,
                                  'timeout_at': timeout_at.isoformat() if timeout_at else None,
                                  'timeout_action': timeout_action,
                                  'paused_at': datetime.utcnow().isoformat(),
                              })

        # Send WebSocket notification
        try:
            await self._send_status_notification(context['execution_id'], {
                'type': 'event_wait_created',
                'node_id': node_id,
                'node_type': 'wait_for_event',
                'node_label': label,
                'status': 'paused',
                'wait_id': wait_id,
                'callback_token': callback_token,
                'app_id': app_id,
                'app_name': app_name,
                'event_name': event_name,
                'match_mode': match_mode,
                'message': f'⏸️ Waiting for event: {event_name} from {app_name or app_id}',
                'paused_at': datetime.utcnow().isoformat(),
                'timeout_at': timeout_at.isoformat() if timeout_at else None,
                'timeout_action': timeout_action,
            })
        except Exception as ws_error:
            logger.warning(f"Failed to send event wait WebSocket notification: {ws_error}")

        return {
            '_event_wait_paused': True,
            'wait_id': wait_id,
            'callback_token': callback_token,
            'status': 'waiting_for_event',
            'app_id': app_id,
            'event_name': event_name,
            'match_mode': match_mode,
        }

    async def resume_after_event(self, wait_id: str, event_output: Dict[str, Any],
                                  flow_definition: Dict[str, Any], tenant_schema: str):
        """Resume flow execution after an event wait is matched."""
        with get_tenant_db(tenant_schema) as db:
            event_wait = db.query(EventWait).filter(EventWait.wait_id == wait_id).first()
            if not event_wait:
                raise ValueError(f"EventWait {wait_id} not found")

            execution = db.query(FlowExecution).filter(
                FlowExecution.execution_id == event_wait.execution_id
            ).first()
            if not execution:
                raise ValueError(f"Execution {event_wait.execution_id} not found")

            # Restore execution context from snapshot
            snapshot = event_wait.execution_snapshot or {}
            context = {
                'data': event_output,
                'variables': snapshot.get('variables', {}),
                'node_outputs': snapshot.get('node_outputs', {}),
                'global_vars': snapshot.get('global_vars', {}),
                'execution_id': event_wait.execution_id,
                'tenant_id': event_wait.tenant_id,
                'user_id': snapshot.get('user_id', ''),
                'schema_name': snapshot.get('schema_name', tenant_schema),
                'flow_id': event_wait.flow_id,
                '_completed_nodes': set(),
                '_pending_executions': {},
            }

            # Restore loop context if applicable
            if snapshot.get('_in_loop'):
                context['_in_loop'] = True
                context['_loop_node_id'] = snapshot.get('_loop_node_id')
                context['_loop_type'] = snapshot.get('_loop_type')
                context['loop'] = snapshot.get('loop', {})

            # Inject event output as the node's output
            context['node_outputs'][event_wait.node_id] = event_output

            # Update execution status
            execution.status = ExecutionStatus.RUNNING
            db.commit()

        # Log event wait completion
        with get_tenant_db(tenant_schema) as db:
            timed_out = event_output.get('_timed_out', False)
            msg = "⏰ Event wait timed out - flow resuming with defaults" if timed_out else "✅ Event received - flow resuming"
            self._log_execution(db, event_wait.execution_id, event_wait.node_id, "info",
                              msg,
                              {
                                  'wait_id': wait_id,
                                  'timed_out': timed_out,
                                  'timeout_action': event_output.get('_timeout_action'),
                                  'execution_stage': 'node_complete',
                              })

        # Send WebSocket notification for resume
        try:
            await self._send_status_notification(event_wait.execution_id, {
                'type': 'event_wait_completed',
                'node_id': event_wait.node_id,
                'node_type': 'wait_for_event',
                'status': 'running',
                'wait_id': wait_id,
                'timed_out': timed_out,
                'message': msg,
            })
        except Exception as ws_error:
            logger.warning(f"Failed to send event wait resume WebSocket notification: {ws_error}")

        # Build adjacency and find next nodes
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        adjacency = self._build_adjacency_list(edges)

        # Build reverse adjacency for fork-join
        reverse_adjacency = self._build_reverse_adjacency_list(edges)
        context['_reverse_adjacency'] = reverse_adjacency
        context['_all_nodes'] = nodes

        # Set up variable manager
        self.variable_manager = FlowVariableManager()
        for nid, output in context['node_outputs'].items():
            self.variable_manager.set_node_output(nid, output)
        for var_name, var_value in context.get('variables', {}).items():
            self.variable_manager.set_global(var_name, var_value)
        for var_name, var_value in context.get('global_vars', {}).items():
            self.variable_manager.set_global(var_name, var_value)

        # Set up log callback
        context['log_callback'] = lambda step_id, level, message, data=None: None

        try:
            # Execute next nodes from the wait_for_event node
            next_node_ids = adjacency.get(event_wait.node_id, [])
            for next_node_id in next_node_ids:
                next_node = self._find_node_by_id(next_node_id, nodes)
                if next_node:
                    await self._execute_node(next_node, nodes, edges, adjacency, context)

            # Mark execution as completed if still running
            execution_actually_completed = False
            result_data = None
            response_headers = None
            response_status = None
            completed_at = None
            with get_tenant_db(tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == event_wait.execution_id
                ).first()
                if execution and execution.status == ExecutionStatus.RUNNING:
                    execution.status = ExecutionStatus.COMPLETED
                    execution.completed_at = datetime.utcnow()
                    final_outputs = {}
                    for nid, output in context.get('node_outputs', {}).items():
                        try:
                            final_outputs[nid] = self._convert_attrdict_to_dict(output)
                        except Exception:
                            final_outputs[nid] = str(output)
                    execution.node_outputs = final_outputs
                    db.commit()

                    db.refresh(execution)
                    result_data = execution.result_data
                    response_headers = execution.response_headers
                    response_status = execution.response_status
                    completed_at = execution.completed_at.isoformat() if execution.completed_at else None
                    execution_actually_completed = True
                else:
                    logger.info(f"Event wait resume: execution {event_wait.execution_id} status is {execution.status if execution else 'not found'}, skipping completion notification")

            if execution_actually_completed:
                await self._send_status_notification(event_wait.execution_id, {
                    'type': 'execution_complete',
                    'execution_id': event_wait.execution_id,
                    'status': 'completed',
                    'completed_at': completed_at,
                    'final_status': 'success',
                    'result': result_data,
                    'response_headers': response_headers,
                    'response_status': response_status,
                    'message': 'Flow execution completed',
                })
                logger.info(f"Event wait resume: execution_complete sent for {event_wait.execution_id}")

        except Exception as e:
            logger.error(f"Error resuming flow after event wait: {e}", exc_info=True)
            with get_tenant_db(tenant_schema) as db:
                execution = db.query(FlowExecution).filter(
                    FlowExecution.execution_id == event_wait.execution_id
                ).first()
                if execution:
                    execution.status = ExecutionStatus.FAILED
                    execution.completed_at = datetime.utcnow()
                    db.commit()

            await self._send_status_notification(event_wait.execution_id, {
                'type': 'execution_error',
                'status': 'failed',
                'error': str(e),
                'message': f'Flow execution failed after event wait resume: {str(e)}',
            })
            raise
        finally:
            # Release any flow-scoped DB transaction pinned while resuming.
            try:
                from services import db_transaction_manager
                await db_transaction_manager.release_all(event_wait.execution_id)
            except Exception as _txn_release_err:
                logger.warning(f"Error releasing DB transactions after event wait resume: {_txn_release_err}")

    async def _execute_transform_node(self, node_id: str, node_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a transform node - run user script to transform data."""
        script = node_data.get('script', '') or node_data.get('code', '')
        
        if not script:
            # If no script provided, pass data through
            logger.warning(f"Transform node {node_id} has no script, passing data through")
            return context['data']
        
        # Build context for transform execution
        transform_context = self.variable_manager.get_context(
            node_id,
            context['data']
        )
        
        # Add current global vars to context
        transform_context['global_vars'] = context.get('global_vars', {})
        
        # IMPORTANT: Override input with original flow variables
        # The variable_manager.get_context sets input to context['data'] which might be
        # output from a previous node. We want the original flow input variables.
        if 'variables' in context:
            transform_context['input'] = context['variables']
        
        # Add loop variables if we're inside a loop
        if context.get('_in_loop') and context.get('loop'):
            transform_context['loop'] = context.get('loop', {})
            # Also add loop vars to input for backward compatibility
            if 'input' in transform_context and isinstance(transform_context['input'], dict):
                transform_context['input']['loop'] = context.get('loop', {})

        # Most recent handled node failure, for transforms on an error branch
        if context.get('last_error') is not None and 'error' not in transform_context:
            transform_context['error'] = context['last_error']

        # Handle large file attachments to prevent execution hangs
        with get_tenant_db(self.tenant_schema) as db:
            # Check file sizes before processing
            input_data = transform_context.get('input', {})
            file_attach = input_data.get('file_attach')
            if file_attach:
                if isinstance(file_attach, dict) and file_attach.get('size', 0) > 5 * 1024 * 1024:
                    file_mb = file_attach.get('size', 0) / (1024 * 1024)
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      f"Analyzing large file ({file_mb:.1f}MB) before processing...")
                elif isinstance(file_attach, list):
                    total_size = sum(f.get('size', 0) for f in file_attach if isinstance(f, dict))
                    if total_size > 5 * 1024 * 1024:
                        total_mb = total_size / (1024 * 1024)
                        self._log_execution(db, context['execution_id'], node_id, "info",
                                          f"Analyzing {len(file_attach)} files ({total_mb:.1f}MB total) before processing...")
        
        self._handle_large_file_attachments(transform_context)
        
        # Log completion of file handling for large files
        with get_tenant_db(self.tenant_schema) as db:
            input_data = transform_context.get('input', {})
            file_attach = input_data.get('file_attach')
            if file_attach:
                # Check if any files were processed or modified
                has_large_files = False
                if isinstance(file_attach, dict):
                    has_large_files = file_attach.get('large_file', False)
                elif isinstance(file_attach, list):
                    has_large_files = any(f.get('large_file', False) for f in file_attach if isinstance(f, dict))
                
                if has_large_files:
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      "File analysis complete. Starting transform script execution...")
                    
                    # Additional warning for very large files
                    very_large_detected = False
                    if isinstance(file_attach, dict) and file_attach.get('size', 0) > 12 * 1024 * 1024:
                        very_large_detected = True
                    elif isinstance(file_attach, list):
                        total_size = sum(f.get('size', 0) for f in file_attach if isinstance(f, dict))
                        very_large_detected = total_size > 12 * 1024 * 1024
                    
                    if very_large_detected:
                        self._log_execution(db, context['execution_id'], node_id, "info",
                                          "⚠️ Very large file detected. Processing may take 1-2 minutes...",
                                          {"progress_stage": "large_file_warning"})
        
        # Execute the transform
        transform_executor = TransformExecutor()
        
        try:
            # Removed redundant "Executing transform script" log
            
            # Log start time for timeout tracking
            import time
            start_time = time.time()
            
            # Add progress tracking for long operations
            with get_tenant_db(self.tenant_schema) as db:
                # Check if we have large files that might take time
                input_data = transform_context.get('input', {})
                file_attach = input_data.get('file_attach')
                has_large_file = False
                total_file_size = 0
                
                if file_attach:
                    if isinstance(file_attach, dict) and 'size' in file_attach:
                        total_file_size = file_attach.get('size', 0)
                        has_large_file = total_file_size > 5 * 1024 * 1024  # 5MB+
                    elif isinstance(file_attach, list):
                        for f in file_attach:
                            if isinstance(f, dict) and 'size' in f:
                                total_file_size += f.get('size', 0)
                        has_large_file = total_file_size > 5 * 1024 * 1024
                
                if has_large_file:
                    total_mb = total_file_size / (1024 * 1024)
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      f"Processing large file(s) ({total_mb:.1f}MB). This may take some time...",
                                      {"file_size_mb": total_mb, "progress_stage": "file_processing"})
                    
                    # Send an immediate progress indicator about expected duration
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      f"Large file processing may take 30-60 seconds. Please wait...",
                                      {"progress_stage": "duration_warning"})
            
            # Execute the script with progress monitoring
            try:
                # For large files, send intermediate progress updates
                if has_large_file:
                    # Send progress update before starting execution
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], node_id, "info",
                                          "🚀 Starting transform script execution with large file processing...",
                                          {"progress_stage": "script_execution_start"})
                
                # Execute the script with progress monitoring
                script_start_time = time.time()
                
                # For large files, start a simple progress monitor
                if has_large_file:
                    import threading
                    import time as time_module
                    
                    stop_progress = threading.Event()
                    
                    def monitor_progress():
                        """Simple progress monitor that runs every 15 seconds"""
                        count = 0
                        while not stop_progress.wait(15):  # Wait 15 seconds or until stopped
                            count += 1
                            elapsed = time_module.time() - script_start_time
                            if elapsed > 15:  # Only start showing after 15 seconds
                                try:
                                    with get_tenant_db(self.tenant_schema) as db:
                                        self._log_execution(db, context['execution_id'], node_id, "info",
                                                          f"⏳ Transform script running... ({elapsed:.0f}s elapsed)",
                                                          {"progress_stage": "script_running", "elapsed_time": elapsed})
                                except Exception as e:
                                    logger.error(f"Progress monitoring error: {e}")
                                    break
                    
                    # Start the progress monitor
                    progress_thread = threading.Thread(target=monitor_progress, daemon=True)
                    progress_thread.start()
                    
                    try:
                        # Execute the script
                        result = transform_executor.execute(script, transform_context, self.variable_manager)
                    finally:
                        # Stop progress monitoring
                        stop_progress.set()
                else:
                    # Execute the script normally for small files
                    result = transform_executor.execute(script, transform_context, self.variable_manager)
                
                # Handle the return value - it may be a tuple (result, print_output) or just result
                print_output = None
                if isinstance(result, tuple) and len(result) == 2:
                    result, print_output = result
                    
                    # Log any print output immediately within the transform node context
                    if print_output:
                        # Split print output into individual lines for better readability
                        lines = print_output.rstrip('\n').split('\n')
                        
                        # Create properly formatted output with each line on its own
                        formatted_lines = []
                        formatted_lines.append("📝 Transform Script Output:")
                        formatted_lines.append("")
                        
                        # Add each print statement as a separate line without extra indentation
                        for line in lines:
                            formatted_lines.append(line)
                        
                        formatted_output = "\n".join(formatted_lines)
                        
                        with get_tenant_db(self.tenant_schema) as db:
                            self._log_execution(db, context['execution_id'], node_id, "info",
                                              formatted_output,
                                              {"print_output": print_output, "type": "script_output"})
                
            except Exception as e:
                # Let the existing error handling take care of this
                raise
            
            # Calculate execution time but don't log redundantly
            execution_time = time.time() - start_time
            
            # Update global variables in context
            context['global_vars'] = self.variable_manager.global_vars
            logger.info(f"Transform updated global vars: {list(self.variable_manager.global_vars.keys())}")
            logger.info(f"Global var 'args' value: {self.variable_manager.global_vars.get('args')}")
            
            # Log debug info only to logger, not to execution logs
            logger.debug(f"Transform executed successfully with keys: {list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
            
            return result
            
        except Exception as e:
            # Calculate execution time for error context
            execution_time = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Enhanced error logging with timing and context
            if error_msg == "0" or error_msg == "":
                # Try to get more details about the exception
                import traceback
                tb_str = traceback.format_exc()
                logger.error(f"Transform execution failed with cryptic error after {execution_time:.2f}s. Type: {error_type}, Value: {repr(e)}, Traceback: {tb_str}")
                error_msg = f"{error_type}: {repr(e)} (See logs for traceback)"
            else:
                logger.error(f"Transform execution failed after {execution_time:.2f}s: {error_msg}")
            
            # Determine error category for better user feedback
            error_category = "error"
            user_friendly_msg = error_msg
            
            if "timed out" in error_msg.lower() or "time limit" in error_msg.lower():
                error_category = "timeout"
                user_friendly_msg = f"Transform script timed out after {execution_time:.2f}s. {error_msg}"
            elif "memory" in error_msg.lower() or "MemoryError" in error_type:
                error_category = "memory"
                user_friendly_msg = f"Transform script ran out of memory. {error_msg}"
            elif "iterations" in error_msg.lower() or "loop" in error_msg.lower():
                error_category = "infinite_loop"
                user_friendly_msg = f"Transform script appears to have an infinite loop. {error_msg}"
            elif "output" in error_msg.lower() and "large" in error_msg.lower():
                error_category = "output_size"
                user_friendly_msg = f"Transform script output too large. {error_msg}"
            elif "syntax" in error_msg.lower() or "SyntaxError" in error_type:
                error_category = "syntax"
                user_friendly_msg = f"Transform script has syntax errors. {error_msg}"
            
            # Log error BEFORE raising exception to ensure it's saved
            with get_tenant_db(self.tenant_schema) as db:
                logger.error(f"Transform error occurred: {user_friendly_msg}")
                self._log_execution(db, context['execution_id'], node_id, "error",
                                  user_friendly_msg,
                                  {"error_category": error_category, "execution_time": execution_time, "error_type": error_type})
            
            raise ValueError(user_friendly_msg)
    
    def _handle_large_file_attachments(self, transform_context: Dict[str, Any]) -> None:
        """
        Handle large file attachments to prevent transform execution hangs.
        
        Uses a tiered approach:
        - Files < 8MB: Process normally with warning
        - Files 8-12MB: Process with strong warning about potential issues
        - Files > 12MB: Replace with metadata only (prevents hanging)
        """
        # Tiered thresholds for better file handling
        WARNING_SIZE = 8 * 1024 * 1024   # 8MB - Show warning but process
        CRITICAL_SIZE = 12 * 1024 * 1024  # 12MB - Strong warning, still process
        MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB - Drop file data (prevents hanging)
        
        # Check file_attach in input context
        if 'input' in transform_context and isinstance(transform_context['input'], dict):
            file_attach = transform_context['input'].get('file_attach')
            
            if file_attach:
                try:
                    # Handle single file
                    if isinstance(file_attach, dict) and 'data' in file_attach:
                        file_size = file_attach.get('size', 0)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        if file_size > MAX_FILE_SIZE:
                            logger.warning(f"Very large file detected ({file_size} bytes = {file_size_mb:.1f}MB), dropping file data to prevent hanging")
                            # Log the error and raise an exception for very large files
                            error_msg = f"File size ({file_size_mb:.1f}MB) exceeds maximum allowed size (15MB) for transform processing. This prevents potential system hangs and memory issues."
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                        elif file_size > CRITICAL_SIZE:
                            logger.warning(f"Large file detected ({file_size} bytes = {file_size_mb:.1f}MB), processing with strong warning about potential performance issues")
                            # Keep file data but add strong warnings
                            file_attach['large_file'] = True
                            file_attach['warning_level'] = 'high'
                            file_attach['performance_warning'] = f'Large file ({file_size_mb:.1f}MB) may cause transform timeouts or memory issues. Consider processing smaller files or using file metadata only.'
                        elif file_size > WARNING_SIZE:
                            logger.info(f"Medium-large file detected ({file_size} bytes = {file_size_mb:.1f}MB), processing with performance warning")
                            # Keep file data but add mild warning
                            file_attach['large_file'] = True
                            file_attach['warning_level'] = 'medium'
                            file_attach['performance_warning'] = f'Medium-large file ({file_size_mb:.1f}MB) detected. Monitor for potential performance issues.'
                    
                    # Handle multiple files
                    elif isinstance(file_attach, list):
                        modified_files = []
                        for i, file_obj in enumerate(file_attach):
                            if isinstance(file_obj, dict) and 'data' in file_obj:
                                file_size = file_obj.get('size', 0)
                                file_size_mb = file_size / (1024 * 1024)
                                
                                if file_size > MAX_FILE_SIZE:
                                    logger.warning(f"Very large file detected in list[{i}] ({file_size} bytes = {file_size_mb:.1f}MB), dropping file data")
                                    file_name = file_obj.get('name', f'file_{i}')
                                    error_msg = f"File '{file_name}' size ({file_size_mb:.1f}MB) exceeds maximum allowed size (15MB) for transform processing. This prevents potential system hangs and memory issues."
                                    logger.error(error_msg)
                                    raise ValueError(error_msg)
                                elif file_size > CRITICAL_SIZE:
                                    logger.warning(f"Large file detected in list[{i}] ({file_size} bytes = {file_size_mb:.1f}MB), processing with strong warning")
                                    # Keep file data but add strong warnings
                                    file_obj_copy = file_obj.copy()
                                    file_obj_copy['large_file'] = True
                                    file_obj_copy['warning_level'] = 'high'
                                    file_obj_copy['performance_warning'] = f'Large file ({file_size_mb:.1f}MB) may cause transform timeouts or memory issues.'
                                    modified_files.append(file_obj_copy)
                                elif file_size > WARNING_SIZE:
                                    logger.info(f"Medium-large file detected in list[{i}] ({file_size} bytes = {file_size_mb:.1f}MB), processing with warning")
                                    # Keep file data but add mild warning
                                    file_obj_copy = file_obj.copy()
                                    file_obj_copy['large_file'] = True
                                    file_obj_copy['warning_level'] = 'medium'
                                    file_obj_copy['performance_warning'] = f'Medium-large file ({file_size_mb:.1f}MB) detected. Monitor for potential performance issues.'
                                    modified_files.append(file_obj_copy)
                                else:
                                    # Keep small files as-is
                                    modified_files.append(file_obj)
                            else:
                                # Keep non-file objects as-is
                                modified_files.append(file_obj)
                        
                        transform_context['input']['file_attach'] = modified_files
                
                except ValueError as e:
                    # Re-raise ValueError for file size violations - these should stop execution
                    logger.error(f"File size validation failed: {str(e)}")
                    raise
                except Exception as e:
                    logger.error(f"Error handling file attachments: {str(e)}")
                    # In case of other errors, remove file_attach to prevent hanging
                    if 'input' in transform_context and isinstance(transform_context['input'], dict):
                        transform_context['input'].pop('file_attach', None)
    
    def _send_progress_update(self, execution_id: str, node_id: str, message: str) -> None:
        """
        Send progress update during long-running operations.
        
        Args:
            execution_id: The execution ID
            node_id: The node being executed
            message: Progress message to send
        """
        try:
            import time
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, execution_id, node_id, "info", message, 
                                  {"progress_update": True, "timestamp": time.time()})
        except Exception as e:
            logger.error(f"Failed to send progress update: {str(e)}")
    
    async def _execute_loop_node(self, node: Dict[str, Any], node_data: Dict[str, Any], 
                                context: Dict[str, Any], all_nodes: List[Dict[str, Any]], 
                                edges: List[Dict[str, Any]], adjacency: Dict[str, List[str]]) -> Dict[str, Any]:
        """Execute a loop node - iterate over data or repeat actions."""
        node_id = node['id']
        loop_type = node_data.get('loopType', 'forEach')
        
        # Debug logging
        with get_tenant_db(self.tenant_schema) as db:
            self._log_execution(db, context['execution_id'], node_id, "debug",
                              f"Loop node configuration",
                              {
                                  "total_edges": len(edges), 
                                  "node_id": node_id,
                                  "loop_type": loop_type,
                                  "node_data": node_data
                              })
        
        # Find the loop body start node (connected to 'loop-body' handle)
        loop_body_node = None
        continue_node = None
        
        # Also track which nodes connect back to this loop (for loop-back)
        loop_back_nodes = []
        
        for edge in edges:
            # Log each edge for debugging
            logger.debug(f"Checking edge: source={edge.get('source')}, target={edge.get('target')}, "
                        f"sourceHandle={edge.get('sourceHandle')}, targetHandle={edge.get('targetHandle')}")
            
            if edge['source'] == node_id:
                if edge.get('sourceHandle') == 'loop-body':
                    loop_body_node = self._find_node_by_id(edge['target'], all_nodes)
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], node_id, "debug",
                                          f"Found loop body node: {edge['target']}")
                elif edge.get('sourceHandle') == 'continue':
                    continue_node = self._find_node_by_id(edge['target'], all_nodes)
            elif edge['target'] == node_id and edge.get('targetHandle') == 'loop-back':
                # This edge connects back to the loop (now on the right side)
                loop_back_nodes.append(edge['source'])
        
        if not loop_body_node:
            # No loop body, just continue
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], node_id, "warning",
                                  "Loop node has no body, continuing to next node")
            return context['data']
        
        # Initialize loop context
        original_data = context.get('data', {})
        loop_results = []
        loop_broken_early = False
        
        try:
            if loop_type == 'forEach':
                # Get the array to iterate over
                array_path = node_data.get('arrayPath', '')
                iterator_name = node_data.get('iteratorName', 'item')
                
                # Remove {{}} from array path if present
                if isinstance(array_path, str) and array_path.startswith('{{') and array_path.endswith('}}'):
                    array_path = array_path[2:-2].strip()
                
                # Debug log the array path resolution
                logger.info(f"Loop node {node_id} - Resolving array path: {array_path}")
                logger.info(f"Available node_outputs: {list(context.get('node_outputs', {}).keys())}")
                
                # Log the structure of node outputs for debugging nested paths
                node_outputs = context.get('node_outputs', {})
                for node_key in list(node_outputs.keys())[:3]:  # Log first 3 nodes
                    node_value = node_outputs[node_key]
                    if isinstance(node_value, dict):
                        logger.debug(f"Node {node_key} structure: {list(node_value.keys())[:10]}")
                        # Check for common nested structures
                        if 'result' in node_value and isinstance(node_value['result'], dict):
                            result_keys = list(node_value['result'].keys())
                            logger.debug(f"  - result keys: {result_keys}")
                            if 'data' in node_value['result']:
                                data_type = type(node_value['result']['data']).__name__
                                logger.debug(f"  - result.data type: {data_type}")
                                if isinstance(node_value['result']['data'], list):
                                    logger.debug(f"  - result.data length: {len(node_value['result']['data'])}")
                
                # Resolve the array from the variable path
                array_value = self._get_field_value(array_path, context)
                
                logger.info(f"Array path '{array_path}' resolved to type: {type(array_value).__name__ if array_value is not None else 'None'}")
                
                if array_value is not None and not isinstance(array_value, list):
                    # Provide helpful error message with suggestions
                    error_msg = f"Loop node expects an array at path '{array_path}', but got {type(array_value).__name__}"
                    
                    # If it's a dict, suggest possible array paths
                    if isinstance(array_value, dict):
                        array_fields = [k for k, v in array_value.items() if isinstance(v, list)]
                        if array_fields:
                            error_msg += f"\n\nFound arrays in the resolved object at: {array_fields}"
                            error_msg += f"\nTry using path: '{array_path}.{array_fields[0]}'"
                        
                        # Check for common patterns
                        if 'result' in array_value and isinstance(array_value['result'], dict):
                            if 'data' in array_value['result'] and isinstance(array_value['result']['data'], list):
                                error_msg += f"\n\nDetected nested array at 'result.data'. Try using path: '{array_path}.result.data'"
                    
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], node_id, "error", error_msg)
                    
                    raise ValueError(error_msg)
                
                elif array_value is None:
                    error_msg = f"Could not resolve array at path '{array_path}'. Path returned None."
                    error_msg += "\n\nCheck that:"
                    error_msg += f"\n1. The path '{array_path}' is correct"
                    error_msg += "\n2. The previous node has executed and produced output"
                    error_msg += "\n3. The data structure contains the expected nested path"
                    
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], node_id, "error", error_msg)
                    
                    raise ValueError(error_msg)
                
                with get_tenant_db(self.tenant_schema) as db:
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      f"Starting forEach loop with {len(array_value)} items")
                
                # Iterate over each item
                for index, item in enumerate(array_value):
                    # Create loop context variables
                    loop_vars = {
                        'index': index,
                        'count': index + 1,
                        'first': index == 0,
                        'last': index == len(array_value) - 1,
                        iterator_name: item
                    }
                    
                    # Create a new context for this iteration
                    loop_context = {
                        **context,
                        'data': {**original_data, 'loop': loop_vars},
                        'loop': loop_vars  # Also available directly
                    }
                    
                    # Debug logging for loop context
                    logger.info(f"Loop iteration {index} - Created loop context")
                    logger.info(f"Loop context has node_outputs: {'node_outputs' in loop_context}")
                    logger.info(f"Loop context node_outputs keys: {list(loop_context.get('node_outputs', {}).keys())}")
                    logger.info(f"Loop context data keys: {list(loop_context.get('data', {}).keys()) if isinstance(loop_context.get('data'), dict) else 'not a dict'}")
                    logger.info(f"Iterator '{iterator_name}' value: {item}")
                    
                    # Mark this as being inside a loop for proper flow control
                    loop_context['_in_loop'] = True
                    loop_context['_loop_node_id'] = node_id
                    loop_context['_loop_back_nodes'] = loop_back_nodes
                    loop_context['_loop_type'] = 'forEach'
                    loop_context['_iterator_name'] = iterator_name
                    loop_context['_total_items'] = len(array_value)
                    loop_context['_edges'] = edges  # Pass edges for condition node to check exit paths
                    
                    # Ensure we preserve existing variables in the loop context
                    if 'variables' not in loop_context:
                        loop_context['variables'] = {}
                    # Copy existing variables but don't add loop vars here - they're in the top-level 'loop' context
                    loop_context['variables'] = {**context.get('variables', {})}
                    
                    # Execute the loop body
                    try:
                        # Set a flag to track if we returned to the loop
                        loop_context['_returned_to_loop'] = False
                        
                        await self._execute_node(loop_body_node, all_nodes, edges, adjacency, loop_context)
                        # Collect results
                        loop_results.append(loop_context.get('data', {}))
                        
                        # If execution didn't return to the loop, break
                        if not loop_context.get('_returned_to_loop', False):
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "info",
                                                  f"Loop ended - execution path didn't return to loop at iteration {index + 1}")
                            loop_broken_early = True
                            break
                    except Exception as e:
                        if "Loop exit" in str(e):
                            # Early exit from loop
                            # Check if we have an exit target node to execute
                            if loop_context.get('_loop_exit_target'):
                                exit_target_node = self._find_node_by_id(loop_context['_loop_exit_target'], all_nodes)
                                if exit_target_node:
                                    # Execute the exit target node with the current context
                                    exit_context = {
                                        **context,
                                        'data': loop_context.get('data', original_data),
                                        'variables': loop_context.get('variables', context.get('variables', {})),
                                        'node_outputs': loop_context.get('node_outputs', context.get('node_outputs', {}))
                                    }
                                    await self._execute_downstream_of(node_id, exit_target_node, all_nodes, edges, adjacency, exit_context)
                                    # Update the main context with any changes
                                    context.update(exit_context)
                                    # Skip the continue node since we're breaking out
                                    return exit_context.get('data', original_data)
                            break
                        
                        # Enhanced error logging for debugging
                        error_msg = str(e)
                        if error_msg == "0" or error_msg == "":
                            import traceback
                            tb_str = traceback.format_exc()
                            logger.error(f"Loop body execution failed with cryptic error at iteration {index}. Type: {type(e).__name__}, Value: {repr(e)}, Traceback: {tb_str}")
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "error",
                                                  f"Loop failed at iteration {index}: {type(e).__name__}: {repr(e)}")
                        else:
                            logger.error(f"Loop body execution failed at iteration {index}: {error_msg}")
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "error",
                                                  f"Loop execution failed: {error_msg}")
                        raise
            
            elif loop_type == 'while':
                # While loop with condition
                condition_expr = node_data.get('condition', '')
                iteration = 0
                max_iterations = 10000  # Safety limit
                
                with get_tenant_db(self.tenant_schema) as db:
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      f"Starting while loop with condition: {condition_expr}")
                
                # Check if condition uses counter and warn if no transform node in loop
                if 'counter' in condition_expr:
                    # Check if there's a transform node in the loop body
                    has_transform = False
                    if loop_body_node:
                        # Simple check - in practice, would need to traverse the loop body graph
                        for node in all_nodes:
                            if node.get('type') == 'transform':
                                has_transform = True
                                break
                    
                    if not has_transform:
                        with get_tenant_db(self.tenant_schema) as db:
                            self._log_execution(db, context['execution_id'], node_id, "warning",
                                              "While loop uses 'counter' but no transform node found to update it. "
                                              "This may cause an infinite loop!")
                
                # Initialize counter if not present for while loops
                if 'counter' not in context.get('variables', {}) and 'counter' in condition_expr:
                    context['variables'] = context.get('variables', {})
                    context['variables']['counter'] = 1
                    with get_tenant_db(self.tenant_schema) as db:
                        self._log_execution(db, context['execution_id'], node_id, "debug",
                                          "Initialized counter variable to 1 for while loop")
                
                # Track condition state for infinite loop detection
                last_condition_state = None
                unchanged_iterations = 0
                
                while iteration < max_iterations:
                    # Create loop context variables
                    loop_vars = {
                        'index': iteration,
                        'count': iteration + 1,
                        'first': iteration == 0
                    }
                    
                    # Create a new context for this iteration
                    loop_context = {
                        **context,
                        'data': {**original_data, 'loop': loop_vars},
                        'loop': loop_vars,
                        '_in_loop': True,
                        '_loop_node_id': node_id,
                        '_loop_back_nodes': loop_back_nodes,
                        '_loop_type': 'while',
                        '_iterator_name': None,  # While loops don't have named iterators
                        '_total_items': None,  # Unknown for while loops
                        '_edges': edges  # Pass edges for condition node to check exit paths
                    }
                    
                    # Ensure we preserve existing variables in the loop context
                    if 'variables' not in loop_context:
                        loop_context['variables'] = {}
                    # Copy existing variables but don't add loop vars here - they're in the top-level 'loop' context
                    loop_context['variables'] = {**context.get('variables', {})}
                    
                    # Evaluate condition
                    condition_result = self._evaluate_expression(condition_expr, loop_context)
                    
                    # Check for potential infinite loop
                    current_condition_state = str(context.get('variables', {}))
                    if current_condition_state == last_condition_state:
                        unchanged_iterations += 1
                        if unchanged_iterations >= 10:
                            raise ValueError(f"While loop appears to be infinite - variables haven't changed in {unchanged_iterations} iterations. "
                                           f"Make sure to update the condition variables (e.g., counter) inside the loop.")
                    else:
                        unchanged_iterations = 0
                    last_condition_state = current_condition_state
                    
                    if not condition_result:
                        break
                    
                    # Execute the loop body
                    try:
                        # Set a flag to track if we returned to the loop
                        loop_context['_returned_to_loop'] = False
                        
                        await self._execute_node(loop_body_node, all_nodes, edges, adjacency, loop_context)
                        
                        # Update original data and variables with any changes from the loop
                        original_data = loop_context.get('data', original_data)
                        # IMPORTANT: Update the context variables for the next iteration
                        context['variables'] = loop_context.get('variables', context.get('variables', {}))
                        # Propagate global_vars changes back to outer context
                        context['global_vars'] = loop_context.get('global_vars', context.get('global_vars', {}))
                        
                        loop_results.append(original_data)
                        
                        # If execution didn't return to the loop, break
                        if not loop_context.get('_returned_to_loop', False):
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "info",
                                                  f"While loop ended - execution path didn't return to loop at iteration {iteration + 1}")
                            loop_broken_early = True
                            break
                        
                        iteration += 1
                        
                        # Log current state for debugging
                        with get_tenant_db(self.tenant_schema) as db:
                            self._log_execution(db, context['execution_id'], node_id, "debug",
                                              f"While loop iteration {iteration} completed",
                                              {
                                                  "condition": condition_expr,
                                                  "variables": context.get('variables', {}),
                                                  "will_continue": iteration < max_iterations
                                              })
                    except Exception as e:
                        if "Loop exit" in str(e):
                            # Early exit from loop
                            # Check if we have an exit target node to execute
                            if loop_context.get('_loop_exit_target'):
                                exit_target_node = self._find_node_by_id(loop_context['_loop_exit_target'], all_nodes)
                                if exit_target_node:
                                    # Execute the exit target node with the current context
                                    exit_context = {
                                        **context,
                                        'data': loop_context.get('data', original_data),
                                        'variables': loop_context.get('variables', context.get('variables', {})),
                                        'node_outputs': loop_context.get('node_outputs', context.get('node_outputs', {}))
                                    }
                                    await self._execute_downstream_of(node_id, exit_target_node, all_nodes, edges, adjacency, exit_context)
                                    # Update the main context with any changes
                                    context.update(exit_context)
                                    # Skip the continue node since we're breaking out
                                    return exit_context.get('data', original_data)
                            break
                        
                        # Enhanced error logging for debugging
                        error_msg = str(e)
                        if error_msg == "0" or error_msg == "":
                            import traceback
                            tb_str = traceback.format_exc()
                            logger.error(f"Loop body execution failed with cryptic error at iteration {index}. Type: {type(e).__name__}, Value: {repr(e)}, Traceback: {tb_str}")
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "error",
                                                  f"Loop failed at iteration {index}: {type(e).__name__}: {repr(e)}")
                        else:
                            logger.error(f"Loop body execution failed at iteration {index}: {error_msg}")
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "error",
                                                  f"Loop execution failed: {error_msg}")
                        raise
                
                if iteration >= max_iterations:
                    raise ValueError(f"While loop exceeded maximum iterations ({max_iterations})")
            
            elif loop_type == 'for':
                # For loop with range - support both direct values and variables
                start_value = node_data.get('startValue', node_data.get('start', '1'))
                end_value = node_data.get('endValue', node_data.get('end', '10'))
                step_value = node_data.get('stepValue', node_data.get('step', '1'))
                iterator_name = node_data.get('iteratorName', 'i')
                
                # Resolve values from variables if needed
                try:
                    # Check if it's a variable reference or a direct number
                    if isinstance(start_value, str) and start_value.startswith('{{') and start_value.endswith('}}'):
                        # Remove the {{ }} and resolve the variable
                        var_path = start_value[2:-2].strip()
                        start = int(self._get_field_value(var_path, context))
                    else:
                        start = int(start_value)
                        
                    if isinstance(end_value, str) and end_value.startswith('{{') and end_value.endswith('}}'):
                        # Remove the {{ }} and resolve the variable
                        var_path = end_value[2:-2].strip()
                        end = int(self._get_field_value(var_path, context))
                    else:
                        end = int(end_value)
                        
                    if isinstance(step_value, str) and step_value.startswith('{{') and step_value.endswith('}}'):
                        # Remove the {{ }} and resolve the variable
                        var_path = step_value[2:-2].strip()
                        step = int(self._get_field_value(var_path, context))
                    else:
                        step = int(step_value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid numeric value in for loop: {str(e)}")
                
                with get_tenant_db(self.tenant_schema) as db:
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      f"Starting for loop from {start} to {end} with step {step}")
                
                # Calculate the range
                current = start
                iteration = 0
                
                while (step > 0 and current <= end) or (step < 0 and current >= end):
                    # Calculate total iterations for 'last' flag
                    total_iterations = abs((end - start) // step) + 1
                    is_last = (step > 0 and current + step > end) or (step < 0 and current + step < end)
                    
                    # Create loop context variables
                    loop_vars = {
                        'index': iteration,
                        'count': iteration + 1,
                        'first': iteration == 0,
                        'last': is_last,
                        iterator_name: current
                    }
                    
                    # Create a new context for this iteration
                    loop_context = {
                        **context,
                        'data': {**original_data, 'loop': loop_vars},
                        'loop': loop_vars,
                        '_in_loop': True,
                        '_loop_node_id': node_id,
                        '_loop_back_nodes': loop_back_nodes,
                        '_loop_type': 'for',
                        '_iterator_name': iterator_name,
                        '_total_items': total_iterations,
                        '_edges': edges  # Pass edges for condition node to check exit paths
                    }
                    
                    # Ensure we preserve existing variables in the loop context
                    if 'variables' not in loop_context:
                        loop_context['variables'] = {}
                    # Copy existing variables but don't add loop vars here - they're in the top-level 'loop' context
                    loop_context['variables'] = {**context.get('variables', {})}
                    
                    # Execute the loop body
                    try:
                        # Set a flag to track if we returned to the loop
                        loop_context['_returned_to_loop'] = False
                        
                        await self._execute_node(loop_body_node, all_nodes, edges, adjacency, loop_context)
                        loop_results.append(loop_context.get('data', {}))
                        
                        # If execution didn't return to the loop, break
                        if not loop_context.get('_returned_to_loop', False):
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "info",
                                                  f"For loop ended - execution path didn't return to loop at iteration {iteration + 1}")
                            loop_broken_early = True
                            break
                        
                        current += step
                        iteration += 1
                    except Exception as e:
                        if "Loop exit" in str(e):
                            # Early exit from loop
                            # Check if we have an exit target node to execute
                            if loop_context.get('_loop_exit_target'):
                                exit_target_node = self._find_node_by_id(loop_context['_loop_exit_target'], all_nodes)
                                if exit_target_node:
                                    # Execute the exit target node with the current context
                                    exit_context = {
                                        **context,
                                        'data': loop_context.get('data', original_data),
                                        'variables': loop_context.get('variables', context.get('variables', {})),
                                        'node_outputs': loop_context.get('node_outputs', context.get('node_outputs', {}))
                                    }
                                    await self._execute_downstream_of(node_id, exit_target_node, all_nodes, edges, adjacency, exit_context)
                                    # Update the main context with any changes
                                    context.update(exit_context)
                                    # Skip the continue node since we're breaking out
                                    return exit_context.get('data', original_data)
                            break
                        
                        # Enhanced error logging for debugging
                        error_msg = str(e)
                        if error_msg == "0" or error_msg == "":
                            import traceback
                            tb_str = traceback.format_exc()
                            logger.error(f"Loop body execution failed with cryptic error at iteration {index}. Type: {type(e).__name__}, Value: {repr(e)}, Traceback: {tb_str}")
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "error",
                                                  f"Loop failed at iteration {index}: {type(e).__name__}: {repr(e)}")
                        else:
                            logger.error(f"Loop body execution failed at iteration {index}: {error_msg}")
                            with get_tenant_db(self.tenant_schema) as db:
                                self._log_execution(db, context['execution_id'], node_id, "error",
                                                  f"Loop execution failed: {error_msg}")
                        raise
            
            # After loop completion, execute the continue node if present
            # But only if the loop wasn't broken early due to flow not returning
            if continue_node and not loop_broken_early:
                # Pass the accumulated results or the final state
                final_context = {
                    **context,
                    'data': {
                        **original_data,
                        'loop_results': loop_results
                    }
                }
                await self._execute_downstream_of(node_id, continue_node, all_nodes, edges, adjacency, final_context)
            elif loop_broken_early:
                with get_tenant_db(self.tenant_schema) as db:
                    self._log_execution(db, context['execution_id'], node_id, "info",
                                      f"Skipping continue node - loop was broken early")
            
            # Return the accumulated results
            return {
                **original_data,
                'loop_results': loop_results
            }
            
        except Exception as e:
            logger.error(f"Loop execution failed: {str(e)}")
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], node_id, "error",
                                  f"Loop execution failed: {str(e)}")
            raise
    
    async def _execute_downstream_of(self, owner_node_id: str, node: Dict[str, Any],
                                     all_nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]],
                                     adjacency: Dict[str, List[str]], context: Dict[str, Any]):
        """Execute a node that lies *after* ``owner_node_id`` but is launched from
        inside the owner's handler (e.g. a loop's continue path). A failure there
        is not the owner's own failure, so it bypasses the owner's error policy."""
        try:
            await self._execute_node(node, all_nodes, edges, adjacency, context)
        except Exception as e:
            mark_skip_policy(e, owner_node_id)
            raise

    def _build_adjacency_list(self, edges: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Build adjacency list from edges.

        Error-handle edges are excluded: they only run when their source node
        fails and routes to its error branch (see _follow_error_branch)."""
        adjacency = {}
        for edge in edges:
            if edge.get('sourceHandle') == ERROR_HANDLE:
                continue
            source = edge['source']
            target = edge['target']
            if source not in adjacency:
                adjacency[source] = []
            adjacency[source].append(target)
        return adjacency
    
    def _build_reverse_adjacency_list(self, edges: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Build reverse adjacency list (incoming edges) for fork-join synchronization."""
        reverse_adjacency = {}
        for edge in edges:
            source = edge['source']
            target = edge['target']
            
            # Skip loop-specific edges for fork-join synchronization
            # These are handled internally by the loop node
            source_handle = edge.get('sourceHandle', '')
            target_handle = edge.get('targetHandle', '')
            if source_handle in ['loop-body', 'continue'] or target_handle in ['loop-back']:
                continue
            # Error-handle edges are alternative paths, not join inputs: a node
            # fed by an error branch must not wait for its failed source
            if source_handle == ERROR_HANDLE:
                continue
            
            if target not in reverse_adjacency:
                reverse_adjacency[target] = []
            reverse_adjacency[target].append(source)
        return reverse_adjacency
    
    async def _can_execute_node(self, completed_node_id: str, target_node_id: str, context: Dict[str, Any]) -> bool:
        """
        Check if a target node can be executed based on fork-join synchronization.
        A node can execute only when ALL its incoming edges have completed.
        """
        # Mark the current node as completed
        context['_completed_nodes'].add(completed_node_id)
        
        # Special handling for loop nodes - they manage their own flow control
        # Loop edges like 'loop-body', 'continue', 'loop-back' should not participate in fork-join
        all_nodes = context.get('_all_nodes', [])
        target_node = self._find_node_by_id(target_node_id, all_nodes)
        if target_node and target_node.get('type') == 'loop':
            # Loops don't need fork-join synchronization for their special edges
            return True
        
        # Get all incoming edges for the target node
        reverse_adjacency = context.get('_reverse_adjacency', {})
        incoming_nodes = reverse_adjacency.get(target_node_id, [])
        
        # If no incoming edges, can execute immediately
        if not incoming_nodes:
            return True
        
        # If only one incoming edge, can execute immediately  
        if len(incoming_nodes) == 1:
            return True
        
        # Check if ALL incoming nodes have completed. An input on a path that
        # was skipped (dead) counts as resolved — see _propagate_dead_path.
        completed_nodes = context['_completed_nodes']
        dead_edges = context.get('_dead_edges', set())
        all_incoming_completed = all(
            node_id in completed_nodes or (node_id, target_node_id) in dead_edges
            for node_id in incoming_nodes
        )
        
        if all_incoming_completed:
            # All incoming edges completed, can execute
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], target_node_id, "info",
                                  f"Fork-join synchronization: All {len(incoming_nodes)} incoming edges completed, executing node")
            return True
        else:
            # Still waiting for some incoming edges
            waiting_for = [node_id for node_id in incoming_nodes
                           if node_id not in completed_nodes and (node_id, target_node_id) not in dead_edges]
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], target_node_id, "debug",
                                  f"Fork-join synchronization: Waiting for nodes {waiting_for} to complete")
            return False
    
    def _find_node_by_id(self, node_id: str, nodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find node by ID."""
        for node in nodes:
            if node['id'] == node_id:
                return node
        return None
    
    def _map_parameters(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Map parameters using context data."""
        logger.info(f"_map_parameters input: {parameters}")
        logger.info(f"Available global_vars: {list(context.get('global_vars', {}).keys())}")
        logger.info(f"In loop: {context.get('_in_loop', False)}")
        if context.get('_in_loop'):
            logger.info(f"Loop variables: {context.get('loop', {})}")
        logger.info(f"Available node_outputs in _map_parameters: {list(context.get('node_outputs', {}).keys())}")
        mapped = {}
        for key, value in parameters.items():
            # Skip invalid keys
            if key in ['undefined', 'null', None, '']:
                logger.warning(f"Skipping invalid parameter key: '{key}'")
                continue
                
            if isinstance(value, str):
                # Check if this is a complete template variable
                if value.startswith('{{') and value.endswith('}}') and value.count('{{') == 1:
                    # Variable reference - handle both double and quadruple curly braces
                    # Remove outer braces
                    inner_content = value[2:-2].strip()
                    
                    # Check if we have nested braces (e.g., {{{{input.sales_order}}}})
                    if inner_content.startswith('{{') and inner_content.endswith('}}'):
                        # Remove the inner braces too
                        var_path = inner_content[2:-2].strip()
                    else:
                        var_path = inner_content
                    
                    # Special handling for object parameters
                    # If the path ends with just a node reference, we might want the whole object
                    path_parts = var_path.split('.')
                    if len(path_parts) == 2 and path_parts[0] == 'input':
                        # This might be a reference to a whole node output object
                        logger.debug(f"Detected possible node reference: {var_path}")
                    
                    resolved_value = self._get_field_value(var_path, context)
                    if resolved_value is not None:
                        mapped[key] = resolved_value
                        # Add special logging for attachments
                        if key == 'attachments' and isinstance(resolved_value, dict):
                            logger.info(f"Attachment resolved: filename={resolved_value.get('filename')}, "
                                      f"content_length={len(resolved_value.get('content', ''))}, "
                                      f"size={resolved_value.get('size')}")
                        else:
                            logger.debug(f"Mapped parameter {key}: {value} -> {resolved_value}")
                    else:
                        # Variable doesn't exist - replace with empty string instead of None
                        logger.warning(f"Failed to resolve variable reference: {value}, using empty string")
                        logger.debug(f"Available context keys: {list(context.keys())}")
                        logger.debug(f"Available variables: {list(context.get('variables', {}).keys())}")
                        logger.debug(f"Available node outputs: {list(context.get('node_outputs', {}).keys())}")
                        mapped[key] = ""
                elif '{{' in value and '}}' in value:
                    # String contains embedded template variables
                    import re
                    result = value
                    # Find all template variables in the string
                    pattern = r'\{\{([^}]+)\}\}'
                    matches = re.findall(pattern, value)
                    
                    # Check if this looks like a JSON array/list literal that needs proper quoting
                    is_list_literal = value.strip().startswith('[') and value.strip().endswith(']')
                    
                    for var_path in matches:
                        var_path = var_path.strip()
                        resolved_value = self._get_field_value(var_path, context)
                        if resolved_value is not None:
                            # For list literals, properly quote string values
                            if is_list_literal and isinstance(resolved_value, str):
                                # Escape quotes and wrap in quotes for proper Python/JSON literal
                                escaped_value = resolved_value.replace('\\', '\\\\').replace('"', '\\"')
                                replacement = f'"{escaped_value}"'
                            else:
                                # For other contexts or non-strings, just convert to string
                                replacement = str(resolved_value)

                            result = result.replace(f"{{{{{var_path}}}}}", replacement)
                            logger.debug(f"Substituted {{{{{var_path}}}}} with {replacement} (type: {type(resolved_value).__name__})")
                        else:
                            # Replace unresolved variables with empty string instead of leaving literal {{variable}}
                            logger.warning(f"Failed to resolve embedded variable: {var_path}, replacing with empty string")
                            result = result.replace(f"{{{{{var_path}}}}}", "")
                    
                    mapped[key] = result
                    logger.debug(f"Mapped parameter with substitutions {key}: {value} -> {result}")
                else:
                    # Plain string, no template variables
                    mapped[key] = value
            elif isinstance(value, dict):
                # Recursively map nested dictionaries
                mapped[key] = self._map_parameters(value, context)
            elif isinstance(value, list):
                # Map each item in the list
                mapped[key] = [
                    self._map_parameters({'_': item}, context).get('_', item) 
                    if isinstance(item, (str, dict, list)) else item 
                    for item in value
                ]
            else:
                mapped[key] = value
        
        logger.debug(f"_map_parameters output: {mapped}")
        return mapped
    
    def _convert_attrdict_to_dict(self, obj: Any) -> Any:
        """Recursively convert AttrDict objects to regular dicts."""
        if hasattr(obj, '__class__') and obj.__class__.__name__ == 'AttrDict':
            # Convert AttrDict to regular dict and recursively process values
            return {k: self._convert_attrdict_to_dict(v) for k, v in dict(obj).items()}
        elif isinstance(obj, dict):
            # Recursively process dict values
            return {k: self._convert_attrdict_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            # Recursively process list items
            return [self._convert_attrdict_to_dict(item) for item in obj]
        else:
            # Return as-is for other types
            return obj
    
    def _parse_path(self, path: str) -> List[str]:
        """Parse a path that may contain both dot notation and bracket notation."""
        import re
        # Handle bracket notation: node_outputs['123'].products -> ['node_outputs', '123', 'products']
        # First, replace bracket notation with dots
        path = re.sub(r"\['([^']+)'\]", r".\1", path)
        path = re.sub(r'\["([^"]+)"\]', r".\1", path)
        path = re.sub(r"\[([^\]]+)\]", r".\1", path)
        # Now split by dots
        return path.split('.')
    
    def _get_field_value(self, field_path: str, context: Dict[str, Any]) -> Any:
        """Get field value from context using dot notation.
        
        Supports paths like:
        - node_outputs.node_123.result.data
        - input.variable_name
        - loop.item.property
        - global.variable_name
        """
        logger.debug(f"_get_field_value called with path: {field_path}")
        
        # Handle empty or invalid field paths
        if not field_path or field_path in ['undefined', 'null', '']:
            logger.warning(f"Invalid field path: '{field_path}'")
            return None
            
        parts = self._parse_path(field_path)
        logger.debug(f"Split path '{field_path}' into parts: {parts}")
        
        # Handle different context namespaces
        logger.debug(f"First part of path: '{parts[0]}'")
        if parts[0] == 'input':
            # Check if the second part is a node reference
            if len(parts) > 1:
                # Try to find the node output by checking various patterns
                node_outputs = context.get('node_outputs', {})
                found_node = False
                
                # First try exact match with node outputs
                if parts[1] in node_outputs:
                    value = node_outputs[parts[1]]
                    parts = parts[2:]  # Skip 'input' and node ID
                    found_node = True
                else:
                    # Try to match by node type/name pattern
                    for node_id, node_data in node_outputs.items():
                        # Check if this might be the node we're looking for
                        if parts[1].endswith('_node'):
                            node_type = parts[1].replace('_node', '')
                            # Check if the node data matches this type
                            if (isinstance(node_data, dict) and 
                                (node_data.get('node_type') == node_type or 
                                 node_data.get('type') == node_type or
                                 node_type in str(node_id))):
                                value = node_data
                                parts = parts[2:]  # Skip 'input' and node reference
                                found_node = True
                                break
                
                if not found_node:
                    # Check if we can find it in the regular node outputs
                    # Sometimes the reference might be input.sales_order instead of node_outputs.node_123
                    for node_id, node_data in node_outputs.items():
                        # Check if the node has a label that matches
                        if isinstance(node_data, dict):
                            node_label = None
                            # Try different ways to get the node label
                            if 'label' in node_data:
                                node_label = node_data['label']
                            elif 'node_label' in node_data:
                                node_label = node_data['node_label']
                            elif 'name' in node_data:
                                node_label = node_data['name']
                            
                            # Check if the label matches our reference
                            if node_label and isinstance(node_label, str):
                                normalized_label = node_label.lower().replace(' ', '_')
                                if (normalized_label == parts[1] or 
                                    normalized_label + '_node' == parts[1]):
                                    value = node_data
                                    parts = parts[2:]  # Skip 'input' and node reference
                                    found_node = True
                                    break
                    
                    if not found_node:
                        # Fall back to variables
                        value = context.get('variables', {})
                        parts = parts[1:]  # Remove 'input' prefix
            else:
                # Access variables from input
                value = context.get('variables', {})
                parts = parts[1:]  # Remove 'input' prefix
        elif parts[0] == 'trigger':
            # Access trigger node output (for compatibility with flows that use trigger.field)
            # First try the 'trigger' alias in node_outputs
            if 'trigger' in context.get('node_outputs', {}):
                value = context['node_outputs']['trigger']
                parts = parts[1:]  # Remove 'trigger' prefix
            else:
                # Fall back to finding the trigger node output
                node_outputs = context.get('node_outputs', {})
                trigger_output = None
                for node_id, output in node_outputs.items():
                    if node_id.startswith('trigger'):
                        trigger_output = output
                        break
                if trigger_output is not None:
                    value = trigger_output
                    parts = parts[1:]  # Remove 'trigger' prefix
                else:
                    # Last fallback: use variables directly
                    value = context.get('variables', {})
                    parts = parts[1:]  # Remove 'trigger' prefix
        elif parts[0] == 'data':
            # Access data from context
            value = context.get('data', {})
            parts = parts[1:]  # Remove 'data' prefix
        elif parts[0] == 'flow':
            # Access flow metadata
            value = {
                'execution_id': context.get('execution_id'),
                'start_time': context.get('start_time'),
                'current_node': context.get('current_node')
            }
            parts = parts[1:]  # Remove 'flow' prefix
        elif parts[0] == 'global_vars':
            # Access global variables
            value = context.get('global_vars', {})
            parts = parts[1:]  # Remove 'global_vars' prefix
        elif parts[0] == 'global':
            # Access global variables (new syntax)
            value = context.get('global_vars', {})
            parts = parts[1:]  # Remove 'global' prefix
        elif parts[0] == 'node_outputs':
            logger.debug(f"Handling node_outputs path")
            # Access node outputs collection
            value = context.get('node_outputs', {})
            logger.debug(f"node_outputs value type: {type(value)}, keys: {list(value.keys()) if isinstance(value, dict) else 'not a dict'}")
            parts = parts[1:]  # Remove 'node_outputs' prefix
            logger.debug(f"After removing node_outputs prefix, remaining parts: {parts}")
            logger.debug(f"node_outputs content: {list(value.keys()) if isinstance(value, dict) else 'not a dict'}")
            
            # If we still have parts and value is dict, try to find by node ID
            if parts and isinstance(value, dict):
                node_id_to_find = parts[0]
                logger.debug(f"Looking for node ID: {node_id_to_find}")
                logger.debug(f"Available node IDs: {list(value.keys())}")
                
                if node_id_to_find in value:
                    value = value[node_id_to_find]
                    parts = parts[1:]  # Remove node_id
                    logger.debug(f"Found exact match for node ID: {node_id_to_find}, remaining parts: {parts}")
                    logger.debug(f"Node output type: {type(value)}, keys if dict: {list(value.keys())[:10] if isinstance(value, dict) else 'not a dict'}")
                else:
                    # If node_id_to_find starts with 'node_', try without prefix
                    if node_id_to_find.startswith('node_'):
                        actual_id = node_id_to_find[5:]  # Remove 'node_' prefix
                        if actual_id in value:
                            value = value[actual_id]
                            parts = parts[1:]
                            logger.debug(f"Found match without 'node_' prefix: {actual_id}, remaining parts: {parts}")
                        else:
                            logger.debug(f"No match found for {node_id_to_find} or {actual_id}")
                            return None  # Return None early if node not found
                    else:
                        # Try to find by partial match (e.g., action1 might match node_abc123)
                        found = False
                        for node_id, node_data in value.items():
                            if node_id_to_find in node_id or node_id in node_id_to_find:
                                value = node_data
                                parts = parts[1:]
                                found = True
                                logger.debug(f"Found partial match: {node_id} for {node_id_to_find}, remaining parts: {parts}")
                                break
                        if not found:
                            logger.debug(f"No partial match found for {node_id_to_find}")
                            return None  # Return None early if node not found
        elif parts[0].startswith('node_'):
            # Access node outputs directly by node_id
            logger.debug(f"Direct node access: {parts[0]}")
            value = context.get('node_outputs', {}).get(parts[0])
            parts = parts[1:]  # Remove node_id prefix
        elif parts[0] == 'error' and context.get('last_error') is not None:
            # Most recent handled node failure (error branch / continue).
            # Only active once an error was handled, so flows that use a
            # plain variable named 'error' keep resolving it from variables.
            value = context.get('last_error')
            parts = parts[1:]
        elif parts[0] == 'loop':
            # Access loop variables directly
            logger.debug(f"Accessing loop variables")
            value = context.get('loop', {})
            parts = parts[1:]  # Remove 'loop' prefix
        else:
            # Check if the first part is a node ID in node_outputs
            node_outputs = context.get('node_outputs', {})
            if parts[0] in node_outputs:
                logger.debug(f"Found node ID '{parts[0]}' in node_outputs")
                value = node_outputs[parts[0]]
                parts = parts[1:]  # Remove node_id from path
            else:
                # Try direct access from variables (backward compatibility)
                value = context.get('variables', {})
        
        # Navigate through the remaining path
        logger.debug(f"Starting navigation through remaining parts: {parts}")
        logger.debug(f"Current value type: {type(value)}, is dict: {isinstance(value, dict)}")

        for i, part in enumerate(parts):
            logger.debug(f"Navigation step {i}: part='{part}', current_value_type={type(value).__name__}")

            if value is None:
                logger.debug(f"Value is None at path part '{part}', returning None")
                return None

            if isinstance(value, dict):
                logger.debug(f"Value is dict with keys: {list(value.keys())[:20]}")
                logger.debug(f"Value class name: {value.__class__.__name__}")
                # Check if it's an AttrDict
                if hasattr(value, '__class__') and value.__class__.__name__ == 'AttrDict':
                    logger.debug(f"Value is an AttrDict, converting to regular dict for navigation")
                # Special logging for attachment fields
                if part == 'attachment' or (i == 0 and 'attachment' in value):
                    logger.info(f"Navigating to attachment field, current value has keys: {list(value.keys()) if isinstance(value, dict) else 'not a dict'}")
                    if isinstance(value, dict) and 'attachment' in value:
                        att = value.get('attachment', {})
                        if isinstance(att, dict):
                            logger.info(f"Attachment found: filename={att.get('filename')}, size={att.get('size')}, content_length={len(att.get('content', ''))}")
                
                # Get the next value
                prev_value = value

                # Special handling for AttrDict
                if hasattr(value, '__class__') and value.__class__.__name__ == 'AttrDict':
                    logger.debug(f"Accessing '{part}' from AttrDict")
                    # Try different access methods
                    try:
                        # First try regular dict access
                        if part in value:
                            value = value[part]
                        else:
                            value = value.get(part)
                    except Exception as e:
                        logger.warning(f"Error accessing '{part}' from AttrDict: {e}")
                        value = None
                else:
                    value = value.get(part)

                logger.debug(f"After accessing '{part}': value type={type(value).__name__ if value is not None else 'None'}, value={'<dict>' if isinstance(value, dict) else str(value)[:100] if value is not None else 'None'}")

                # Check if we got a nested dict that might be an AttrDict
                if isinstance(value, dict) and hasattr(value, '__class__'):
                    logger.debug(f"Retrieved value is a {value.__class__.__name__}")

                # Enhanced logging for nested path resolution
                if i < len(parts) - 1:  # Not the last part
                    logger.debug(f"Navigating path: {'.'.join(parts[:i+1])} -> {type(value).__name__ if value is not None else 'None'}")
                    logger.debug(f"Still have {len(parts) - i - 1} parts to navigate: {parts[i+1:]}")
                    if value is None:
                        logger.warning(f"Path resolution failed at '{part}'. Available keys in parent: {list(prev_value.keys())[:20]}")
                        # Log more details about what was in the parent
                        if part in ['data', 'response', 'result']:
                            logger.warning(f"Looking for '{part}' in parent. Parent type: {type(prev_value)}, Parent keys: {list(prev_value.keys()) if isinstance(prev_value, dict) else 'not a dict'}")
                
                # Log after getting attachment value
                if part == 'attachment' and isinstance(value, dict):
                    logger.info(f"Retrieved attachment value: filename={value.get('filename')}, size={value.get('size')}, content_length={len(value.get('content', ''))}")
                    
            elif isinstance(value, list):
                if part.isdigit():
                    # Handle array index access
                    try:
                        index = int(part)
                        if 0 <= index < len(value):
                            value = value[index]
                            logger.debug(f"Accessed array index {index}, got {type(value).__name__}")
                        else:
                            logger.warning(f"Array index {index} out of bounds (array length: {len(value)})")
                            return None
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to access array with index '{part}': {e}")
                        return None
                else:
                    logger.warning(f"Cannot access list with non-numeric index '{part}'")
                    return None
            else:
                logger.debug(f"Cannot navigate further: value is {type(value).__name__}, but need dict or list for part '{part}'")
                return None
                
        # Special logging for final attachment values
        if field_path.endswith('attachment') and isinstance(value, dict):
            logger.info(f"Final attachment value for {field_path}: filename={value.get('filename')}, size={value.get('size')}, content_length={len(value.get('content', ''))}, keys={list(value.keys())}")
        else:
            logger.debug(f"Resolved {field_path} to {value}")
            
        return value
    
    def _evaluate_condition(self, field_value: Any, operator: str, compare_value: Any) -> bool:
        """Evaluate a condition."""
        if operator == 'equals':
            return field_value == compare_value
        elif operator == 'not_equals':
            return field_value != compare_value
        elif operator == 'greater_than':
            return float(field_value) > float(compare_value)
        elif operator == 'less_than':
            return float(field_value) < float(compare_value)
        elif operator == 'contains':
            return compare_value in str(field_value)
        elif operator == 'not_contains':
            return compare_value not in str(field_value)
        elif operator == 'is_empty':
            return not field_value
        elif operator == 'is_not_empty':
            return bool(field_value)
        else:
            raise ValueError(f"Unknown operator: {operator}")
    
    def _evaluate_expression(self, expression: str, context: Dict[str, Any]) -> bool:
        """Evaluate a JavaScript-like expression safely."""
        try:
            # Build evaluation context with all available variables
            variables = context.get('variables', {})
            
            # Also check data field for variables (in case they're passed there)
            data = context.get('data', {})
            
            # Merge variables from both sources, preferring explicit variables
            all_variables = {**data, **variables}
            
            # Log what we're working with
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"_evaluate_expression - variables from context: {variables}")
            logger.info(f"_evaluate_expression - data from context: {data}")
            logger.info(f"_evaluate_expression - merged variables: {all_variables}")
            logger.info(f"_evaluate_expression - expression: {expression}")
            
            # Create input object with all variables
            eval_context = {
                'input': all_variables,  # All variables are accessible under 'input'
                'flow': {
                    'execution_id': context.get('execution_id'),
                    'start_time': context.get('start_time'),
                    'current_node': context.get('current_node')
                },
                'node_outputs': context.get('node_outputs', {}),  # Add node_outputs to context
                'loop': context.get('loop', {}),  # Add loop variables to context
                'global_vars': dict(self.variable_manager.global_vars) if hasattr(self, 'variable_manager') and self.variable_manager else dict(context.get('global_vars', {})),  # Global variables (aliased because 'global' is a Python keyword)
            }
            
            # Also make variables available directly (for backward compatibility)
            eval_context.update(all_variables)
            
            # Add node outputs (e.g., node_123 -> accessible as node_123)
            for node_id, output in context.get('node_outputs', {}).items():
                eval_context[f'node_{node_id}'] = output
            
            # Import re module first
            import re
            
            # Replace JavaScript operators with Python equivalents
            py_expression = expression
            
            # Handle template syntax {{variable}} - remove the curly braces
            # This pattern matches {{...}} and captures the content inside
            template_pattern = r'\{\{([^}]+)\}\}'
            py_expression = re.sub(template_pattern, r'\1', py_expression)
            
            py_expression = py_expression.replace('===', '==')
            py_expression = py_expression.replace('!==', '!=')
            py_expression = py_expression.replace('&&', ' and ')
            py_expression = py_expression.replace('||', ' or ')
            py_expression = py_expression.replace('!', ' not ')

            # Replace 'global.' with 'global_vars.' since 'global' is a Python reserved keyword
            py_expression = re.sub(r'\bglobal\.', 'global_vars.', py_expression)
            
            # Handle node_outputs with numeric IDs (e.g., node_outputs.1234 -> node_outputs['1234'])
            # Pattern to match node_outputs.numeric_id
            node_outputs_pattern = r'node_outputs\.(\d+)'
            py_expression = re.sub(node_outputs_pattern, r"node_outputs['\1']", py_expression)
            
            # Handle .includes() method
            includes_pattern = r'(\w+(?:\.\w+)*?)\.includes\((.*?)\)'
            py_expression = re.sub(includes_pattern, r'\2 in \1', py_expression)
            
            # Handle .startsWith() and .endsWith()
            starts_pattern = r'(\w+(?:\.\w+)*?)\.startsWith\((.*?)\)'
            py_expression = re.sub(starts_pattern, r'\1.startswith(\2)', py_expression)
            ends_pattern = r'(\w+(?:\.\w+)*?)\.endsWith\((.*?)\)'
            py_expression = re.sub(ends_pattern, r'\1.endswith(\2)', py_expression)
            
            # Safely evaluate the expression
            # Use a restricted eval with only safe operations
            import ast
            import operator
            
            # Parse and compile the expression
            node = ast.parse(py_expression, mode='eval')
            
            # Define allowed operations
            allowed_ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Mod: operator.mod,
                ast.Eq: operator.eq,
                ast.NotEq: operator.ne,
                ast.Lt: operator.lt,
                ast.LtE: operator.le,
                ast.Gt: operator.gt,
                ast.GtE: operator.ge,
                ast.And: lambda x, y: x and y,
                ast.Or: lambda x, y: x or y,
                ast.Not: operator.not_,
                ast.In: lambda x, y: x in y,
                ast.NotIn: lambda x, y: x not in y,
            }
            
            def safe_eval(node):
                if isinstance(node, ast.Expression):
                    return safe_eval(node.body)
                elif isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.Name):
                    if node.id not in eval_context:
                        raise ValueError(f"Variable '{node.id}' is not defined")
                    return eval_context.get(node.id)
                elif isinstance(node, ast.Attribute):
                    obj = safe_eval(node.value)
                    if obj is None:
                        # Get variable name for better error message
                        var_name = ast.dump(node.value)
                        raise ValueError(f"Variable '{var_name}' is not defined")
                    try:
                        # Handle dictionary access first
                        if isinstance(obj, dict):
                            if node.attr not in obj:
                                # Variable not found - raise error
                                var_path = f"{ast.dump(node.value)}.{node.attr}"
                                raise ValueError(f"Variable '{var_path}' not found in context")
                            return obj[node.attr]
                        # Then try attribute access
                        if hasattr(obj, node.attr):
                            return getattr(obj, node.attr)
                        else:
                            # Attribute not found - raise error
                            var_path = f"{ast.dump(node.value)}.{node.attr}"
                            raise ValueError(f"Variable '{var_path}' not found in context")
                    except ValueError:
                        # Re-raise ValueError (variable not found)
                        raise
                    except Exception as e:
                        # Other errors
                        raise ValueError(f"Error accessing variable: {str(e)}")
                elif isinstance(node, ast.Subscript):
                    # Handle subscript operations like dict['key'] or list[0]
                    obj = safe_eval(node.value)
                    if obj is None:
                        var_name = ast.dump(node.value)
                        raise ValueError(f"Variable '{var_name}' is not defined")
                    
                    key = safe_eval(node.slice)
                    try:
                        if isinstance(obj, (dict, list, tuple, str)):
                            return obj[key]
                        else:
                            raise ValueError(f"Cannot subscript object of type {type(obj).__name__}")
                    except KeyError:
                        raise ValueError(f"Key '{key}' not found in object")
                    except IndexError:
                        raise ValueError(f"Index {key} out of range")
                    except Exception as e:
                        raise ValueError(f"Error accessing subscript: {str(e)}")
                elif isinstance(node, ast.Compare):
                    left = safe_eval(node.left)
                    for op, right_node in zip(node.ops, node.comparators):
                        right = safe_eval(right_node)
                        op_func = allowed_ops.get(type(op))
                        if op_func:
                            if not op_func(left, right):
                                return False
                        else:
                            raise ValueError(f"Unsupported operation: {type(op)}")
                        left = right
                    return True
                elif isinstance(node, ast.BoolOp):
                    op_func = allowed_ops.get(type(node.op))
                    if not op_func:
                        raise ValueError(f"Unsupported operation: {type(node.op)}")
                    
                    values = [safe_eval(val) for val in node.values]
                    result = values[0]
                    for val in values[1:]:
                        result = op_func(result, val)
                    return result
                elif isinstance(node, ast.UnaryOp):
                    op_func = allowed_ops.get(type(node.op))
                    if not op_func:
                        raise ValueError(f"Unsupported operation: {type(node.op)}")
                    return op_func(safe_eval(node.operand))
                elif isinstance(node, ast.ListComp):
                    # Handle list comprehensions
                    # e.g., [h['value'] for h in headers if h['name'] == 'Subject']
                    elements = []
                    for generator in node.generators:
                        # Get the iterable
                        iterable = safe_eval(generator.iter)
                        if not iterable:
                            return []

                        # Iterate through the iterable
                        for item in iterable:
                            # Set up the loop variable
                            var_name = generator.target.id if isinstance(generator.target, ast.Name) else None
                            if var_name:
                                old_value = eval_context.get(var_name)
                                eval_context[var_name] = item

                                # Check filters (if conditions)
                                passes_filters = True
                                for filter_expr in generator.ifs:
                                    if not safe_eval(filter_expr):
                                        passes_filters = False
                                        break

                                # If passes all filters, evaluate the element
                                if passes_filters:
                                    elements.append(safe_eval(node.elt))

                                # Restore old value
                                if old_value is not None:
                                    eval_context[var_name] = old_value
                                elif var_name in eval_context:
                                    del eval_context[var_name]

                    return elements

                elif isinstance(node, ast.GeneratorExp):
                    # Handle generator expressions (similar to list comprehensions but lazy)
                    # Used in functions like any(), all(), next()
                    for generator in node.generators:
                        iterable = safe_eval(generator.iter)
                        if not iterable:
                            return iter([])  # Empty generator

                        def gen():
                            for item in iterable:
                                var_name = generator.target.id if isinstance(generator.target, ast.Name) else None
                                if var_name:
                                    old_value = eval_context.get(var_name)
                                    eval_context[var_name] = item

                                    passes_filters = True
                                    for filter_expr in generator.ifs:
                                        if not safe_eval(filter_expr):
                                            passes_filters = False
                                            break

                                    if passes_filters:
                                        yield safe_eval(node.elt)

                                    if old_value is not None:
                                        eval_context[var_name] = old_value
                                    elif var_name in eval_context:
                                        del eval_context[var_name]

                        return gen()

                elif isinstance(node, ast.Call):
                    # Handle built-in functions and method calls
                    if isinstance(node.func, ast.Name):
                        # Built-in functions like any(), all(), next(), join()
                        func_name = node.func.id

                        if func_name == 'any':
                            # any(iterable)
                            if node.args:
                                arg = safe_eval(node.args[0])
                                return any(arg)
                            return False

                        elif func_name == 'all':
                            # all(iterable)
                            if node.args:
                                arg = safe_eval(node.args[0])
                                return all(arg)
                            return True

                        elif func_name == 'next':
                            # next(iterator, default)
                            if node.args:
                                iterator = safe_eval(node.args[0])
                                default = safe_eval(node.args[1]) if len(node.args) > 1 else None
                                try:
                                    return next(iterator, default)
                                except (TypeError, StopIteration):
                                    return default
                            return None

                        elif func_name == 'str':
                            # str(object)
                            if node.args:
                                return str(safe_eval(node.args[0]))
                            return ''

                        elif func_name == 'int':
                            # int(object)
                            if node.args:
                                return int(safe_eval(node.args[0]))
                            return 0

                        elif func_name == 'float':
                            # float(object)
                            if node.args:
                                return float(safe_eval(node.args[0]))
                            return 0.0

                        elif func_name == 'len':
                            # len(object)
                            if node.args:
                                return len(safe_eval(node.args[0]))
                            return 0

                        else:
                            raise ValueError(f"Unsupported function: {func_name}")

                    elif isinstance(node.func, ast.Attribute):
                        # Method calls like str.startswith, str.join
                        obj = safe_eval(node.func.value)
                        method_name = node.func.attr
                        args = [safe_eval(arg) for arg in node.args]

                        # Check if object exists and has the method
                        if obj is not None:
                            if method_name in ['startswith', 'endswith', 'lower', 'upper', 'strip', 'split'] and hasattr(str(obj), method_name):
                                # String methods - convert to string and call method
                                return getattr(str(obj), method_name)(*args)
                            elif method_name == 'join' and isinstance(obj, str):
                                # str.join(iterable)
                                if args:
                                    return obj.join(str(item) for item in args[0])
                                return ''
                            elif method_name == 'includes':
                                # Handle includes as 'in' operator
                                return args[0] in str(obj) if args else False
                            elif method_name in ['append', 'extend', 'pop', 'remove'] and isinstance(obj, list):
                                # List methods
                                return getattr(obj, method_name)(*args)
                            elif method_name in ['get', 'keys', 'values', 'items'] and isinstance(obj, dict):
                                # Dictionary methods
                                return getattr(obj, method_name)(*args)
                        return False
                    else:
                        raise ValueError(f"Unsupported function call: {ast.dump(node)}")
                else:
                    raise ValueError(f"Unsupported expression: {ast.dump(node)}")
            
            result = safe_eval(node)
            return bool(result)
            
        except Exception as e:
            # Log detailed error information
            with get_tenant_db(self.tenant_schema) as db:
                error_details = {
                    'error': str(e),
                    'expression': expression,
                    'python_expression': py_expression,
                    'available_variables': list(eval_context.keys()),
                    'input_variables': eval_context.get('input', {}),
                    'loop_variables': eval_context.get('loop', {}),
                    'node_outputs': list(context.get('node_outputs', {}).keys())
                }
                self._log_execution(db, context['execution_id'], context.get('current_node'), "error", 
                                  f"Condition evaluation failed: {str(e)}",
                                  error_details)
            
            logger.error(f"Expression evaluation failed: {str(e)}")
            logger.error(f"Expression: {expression}")
            logger.error(f"Python expression: {py_expression}")
            logger.error(f"Available variables: {list(eval_context.keys())}")
            logger.error(f"Input variables: {eval_context.get('input', {})}")
            raise ValueError(f"Failed to evaluate expression: {str(e)}")
    
    def _evaluate_simple_condition(self, field: str, operator: str, value: Any, context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition (legacy format)."""
        field_value = self._get_field_value(field, context)
        return self._evaluate_condition(field_value, operator, value)
    
    def _build_auth_headers(self, auth_config: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, str]:
        """Build authentication headers."""
        headers = {'Content-Type': 'application/json'}
        
        # First, add custom headers if present (from merged custom params)
        if 'headers' in credentials:
            logger.info(f"Adding custom headers from credentials: {list(credentials['headers'].keys())}")
            headers.update(credentials['headers'])
        
        auth_type = auth_config.get('type')
        if auth_type == 'api_key':
            key_header = auth_config.get('key_header', 'X-API-Key')
            headers[key_header] = credentials.get('api_key', '')
        elif auth_type == 'bearer':
            headers['Authorization'] = f"Bearer {credentials.get('access_token', '')}"
        elif auth_type == 'basic':
            import base64
            username = credentials.get('username', '')
            password = credentials.get('password', '')
            auth_str = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers['Authorization'] = f"Basic {auth_str}"
        
        return headers
    
    @with_retry(config=NETWORK_RETRY_CONFIG)
    async def _make_http_request(self, method: str, url: str, headers: Dict[str, str], 
                               json: Optional[Dict[str, Any]] = None, 
                               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                params=params
            )
            response.raise_for_status()
            
            if response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            else:
                return {'response': response.text}
        
        except httpx.HTTPStatusError as e:
            # Don't retry on 4xx errors (client errors)
            if 400 <= e.response.status_code < 500:
                logger.error(f"HTTP client error: {e.response.status_code} - {e.response.text}")
                raise
            # Do retry on 5xx errors (server errors)
            logger.error(f"HTTP server error: {e.response.status_code} - {e.response.text}")
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            # These are retryable network errors
            logger.error(f"Network error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise
    
    def _log_with_context(self, execution_id: str, step_id: Optional[str],
                         level: str, message: str, data: Optional[Dict[str, Any]] = None,
                         context: Optional[Dict[str, Any]] = None):
        """Helper method to log with context using the current database session."""
        with get_tenant_db(self.tenant_schema) as db:
            self._log_execution(db, execution_id, step_id, level, message, data, context)

    # ------------------------------------------------------------------
    # Flow-level execution logging (execution_log_level / flow_log_sample_rate)
    # Implemented centrally in the logging helper — applies to ALL trigger
    # types, never per-trigger code.
    # ------------------------------------------------------------------

    # Data keys kept in node_summary mode — enough for "node, status, result summary"
    _SUMMARY_DATA_KEYS = ('execution_stage', 'node_type', 'label', 'service_name',
                          'trigger_type', 'error', 'loop_iteration', 'extracted_params')

    def _init_log_policy(self, execution_id: str, flow_definition: Optional[Dict[str, Any]]):
        """Register the flow-level execution log policy for this execution.

        Levels (flow_definition.settings.execution_log_level):
          full         — every step logged in detail (default, current behavior)
          node_summary — one line per node (start summary + completion + errors/
                         warnings), payload data stripped to short summary keys
          errors_only  — nothing persisted while the flow succeeds; entries are
                         buffered in memory and flushed only when an error occurs

        flow_definition.settings.flow_log_sample_rate (0.0-1.0, default 1.0):
        the sampled fraction of executions logs at the configured level;
        unsampled executions fall back to errors_only. The operator env
        setting flow_log_min_level caps verbosity for every flow.
        """
        try:
            flow_settings = {}
            if isinstance(flow_definition, dict):
                flow_settings = flow_definition.get('settings') or {}
            if not isinstance(flow_settings, dict):
                flow_settings = {}

            level = flow_settings.get('execution_log_level') or 'full'
            if level not in self._LOG_LEVEL_VERBOSITY:
                level = 'full'

            try:
                sample_rate = float(flow_settings.get('flow_log_sample_rate', 1.0))
            except (TypeError, ValueError):
                sample_rate = 1.0
            if 0.0 <= sample_rate < 1.0 and random.random() >= sample_rate:
                # Unsampled execution: only errors get persisted
                level = 'errors_only'

            floor = getattr(settings, 'flow_log_min_level', None)
            if floor in self._LOG_LEVEL_VERBOSITY and \
                    self._LOG_LEVEL_VERBOSITY[floor] < self._LOG_LEVEL_VERBOSITY[level]:
                level = floor

            if level != 'full':
                ExecutionEngine._log_policies[str(execution_id)] = {
                    'level': level,
                    'buffer': [],
                    'tripped': False,
                }
        except Exception as e:
            # A broken log policy must never break execution
            logger.warning(f"Failed to initialize log policy for execution {execution_id}: {e}")

    def _finalize_log_policy(self, execution_id: str):
        """Drop the per-execution log policy (and any never-flushed buffer)."""
        ExecutionEngine._log_policies.pop(str(execution_id), None)

    def _apply_log_policy(self, db: Session, execution_id: str, step_id: Optional[str],
                          level: str, message: str, data):
        """Apply the execution's log policy to one entry.

        Returns (should_write, data): buffered/dropped entries return False and
        are never persisted nor notified over WebSocket.
        """
        policy = ExecutionEngine._log_policies.get(str(execution_id))
        if not policy or policy.get('tripped'):
            return True, data

        is_error = level in ('error', 'critical')

        if policy['level'] == 'errors_only':
            if is_error:
                # First error: flush the buffered history so the failing path
                # is fully visible, then write through for the rest of the run
                policy['tripped'] = True
                self._flush_log_buffer(db, execution_id, policy)
                return True, data
            policy['buffer'].append({
                'step_id': step_id,
                'level': level,
                'message': message,
                'data': data if isinstance(data, dict) else {},
                'timestamp': datetime.utcnow(),
            })
            if len(policy['buffer']) > 1000:
                policy['buffer'].pop(0)
            return False, data

        if policy['level'] == 'node_summary':
            stage = data.get('execution_stage') if isinstance(data, dict) else None
            if not is_error and level != 'warning' and \
                    stage not in ('execution_start', 'node_complete', 'execution_complete'):
                return False, data
            if isinstance(data, dict):
                data = {k: v for k, v in data.items() if k in self._SUMMARY_DATA_KEYS}
            return True, data

        return True, data

    def _flush_log_buffer(self, db: Session, execution_id: str, policy: Dict[str, Any]):
        """Lazy errors_only write: persist the buffered entries in one commit."""
        buffered = policy.get('buffer') or []
        policy['buffer'] = []
        if not buffered:
            return
        try:
            for entry in buffered:
                db.add(ExecutionLog(
                    execution_id=execution_id,
                    step_id=entry['step_id'],
                    timestamp=entry['timestamp'],
                    level=entry['level'],
                    message=entry['message'],
                    data=entry['data']
                ))
            db.commit()
            logger.info(f"Flushed {len(buffered)} buffered log entries for failing "
                        f"execution {execution_id}")
        except Exception as e:
            logger.error(f"Failed to flush buffered logs for execution {execution_id}: {e}")


    def _log_execution(self, db: Session, execution_id: str, step_id: Optional[str], 
                      level: str, message: str, data: Optional[Dict[str, Any]] = None,
                      context: Optional[Dict[str, Any]] = None):
        """Log execution event with proper loop context."""
        # Ensure data is JSON serializable to avoid circular reference errors
        safe_data = {}
        if data:
            try:
                # Test if data can be serialized
                json.dumps(data)
                safe_data = data.copy() if isinstance(data, dict) else data
            except Exception as e:
                # If not, create a safe representation
                safe_data = {
                    'error': 'Data could not be fully serialized',
                    'reason': str(e),
                    'data_keys': list(data.keys()) if isinstance(data, dict) else str(type(data))
                }
        
        # Add comprehensive loop context if we're inside a loop
        if context and context.get('_in_loop') and context.get('loop'):
            if not isinstance(safe_data, dict):
                safe_data = {'value': safe_data}
            
            loop_info = context.get('loop', {})
            # Add detailed loop execution context
            safe_data['loop_context'] = {
                'loop_node_id': context.get('_loop_node_id'),
                'iteration_index': loop_info.get('index', 0),
                'iteration_count': loop_info.get('count', loop_info.get('index', 0) + 1),
                'is_first': loop_info.get('first', False),
                'is_last': loop_info.get('last', False),
                'iterator_name': context.get('_iterator_name'),
                'iterator_value': loop_info.get(context.get('_iterator_name')) if context.get('_iterator_name') else None,
                'loop_type': context.get('_loop_type'),
                'total_items': context.get('_total_items')
            }
            # Keep backward compatibility
            safe_data['loop_iteration'] = loop_info.get('count', loop_info.get('index', 0) + 1)
            safe_data['loop_node_id'] = context.get('_loop_node_id')

        # Secrets never reach the log store or the live log WebSocket (the
        # ExecutionLog model redacts too, for writers that bypass this method).
        message = redact_text(message)
        safe_data = redact_secrets(safe_data)

        # Flow-level execution log policy (node_summary / errors_only):
        # buffered or dropped entries are neither persisted nor notified
        should_write, safe_data = self._apply_log_policy(
            db, execution_id, step_id, level, message, safe_data)
        if not should_write:
            return

        log = ExecutionLog(
            execution_id=execution_id,
            step_id=step_id,
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            data=safe_data
        )
        db.add(log)
        db.commit()

        # Send WebSocket notification for log entry in a thread-safe way.
        # Log writes may run inside asyncio.to_thread (no loop in this thread),
        # so fall back to the captured main loop.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = ExecutionEngine._main_loop
        if loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._send_log_notification(execution_id, {
                        'step_id': step_id,
                        'level': level,
                        'message': message,
                        'data': safe_data,
                        'timestamp': datetime.utcnow().isoformat()
                    }),
                    loop
                )
            except Exception as e:
                logger.error(f"Failed to schedule WebSocket notification: {e}")
        else:
            logger.debug(f"No event loop available for WebSocket log notification "
                         f"(execution {execution_id})")
    
    def _mark_execution_failed(self, db: Session, execution_id: str, error_message: str, failed_node_id: str = None):
        """Mark execution as failed."""
        execution = db.query(FlowExecution).filter(
            FlowExecution.execution_id == execution_id
        ).first()
        if execution:
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = datetime.utcnow()
            # Only log a generic execution failure if we haven't already logged a specific node error
            # Use the failed_node_id if provided, otherwise use 'flow' for general execution failures
            step_id = failed_node_id if failed_node_id else 'flow'
            # Don't duplicate error logs - check if we've already logged this error
            if not failed_node_id:  # Only log general execution errors, not node-specific ones
                self._log_execution(db, execution_id, step_id, "error",
                                  f"Execution failed: {error_message}")
            db.commit()
            
            # Send WebSocket notification for status update in a thread-safe way
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    self._send_status_notification(execution_id, {
                        'status': 'failed',
                        'error_message': error_message,
                        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None
                    }),
                    loop
                )
            except RuntimeError:
                try:
                    asyncio.create_task(self._send_status_notification(execution_id, {
                        'status': 'failed',
                        'error_message': error_message,
                        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None
                    }))
                except Exception as e:
                    logger.error(f"Failed to schedule WebSocket notification: {e}")

    async def _commit_billing(self, context: Dict[str, Any], db: Session):
        """Commit reserved funds after successful service execution."""
        execution_id = context.get('execution_id')
        billing_mode = context.get('billing_mode')

        if execution_id and billing_mode == 'prepaid':
            try:
                # Calculate actual cost from context or use estimated cost
                actual_cost = context.get('billing_actual_cost', context.get('billing_estimated_cost', 0))

                balance_enforcer.commit_reserved_funds(
                    execution_id=execution_id,
                    actual_cost=actual_cost,
                    db=db
                )
                logger.info(f"Committed funds for execution {execution_id}, actual cost: {actual_cost}")

                # Clean up billing context
                context.pop('billing_mode', None)
                context.pop('billing_estimated_cost', None)
                context.pop('billing_actual_cost', None)
            except Exception as e:
                logger.error(f"Failed to commit billing funds: {str(e)}", exc_info=True)
                # Don't raise - the service executed successfully, just log the billing issue

    async def _release_billing(self, context: Dict[str, Any], db: Session):
        """Release reserved funds after failed service execution."""
        execution_id = context.get('execution_id')
        billing_mode = context.get('billing_mode')

        if execution_id and billing_mode == 'prepaid':
            try:
                balance_enforcer.release_reserved_funds(
                    execution_id=execution_id,
                    db=db
                )
                logger.info(f"Released reserved funds for execution {execution_id}")

                # Clean up billing context
                context.pop('billing_mode', None)
                context.pop('billing_estimated_cost', None)
                context.pop('billing_actual_cost', None)
            except Exception as e:
                logger.error(f"Failed to release billing funds: {str(e)}", exc_info=True)
                # Don't raise - we're already in error handling

    async def _execute_debug_action(self, app: Application, service_name: str, parameters: Dict[str, Any],
                                   context: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Execute Debug application actions."""
        # Map parameters
        mapped_params = self._map_parameters(parameters, context)
        
        if service_name == "print":
            # Handle print action
            message = mapped_params.get('message', '')
            variables = mapped_params.get('variables', {})
            level = mapped_params.get('level', 'info')
            
            # If no specific variables provided, print all flow variables
            if not variables and not message:
                # Get all flow variables - create a safe copy to avoid circular references
                try:
                    # Create a deep copy but limit depth to avoid circular references
                    variables = {
                        'execution_id': context.get('execution_id'),
                        'current_node_id': context.get('current_node_id'),
                    }
                    
                    # Safely copy input variables (user-provided variables only)
                    if 'variables' in context:
                        variables['input'] = context['variables']
                    
                    # Safely copy node outputs
                    if 'node_outputs' in context:
                        node_outputs = {}
                        for k, v in context['node_outputs'].items():
                            try:
                                # Try to serialize to JSON to check for circular refs
                                json.dumps(v)
                                node_outputs[k] = v
                            except:
                                # If can't serialize, just use string representation
                                node_outputs[str(k)] = f"<Output of node {k} - too complex to display>"
                        variables['node_outputs'] = node_outputs
                    
                    # Safely copy current data
                    if 'data' in context:
                        try:
                            json.dumps(context['data'])
                            variables['data'] = context['data']
                        except:
                            variables['data'] = str(context['data'])
                    
                except Exception as e:
                    # Fallback to basic info if something goes wrong
                    variables = {
                        'error': f"Could not serialize all variables: {str(e)}",
                        'execution_id': context.get('execution_id'),
                        'current_node_id': context.get('current_node_id'),
                    }
                
                message = "All flow variables"
            elif not variables:
                # If only message is provided, still include flow context
                variables = {
                    'flow_data': context.get('data', {}),
                    'flow_variables': context.get('variables', {})
                }
            
            # Create log message
            log_parts = []
            if message:
                log_parts.append(f"Message: {message}")
            
            if variables:
                log_parts.append("Variables:")
                for key, value in variables.items():
                    try:
                        log_parts.append(f"  {key} = {json.dumps(value, indent=2)}")
                    except:
                        # Handle non-JSON serializable objects
                        log_parts.append(f"  {key} = {str(value)}")
            
            log_message = '\n'.join(log_parts) if log_parts else "Debug print (empty)"
            
            # Log to execution log
            self._log_execution(db, context['execution_id'], 
                              context.get('current_node_id'), level, 
                              f"[DEBUG PRINT] {log_message}", 
                              {"message": message, "variables": variables})
            
            # Return the input data plus debug info
            return {
                **context['data'],
                '_debug_print': {
                    'message': message,
                    'variables': variables,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        
        elif service_name == "log":
            # Handle log action
            message = mapped_params.get('message', '')
            level = mapped_params.get('level', 'info')
            
            # Process message with variable interpolation
            processed_message = message
            if '{{' in message and '}}' in message:
                # Simple variable interpolation
                import re
                pattern = r'\{\{([\w\.\[\]]+)\}\}'
                
                def replace_variable(match):
                    var_path = match.group(1).strip()
                    try:
                        # Build context similar to expression evaluator
                        eval_context = {
                            'input': context.get('variables', {}),
                            'data': context.get('data', {}),
                            'flow': {
                                'execution_id': context.get('execution_id'),
                                'start_time': context.get('start_time'),
                                'current_node': context.get('current_node')
                            }
                        }
                        
                        # Add node outputs
                        for node_id, output in context.get('node_outputs', {}).items():
                            eval_context[f'node_{node_id}'] = output
                        
                        # Navigate through the variable path
                        value = eval_context
                        for part in var_path.split('.'):
                            if '[' in part and ']' in part:
                                # Handle array notation
                                key = part[:part.index('[')]
                                index = int(part[part.index('[')+1:part.index(']')])
                                value = value.get(key, [])[index] if isinstance(value, dict) else value[key][index]
                            else:
                                if isinstance(value, dict):
                                    value = value.get(part, f"{{{{ {var_path} }}}}")
                                else:
                                    value = getattr(value, part, f"{{{{ {var_path} }}}}")
                        return str(value)
                    except Exception as e:
                        logger.debug(f"Variable interpolation failed for {var_path}: {str(e)}")
                        return f"{{{{ {var_path} }}}}"  # Keep original if can't resolve
                
                processed_message = re.sub(pattern, replace_variable, message)
            
            # Log with the specified level
            self._log_execution(db, context['execution_id'], 
                              context.get('current_node_id'), level, 
                              f"[USER LOG] {processed_message}",
                              {"original_message": message, "processed_message": processed_message, "level": level})
            
            # Return the input data plus log info
            return {
                **context['data'],
                '_debug_log': {
                    'message': processed_message,
                    'level': level,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        
        elif service_name == "wait":
            # Handle wait action
            seconds = mapped_params.get('seconds', 0)
            
            self._log_execution(db, context['execution_id'], 
                              context.get('current_node_id'), 'info', 
                              f"[DEBUG WAIT] Waiting for {seconds} seconds...")
            
            # Wait for specified duration
            await asyncio.sleep(seconds)
            
            self._log_execution(db, context['execution_id'], 
                              context.get('current_node_id'), 'info', 
                              f"[DEBUG WAIT] Wait completed")
            
            # Return the input data
            return context['data']
        
        else:
            raise ValueError(f"Unknown Debug service: {service_name}")
    
    async def _execute_service_with_type(self, service_obj: ApplicationService, subscription: ApplicationSubscription,
                                       parameters: Dict[str, Any], context: Dict[str, Any], is_simulation: bool = False) -> Dict[str, Any]:
        """Execute a service using the new service type system."""
        service_type = service_obj.service_type
        
        # Ensure parameters is a dictionary
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
                logger.info(f"Converted parameters from string in _execute_service_with_type")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse parameters string in _execute_service_with_type: {parameters}")
                parameters = {}
        elif not isinstance(parameters, dict):
            logger.error(f"Parameters is not a dict in _execute_service_with_type: {type(parameters)}")
            parameters = {}
        
        # Ensure service_config and response_config are dicts (handles both PostgreSQL JSONB and SQLite TEXT/double-serialized)
        service_config = ensure_dict(service_obj.service_config, "service_config")
        response_config = ensure_dict(service_obj.response_config, "response_config")

        # Add response_config to service_config if it exists
        if response_config:
            service_config['response_config'] = response_config
        
        # All configuration is now in service_config
        # Add base_url from subscription if available, otherwise fall back to application base_url
        if subscription:
            # Ensure subscription_config is a dict (handles both PostgreSQL JSONB and SQLite TEXT/double-serialized)
            sub_config = ensure_dict(subscription.subscription_config, "subscription_config")

            # First try subscription's base_url, then fall back to application's base_url
            if sub_config.get('base_url'):
                service_config['base_url'] = sub_config['base_url']
                logger.info(f"Using base_url from subscription config: {sub_config['base_url']}")
            elif subscription.application and subscription.application.base_url:
                service_config['base_url'] = subscription.application.base_url
                logger.info(f"Using base_url from application: {subscription.application.base_url}")
            else:
                logger.warning(f"No base_url found in subscription or application for service {service_obj.service_name}")
        else:
            logger.warning(f"Subscription is None for service {service_obj.service_name}")
            # Try to get base_url from service's application directly
            if service_obj.application and service_obj.application.base_url:
                service_config['base_url'] = service_obj.application.base_url
                logger.info(f"Using base_url from service's application: {service_obj.application.base_url}")
        
        # Add service_name to config so executors know which service is being called
        service_config['service_name'] = service_obj.service_name
        # The service's own timeout is a column, not part of service_config; the
        # executors read it from service_config['timeout_seconds'] and otherwise
        # fall back to 30 s — which cut off every slow API (an LLM answering a
        # batch) whatever the connector declared.
        if service_obj.timeout_seconds and 'timeout_seconds' not in service_config:
            service_config['timeout_seconds'] = service_obj.timeout_seconds
        # Who is being called, for usage metering (services/flow_usage.py), and
        # the prices this tenant's connection overrides.
        service_config['app_id'] = str(service_obj.app_id) if service_obj.app_id else None
        if service_obj.application is not None:
            service_config['app_name'] = service_obj.application.app_name
        if subscription:
            _usage_prices = ensure_dict(subscription.subscription_config, "subscription_config").get('usage_prices')
            if isinstance(_usage_prices, dict):
                service_config['usage_price_overrides'] = _usage_prices
        
        # Log the final service_config for debugging
        logger.info(f"Final service_config for {service_type}: {json.dumps(redact_secrets(service_config), indent=2, default=str)}")
        
        # Log service execution details (node execution is already logged in _execute_node)
        with get_tenant_db(self.tenant_schema) as db:
            self._log_execution(db, context['execution_id'], context.get('current_node_id'), "debug",
                              f"Service configuration for {service_obj.service_name}",
                              {"service_type": service_type, "config": service_config}, context)
        
        # Log available context for debugging
        with get_tenant_db(self.tenant_schema) as db:
            self._log_execution(db, context['execution_id'], context.get('current_node_id'), "info",
                              f"Mapping parameters for {service_type} service",
                              {
                                  "parameters": parameters,
                                  "available_variables": list(context.get('variables', {}).keys()),
                                  "available_node_outputs": list(context.get('node_outputs', {}).keys())
                              }, context)
        
        # Clean up parameters before mapping
        cleaned_parameters = {}
        for key, value in parameters.items():
            # Skip undefined or None keys
            if key not in ['undefined', 'null', None, ''] and value is not None:
                cleaned_parameters[key] = value
        
        # Map parameters using context
        mapped_params = self._map_parameters(cleaned_parameters, context)
        
        # Clean up mapped parameters to remove any undefined keys that might have been introduced
        cleaned_mapped_params = {}
        for key, value in mapped_params.items():
            if key not in ['undefined', 'null', None, ''] and value is not None:
                cleaned_mapped_params[key] = value
        mapped_params = cleaned_mapped_params
        
        # Log the mapped parameters for debugging
        if service_type in ['api_call', 'database_query', 'graphql']:
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], context.get('current_node_id'), "info",
                                  f"{service_type} parameters after mapping and cleanup",
                                  {
                                      "service_type": service_type,
                                      "original": parameters,
                                      "cleaned": cleaned_parameters,
                                      "mapped": mapped_params,
                                      "method": service_config.get('method', 'POST') if service_type in ['api_call', 'graphql'] else 'N/A'
                                  }, context)
        
        # A metered call (the connector declares response_config.usage) stops
        # once the flow's daily budget is used up — the run fails with the reason.
        if not is_simulation and context.get('_budget') and (response_config or {}).get('usage'):
            from services import flow_usage
            await asyncio.to_thread(flow_usage.check_budget, self.tenant_schema,
                                    context.get('flow_id'), context['_budget'])

        # In simulation mode, don't make actual calls
        if is_simulation:
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], context.get('current_node_id'), "info",
                                  f"[SIMULATION] Would execute {service_type}: {service_obj.service_name}",
                                  {"parameters": mapped_params, "config": service_config})
            return {
                'simulation': True,
                'service_type': service_type,
                'service_name': service_obj.service_name,
                'would_send': mapped_params
            }
        
        # Get auth credentials if needed - PostgreSQL stores JSONB natively
        auth_credentials = None
        if subscription and subscription.auth_credentials:
            logger.info(f"Subscription has auth_credentials: {bool(subscription.auth_credentials)}")
            auth_creds_to_decrypt = subscription.auth_credentials
            auth_credentials = decrypt_credentials(auth_creds_to_decrypt) if auth_creds_to_decrypt else {}
            logger.info(f"Decrypted auth credentials keys: {list(auth_credentials.keys()) if auth_credentials else 'None'}")
            # Log masked credential values for debugging
            if auth_credentials:
                for key, value in auth_credentials.items():
                    if isinstance(value, str) and len(value) > 3:
                        masked_value = f"{'*' * (len(value)-3)}{value[-3:]}"
                        logger.info(f"Credential '{key}': {masked_value}")
                    else:
                        logger.info(f"Credential '{key}': [present]")
        
        # Merge custom parameters from subscription_config
        from services.custom_params_patch import merge_custom_params_with_credentials

        # Ensure subscription_config is a dict (handles both PostgreSQL JSONB and SQLite TEXT/double-serialized)
        sub_config = ensure_dict(subscription.subscription_config if subscription else None, "subscription_config")

        # Merge custom params with auth credentials
        logger.info(f"Before merge - auth_credentials: {list(auth_credentials.keys()) if auth_credentials else 'None'}")
        logger.info(f"Before merge - sub_config: {redact_secrets(sub_config)}")
        logger.info(f"Before merge - custom_params in sub_config: {redact_secrets(sub_config.get('custom_params', {}))}")
        
        auth_credentials = merge_custom_params_with_credentials(auth_credentials or {}, sub_config)
        
        logger.info(f"After merging custom params, auth credentials keys: {list(auth_credentials.keys()) if auth_credentials else 'None'}")
        if auth_credentials and 'headers' in auth_credentials:
            logger.info(f"Merged headers: {redact_secrets(auth_credentials['headers'])}")
        if auth_credentials and 'query_params' in auth_credentials:
            logger.info(f"Merged query_params: {redact_secrets(auth_credentials['query_params'])}")
        if auth_credentials and 'body_params' in auth_credentials:
            logger.info(f"Merged body_params: {redact_secrets(auth_credentials['body_params'])}")
        
        # Get the appropriate executor
        try:
            # Get auth config from application
            auth_config = None
            if subscription and subscription.application and hasattr(subscription.application, 'auth_config'):
                # Ensure auth_config is a dict (handles both PostgreSQL JSONB and SQLite TEXT/double-serialized)
                auth_config = ensure_dict(subscription.application.auth_config, "auth_config")
                logger.info(f"Auth config from application: {redact_secrets(auth_config)}")

                # Add base_url to auth_config for template processing
                if subscription.application.base_url:
                    auth_config['base_url'] = subscription.application.base_url
                    logger.info(f"Added base_url to auth_config: {subscription.application.base_url}")
            else:
                logger.warning(f"No auth config available - subscription: {bool(subscription)}, application: {bool(subscription and subscription.application)}")
            
            subscription_id = subscription.subscription_id if subscription else None

            # Get application base URL for executor selection (needed for Arrow Flight detection)
            application_base_url = None
            if subscription and subscription.application:
                application_base_url = subscription.application.base_url

            executor = get_service_executor(
                service_type,
                service_config,
                auth_credentials,
                subscription_id,
                auth_config,
                application_base_url
            )
            
            # Add base_url to context - use subscription's base_url if available, otherwise application's
            if subscription:
                # Ensure subscription_config is a dict (handles both PostgreSQL JSONB and SQLite TEXT/double-serialized)
                sub_config = ensure_dict(subscription.subscription_config, "subscription_config")

                # Use subscription's base_url for databases and other configurable services
                if sub_config.get('base_url'):
                    context['application_base_url'] = sub_config['base_url']
                elif subscription.application:
                    context['application_base_url'] = subscription.application.base_url
            
            # Special logging for SMTP with attachments
            if service_type == 'smtp_send' and 'attachments' in mapped_params:
                att = mapped_params['attachments']
                if isinstance(att, dict):
                    logger.info(f"SMTP: Passing attachment to executor - filename={att.get('filename')}, "
                              f"content_length={len(att.get('content', ''))}, size={att.get('size')}")
                    # Log the actual keys in the attachment dict
                    logger.info(f"SMTP: Attachment dict keys: {list(att.keys())}")
                elif isinstance(att, list) and att:
                    for i, a in enumerate(att):
                        if isinstance(a, dict):
                            logger.info(f"SMTP: Attachment[{i}] - filename={a.get('filename')}, "
                                      f"content_length={len(str(a.get('content', '')))}, size={a.get('size')}")
                            # Log the actual keys in each attachment
                            logger.info(f"SMTP: Attachment[{i}] keys: {list(a.keys())}")
                        else:
                            logger.info(f"SMTP: Attachment[{i}] is not a dict, type: {type(a)}, value: {str(a)[:100]}")
            
            result = await executor.execute(mapped_params, context)
            
            # Check if the result indicates an error
            if isinstance(result, dict) and result.get('error'):
                # Log the full error result for debugging
                logger.error(f"Service execution returned error result: {json.dumps(result, indent=2)}")
                
                # Handle various error message formats
                raw_message = result.get('message', 'Unknown error')
                if isinstance(raw_message, str):
                    error_msg = raw_message
                elif isinstance(raw_message, bool):
                    error_msg = f"API Error: {raw_message}"
                else:
                    error_msg = str(raw_message) if raw_message is not None else 'Unknown error'
                
                is_auth_error = result.get('auth_error', False)
                
                with get_tenant_db(self.tenant_schema) as db:
                    if is_auth_error:
                        self._log_execution(db, context['execution_id'], context.get('current_node_id'), "error",
                                          f"{service_type} authentication failed: {error_msg}",
                                          {"result": mask_sensitive_data(result), "auth_error": True})
                    else:
                        self._log_execution(db, context['execution_id'], context.get('current_node_id'), "error",
                                          f"{service_type} failed: {error_msg}",
                                          {"result": mask_sensitive_data(result), "parameters": mask_sensitive_data(mapped_params)})
                
                # Structured error so the node's error policy can classify it
                # (status code, auth) for retries and error branches
                result_status = result.get('status_code', result.get('status'))
                result_status = result_status if isinstance(result_status, int) else None
                if is_auth_error:
                    raise ServiceExecutionError(
                        f"{service_type} authentication failed. Please check your credentials.",
                        error_type='auth', status_code=result_status,
                        response=result.get('response', result.get('data')))
                else:
                    raise ServiceExecutionError(
                        f"{service_type} execution failed: {error_msg}",
                        status_code=result_status,
                        response=result.get('response', result.get('data')))
            
            # Log successful execution
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], context.get('current_node_id'), "info",
                                  f"{service_type} completed successfully",
                                  {"result": result}, context)
            
            return result
            
        except Exception as e:
            logger.error(f"Service execution failed: {str(e)}", exc_info=True)
            
            # Create detailed error information
            error_details = {
                "error": str(e),
                "error_type": type(e).__name__,
                "parameters": mask_sensitive_data(mapped_params),
                "service_type": service_type,
                "service_config": mask_sensitive_data(service_config) if service_config else None,
            }
            
            # Add additional context if available
            if hasattr(e, '__cause__') and e.__cause__:
                error_details["cause"] = str(e.__cause__)
                error_details["cause_type"] = type(e.__cause__).__name__
            
            with get_tenant_db(self.tenant_schema) as db:
                self._log_execution(db, context['execution_id'], context.get('current_node_id'), "error",
                                  f"{service_type} execution failed: {str(e)}",
                                  error_details)
            raise
    
    async def close(self):
        """No-op kept for backward compatibility: the HTTP client is shared
        across all engine instances, so closing it here would break every
        other in-flight execution. The shared pool lives for the process."""
        pass
    
    async def _send_status_notification(self, execution_id: str, status_data: dict):
        """Send execution status update via WebSocket."""
        event_type = status_data.get('type', 'unknown')
        logger.debug(f"Sending {event_type} notification for execution {execution_id} to tenant {self.tenant_id}")
        try:
            await ws_manager.send_execution_update(
                execution_id=execution_id,
                tenant_id=self.tenant_id,
                update_data=status_data
            )
            logger.debug(f"✓ {event_type} notification sent successfully")
        except Exception as e:
            logger.error(f"✗ Failed to send {event_type} WebSocket notification: {e}")
    
    async def _send_log_notification(self, execution_id: str, log_data: dict):
        """Send execution log entry via WebSocket."""
        try:
            await ws_manager.send_execution_log(
                execution_id=execution_id,
                tenant_id=self.tenant_id,
                log_entry=log_data
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket log notification: {e}")
    
    async def _send_progress_notification(self, execution_id: str, progress_data: dict):
        """Send execution progress update via WebSocket."""
        try:
            await ws_manager.send_execution_progress(
                execution_id=execution_id,
                tenant_id=self.tenant_id,
                progress_data=progress_data
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket progress notification: {e}")
    
    async def _send_debug_event(self, execution_id: str, event_data: dict):
        """Send debug event via WebSocket."""
        try:
            # Send as a special type of execution update
            await ws_manager.send_execution_update(
                execution_id=execution_id,
                tenant_id=self.tenant_id,
                update_data=event_data
            )
        except Exception as e:
            logger.error(f"Failed to send debug event: {e}")
    
    async def _wait_for_debug_step(self, execution_id: str, node_id: str):
        """Wait for user to continue in debug step mode."""
        logger.info(f"[DEBUG_WAIT] Starting wait for node: {node_id}, execution: {execution_id}")
        
        # Check if session exists
        if not debug_coordinator.session_exists(execution_id):
            logger.warning(f"[DEBUG_WAIT] No session exists for {execution_id}, creating one")
            debug_coordinator.create_session(execution_id)
        
        # Send waiting event
        logger.info(f"[DEBUG_WAIT] Sending waiting_for_step event for node {node_id}")
        await self._send_debug_event(execution_id, {
            'type': 'waiting_for_step',
            'node_id': node_id
        })
        
        # Wait for continue signal
        logger.info(f"[DEBUG_WAIT] Calling wait_for_continue for {execution_id}")
        success = await debug_coordinator.wait_for_continue(execution_id)
        
        if success:
            logger.info(f"[DEBUG_WAIT] Step continue received for node {node_id}")
        else:
            logger.error(f"[DEBUG_WAIT] Failed to receive step signal for node {node_id}")
            raise Exception("Debug step failed")
    
    def _get_flow_from_db(self, flow_id: str):
        """Get flow from database."""
        try:
            with get_tenant_db(self.tenant_schema) as db:
                flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
                return flow
        except Exception as e:
            logger.error(f"Failed to get flow {flow_id} from database: {e}")
            return None
    
    async def _get_event_configuration_for_flow(self, db, flow) -> Optional[Dict[str, Any]]:
        """Get event configuration for unified parameter extraction from output_schema for ALL event types."""
        if not flow or not flow.trigger_config:
            return None
            
        trigger_config = flow.trigger_config
        
        # Handle different trigger types
        if trigger_config.get('type') == 'event':
            # Application event trigger - get from application_events table
            app_id = trigger_config.get('app_id')
            event_id = trigger_config.get('event_id')
            event_name = trigger_config.get('event_name')
            
            if not app_id:
                return None
            
            # Support both event_id and event_name for backward compatibility
            if not event_id and not event_name:
                return None
                
            try:
                from db.application_models import ApplicationEvent
                
                # First try to query by event_id if available
                event = None
                if event_id:
                    event = db.query(ApplicationEvent).filter(
                        ApplicationEvent.app_id == app_id,
                        ApplicationEvent.event_id == event_id
                    ).first()
                
                # If not found by event_id (or event_id not provided), try by event_name
                if not event and event_name:
                    event = db.query(ApplicationEvent).filter(
                        ApplicationEvent.app_id == app_id,
                        ApplicationEvent.event_name == event_name
                    ).first()
                
                if event and event.output_schema:
                    if isinstance(event.output_schema, str):
                        import json
                        return json.loads(event.output_schema)
                    return event.output_schema
                    
            except Exception as e:
                logger.warning(f"Failed to get event configuration: {e}")
        
        elif trigger_config.get('type') == 'manual':
            # Manual trigger - construct schema from manual_variables
            manual_variables = trigger_config.get('manual_variables', [])
            if manual_variables:
                properties = {}
                required = []
                
                for var in manual_variables:
                    var_name = var.get('name')
                    var_type = var.get('type', 'string')
                    var_description = var.get('description', '')
                    var_required = var.get('required', False)
                    
                    if var_name:
                        properties[var_name] = {
                            'type': var_type,
                            'description': var_description
                        }
                        if var_required:
                            required.append(var_name)
                
                return {
                    'type': 'object',
                    'properties': properties,
                    'required': required
                }
        
        elif trigger_config.get('type') in ['webhook', 'api_call']:
            # Webhook/API call - use manual_variables if available, otherwise generic schema
            manual_variables = trigger_config.get('manual_variables', [])
            if manual_variables:
                properties = {}
                mappings = {}
                required = []
                
                for var in manual_variables:
                    var_name = var.get('name')
                    var_type = var.get('type', 'string')
                    var_description = var.get('description', '')
                    var_required = var.get('required', False)
                    
                    if var_name:
                        properties[var_name] = {
                            'type': var_type,
                            'description': var_description
                        }
                        if var_required:
                            required.append(var_name)
                        
                        # Extract JSONPath from description for parameter extraction
                        if 'extracted from $' in var_description:
                            try:
                                json_path = var_description.split('extracted from $')[1].strip()
                                if json_path.startswith('.'):
                                    json_path = json_path[1:]  # Remove leading dot
                                mappings[var_name] = json_path
                            except:
                                pass
                
                schema = {
                    'type': 'object',
                    'properties': properties,
                    'required': required
                }
                
                # Add parameter extraction if we have mappings
                if mappings:
                    schema['parameter_extraction'] = {
                        'method': 'json_path',
                        'mappings': mappings
                    }
                
                return schema
            
        return None
    
    async def _extract_parameters_unified(self, webhook_data: Dict[str, Any], 
                                        event_config: Dict[str, Any], 
                                        execution_id: str) -> Dict[str, Any]:
        """Extract parameters using unified output_schema approach."""
        variables = {}
        
        # Handle None event_config
        if not event_config:
            event_config = {}
        
        # Get parameter extraction configuration
        param_extraction = event_config.get('parameter_extraction', {})
        if not param_extraction:
            param_extraction = {}
        
        method = param_extraction.get('method', 'json_path')
        mappings = param_extraction.get('mappings', {})
        if mappings is None:
            mappings = {}
        
        with get_tenant_db(self.tenant_schema) as db:
            self._log_execution(db, execution_id, None, "debug",
                              f"Using unified parameter extraction",
                              {"method": method, "mappings": mappings})
        
        # Extract based on mappings
        if mappings:
            for var_name, mapping_path in mappings.items():
                try:
                    if method == 'json_path':
                        value = self._extract_json_path_value(webhook_data, mapping_path)
                    elif method == 'form_data':
                        # Handle form data extraction
                        value = webhook_data.get(mapping_path)
                    elif method == 'query_params':
                        # Handle query parameter extraction
                        query_params = webhook_data.get('query_params', {})
                        value = query_params.get(mapping_path)
                    else:
                        # Default to simple key lookup
                        value = webhook_data.get(mapping_path)
                        
                    if value is not None:
                        variables[var_name] = value
                        
                except Exception as e:
                    logger.warning(f"Failed to extract parameter {var_name} using path {mapping_path}: {e}")
        
        # Also include properties defined in schema
        properties = event_config.get('properties', {})
        if properties is None:
            properties = {}
        
        if properties:
            for prop_name, prop_def in properties.items():
                if prop_def and isinstance(prop_def, dict) and prop_name not in variables and 'mapping' in prop_def:
                    try:
                        mapping_path = prop_def['mapping']
                        value = self._extract_json_path_value(webhook_data, mapping_path)
                        if value is not None:
                            variables[prop_name] = value
                    except Exception as e:
                        logger.warning(f"Failed to extract property {prop_name}: {e}")
        
        # Store the original webhook_data separately for access if needed
        variables['_webhook_data'] = webhook_data
        
        return variables
    
    async def _extract_parameters_legacy(self, webhook_data: Dict[str, Any], 
                                       trigger_config: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy parameter extraction for backward compatibility."""
        variables = {}
        # Handle both naming conventions: manual_variables (snake_case) and manualVariables (camelCase)
        manual_variables = trigger_config.get('manual_variables', trigger_config.get('manualVariables', []))
        
        # Ensure manual_variables is not None
        if manual_variables is None:
            manual_variables = []
        
        # Extract variables based on their JSONPath expressions
        for var_config in manual_variables:
            var_name = var_config.get('name')
            var_description = var_config.get('description', '')
            
            if var_name and 'extracted from $' in var_description:
                # Extract the JSONPath from description like "extracted from $.text.body"
                try:
                    json_path = var_description.split('extracted from $')[1].strip()
                    if json_path.startswith('.'):
                        json_path = json_path[1:]  # Remove leading dot
                    
                    # Navigate the path in webhook_data
                    value = self._extract_json_path_value(webhook_data, json_path)
                    if value is not None:
                        variables[var_name] = value
                        
                except Exception as e:
                    logger.warning(f"Failed to extract variable {var_name}: {e}")
                    
        # Also include the entire webhook_data for backward compatibility
        variables.update(webhook_data)
        
        return variables

    def _extract_json_path_value(self, data: Dict[str, Any], path: str) -> Any:
        """Extract value from nested dict using JSONPath notation like '$.text.body' or dot notation 'text.body'."""
        try:
            # Handle JSONPath format ($.) and root reference ($)
            if path == '$':
                return data
            elif path.startswith('$.'):
                # Remove the $. prefix for JSONPath format
                path = path[2:]
            elif path.startswith('$'):
                # Handle just $ prefix
                path = path[1:]
                
            # If path is empty after removing $, return the whole data
            if not path:
                return data
            
            current = data
            segments = path.split('.')
            
            for segment in segments:
                if isinstance(current, dict) and segment in current:
                    current = current[segment]
                else:
                    return None
                    
            return current
        except Exception as e:
            logger.warning(f"Failed to extract path '{path}' from data: {e}")
            return None
    
    def _interpolate_template_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        Interpolate template variables in a string.
        
        Replaces {{variable.path}} with actual values from context.
        Supports mixed content like "Hello {{input.name}}, your score is {{data.score}}!"
        """
        import re
        
        if not isinstance(template_string, str):
            return template_string
        
        # Pattern to match template variables: {{variable.path}}
        pattern = r'\{\{([^}]+)\}\}'
        
        def replace_template(match):
            """Replace each template variable with its resolved value."""
            variable_path = match.group(1).strip()
            logger.debug(f"Resolving template variable: {variable_path}")
            
            try:
                # Get the value using the existing field resolution logic
                resolved_value = self._get_field_value(variable_path, context)
                
                if resolved_value is None:
                    logger.warning(f"Template variable '{variable_path}' resolved to None")
                    return f"{{{{ {variable_path} }}}}"  # Return original if not found
                
                # Convert to string for interpolation
                if isinstance(resolved_value, (dict, list)):
                    import json
                    return json.dumps(resolved_value)
                else:
                    return str(resolved_value)
                    
            except Exception as e:
                logger.error(f"Error resolving template variable '{variable_path}': {e}")
                return f"{{{{ {variable_path} }}}}"  # Return original if error
        
        # Replace all template variables in the string
        try:
            result = re.sub(pattern, replace_template, template_string)
            logger.debug(f"Template interpolation: '{template_string}' -> '{result}'")
            return result
        except Exception as e:
            logger.error(f"Error during template interpolation: {e}")
            return template_string  # Return original string if interpolation fails