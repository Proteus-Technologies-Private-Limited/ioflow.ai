"""
Debug Execution Manager - State-based debug execution
Each node execution completes and persists state, client triggers next step
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from db.database import get_tenant_db
from services.execution_engine import ExecutionEngine

# Import models - PostgreSQL Only
from db.models import Flow, FlowExecution, ExecutionStatus, ExecutionLog

logger = logging.getLogger(__name__)

class DebugExecutionManager:
    """Manages state-based debug execution"""
    
    @staticmethod
    def get_debug_state(tenant_schema: str, execution_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get the current debug state for an execution"""
        with get_tenant_db(tenant_schema) as db:
            query = db.query(FlowExecution).join(Flow).filter(
                FlowExecution.execution_id == execution_id
            )
            
            # Add tenant filter if tenant_id is provided (for SQLite mode)
            if tenant_id:
                query = query.filter(Flow.tenant_id == tenant_id)
            
            execution = query.first()
            
            if not execution:
                return None
                
            execution_data = execution.execution_data or {}
            debug_state = execution_data.get('debug_state')
            
            # Ensure we have the debug state
            if not debug_state:
                return None
            
            # Log what we retrieved
            logger.info(f"Retrieved debug_state with keys: {list(debug_state.keys())}")
            if 'context' in debug_state:
                logger.info(f"Retrieved context with keys: {list(debug_state.get('context', {}).keys())}")
                if 'global_vars' in debug_state.get('context', {}):
                    logger.info(f"Retrieved context global_vars: {debug_state['context']['global_vars']}")
            
            # The issue: SQLite JSON might not preserve types correctly
            # Apply type preservation to restore numeric types
            debug_state = DebugExecutionManager._preserve_types(debug_state)
            return debug_state
    
    @staticmethod
    def _preserve_types(data: Any) -> Any:
        """Recursively preserve numeric types in data structure."""
        if isinstance(data, dict):
            return {k: DebugExecutionManager._preserve_types(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [DebugExecutionManager._preserve_types(item) for item in data]
        # Don't auto-convert strings - this could break actual string data
        # The real fix is to ensure data is stored with correct types initially
        else:
            return data
    
    @staticmethod
    def _sanitize_for_json(obj: Any, path: str = "root", seen: set = None) -> Any:
        """Recursively sanitize an object to make it JSON serializable."""
        import types
        import json
        
        # Initialize seen set for circular reference detection
        if seen is None:
            seen = set()
        
        # Check if it's a primitive type that's already JSON serializable
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        
        # Check for circular references
        obj_id = id(obj)
        if obj_id in seen:
            return "<Circular reference>"
        
        # Check if it's a module or function
        if isinstance(obj, (types.ModuleType, types.FunctionType, types.MethodType, 
                          types.BuiltinFunctionType, types.BuiltinMethodType)):
            logger.warning(f"Found non-serializable {type(obj).__name__} at path {path}, replacing with string representation")
            return f"<{type(obj).__name__}: {str(obj)[:50]}>"
        
        # Add to seen set for circular reference detection
        seen.add(obj_id)
        
        try:
            # Handle dictionaries
            if isinstance(obj, dict):
                sanitized = {}
                for key, value in obj.items():
                    try:
                        sanitized_key = str(key) if not isinstance(key, str) else key
                        sanitized[sanitized_key] = DebugExecutionManager._sanitize_for_json(value, f"{path}.{key}", seen)
                    except Exception as e:
                        logger.warning(f"Error sanitizing key {key} at path {path}: {e}")
                        sanitized[str(key)] = f"<Error sanitizing: {str(e)[:50]}>"
                return sanitized
        
            # Handle lists and tuples
            if isinstance(obj, (list, tuple)):
                sanitized_list = []
                for i, item in enumerate(obj):
                    try:
                        sanitized_list.append(DebugExecutionManager._sanitize_for_json(item, f"{path}[{i}]", seen))
                    except Exception as e:
                        logger.warning(f"Error sanitizing item {i} at path {path}: {e}")
                        sanitized_list.append(f"<Error sanitizing: {str(e)[:50]}>")
                return sanitized_list
            
            # Handle sets
            if isinstance(obj, set):
                return list(DebugExecutionManager._sanitize_for_json(list(obj), path, seen))
            
            # Try to serialize to check if it's already serializable
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                # For other objects, try to convert to dict or string
                try:
                    if hasattr(obj, '__dict__'):
                        return DebugExecutionManager._sanitize_for_json(obj.__dict__, f"{path}.__dict__", seen)
                    else:
                        logger.warning(f"Non-serializable object {type(obj).__name__} at path {path}, converting to string")
                        return str(obj)[:100]
                except Exception as e:
                    logger.warning(f"Failed to sanitize object at path {path}: {e}")
                    return f"<Non-serializable {type(obj).__name__}>"
        finally:
            # Remove from seen set when done processing this object
            seen.discard(obj_id)
    
    @staticmethod
    def save_debug_state(tenant_schema: str, execution_id: str, state: Dict[str, Any], tenant_id: str = None):
        """Save debug state to database"""
        # Log what we're about to save
        logger.info(f"Saving debug state with keys: {list(state.keys())}")
        if 'context' in state:
            logger.info(f"Debug state has context with keys: {list(state.get('context', {}).keys())}")
            if 'global_vars' in state.get('context', {}):
                logger.info(f"Context has global_vars: {state['context']['global_vars']}")
        
        # Sanitize the state before saving
        try:
            sanitized_state = DebugExecutionManager._sanitize_for_json(state)
            # Log after sanitization too
            logger.info(f"After sanitization, state has keys: {list(sanitized_state.keys())}")
            if 'context' in sanitized_state:
                logger.info(f"Sanitized context has keys: {list(sanitized_state.get('context', {}).keys())}")
                if 'global_vars' in sanitized_state.get('context', {}):
                    logger.info(f"Sanitized context global_vars: {sanitized_state['context']['global_vars']}")
        except Exception as e:
            logger.error(f"Failed to sanitize debug state: {e}")
            # Try to at least save basic info
            sanitized_state = {
                'execution_id': execution_id,
                'error': f'Failed to sanitize state: {str(e)}',
                'current_node': state.get('current_node'),
                'status': state.get('status', 'error')
            }
        
        with get_tenant_db(tenant_schema) as db:
            query = db.query(FlowExecution).join(Flow).filter(
                FlowExecution.execution_id == execution_id
            )
            
            # Add tenant filter if tenant_id is provided (for SQLite mode)
            if tenant_id:
                query = query.filter(Flow.tenant_id == tenant_id)
            
            execution = query.first()
            
            if not execution:
                logger.error(f"Execution {execution_id} not found")
                return False
            
            # Update execution data
            execution_data = execution.execution_data or {}
            execution_data['debug_state'] = sanitized_state
            execution.execution_data = execution_data
            
            # Mark as modified for SQLite
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(execution, 'execution_data')
            
            db.commit()
            logger.info(f"Saved debug state for execution {execution_id}")
            return True
    
    @staticmethod
    def ensure_debug_session(execution_id: str):
        """Ensure a debug session exists in the coordinator"""
        from services.debug_coordinator import debug_coordinator
        if not debug_coordinator.session_exists(execution_id):
            logger.info(f"Creating debug session for execution {execution_id}")
            debug_coordinator.create_session(execution_id)
    
    @staticmethod
    async def step_transform_line(
        tenant_schema: str,
        tenant_id: str,
        execution_id: str,
        node_id: str
    ) -> Dict[str, Any]:
        """Execute one line in transform debug mode"""
        # Try to use the full transform debugger first, fall back to simple if not available
        try:
            from services.transform_debugger import transform_debugger as full_debugger
            # Check if session exists in full debugger
            session_key = f"{execution_id}_{node_id}"
            if session_key in full_debugger.debug_sessions:
                # Use full debugger
                from services.websocket_manager import manager as ws_manager
                debug_info = full_debugger.step_into(execution_id, node_id)
                # Map the output format to match expected format
                if 'status' in debug_info:
                    debug_info['is_complete'] = debug_info.get('status') == 'completed'
                    debug_info['is_stepping'] = debug_info.get('status') != 'completed'
            else:
                # Fall back to simple debugger
                from services.transform_debugger_simple import simple_transform_debugger as transform_debugger
                from services.websocket_manager import manager as ws_manager
                debug_info = transform_debugger.step_line(execution_id, node_id)
        except ImportError:
            # If full debugger not available, use simple
            from services.transform_debugger_simple import simple_transform_debugger as transform_debugger
            from services.websocket_manager import manager as ws_manager
            debug_info = transform_debugger.step_line(execution_id, node_id)
        
        # Send update to frontend
        await ws_manager.send_execution_update(
            execution_id=execution_id,
            tenant_id=tenant_id,
            update_data={
                'type': 'transform_debug_step',
                'node_id': node_id,
                'debug_info': debug_info
            }
        )
        
        # If transform is complete, continue with normal flow
        if debug_info['is_complete']:
            # Determine which debugger was used and get output accordingly
            output = {}
            final_variables = {}
            
            try:
                # Try full debugger first
                from services.transform_debugger import transform_debugger as full_debugger
                session_key = f"{execution_id}_{node_id}"
                if session_key in full_debugger.debug_sessions:
                    # Get output from full debugger  
                    state = full_debugger.debug_sessions[session_key]
                    output = state.execution_globals.get('output', {})
                    # Get variables including global updates
                    # Check if variable_manager was used (preferred) or fallback to global dict
                    global_vars_from_transform = {}
                    
                    # The variable_manager is passed in exec_globals when we create the debug session
                    if 'variable_manager' in state.execution_globals:
                        # Get global vars from the variable_manager
                        vm = state.execution_globals['variable_manager']
                        global_vars_from_transform = vm.global_vars.copy()
                        logger.info(f"Transform debugger global vars from variable_manager: {global_vars_from_transform}")
                        logger.info(f"Variable manager has these globals: {list(vm.global_vars.keys())}")
                    else:
                        # Fallback to global dict (when variable_manager not available)
                        global_vars_from_transform = state.execution_globals.get('global', {})
                        logger.info(f"Transform debugger global vars from global dict (fallback): {global_vars_from_transform}")
                        logger.warning("Variable manager not found in execution_globals, using fallback")
                    
                    final_variables = {
                        'input': state.execution_globals.get('input', {}),
                        'global': global_vars_from_transform,
                        'local': state.execution_locals,
                        'output': output,
                        'node_outputs': state.execution_globals.get('node_outputs', {})
                    }
                    # Clean up session
                    full_debugger.cleanup_session(execution_id, node_id)
                else:
                    # Use simple debugger
                    from services.transform_debugger_simple import simple_transform_debugger
                    output = simple_transform_debugger.end_session(execution_id, node_id) 
                    final_variables = simple_transform_debugger.get_variables(execution_id, node_id)
            except ImportError:
                # Fall back to simple debugger
                from services.transform_debugger_simple import simple_transform_debugger
                output = simple_transform_debugger.end_session(execution_id, node_id)
                final_variables = simple_transform_debugger.get_variables(execution_id, node_id)
            
            # Update debug state
            debug_state = DebugExecutionManager.get_debug_state(tenant_schema, execution_id, tenant_id)
            if debug_state:
                debug_state['transform_debug'] = None
                debug_state['node_outputs'][node_id] = output
                
                # CRITICAL: Update global_vars with any changes made in the transform
                # Save directly in debug_state, not in a nested 'context' structure
                if 'global' in final_variables and final_variables['global']:
                    if 'global_vars' not in debug_state:
                        debug_state['global_vars'] = {}
                    # Merge the global variables from transform debugger
                    debug_state['global_vars'].update(final_variables['global'])
                    logger.info(f"Updated debug_state global_vars after transform debug: {debug_state['global_vars']}")
                    logger.info(f"Transform set these global vars: {list(final_variables['global'].keys())}")
                    logger.info(f"Debug state keys after adding global_vars: {list(debug_state.keys())}")
                else:
                    logger.warning(f"No global variables found in transform debug output. final_variables keys: {list(final_variables.keys())}")
                    if 'global' in final_variables:
                        logger.warning(f"final_variables['global'] is empty or None: {final_variables['global']}")
                
                if node_id not in debug_state['executed_nodes']:
                    debug_state['executed_nodes'].append(node_id)
                
                # Find next node
                flow_definition = debug_state['flow_definition']
                edges = flow_definition.get('edges', [])
                next_nodes = []
                for edge in edges:
                    if edge['source'] == node_id:
                        next_nodes.append(edge['target'])
                
                if next_nodes:
                    debug_state['current_node'] = next_nodes[0]
                    debug_state['status'] = 'waiting_for_step'
                else:
                    debug_state['status'] = 'completed'
                    debug_state['current_node'] = None
                
                DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
                
                # Send transform complete event
                await ws_manager.send_execution_update(
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    update_data={
                        'type': 'transform_debug_complete',
                        'node_id': node_id,
                        'output': output,
                        'next_node': debug_state.get('current_node')
                    }
                )
        
        return debug_info
    
    @staticmethod
    async def continue_transform(
        tenant_schema: str,
        tenant_id: str,
        execution_id: str,
        node_id: str
    ) -> Dict[str, Any]:
        """Continue transform execution to completion"""
        from services.websocket_manager import manager as ws_manager
        
        # Determine which debugger to use
        try:
            from services.transform_debugger import transform_debugger as full_debugger
            session_key = f"{execution_id}_{node_id}"
            if session_key in full_debugger.debug_sessions:
                # Use full debugger - execute all remaining lines
                debug_info = None
                while True:
                    debug_info = full_debugger.step_into(execution_id, node_id)
                    if debug_info.get('status') == 'completed' or debug_info.get('status') == 'error':
                        break
                # Map the output format
                debug_info['is_complete'] = debug_info.get('status') == 'completed'
                debug_info['is_stepping'] = False
                
                # CRITICAL: Extract global variables BEFORE any cleanup happens
                if debug_info['is_complete']:
                    logger.info(f"Transform completed via continue - extracting global vars BEFORE cleanup")
                    state = full_debugger.debug_sessions.get(session_key)
                    if state:
                        # Extract global variables that were set during transform
                        global_vars_from_transform = {}
                        if 'variable_manager' in state.execution_globals:
                            vm = state.execution_globals['variable_manager']
                            global_vars_from_transform = vm.global_vars.copy()
                            logger.info(f"Extracted global vars from variable_manager before cleanup: {list(global_vars_from_transform.keys())}")
                        else:
                            global_vars_from_transform = state.execution_globals.get('global', {})
                            logger.info(f"Extracted global vars from global dict before cleanup: {list(global_vars_from_transform.keys())}")
                        
                        # Save to debug state immediately
                        if global_vars_from_transform:
                            debug_state = DebugExecutionManager.get_debug_state(tenant_schema, execution_id, tenant_id)
                            if debug_state:
                                if 'global_vars' not in debug_state:
                                    debug_state['global_vars'] = {}
                                debug_state['global_vars'].update(global_vars_from_transform)
                                logger.info(f"Saved global_vars to debug state: {debug_state['global_vars']}")
                                DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
            else:
                # Use simple debugger
                from services.transform_debugger_simple import simple_transform_debugger as transform_debugger
                debug_info = transform_debugger.continue_execution(execution_id, node_id)
                
                # Extract and save global vars from simple debugger if complete
                if debug_info.get('is_complete'):
                    final_variables = transform_debugger.get_variables(execution_id, node_id)
                    if 'global' in final_variables and final_variables['global']:
                        debug_state = DebugExecutionManager.get_debug_state(tenant_schema, execution_id, tenant_id)
                        if debug_state:
                            if 'global_vars' not in debug_state:
                                debug_state['global_vars'] = {}
                            debug_state['global_vars'].update(final_variables['global'])
                            logger.info(f"Saved global_vars from simple debugger: {debug_state['global_vars']}")
                            DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
        except ImportError:
            # Fall back to simple debugger
            from services.transform_debugger_simple import simple_transform_debugger as transform_debugger
            debug_info = transform_debugger.continue_execution(execution_id, node_id)
            
            # Extract and save global vars from simple debugger if complete
            if debug_info.get('is_complete'):
                final_variables = transform_debugger.get_variables(execution_id, node_id)
                if 'global' in final_variables and final_variables['global']:
                    debug_state = DebugExecutionManager.get_debug_state(tenant_schema, execution_id, tenant_id)
                    if debug_state:
                        if 'global_vars' not in debug_state:
                            debug_state['global_vars'] = {}
                        debug_state['global_vars'].update(final_variables['global'])
                        logger.info(f"Saved global_vars from simple debugger (fallback): {debug_state['global_vars']}")
                        DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
        
        # Send update to frontend
        await ws_manager.send_execution_update(
            execution_id=execution_id,
            tenant_id=tenant_id,
            update_data={
                'type': 'transform_debug_continue',
                'node_id': node_id,
                'debug_info': debug_info
            }
        )
        
        # If complete, handle like step completion
        if debug_info['is_complete']:
            return await DebugExecutionManager.step_transform_line(
                tenant_schema, tenant_id, execution_id, node_id
            )
        
        return debug_info
    
    @staticmethod
    async def set_transform_breakpoint(
        execution_id: str,
        node_id: str,
        line_number: int
    ) -> bool:
        """Set a breakpoint in transform code"""
        from services.transform_debugger_simple import simple_transform_debugger as transform_debugger
        return transform_debugger.set_breakpoint(execution_id, node_id, line_number)
    
    @staticmethod
    async def clear_transform_breakpoint(
        execution_id: str,
        node_id: str,
        line_number: int
    ) -> bool:
        """Clear a breakpoint in transform code"""
        from services.transform_debugger_simple import simple_transform_debugger as transform_debugger
        return transform_debugger.clear_breakpoint(execution_id, node_id, line_number)
    
    @staticmethod
    async def start_debug_execution(
        tenant_schema: str,
        tenant_id: str,
        flow_id: str, 
        execution_id: str,
        trigger_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start a debug execution and execute first node (trigger)"""
        
        # Get flow definition
        with get_tenant_db(tenant_schema) as db:
            flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
            if not flow:
                raise ValueError(f"Flow {flow_id} not found")
            
            flow_definition = flow.flow_definition
            
        # Find trigger node
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        trigger_node = None
        for node in nodes:
            if node['type'] == 'trigger':
                trigger_node = node
                break
        
        if not trigger_node:
            raise ValueError("No trigger node found in flow")
        
        # Initialize debug state with full context
        # Extract the actual variable values from trigger_data
        # The trigger_data may contain variables in different formats:
        # 1. Direct variables: {var1: value1, var2: value2} (from API)
        # 2. Nested: {variables: {var1: value1, var2: value2}} (from frontend)
        
        # Check if 'variables' is a nested key or if trigger_data itself contains the variables
        if 'variables' in trigger_data and isinstance(trigger_data['variables'], dict):
            # Frontend format: {variables: {...}}
            variables = trigger_data['variables']
        else:
            # API format: direct variables, but exclude system fields
            system_fields = {'trigger_type', 'triggered_by', 'timestamp', 'debug_mode', 'debug_step_mode'}
            variables = {k: v for k, v in trigger_data.items() if k not in system_fields}
        
        # Now also check if the trigger node defines variables and merge with defaults
        trigger_node_variables = trigger_node.get('data', {}).get('variables', {})
        if trigger_node_variables:
            # For each variable defined in the trigger node, ensure it exists in variables
            for var_name, var_config in trigger_node_variables.items():
                if var_name not in variables:
                    # Use the default value if specified, otherwise use None
                    default_value = var_config.get('default', None)
                    variables[var_name] = default_value
                    logger.info(f"Added default value for variable '{var_name}': {default_value}")
        
        logger.info(f"Debug start - trigger_data: {trigger_data}")
        logger.info(f"Debug start - trigger node variables: {trigger_node_variables}")
        logger.info(f"Debug start - final variables: {variables}")
        
        debug_state = {
            'flow_id': flow_id,
            'execution_id': execution_id,
            'current_node': trigger_node['id'],
            'executed_nodes': [],
            'node_outputs': {},  # Will store outputs from ALL executed nodes
            'variables': variables,  # Global variables accessible to all nodes
            'flow_definition': flow_definition,
            'status': 'running',
            'created_at': datetime.utcnow().isoformat(),
            # Store the variables as context data (this is what gets passed to nodes)
            'context_data': variables,  # This is the 'data' that flows between nodes
            'trigger_data': trigger_data,  # Keep original trigger data for reference
            'loop_state': {},  # Track state of each loop node
            'pending_branches': [],  # Fork-join: [[source_node, branch_node], ...] not yet stepped
            'completed_nodes': [],  # Fork-join: all completed node IDs for merge sync
        }
        
        # Execute trigger node (passes the variables through)
        # The trigger node output becomes the initial data
        trigger_output = variables  # Pass variables as the initial data
        debug_state['node_outputs'][trigger_node['id']] = trigger_output
        debug_state['executed_nodes'].append(trigger_node['id'])
        
        # Log trigger execution (matching manual trigger format)
        with get_tenant_db(tenant_schema) as db:
            # Log trigger start
            trigger_log = ExecutionLog(
                execution_id=execution_id,
                step_id=trigger_node['id'],
                level='info',
                message=f"Executing trigger node: {trigger_node.get('data', {}).get('label', 'Manual Trigger')}",
                data={'node_type': 'trigger', 'trigger_data': trigger_output}
            )
            db.add(trigger_log)
            
            # Log trigger completion
            completion_log = ExecutionLog(
                execution_id=execution_id,
                step_id=trigger_node['id'],
                level='info',
                message=f"Trigger node completed successfully",
                data={'node_type': 'trigger', 'output': trigger_output}
            )
            db.add(completion_log)
            db.commit()
        
        logger.info(f"Trigger node {trigger_node['id']} output stored: {trigger_output}")
        
        # Send trigger completion event via WebSocket
        from services.websocket_manager import manager as ws_manager
        await ws_manager.send_execution_update(
            execution_id=execution_id,
            tenant_id=tenant_id,
            update_data={
                'type': 'node_complete',
                'node_id': trigger_node['id'],
                'node_type': 'trigger',
                'node_label': trigger_node.get('data', {}).get('label', 'Manual Trigger'),
                'result': trigger_output,
                'variables': {
                    'output': trigger_output
                }
            }
        )
        
        # Find next node
        next_nodes = []
        logger.info(f"Looking for edges from trigger node {trigger_node['id']}")
        logger.info(f"Available edges: {edges}")
        for edge in edges:
            if edge['source'] == trigger_node['id']:
                logger.info(f"Found edge from trigger to {edge['target']}")
                for node in nodes:
                    if node['id'] == edge['target']:
                        next_nodes.append(node['id'])
                        logger.info(f"Added next node: {node['id']}")
                        break
        
        logger.info(f"Next nodes after trigger: {next_nodes}")
        if next_nodes:
            debug_state['current_node'] = next_nodes[0]  # Take first for now
            debug_state['status'] = 'waiting_for_step'
            logger.info(f"Set current_node to: {debug_state['current_node']}")
        else:
            debug_state['status'] = 'completed'
            logger.info("No next nodes found - flow completed")
        
        # Save state
        DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
        
        # Ensure debug coordinator session exists
        DebugExecutionManager.ensure_debug_session(execution_id)
        
        # Send WebSocket notification
        from services.websocket_manager import manager as ws_manager
        next_node_id = debug_state.get('current_node')
        
        # Find the next node's label for better UX
        next_node_label = None
        if next_node_id:
            for node in nodes:
                if node['id'] == next_node_id:
                    next_node_label = node.get('data', {}).get('label', next_node_id)
                    break
        
        logger.info(f"Sending waiting_for_step WebSocket event with node_id: {next_node_id}, label: {next_node_label}")
        
        # Include current state of all variables with enhanced node outputs
        current_variables = {
            'input': DebugExecutionManager._sanitize_for_json(debug_state.get('variables', {})),
            'global': DebugExecutionManager._sanitize_for_json(debug_state.get('global_vars', {})),
            'all_node_outputs': DebugExecutionManager._sanitize_for_json(debug_state.get('node_outputs', {})),  # Complete history of all node outputs
            'context_data': DebugExecutionManager._sanitize_for_json(debug_state.get('context_data', {})),
            'trigger_data': DebugExecutionManager._sanitize_for_json(debug_state.get('trigger_data', {})),
            'executed_nodes': debug_state.get('executed_nodes', []),
            'next_node': next_node_id,
            'next_node_label': next_node_label
        }
        
        # Log summary of node outputs
        logger.info(f"Debug state has outputs from {len(debug_state.get('node_outputs', {}))} nodes: {list(debug_state.get('node_outputs', {}).keys())}")
        
        await ws_manager.send_execution_update(
            execution_id=execution_id,
            tenant_id=tenant_id,
            update_data={
                'type': 'waiting_for_step',
                'node_id': next_node_id,
                'node_label': next_node_label,
                'executed_nodes': debug_state['executed_nodes'],
                'variables': current_variables
            }
        )
        
        return {
            'execution_id': execution_id,
            'status': debug_state['status'],
            'current_node': debug_state.get('current_node'),
            'executed_nodes': debug_state['executed_nodes']
        }
    
    @staticmethod
    async def execute_next_step(
        tenant_schema: str,
        tenant_id: str,
        execution_id: str
    ) -> Dict[str, Any]:
        """Execute the next node in debug execution"""
        
        # Get current state
        debug_state = DebugExecutionManager.get_debug_state(tenant_schema, execution_id, tenant_id)
        if not debug_state:
            raise ValueError(f"No debug state found for execution {execution_id}")
        
        if debug_state['status'] == 'completed':
            return {
                'execution_id': execution_id,
                'status': 'completed',
                'message': 'Execution already completed',
                'executed_nodes': debug_state.get('executed_nodes', []),
                'current_node': None
            }

        if debug_state['status'] == 'waiting_for_hitl':
            return {
                'execution_id': execution_id,
                'status': 'waiting_for_hitl',
                'message': 'Execution paused waiting for HITL task completion',
                'executed_nodes': debug_state.get('executed_nodes', []),
                'current_node': debug_state.get('current_node'),
                'hitl_task_id': debug_state.get('hitl_task_id')
            }
        
        current_node_id = debug_state.get('current_node')
        if not current_node_id:
            raise ValueError("No current node in debug state")
        
        # Find current node in flow definition
        flow_definition = debug_state['flow_definition']
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        current_node = None
        for node in nodes:
            if node['id'] == current_node_id:
                current_node = node
                break
        
        if not current_node:
            raise ValueError(f"Node {current_node_id} not found in flow")

        # Fork-join: Check if current node is a merge point (multiple incoming edges)
        # If not all incoming branches have completed, switch to next pending branch
        incoming_sources = [
            e['source'] for e in edges
            if e['target'] == current_node_id
            and e.get('targetHandle') != 'loop-back'
            and e.get('sourceHandle') not in ('loop-body', 'continue')
        ]
        if len(incoming_sources) > 1:
            completed_nodes = debug_state.get('completed_nodes', [])
            all_ready = all(src in completed_nodes for src in incoming_sources)
            if not all_ready:
                waiting_for = [src for src in incoming_sources if src not in completed_nodes]
                logger.info(f"Fork-join: Merge node {current_node_id} waiting for branches: {waiting_for}")
                # Switch to next pending branch if available
                pending_branches = debug_state.get('pending_branches', [])
                if pending_branches:
                    next_branch = pending_branches.pop(0)
                    debug_state['pending_branches'] = pending_branches
                    debug_state['current_node'] = next_branch[1]  # [source_node, branch_node]
                    debug_state['status'] = 'waiting_for_step'
                    DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)

                    from services.websocket_manager import manager as ws_manager
                    await ws_manager.send_execution_update(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'branch_switch',
                            'node_id': next_branch[1],
                            'message': f"Switching to branch: waiting for {len(waiting_for)} more branch(es) to complete before merge",
                            'pending_branches': len(pending_branches),
                        }
                    )
                    await ws_manager.send_execution_update(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'waiting_for_step',
                            'node_id': next_branch[1],
                            'executed_nodes': debug_state['executed_nodes'],
                        }
                    )
                    return {
                        'execution_id': execution_id,
                        'status': 'waiting_for_step',
                        'current_node': next_branch[1],
                        'executed_nodes': debug_state['executed_nodes'],
                        'message': f'Switched to next branch (merge node waiting for {len(waiting_for)} branch(es))'
                    }
                else:
                    # No more branches to execute — this shouldn't happen in a valid flow
                    logger.warning(f"Fork-join: Merge node {current_node_id} blocked but no pending branches")

        # Restore the COMPLETE context from the saved state
        # This ensures we have the exact same state as normal execution would have
        
        # Determine the input data for the current node
        # Find which node's output should be used as input to this node
        input_data = debug_state.get('context_data', {})

        # Collect all incoming edges to this node
        incoming_edges = [e for e in edges if e['target'] == current_node_id
                         and e.get('targetHandle') != 'loop-back']
        source_found = False

        if len(incoming_edges) > 1:
            # Merge node: merge outputs from all incoming branches
            merged_data = {}
            for i, edge in enumerate(incoming_edges):
                source_node_id = edge['source']
                if source_node_id in debug_state.get('node_outputs', {}):
                    branch_output = debug_state['node_outputs'][source_node_id]
                    if isinstance(branch_output, dict):
                        merged_data.update(branch_output)
                    merged_data[f'branch_{i}'] = branch_output
                    merged_data[f'branch_{source_node_id}'] = branch_output
            if merged_data:
                input_data = merged_data
                source_found = True
                logger.info(f"Fork-join: Merged {len(incoming_edges)} branch outputs for merge node {current_node_id}")
        else:
            # Single incoming edge: use source node's output
            for edge in incoming_edges:
                source_node_id = edge['source']
                if source_node_id in debug_state.get('node_outputs', {}):
                    input_data = debug_state['node_outputs'][source_node_id]
                    logger.info(f"Using output from node {source_node_id} as input for {current_node_id}")
                    logger.info(f"Input data: {json.dumps(input_data, default=str)[:200]}")
                    source_found = True
                    break

        if not source_found:
            logger.info(f"No source found for node {current_node_id}, using context_data")
        
        # 1. Start with base context
        context = {
            'execution_id': execution_id,
            'data': input_data,  # Use the determined input data
            'variables': debug_state.get('variables', {}),  # Global variables
            'node_outputs': {},  # Will be populated below
            'is_simulation': False,
            'tenant_schema': tenant_schema,
            'tenant_id': tenant_id
        }
        
        # CRITICAL: Restore global_vars from debug_state (set after transform debug)
        # Look directly in debug_state, not in a nested 'context' structure
        if 'global_vars' in debug_state:
            context['global_vars'] = debug_state['global_vars']
            logger.info(f"Restored global_vars from debug state: {context['global_vars']}")
        else:
            logger.info(f"No global_vars in debug_state. Debug state keys: {list(debug_state.keys())}")
        
        # 2. CRITICAL: Restore ALL node outputs from all previously executed nodes
        # This ensures expressions can reference any previous node's output
        all_node_outputs = debug_state.get('node_outputs', {})
        for node_id, output in all_node_outputs.items():
            context['node_outputs'][node_id] = output
        
        logger.info(f"Restored node outputs for {len(context['node_outputs'])} nodes: {list(context['node_outputs'].keys())}")
        logger.info(f"Restored variables: {context['variables']}")
        
        # Log specific node outputs for debugging
        for node_id in list(context['node_outputs'].keys())[:3]:  # Log first 3 node outputs
            logger.info(f"Node {node_id} output: {json.dumps(context['node_outputs'][node_id], default=str)[:100]}")
        
        # 3. Restore loop state if present
        if '_in_loop' in debug_state:
            context['_in_loop'] = debug_state['_in_loop']
        if '_loop_node_id' in debug_state:
            context['_loop_node_id'] = debug_state['_loop_node_id']
        if '_loop_type' in debug_state:
            context['_loop_type'] = debug_state['_loop_type']
        if '_loop_iteration' in debug_state:
            context['_loop_iteration'] = debug_state['_loop_iteration']
        if 'loop' in debug_state:
            context['loop'] = debug_state['loop']
            logger.info(f"Restored loop context: {context['loop']}")
        
        # 4. Restore any custom context keys that were saved
        for key in debug_state:
            if key.startswith('context_'):
                # Remove the 'context_' prefix and restore the key
                original_key = key[8:]  # Remove 'context_' prefix
                context[original_key] = debug_state[key]
                logger.info(f"Restored custom context key: {original_key}")
        
        # 5. Ensure loop_state tracking is maintained for debug mode
        if 'loop_state' in debug_state:
            # This is our custom loop tracking for debug mode
            # Don't add to context, just ensure it's in debug_state
            pass
        
        # Execute the node
        engine = ExecutionEngine(tenant_schema, tenant_id)
        
        # Initialize variable manager with stored state from debug context
        # This is critical for transform nodes to work correctly
        if hasattr(engine, 'variable_manager'):
            # Restore node outputs to variable manager
            for node_id, output in context.get('node_outputs', {}).items():
                engine.variable_manager.set_node_output(node_id, output)
            # Restore global variables - IMPORTANT: Don't confuse input variables with global_vars!
            # 'variables' contains input variables from trigger, not global variables
            # 'global_vars' contains actual global variables set by set_global()
            
            # Start with empty global_vars
            engine.variable_manager.global_vars = {}
            
            # Restore any global_vars that were set during transform debug or previous nodes
            if 'global_vars' in context:
                logger.info(f"Found global_vars in context, setting in variable manager: {context['global_vars']}")
                engine.variable_manager.global_vars = context['global_vars'].copy()
                logger.info(f"Set variable manager global_vars to: {engine.variable_manager.global_vars}")
            else:
                logger.info("No global_vars found in context, starting with empty global_vars")
        
        try:
            # Build adjacency list for navigation
            adjacency = {}
            for edge in edges:
                if edge['source'] not in adjacency:
                    adjacency[edge['source']] = []
                adjacency[edge['source']].append(edge['target'])
            
            # Send node start event to highlight the node
            from services.websocket_manager import manager as ws_manager
            # Collect all variable types for debugging with their current values
            # Show ALL available variables just like transform nodes do
            all_variables = {
                'input': DebugExecutionManager._sanitize_for_json(dict(context.get('variables', {}))),
                'global': DebugExecutionManager._sanitize_for_json(dict(context.get('global_vars', {}))),
                'output': {},  # Node hasn't produced output yet
                'loop': DebugExecutionManager._sanitize_for_json(dict(context.get('loop', {}))) if context.get('_in_loop') else {},
                'all_node_outputs': DebugExecutionManager._sanitize_for_json(dict(debug_state.get('node_outputs', {}))),  # ALL outputs from previously executed nodes
                'available_node_outputs': DebugExecutionManager._sanitize_for_json(dict(context.get('node_outputs', {}))),  # Outputs available to this node
                'data': DebugExecutionManager._sanitize_for_json(
                    context.get('data', {}) if isinstance(context.get('data'), dict) else {'value': context.get('data')}
                ),  # Current data flowing through
                'context_data': DebugExecutionManager._sanitize_for_json(
                    debug_state.get('context_data', {}) if isinstance(debug_state.get('context_data'), dict) else {'value': debug_state.get('context_data')}
                ),  # Saved context data
                'trigger_data': DebugExecutionManager._sanitize_for_json(dict(debug_state.get('trigger_data', {})))  # Original trigger data
            }
            
            # Log what node outputs are available
            logger.info(f"Node {current_node_id} starting with access to outputs from: {list(context.get('node_outputs', {}).keys())}")
            
            # Add variable manager state if available
            if hasattr(engine, 'variable_manager'):
                all_variables['variable_manager_state'] = DebugExecutionManager._sanitize_for_json({
                    'global_vars': dict(engine.variable_manager.global_vars),
                    'node_outputs_count': len(engine.variable_manager.node_outputs)
                })
            
            await ws_manager.send_execution_update(
                execution_id=execution_id,
                tenant_id=tenant_id,
                update_data={
                    'type': 'node_start',
                    'node_id': current_node_id,
                    'node_type': current_node['type'],
                    'node_label': current_node.get('data', {}).get('label', current_node_id),
                    'variables': all_variables
                }
            )
            
            # Execute ONLY the current node (not its children)
            # We need to execute just this node without following edges
            node_type = current_node['type']
            node_data = current_node.get('data', {})
            
            # Set current node ID in context
            context['current_node_id'] = current_node_id
            
            # Check for updated node configuration from debug coordinator
            from services.debug_coordinator import debug_coordinator
            if debug_coordinator.session_exists(execution_id):
                updated_config = debug_coordinator.get_updated_node_config(execution_id, current_node_id)
                if updated_config:
                    logger.info(f"Applying updated configuration for node {current_node_id}")
                    logger.info(f"Original node_data: {node_data}")
                    logger.info(f"Updated config: {updated_config}")
                    # Merge updated config with existing node data
                    node_data = {**node_data, **updated_config}
                    current_node['data'] = node_data
                    logger.info(f"Merged node_data: {node_data}")
                
                # Apply any updated variables
                updated_vars = debug_coordinator.get_updated_variables(execution_id)
                if updated_vars:
                    logger.info(f"Applying updated variables: {updated_vars}")
                    context.setdefault('variables', {}).update(updated_vars)
                    # Also update the debug_state variables
                    debug_state['variables'].update(updated_vars)
            
            # Log node execution start (just like manual trigger mode)
            with get_tenant_db(tenant_schema) as db:
                log_entry = ExecutionLog(
                    execution_id=execution_id,
                    step_id=current_node_id,
                    level='info',
                    message=f"Executing {node_type} node: {node_data.get('label', current_node_id)}",
                    data={'node_type': node_type, 'input_data': context.get('data', {})}
                )
                db.add(log_entry)
                db.commit()
            
            # Execute based on node type
            if node_type == 'trigger':
                # Trigger node just passes data through
                node_output = context.get('data', {})
            elif node_type == 'action':
                # CRITICAL: Ensure context has the latest global_vars from variable_manager
                # This is needed for template resolution in action parameters
                logger.info(f"Before action - variable_manager.global_vars: {engine.variable_manager.global_vars}")
                logger.info(f"Before action - context already has global_vars: {'global_vars' in context}")
                if 'global_vars' in context:
                    logger.info(f"Before action - existing context['global_vars']: {context['global_vars']}")
                
                # Update context with variable_manager's global_vars
                context['global_vars'] = engine.variable_manager.global_vars.copy()
                logger.info(f"Action node execution - global_vars in context after update: {context['global_vars']}")
                logger.info(f"Action node execution - global_vars keys: {list(context['global_vars'].keys())}")
                
                node_output = await engine._execute_action_node(node_data, context)
            elif node_type == 'condition':
                node_output = await engine._execute_condition_node(node_data, context)
            elif node_type == 'transform':
                # Check if we should step into transform debug mode
                from services.debug_coordinator import debug_coordinator
                logger.info(f"Transform node {current_node_id}: Checking debug mode")
                if debug_coordinator.session_exists(execution_id):
                    transform_debug_mode = debug_coordinator.get_transform_debug_mode(execution_id, current_node_id)
                    logger.info(f"Transform debug mode for {current_node_id}: {transform_debug_mode}")
                    if transform_debug_mode == 'step_into':
                        # Start transform debug session
                        script = node_data.get('script', '')
                        
                        # Build transform context
                        transform_context = engine.variable_manager.get_context(
                            current_node_id,
                            context['data']
                        )
                        transform_context['global_vars'] = context.get('global_vars', {})
                        # CRITICAL: Pass the variable_manager so set_global works properly
                        transform_context['variable_manager'] = engine.variable_manager
                        logger.info(f"Passing variable_manager to transform debugger. Current global_vars: {engine.variable_manager.global_vars}")
                        if 'variables' in context:
                            transform_context['input'] = context['variables']
                        if context.get('_in_loop') and context.get('loop'):
                            transform_context['loop'] = context.get('loop', {})
                        
                        # Create and start debug session
                        from services.transform_debugger import transform_debugger
                        debug_session = transform_debugger.create_debug_session(
                            execution_id=execution_id,
                            node_id=current_node_id,
                            script=script,
                            context=transform_context
                        )
                        
                        # Get initial debug info
                        debug_info = {
                            'execution_id': execution_id,
                            'node_id': current_node_id,
                            'current_line': debug_session.current_line,
                            'total_lines': len(debug_session.lines),
                            'current_line_text': debug_session.lines[0] if debug_session.lines else '',
                            'preview_lines': [
                                {
                                    'line_number': i + 1,
                                    'text': line,
                                    'is_current': i == debug_session.current_line,
                                    'has_breakpoint': i in debug_session.breakpoints
                                }
                                for i, line in enumerate(debug_session.lines[:10])
                            ],
                            'is_complete': False,
                            'is_stepping': True,
                            'breakpoints': list(debug_session.breakpoints),
                            'variables': transform_debugger._extract_variables(debug_session),
                            'script_lines': debug_session.lines,
                            'executed_lines': list(debug_session.executed_lines)
                        }
                        
                        # Store transform debug state (including script/context for cross-worker session creation)
                        serializable_context = {
                            k: v for k, v in transform_context.items()
                            if k != 'variable_manager'
                        }
                        debug_state['transform_debug'] = {
                            'node_id': current_node_id,
                            'is_active': True,
                            'debug_info': debug_info,
                            'script': script,
                            'context': DebugExecutionManager._sanitize_for_json(serializable_context),
                        }
                        
                        # Save state and notify frontend
                        DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
                        
                        # Sanitize debug_info before sending via WebSocket
                        sanitized_debug_info = DebugExecutionManager._sanitize_for_json(debug_info)
                        
                        # Send transform debug start event
                        from services.websocket_manager import manager as ws_manager
                        await ws_manager.send_execution_update(
                            execution_id=execution_id,
                            tenant_id=tenant_id,
                            update_data={
                                'type': 'transform_debug_start',
                                'node_id': current_node_id,
                                'debug_info': sanitized_debug_info
                            }
                        )
                        
                        # Return without completing the node - wait for step commands
                        return {
                            'execution_id': execution_id,
                            'status': 'transform_debugging',
                            'current_node': current_node_id,
                            'transform_debug': sanitized_debug_info
                        }
                    else:
                        # Normal execution
                        logger.info(f"Transform node {current_node_id}: Executing normally (debug mode not 'step_into')")
                        node_output = await engine._execute_transform_node(current_node_id, node_data, context)
                else:
                    # Normal execution
                    logger.info(f"Transform node {current_node_id}: No debug session exists, executing normally")
                    node_output = await engine._execute_transform_node(current_node_id, node_data, context)
            elif node_type == 'response':
                node_output = await engine._execute_response_node(node_data, context)
            elif node_type == 'loop':
                # For loops in debug mode, we need special handling
                # Check if we're entering the loop for the first time or continuing
                loop_state = debug_state.get('loop_state', {})
                current_loop_state = loop_state.get(current_node_id, {})
                
                if not current_loop_state:
                    # First time entering this loop
                    loop_type = node_data.get('loopType', 'forEach')
                    
                    if loop_type == 'forEach':
                        # Get the array to iterate over
                        source = node_data.get('source', 'input')
                        array_path = node_data.get('arrayPath', '')
                        
                        if source == 'input':
                            array_data = context.get('data', {})
                            if array_path:
                                for key in array_path.split('.'):
                                    if isinstance(array_data, dict):
                                        array_data = array_data.get(key, [])
                        else:
                            # Source from node output
                            array_data = context.get('node_outputs', {}).get(source, [])
                        
                        if not isinstance(array_data, list):
                            array_data = []
                        
                        current_loop_state = {
                            'type': 'forEach',
                            'array': array_data,
                            'index': 0,
                            'total': len(array_data)
                        }
                    elif loop_type == 'for':
                        # For loops with start, end, step
                        start = int(node_data.get('startValue', 0))
                        end = int(node_data.get('endValue', 10))
                        step = int(node_data.get('stepValue', 1))
                        iterator_name = node_data.get('iteratorName', 'i')
                        
                        # Calculate total iterations (inclusive of end value)
                        if step > 0:
                            # For positive step, iterate from start to end (inclusive)
                            total = max(0, ((end - start) // step) + 1)
                        elif step < 0:
                            # For negative step, iterate from start down to end (inclusive)
                            total = max(0, ((start - end) // (-step)) + 1)
                        else:
                            total = 0
                        
                        logger.info(f"For loop setup: start={start}, end={end}, step={step}, total iterations={total}")
                        
                        current_loop_state = {
                            'type': 'for',
                            'start': start,
                            'end': end,
                            'step': step,
                            'iterator_name': iterator_name,
                            'current_value': start,
                            'index': 0,
                            'total': total
                        }
                    else:
                        # For count loops
                        count = int(node_data.get('count', 1))
                        current_loop_state = {
                            'type': 'count',
                            'index': 0,
                            'total': count
                        }
                    
                    loop_state[current_node_id] = current_loop_state
                    debug_state['loop_state'] = loop_state
                
                # Set loop variables in context
                if current_loop_state['type'] == 'forEach':
                    if current_loop_state['index'] < current_loop_state['total']:
                        item = current_loop_state['array'][current_loop_state['index']]
                        node_output = {
                            **context.get('data', {}),
                            'item': item,
                            'index': current_loop_state['index']
                        }
                        context['loop'] = {
                            'item': item,
                            'index': current_loop_state['index']
                        }
                        # Also set in the context for the transform node to access
                        context['_in_loop'] = True
                        context['_loop_node_id'] = current_node_id
                        context['_loop_type'] = 'forEach'
                        context['_loop_iteration'] = current_loop_state['index']
                        
                        # Store in debug_state so it persists to next step
                        debug_state['_in_loop'] = True
                        debug_state['_loop_node_id'] = current_node_id
                        debug_state['_loop_type'] = 'forEach'
                        debug_state['_loop_iteration'] = current_loop_state['index']
                        debug_state['loop'] = context['loop']
                    else:
                        # Loop complete
                        node_output = context.get('data', {})
                elif current_loop_state['type'] == 'for':
                    # For loop with iterator
                    # Check if current value is within bounds
                    should_execute = False
                    if current_loop_state['step'] > 0:
                        should_execute = current_loop_state['current_value'] <= current_loop_state['end']
                    elif current_loop_state['step'] < 0:
                        should_execute = current_loop_state['current_value'] >= current_loop_state['end']
                    
                    logger.info(f"For loop check: current_value={current_loop_state['current_value']}, end={current_loop_state['end']}, should_execute={should_execute}")
                    
                    if should_execute:
                        iterator_name = current_loop_state['iterator_name']
                        current_value = current_loop_state['current_value']
                        node_output = {
                            **context.get('data', {}),
                            iterator_name: current_value,
                            'index': current_loop_state['index']
                        }
                        context['loop'] = {
                            iterator_name: current_value,
                            'index': current_loop_state['index']
                        }
                        # Also set in the context for the transform node to access
                        context['_in_loop'] = True
                        context['_loop_node_id'] = current_node_id
                        context['_loop_type'] = 'for'
                        context['_loop_iteration'] = current_loop_state['index']
                        
                        # Store in debug_state so it persists to next step
                        debug_state['_in_loop'] = True
                        debug_state['_loop_node_id'] = current_node_id
                        debug_state['_loop_type'] = 'for'
                        debug_state['_loop_iteration'] = current_loop_state['index']
                        debug_state['loop'] = context['loop']
                    else:
                        # Loop complete
                        node_output = context.get('data', {})
                else:
                    # Count loop
                    if current_loop_state['index'] < current_loop_state['total']:
                        node_output = {
                            **context.get('data', {}),
                            'index': current_loop_state['index']
                        }
                        context['loop'] = {
                            'index': current_loop_state['index']
                        }
                        # Also set in the context for the transform node to access
                        context['_in_loop'] = True
                        context['_loop_node_id'] = current_node_id
                        context['_loop_type'] = 'count'
                        context['_loop_iteration'] = current_loop_state['index']
                        
                        # Store in debug_state so it persists to next step
                        debug_state['_in_loop'] = True
                        debug_state['_loop_node_id'] = current_node_id
                        debug_state['_loop_type'] = 'count'
                        debug_state['_loop_iteration'] = current_loop_state['index']
                        debug_state['loop'] = context['loop']
                    else:
                        # Loop complete
                        node_output = context.get('data', {})
            elif node_type == 'parallel':
                # Enhanced parallel debug support
                node_output = context.get('data', {})
                
                # Log parallel execution start for debugging
                logger.info(f"[DEBUG] Parallel node execution started: {node_id}")
                logger.info(f"[DEBUG] Available node_outputs before parallel: {list(context.get('node_outputs', {}).keys())}")
                
                # Store parallel execution info for debugging
                parallel_info = {
                    'total_branches': len(node_data.get('branches', [])),
                    'execution_start': True,
                    'node_outputs_available': list(context.get('node_outputs', {}).keys())
                }
                
                # Update node output with debug info
                if isinstance(node_output, dict):
                    node_output['_parallel_debug'] = parallel_info
                
                logger.info(f"[DEBUG] Parallel node will execute {parallel_info['total_branches']} branches")
            elif node_type == 'human_in_loop':
                node_output = await engine._execute_human_in_loop_node(node_data, context)

                # Check if HITL created a task and paused execution
                if isinstance(node_output, dict) and node_output.get('_hitl_paused'):
                    # Store output and mark as executed
                    debug_state['node_outputs'][current_node_id] = node_output
                    if current_node_id not in debug_state['executed_nodes']:
                        debug_state['executed_nodes'].append(current_node_id)
                    debug_state['context_data'] = node_output
                    debug_state['status'] = 'waiting_for_hitl'
                    debug_state['hitl_task_id'] = node_output.get('task_id')
                    debug_state['hitl_node_id'] = current_node_id

                    # Preserve context state
                    if 'node_outputs' in context:
                        for nid, out in context['node_outputs'].items():
                            debug_state['node_outputs'][nid] = out
                    if 'variables' in context:
                        debug_state['variables'] = context['variables']

                    # Log HITL execution
                    with get_tenant_db(tenant_schema) as db:
                        log_entry = ExecutionLog(
                            execution_id=execution_id,
                            step_id=current_node_id,
                            level='info',
                            message=f"HITL node {node_data.get('label', current_node_id)} created task - waiting for human review",
                            data={'node_type': 'human_in_loop', 'output': node_output}
                        )
                        db.add(log_entry)
                        db.commit()

                    # Save state
                    DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)

                    # Send WebSocket events
                    from services.websocket_manager import manager as ws_manager

                    all_variables = {
                        'input': DebugExecutionManager._sanitize_for_json(dict(context.get('variables', {}))),
                        'global': DebugExecutionManager._sanitize_for_json(dict(context.get('global_vars', {}))),
                        'output': DebugExecutionManager._sanitize_for_json(dict(node_output)),
                        'all_node_outputs': DebugExecutionManager._sanitize_for_json(dict(debug_state.get('node_outputs', {}))),
                    }

                    await ws_manager.send_execution_update(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'node_complete',
                            'node_id': current_node_id,
                            'node_type': 'human_in_loop',
                            'node_label': node_data.get('label', current_node_id),
                            'variables': all_variables,
                            'result': node_output
                        }
                    )

                    await ws_manager.send_execution_update(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'waiting_for_hitl',
                            'node_id': current_node_id,
                            'task_id': node_output.get('task_id'),
                            'task_type': node_output.get('task_type'),
                            'title': node_output.get('title'),
                            'priority': node_output.get('priority'),
                        }
                    )

                    return {
                        'execution_id': execution_id,
                        'status': 'waiting_for_hitl',
                        'current_node': current_node_id,
                        'executed_nodes': debug_state['executed_nodes'],
                        'last_output': node_output
                    }
            elif node_type == 'wait_for_event':
                node_output = await engine._execute_wait_for_event_node(node_data, context)

                # Check if event wait created and paused execution
                if isinstance(node_output, dict) and node_output.get('_event_wait_paused'):
                    # Store output and mark as executed
                    debug_state['node_outputs'][current_node_id] = node_output
                    if current_node_id not in debug_state['executed_nodes']:
                        debug_state['executed_nodes'].append(current_node_id)
                    debug_state['context_data'] = node_output
                    debug_state['status'] = 'waiting_for_event'
                    debug_state['event_wait_id'] = node_output.get('wait_id')
                    debug_state['event_wait_node_id'] = current_node_id

                    # Preserve context state
                    if 'node_outputs' in context:
                        for nid, out in context['node_outputs'].items():
                            debug_state['node_outputs'][nid] = out
                    if 'variables' in context:
                        debug_state['variables'] = context['variables']

                    # Log event wait execution
                    with get_tenant_db(tenant_schema) as db:
                        log_entry = ExecutionLog(
                            execution_id=execution_id,
                            step_id=current_node_id,
                            level='info',
                            message=f"Wait for Event node {node_data.get('label', current_node_id)} - waiting for application event",
                            data={'node_type': 'wait_for_event', 'output': node_output}
                        )
                        db.add(log_entry)
                        db.commit()

                    # Save state
                    DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)

                    # Send WebSocket events
                    from services.websocket_manager import manager as ws_manager

                    all_variables = {
                        'input': DebugExecutionManager._sanitize_for_json(dict(context.get('variables', {}))),
                        'global': DebugExecutionManager._sanitize_for_json(dict(context.get('global_vars', {}))),
                        'output': DebugExecutionManager._sanitize_for_json(dict(node_output)),
                        'all_node_outputs': DebugExecutionManager._sanitize_for_json(dict(debug_state.get('node_outputs', {}))),
                    }

                    await ws_manager.send_execution_update(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'node_complete',
                            'node_id': current_node_id,
                            'node_type': 'wait_for_event',
                            'node_label': node_data.get('label', current_node_id),
                            'variables': all_variables,
                            'result': node_output
                        }
                    )

                    await ws_manager.send_execution_update(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'waiting_for_event',
                            'node_id': current_node_id,
                            'wait_id': node_output.get('wait_id'),
                            'app_id': node_output.get('app_id'),
                            'event_name': node_output.get('event_name'),
                            'match_mode': node_output.get('match_mode'),
                        }
                    )

                    return {
                        'execution_id': execution_id,
                        'status': 'waiting_for_event',
                        'current_node': current_node_id,
                        'executed_nodes': debug_state['executed_nodes'],
                        'last_output': node_output
                    }
            else:
                # Unknown node type, pass data through
                node_output = context.get('data', {})
            
            # Log node execution result (matching manual trigger format)
            with get_tenant_db(tenant_schema) as db:
                if node_type == 'response':
                    # For response nodes, log with response data format
                    log_data = {
                        'node_type': node_type,
                        'output': node_output,
                        'response_data': node_output  # Response nodes return their full output as response_data
                    }
                else:
                    # For other nodes, log with standard output format
                    log_data = {
                        'node_type': node_type,
                        'output': node_output
                    }
                
                log_entry = ExecutionLog(
                    execution_id=execution_id,
                    step_id=current_node_id,
                    level='info',
                    message=f"Node {node_data.get('label', current_node_id)} completed successfully",
                    data=log_data
                )
                db.add(log_entry)
                db.commit()
            
            # Update debug state with comprehensive state preservation
            # 1. Store the output of the current node
            debug_state['node_outputs'][current_node_id] = node_output
            
            # Only append to executed_nodes if not already there (for re-execution)
            if current_node_id not in debug_state['executed_nodes']:
                debug_state['executed_nodes'].append(current_node_id)

            # Track completed nodes for fork-join synchronization
            completed_nodes = debug_state.get('completed_nodes', [])
            if current_node_id not in completed_nodes:
                completed_nodes.append(current_node_id)
                debug_state['completed_nodes'] = completed_nodes

            # Enhanced logging for node outputs
            logger.info(f"=== Node Output for {current_node_id} ({current_node['type']}) ===")
            logger.info(f"Node Label: {current_node.get('data', {}).get('label', current_node_id)}")
            logger.info(f"Output: {json.dumps(node_output, default=str, indent=2)[:500]}")
            logger.info(f"All available node outputs so far: {list(debug_state['node_outputs'].keys())}")
            
            # 2. Save the complete context data for the next step
            # This is what will be passed as 'data' to the next node
            debug_state['context_data'] = node_output
            
            # 3. CRITICAL: Preserve ALL accumulated node outputs
            # The context might have been updated with new node outputs during execution
            if 'node_outputs' in context:
                # Merge with existing node_outputs to ensure we don't lose any
                for node_id, output in context['node_outputs'].items():
                    debug_state['node_outputs'][node_id] = output
            
            # 4. Update global variables (these persist across all nodes)
            # Variables can be modified by any node and should persist
            if 'variables' in context:
                debug_state['variables'] = context['variables']
            
            # 5. Preserve loop-specific state
            if '_in_loop' in context:
                debug_state['_in_loop'] = context['_in_loop']
            if '_loop_node_id' in context:
                debug_state['_loop_node_id'] = context['_loop_node_id']
            if '_loop_type' in context:
                debug_state['_loop_type'] = context['_loop_type']
            if '_loop_iteration' in context:
                debug_state['_loop_iteration'] = context['_loop_iteration']
            if 'loop' in context:
                debug_state['loop'] = context['loop']
            
            # 6. Save any additional context that might have been added
            # Store any custom context keys that nodes might have added
            for key in context:
                if key not in ['execution_id', 'data', 'variables', 'node_outputs', 
                               'is_simulation', 'tenant_schema', 'tenant_id', 'current_node_id',
                               '_in_loop', '_loop_node_id', '_loop_type', '_loop_iteration', 'loop']:
                    # This is a custom context key, preserve it
                    if not key.startswith('_internal_'):  # Skip internal keys
                        debug_state[f'context_{key}'] = context[key]
            
            # Send node complete event
            from services.websocket_manager import manager as ws_manager
            # Collect all variable types for debugging with their current values
            # Show ALL available variables just like transform nodes do
            all_variables = {
                'input': DebugExecutionManager._sanitize_for_json(dict(context.get('variables', {}))),
                'global': DebugExecutionManager._sanitize_for_json(dict(context.get('global_vars', {}))),
                'output': DebugExecutionManager._sanitize_for_json(dict(node_output) if isinstance(node_output, dict) else {'value': node_output}),  # Current node's output
                'loop': DebugExecutionManager._sanitize_for_json(dict(context.get('loop', {}))) if context.get('_in_loop') else {},
                'all_node_outputs': DebugExecutionManager._sanitize_for_json(dict(debug_state.get('node_outputs', {}))),  # ALL node outputs accumulated
                'node_outputs': DebugExecutionManager._sanitize_for_json(dict(context.get('node_outputs', {}))),  # Node outputs available in context
                'data': DebugExecutionManager._sanitize_for_json(dict(node_output) if isinstance(node_output, dict) else {'value': node_output}),  # Node's output
                'context_data': DebugExecutionManager._sanitize_for_json(
                    debug_state.get('context_data', {}) if isinstance(debug_state.get('context_data'), dict) else {'value': debug_state.get('context_data')}
                ),  # Saved context data
                'last_output': DebugExecutionManager._sanitize_for_json(
                    debug_state.get('node_outputs', {}).get(current_node_id, {}) 
                    if isinstance(debug_state.get('node_outputs', {}).get(current_node_id, {}), dict) 
                    else {'value': debug_state.get('node_outputs', {}).get(current_node_id, {})}
                )
            }
            
            # Add debug state info for transparency
            all_variables['debug_info'] = DebugExecutionManager._sanitize_for_json({
                'executed_nodes': list(debug_state.get('executed_nodes', [])),
                'current_node': current_node_id,
                'node_type': current_node['type'],
                'status': debug_state.get('status', 'unknown')
            })
            
            await ws_manager.send_execution_update(
                execution_id=execution_id,
                tenant_id=tenant_id,
                update_data={
                    'type': 'node_complete',
                    'node_id': current_node_id,
                    'node_type': current_node['type'],
                    'node_label': current_node.get('data', {}).get('label', current_node_id),
                    'variables': all_variables,
                    'result': node_output
                }
            )
            
            # Find next node
            next_nodes = []
            
            # Check if this node connects back to a loop
            loop_back_edge = None
            for edge in edges:
                if edge['source'] == current_node_id and edge.get('targetHandle') == 'loop-back':
                    loop_back_edge = edge
                    break
            
            if loop_back_edge:
                # This node connects back to a loop - increment loop counter
                loop_node_id = loop_back_edge['target']
                loop_state = debug_state.get('loop_state', {})
                if loop_node_id in loop_state:
                    loop_state[loop_node_id]['index'] += 1
                    # For 'for' loops, also update the current_value
                    if loop_state[loop_node_id].get('type') == 'for':
                        loop_state[loop_node_id]['current_value'] += loop_state[loop_node_id]['step']
                        logger.info(f"Loop increment: index now {loop_state[loop_node_id]['index']}, value now {loop_state[loop_node_id]['current_value']}, will continue? {loop_state[loop_node_id]['index'] < loop_state[loop_node_id]['total']}")
                    debug_state['loop_state'] = loop_state
                    # Go back to the loop node
                    next_nodes = [loop_node_id]
            elif current_node['type'] == 'loop':
                # Handle loop node navigation
                loop_state = debug_state.get('loop_state', {})
                current_loop_state = loop_state.get(current_node_id, {})
                
                should_continue = False
                if current_loop_state:
                    if current_loop_state['type'] == 'for':
                        # For 'for' loops, check if current value is within bounds
                        if current_loop_state['step'] > 0:
                            should_continue = current_loop_state['current_value'] <= current_loop_state['end']
                        elif current_loop_state['step'] < 0:
                            should_continue = current_loop_state['current_value'] >= current_loop_state['end']
                        logger.info(f"For loop navigation: current_value={current_loop_state['current_value']}, end={current_loop_state['end']}, should_continue={should_continue}")
                    else:
                        # For other loop types, use index-based check
                        should_continue = current_loop_state['index'] < current_loop_state['total']
                
                if should_continue:
                    # Continue to loop body
                    for edge in edges:
                        if edge['source'] == current_node_id and edge.get('sourceHandle') == 'loop-body':
                            next_nodes.append(edge['target'])
                            break
                else:
                    # Loop complete, continue to next node
                    for edge in edges:
                        if edge['source'] == current_node_id and edge.get('sourceHandle') == 'continue':
                            next_nodes.append(edge['target'])
                            break
            elif current_node['type'] == 'condition':
                # Handle condition nodes specially
                condition_result = node_output.get('_condition_result', False)
                for edge in edges:
                    if edge['source'] == current_node_id:
                        source_handle = edge.get('sourceHandle', 'true')
                        if (condition_result and source_handle == 'true') or \
                           (not condition_result and source_handle == 'false'):
                            next_nodes.append(edge['target'])
            else:
                # Regular node - follow all edges
                for edge in edges:
                    if edge['source'] == current_node_id:
                        next_nodes.append(edge['target'])
            
            if next_nodes:
                # Fork-join: If multiple outgoing edges (fork point), store extra branches
                if len(next_nodes) > 1:
                    pending_branches = debug_state.get('pending_branches', [])
                    for extra_branch in next_nodes[1:]:
                        pending_branches.append([current_node_id, extra_branch])
                    debug_state['pending_branches'] = pending_branches
                    logger.info(f"Fork-join: Fork detected at {current_node_id}, {len(next_nodes)} branches. Pending: {len(pending_branches)}")

                debug_state['current_node'] = next_nodes[0]
                debug_state['status'] = 'waiting_for_step'
            else:
                # No outgoing edges - check if there are pending branches to switch to
                pending_branches = debug_state.get('pending_branches', [])
                if pending_branches:
                    next_branch = pending_branches.pop(0)
                    debug_state['pending_branches'] = pending_branches
                    debug_state['current_node'] = next_branch[1]
                    debug_state['status'] = 'waiting_for_step'
                    logger.info(f"Fork-join: Branch ended at {current_node_id}, switching to branch {next_branch[1]}. Remaining: {len(pending_branches)}")
                else:
                    debug_state['status'] = 'completed'
                    debug_state['current_node'] = None

                    # Log execution completion
                    with get_tenant_db(tenant_schema) as db:
                        completion_log = ExecutionLog(
                            execution_id=execution_id,
                            step_id=None,
                            level='info',
                            message='Flow execution completed successfully',
                            data={'total_nodes_executed': len(debug_state.get('executed_nodes', []))}
                        )
                        db.add(completion_log)
                        db.commit()
            
            # Save updated state
            DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
            
            # Send WebSocket notification
            from services.websocket_manager import manager as ws_manager
            
            # Send node complete event
            # Collect all variable types for debugging with their current values
            # Show ALL available variables just like transform nodes do
            all_variables = {
                'input': DebugExecutionManager._sanitize_for_json(dict(context.get('variables', {}))),
                'global': DebugExecutionManager._sanitize_for_json(dict(context.get('global_vars', {}))),
                'output': DebugExecutionManager._sanitize_for_json(dict(node_output) if isinstance(node_output, dict) else {'value': node_output}),  # Current node's output
                'loop': DebugExecutionManager._sanitize_for_json(dict(context.get('loop', {}))) if context.get('_in_loop') else {},
                'all_node_outputs': DebugExecutionManager._sanitize_for_json(dict(debug_state.get('node_outputs', {}))),  # ALL node outputs accumulated
                'node_outputs': DebugExecutionManager._sanitize_for_json(dict(context.get('node_outputs', {}))),  # Node outputs available in context
                'data': DebugExecutionManager._sanitize_for_json(dict(node_output) if isinstance(node_output, dict) else {'value': node_output}),  # Node's output
                'context_data': DebugExecutionManager._sanitize_for_json(
                    debug_state.get('context_data', {}) if isinstance(debug_state.get('context_data'), dict) else {'value': debug_state.get('context_data')}
                ),  # Saved context data
                'last_output': DebugExecutionManager._sanitize_for_json(
                    debug_state.get('node_outputs', {}).get(current_node_id, {}) 
                    if isinstance(debug_state.get('node_outputs', {}).get(current_node_id, {}), dict) 
                    else {'value': debug_state.get('node_outputs', {}).get(current_node_id, {})}
                )
            }
            
            # Add debug state info for transparency
            all_variables['debug_info'] = DebugExecutionManager._sanitize_for_json({
                'executed_nodes': list(debug_state.get('executed_nodes', [])),
                'current_node': current_node_id,
                'node_type': current_node['type'],
                'status': debug_state.get('status', 'unknown')
            })
            
            await ws_manager.send_execution_update(
                execution_id=execution_id,
                tenant_id=tenant_id,
                update_data={
                    'type': 'node_complete',
                    'node_id': current_node_id,
                    'node_type': current_node['type'],
                    'node_label': current_node.get('data', {}).get('label', current_node_id),
                    'variables': all_variables,
                    'result': node_output
                }
            )
            
            # Send next step or completion event
            if debug_state['status'] == 'completed':
                await ws_manager.send_execution_update(
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    update_data={
                        'type': 'execution_complete',
                        'status': 'completed'
                    }
                )
                
                # Update execution status in database
                with get_tenant_db(tenant_schema) as db:
                    execution = db.query(FlowExecution).filter(
                        FlowExecution.execution_id == execution_id
                    ).first()
                    if execution:
                        execution.status = ExecutionStatus.COMPLETED
                        execution.completed_at = datetime.utcnow()
                        db.commit()
            else:
                # Include current state of all variables in waiting_for_step
                current_variables = {
                    'input': DebugExecutionManager._sanitize_for_json(debug_state.get('variables', {})),
                    'global': DebugExecutionManager._sanitize_for_json(debug_state.get('global_vars', {})),
                    'all_node_outputs': DebugExecutionManager._sanitize_for_json(debug_state.get('node_outputs', {})),  # Complete history of all node outputs
                    'context_data': DebugExecutionManager._sanitize_for_json(debug_state.get('context_data', {})),
                    'last_output': DebugExecutionManager._sanitize_for_json(node_output if 'node_output' in locals() else {}),
                    'executed_nodes': debug_state.get('executed_nodes', [])
                }
                
                # Log node outputs summary
                logger.info(f"After node {current_node_id}, total outputs from {len(debug_state.get('node_outputs', {}))} nodes available")
                
                # Send fork_detected event if we just created branches
                pending_branches = debug_state.get('pending_branches', [])
                if len(next_nodes) > 1:
                    await ws_manager.send_execution_update(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        update_data={
                            'type': 'fork_detected',
                            'source_node_id': current_node_id,
                            'total_branches': len(next_nodes),
                            'pending_branches': len(pending_branches),
                        }
                    )

                await ws_manager.send_execution_update(
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    update_data={
                        'type': 'waiting_for_step',
                        'node_id': debug_state['current_node'],
                        'executed_nodes': debug_state['executed_nodes'],
                        'variables': current_variables,
                        'pending_branches': len(pending_branches),
                    }
                )

            return {
                'execution_id': execution_id,
                'status': debug_state['status'],
                'current_node': debug_state.get('current_node'),
                'executed_nodes': debug_state['executed_nodes'],
                'last_output': node_output,
                'pending_branches': len(debug_state.get('pending_branches', [])),
            }
            
        except Exception as e:
            logger.error(f"Error executing node {current_node_id}: {e}")
            
            # Log error in execution log (matching manual trigger format)
            with get_tenant_db(tenant_schema) as db:
                error_log = ExecutionLog(
                    execution_id=execution_id,
                    step_id=current_node_id,
                    level='error',
                    message=f"Node {current_node_id} execution failed",
                    data={'error': str(e), 'node_type': node_type if 'node_type' in locals() else 'unknown'}
                )
                db.add(error_log)
                db.commit()
            
            # Store error in node output
            node_output = {
                '_error': True,
                '_error_message': str(e),
                '_node_id': current_node_id
            }
            
            # Update debug state with error but allow continuation
            debug_state['node_outputs'][current_node_id] = node_output
            debug_state['executed_nodes'].append(current_node_id)
            debug_state['last_error'] = str(e)
            
            # Find next node to allow continuation
            next_nodes = []
            for edge in edges:
                if edge['source'] == current_node_id:
                    next_nodes.append(edge['target'])
            
            if next_nodes:
                debug_state['current_node'] = next_nodes[0]
                debug_state['status'] = 'waiting_for_step'  # Allow continuation
            else:
                debug_state['status'] = 'completed'  # No more nodes
                debug_state['current_node'] = None
            
            # Save state
            DebugExecutionManager.save_debug_state(tenant_schema, execution_id, debug_state, tenant_id)
            
            # Send error notification
            from services.websocket_manager import manager as ws_manager
            await ws_manager.send_execution_update(
                execution_id=execution_id,
                tenant_id=tenant_id,
                update_data={
                    'type': 'node_error',
                    'node_id': current_node_id,
                    'error': str(e)
                }
            )
            
            # Return error status but don't raise - allow continuation
            return {
                'execution_id': execution_id,
                'status': 'error',
                'error': str(e),
                'current_node': debug_state.get('current_node'),
                'executed_nodes': debug_state['executed_nodes'],
                'last_output': node_output
            }