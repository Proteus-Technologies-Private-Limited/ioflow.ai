"""
WebSocket endpoints for real-time updates
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging
from datetime import datetime

from db.database import get_db, get_tenant_db, get_db_context
from api.auth import get_current_user_ws
from core.auth_utils import get_current_user
from api.flows import get_tenant_schema
from services.websocket_manager import manager
from services.transform_debugger import transform_debugger
from services.debug_coordinator import debug_coordinator
from services.debug_execution_manager import DebugExecutionManager
from db.models import User
from core.config import settings

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import Flow, FlowExecution
else:
    from db.models import Flow, FlowExecution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websockets"])


@router.websocket("/executions")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    logger.info(f"WebSocket connection attempt received")
    """
    WebSocket endpoint for real-time execution updates.
    
    Authentication is done via token query parameter.
    
    Message types:
    - Client -> Server:
        - {"action": "subscribe", "execution_id": "uuid"}
        - {"action": "unsubscribe", "execution_id": "uuid"}
        - {"action": "ping"}
    
    - Server -> Client:
        - {"type": "connection", "status": "connected"}
        - {"type": "execution_update", "execution_id": "uuid", "data": {...}}
        - {"type": "execution_log", "execution_id": "uuid", "data": {...}}
        - {"type": "execution_progress", "execution_id": "uuid", "data": {...}}
        - {"type": "subscription", "action": "subscribed/unsubscribed", "execution_id": "uuid"}
        - {"type": "pong"}
        - {"type": "error", "message": "..."}
    """
    
    # Authenticate the user
    logger.info(f"WebSocket authentication attempt with token: {token[:20]}...")
    try:
        current_user = await get_current_user_ws(token, db)
        if not current_user:
            logger.error("WebSocket authentication failed: No user found")
            await websocket.close(code=4001, reason="Authentication failed")
            return
        logger.info(f"WebSocket authenticated for user: {current_user.email}, tenant: {current_user.tenant_id}")
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Connect the WebSocket
    await manager.connect(
        websocket,
        tenant_id=current_user.tenant_id,
        user_id=str(current_user.user_id),
        user_email=current_user.email
    )
    
    try:
        # Keep the connection alive and handle messages
        while True:
            # Wait for messages from client
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                action = message.get("action")
                
                if action == "subscribe":
                    execution_id = message.get("execution_id")
                    logger.info(f"Subscription request for execution: {execution_id}")
                    if execution_id:
                        # Verify the user has access to this execution
                        # We need to check in the tenant database
                        # imports already at top of file
                        
                        # Get proper tenant schema
                        with get_db_context() as db:
                            schema_name = get_tenant_schema(current_user, db)
                            
                        # Use the context manager properly
                        with get_tenant_db(schema_name) as tenant_db:
                            execution = tenant_db.query(FlowExecution).filter(
                                FlowExecution.execution_id == execution_id
                            ).first()
                            
                            if execution:
                                logger.info(f"Execution {execution_id} found, subscribing user")
                                await manager.subscribe_to_execution(websocket, execution_id)
                            else:
                                logger.warning(f"Execution {execution_id} not found or access denied for tenant {current_user.tenant_id}")
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"Execution {execution_id} not found or access denied"
                                })
                
                elif action == "unsubscribe":
                    execution_id = message.get("execution_id")
                    if execution_id:
                        await manager.unsubscribe_from_execution(websocket, execution_id)
                
                elif action == "subscribe_tenant":
                    # Subscribe to all executions for the tenant
                    await manager.subscribe_to_tenant(websocket, current_user.tenant_id)
                
                elif action == "unsubscribe_tenant":
                    # Unsubscribe from tenant-wide updates
                    await manager.unsubscribe_from_tenant(websocket, current_user.tenant_id)
                
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
                    
            except json.JSONDecodeError:
                # Don't try to send message if the WebSocket is closed
                if websocket.client_state.value <= 1:  # CONNECTING=0, CONNECTED=1
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Invalid JSON message"
                        })
                    except:
                        pass  # WebSocket might be closing, ignore send errors
            except Exception as e:
                # Check if this is a disconnect-related error
                error_msg = str(e).lower()
                if any(kw in error_msg for kw in ("disconnect", "receive", "1012", "not connected", "accept", "closed")):
                    logger.info(f"WebSocket disconnected: {e}")
                    break  # Exit the loop cleanly

                logger.error(f"Error processing WebSocket message: {e}")
                # Don't try to send message if the WebSocket is closed
                if websocket.client_state.value <= 1:  # CONNECTING=0, CONNECTED=1
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Error processing message"
                        })
                    except:
                        break  # WebSocket is dead, exit the loop
                
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


@router.get("/status")
async def websocket_status(current_user: User = Depends(get_current_user)):
    """Get WebSocket connection statistics (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return manager.get_connection_stats()


@router.post("/test")
async def test_websocket_notification(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test WebSocket notification sending (for debugging)"""
    # Send a test notification
    test_data = {
        "status": "test",
        "message": "This is a test WebSocket notification",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(f"Sending test WebSocket notification for execution {execution_id}")
    
    await manager.send_execution_update(
        execution_id=execution_id,
        tenant_id=current_user.tenant_id,
        update_data=test_data
    )
    
    await manager.send_execution_log(
        execution_id=execution_id,
        tenant_id=current_user.tenant_id,
        log_entry={
            "level": "info",
            "message": "Test log message from WebSocket test endpoint",
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return {
        "status": "success",
        "message": f"Test notifications sent for execution {execution_id}",
        "tenant_id": current_user.tenant_id
    }


@router.websocket("/debug/{execution_id}")
async def websocket_debug_endpoint(
    websocket: WebSocket,
    execution_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for debug mode execution updates."""
    logger.info(f"Debug WebSocket connection attempt for execution: {execution_id}")
    
    # Authenticate the user
    try:
        current_user = await get_current_user_ws(token, db)
        if not current_user:
            logger.error("Debug WebSocket authentication failed: No user found")
            await websocket.close(code=4001, reason="Authentication failed")
            return
        logger.info(f"Debug WebSocket authenticated for user: {current_user.email}")
    except Exception as e:
        logger.error(f"Debug WebSocket authentication error: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Verify user has access to this execution
    # imports already at top of file
    
    # Get proper tenant schema
    with get_db_context() as db:
        schema_name = get_tenant_schema(current_user, db)
    with get_tenant_db(schema_name) as tenant_db:
        execution = tenant_db.query(FlowExecution).filter(
            FlowExecution.execution_id == execution_id
        ).first()
    
    if not execution:
        logger.error(f"Execution {execution_id} not found for tenant {current_user.tenant_id}")
        await websocket.close(code=4004, reason="Execution not found")
        return
    
    # Check if execution is in debug mode
    debug_mode = (execution.execution_data or {}).get('debug_mode', False)
    if not debug_mode:
        logger.error(f"Execution {execution_id} is not in debug mode")
        await websocket.close(code=4003, reason="Execution not in debug mode")
        return
    
    # Connect the WebSocket
    await manager.connect(
        websocket,
        tenant_id=current_user.tenant_id,
        user_id=str(current_user.user_id),
        user_email=current_user.email
    )
    
    # Automatically subscribe to this execution
    await manager.subscribe_to_execution(websocket, execution_id)
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "debug_connected",
            "execution_id": execution_id,
            "status": "connected"
        })
        
        # Keep the connection alive
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle debug-specific commands if needed
                action = message.get("action") if message else None
                
                if not action:
                    # If no action specified, ignore the message
                    logger.debug(f"Received message without action: {message}")
                    continue
                
                if action == "ping":
                    await websocket.send_json({"type": "pong"})
                
                # Transform debug commands
                elif action == "transform_step_into":
                    # Set transform debug mode for a specific node
                    node_id = message.get("node_id")
                    if node_id:
                        debug_coordinator.set_transform_debug_mode(execution_id, node_id, "step_into")
                        await websocket.send_json({
                            "type": "transform_debug_mode_set",
                            "node_id": node_id,
                            "mode": "step_into"
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "node_id required for transform_step_into"
                        })
                
                elif action == "transform_step":
                    # Execute next line in transform debugger
                    node_id = message.get("node_id")
                    if node_id:
                        # Check if execution is still active
                        # Get proper tenant schema
                        with get_db_context() as db:
                            schema_name = get_tenant_schema(current_user, db)
                            
                        # Use the context manager properly
                        with get_tenant_db(schema_name) as tenant_db:
                            execution = tenant_db.query(FlowExecution).filter(
                                FlowExecution.execution_id == execution_id
                            ).first()
                            
                            if execution and execution.status == 'completed':
                                logger.info(f"Transform step requested for completed execution {execution_id}")
                                await websocket.send_json({
                                    "type": "execution_complete",
                                    "execution_id": execution_id,
                                    "status": "completed"
                                })
                                continue
                        
                        try:
                            # If session doesn't exist in this worker, re-create from saved debug state
                            session_key = f"{execution_id}_{node_id}"
                            if session_key not in transform_debugger.debug_sessions:
                                logger.info(f"Transform session not found in this worker, recreating from debug state")
                                with get_db_context() as db:
                                    schema_name = get_tenant_schema(current_user, db)
                                debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id, current_user.tenant_id)
                                if debug_state and debug_state.get('transform_debug', {}).get('is_active'):
                                    td = debug_state['transform_debug']
                                    transform_debugger.create_debug_session(
                                        execution_id=execution_id,
                                        node_id=node_id,
                                        script=td.get('script', ''),
                                        context=td.get('context', {})
                                    )
                                    logger.info(f"Recreated transform debug session from saved state")

                            result = transform_debugger.step_into(execution_id, node_id)
                            if result is None:
                                logger.error(f"transform_debugger.step_into returned None for {execution_id}, {node_id}")
                                result = {
                                    'error': 'Transform debugger returned None',
                                    'execution_id': execution_id,
                                    'node_id': node_id
                                }
                        except Exception as e:
                            logger.error(f"Error in transform_debugger.step_into: {e}")
                            result = {
                                'error': str(e),
                                'execution_id': execution_id,
                                'node_id': node_id
                            }
                        
                        # Sanitize result before sending
                        if result:
                            result = DebugExecutionManager._sanitize_for_json(result)
                        
                        await websocket.send_json({
                            "type": "transform_step_result",
                            "node_id": node_id,
                            "result": result
                        })
                        
                        # If transform completed, update debug state to allow moving to next node
                        if result and result.get('status') == 'completed':
                            # imports already at top of file
                            
                            # CRITICAL: Extract global variables BEFORE clearing debug mode
                            logger.info(f"Transform completed via WebSocket step - extracting global vars BEFORE cleanup")
                            global_vars_from_transform = {}
                            
                            # Get the variables from the transform debugger session before cleanup
                            session_key = f"{execution_id}_{node_id}"
                            if hasattr(transform_debugger, 'debug_sessions') and session_key in transform_debugger.debug_sessions:
                                state = transform_debugger.debug_sessions[session_key]
                                if 'variable_manager' in state.execution_globals:
                                    vm = state.execution_globals['variable_manager']
                                    global_vars_from_transform = vm.global_vars.copy()
                                    logger.info(f"Extracted global vars from variable_manager: {list(global_vars_from_transform.keys())}")
                                else:
                                    global_vars_from_transform = state.execution_globals.get('global', {})
                                    logger.info(f"Extracted global vars from global dict: {list(global_vars_from_transform.keys())}")
                            else:
                                # Try to get from result if available
                                variables = result.get('variables', {})
                                if 'global' in variables:
                                    global_vars_from_transform = variables['global']
                                    logger.info(f"Extracted global vars from result: {list(global_vars_from_transform.keys())}")
                            
                            # NOW clear transform debug mode after extraction
                            debug_coordinator.clear_transform_debug_mode(execution_id, node_id)
                            
                            # Get and update debug state
                            # Get proper tenant schema
                            with get_db_context() as db:
                                schema_name = get_tenant_schema(current_user, db)
                            debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id, current_user.tenant_id)
                            if debug_state:
                                # Save global variables to debug state
                                if global_vars_from_transform:
                                    if 'global_vars' not in debug_state:
                                        debug_state['global_vars'] = {}
                                    debug_state['global_vars'].update(global_vars_from_transform)
                                    logger.info(f"Saved global_vars to debug state via WebSocket step: {list(debug_state['global_vars'].keys())}")
                                
                                # Mark transform as completed
                                if 'transform_debug' in debug_state:
                                    debug_state['transform_debug']['is_active'] = False
                                # Store the transform output
                                debug_state['node_outputs'][node_id] = result.get('output', {})
                                # Mark this node as executed
                                executed_nodes = debug_state.get('executed_nodes', [])
                                if node_id not in executed_nodes:
                                    executed_nodes.append(node_id)
                                debug_state['executed_nodes'] = executed_nodes

                                # Find the next node based on edges
                                with get_db_context() as db:
                                    schema_name = get_tenant_schema(current_user, db)

                                with get_tenant_db(schema_name) as tenant_db:
                                    flow = tenant_db.query(Flow).filter(
                                        Flow.flow_id == debug_state.get('flow_id')
                                    ).first()

                                    if flow and flow.flow_definition:
                                        edges = flow.flow_definition.get('edges', [])
                                        nodes = flow.flow_definition.get('nodes', [])

                                        next_nodes = []
                                        for edge in edges:
                                            if edge['source'] == node_id:
                                                for node in nodes:
                                                    if node['id'] == edge['target']:
                                                        next_nodes.append(node)
                                                        break

                                        if next_nodes:
                                            next_node = next_nodes[0]
                                            debug_state['current_node'] = next_node['id']
                                            debug_state['status'] = 'waiting_for_step'
                                            DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, current_user.tenant_id)

                                            await websocket.send_json({
                                                "type": "node_complete",
                                                "node_id": node_id,
                                                "node_type": "transform",
                                                "result": result.get('output', {}),
                                                "variables": {'output': result.get('output', {})}
                                            })
                                            await websocket.send_json({
                                                "type": "waiting_for_step",
                                                "node_id": next_node['id'],
                                                "node_label": next_node.get('data', {}).get('label', next_node['id']),
                                                "executed_nodes": debug_state['executed_nodes']
                                            })
                                        else:
                                            debug_state['status'] = 'completed'
                                            DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, current_user.tenant_id)

                                            await websocket.send_json({
                                                "type": "node_complete",
                                                "node_id": node_id,
                                                "node_type": "transform",
                                                "result": result.get('output', {})
                                            })
                                            await websocket.send_json({
                                                "type": "execution_complete",
                                                "execution_id": execution_id,
                                                "status": "completed"
                                            })
                                    else:
                                        DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, current_user.tenant_id)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "node_id required for transform_step"
                        })
                
                elif action == "transform_continue":
                    # Continue transform execution until breakpoint or completion
                    node_id = message.get("node_id")
                    if node_id:
                        # Check if execution is still active
                        # Get proper tenant schema
                        with get_db_context() as db:
                            schema_name = get_tenant_schema(current_user, db)
                            
                        # Use the context manager properly
                        with get_tenant_db(schema_name) as tenant_db:
                            execution = tenant_db.query(FlowExecution).filter(
                                FlowExecution.execution_id == execution_id
                            ).first()
                            
                            if execution and execution.status == 'completed':
                                logger.info(f"Transform continue requested for completed execution {execution_id}")
                                await websocket.send_json({
                                    "type": "execution_complete",
                                    "execution_id": execution_id,
                                    "status": "completed"
                                })
                                continue
                        
                        try:
                            # If session doesn't exist in this worker, re-create from saved debug state
                            session_key = f"{execution_id}_{node_id}"
                            if session_key not in transform_debugger.debug_sessions:
                                logger.info(f"Transform session not found in this worker (continue), recreating from debug state")
                                with get_db_context() as db:
                                    schema_name = get_tenant_schema(current_user, db)
                                debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id, current_user.tenant_id)
                                if debug_state and debug_state.get('transform_debug', {}).get('is_active'):
                                    td = debug_state['transform_debug']
                                    transform_debugger.create_debug_session(
                                        execution_id=execution_id,
                                        node_id=node_id,
                                        script=td.get('script', ''),
                                        context=td.get('context', {})
                                    )

                            result = transform_debugger.continue_execution(execution_id, node_id)
                            if result is None:
                                logger.error(f"transform_debugger.continue_execution returned None for {execution_id}, {node_id}")
                                result = {
                                    'error': 'Transform debugger returned None',
                                    'execution_id': execution_id,
                                    'node_id': node_id
                                }
                        except Exception as e:
                            logger.error(f"Error in transform_debugger.continue_execution: {e}")
                            result = {
                                'error': str(e),
                                'execution_id': execution_id,
                                'node_id': node_id
                            }
                        
                        await websocket.send_json({
                            "type": "transform_continue_result",
                            "node_id": node_id,
                            "result": result
                        })
                        
                        # If transform completed, update debug state and continue flow
                        if result and result.get('status') == 'completed':
                            # imports already at top of file
                            
                            # CRITICAL: Extract global variables BEFORE clearing debug mode
                            logger.info(f"Transform completed via WebSocket - extracting global vars BEFORE cleanup")
                            global_vars_from_transform = {}
                            
                            # Get the variables from the transform debugger session before cleanup
                            session_key = f"{execution_id}_{node_id}"
                            if hasattr(transform_debugger, 'debug_sessions') and session_key in transform_debugger.debug_sessions:
                                state = transform_debugger.debug_sessions[session_key]
                                if 'variable_manager' in state.execution_globals:
                                    vm = state.execution_globals['variable_manager']
                                    global_vars_from_transform = vm.global_vars.copy()
                                    logger.info(f"Extracted global vars from variable_manager: {list(global_vars_from_transform.keys())}")
                                else:
                                    global_vars_from_transform = state.execution_globals.get('global', {})
                                    logger.info(f"Extracted global vars from global dict: {list(global_vars_from_transform.keys())}")
                            else:
                                # Try to get from result if available
                                variables = result.get('variables', {})
                                if 'global' in variables:
                                    global_vars_from_transform = variables['global']
                                    logger.info(f"Extracted global vars from result: {list(global_vars_from_transform.keys())}")
                            
                            # NOW clear transform debug mode after extraction
                            debug_coordinator.clear_transform_debug_mode(execution_id, node_id)
                            
                            # Get and update debug state
                            # Get proper tenant schema
                            with get_db_context() as db:
                                schema_name = get_tenant_schema(current_user, db)
                            debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id, current_user.tenant_id)
                            if debug_state:
                                # Save global variables to debug state
                                if global_vars_from_transform:
                                    if 'global_vars' not in debug_state:
                                        debug_state['global_vars'] = {}
                                    debug_state['global_vars'].update(global_vars_from_transform)
                                    logger.info(f"Saved global_vars to debug state via WebSocket: {list(debug_state['global_vars'].keys())}")
                                
                                if debug_state.get('transform_debug'):
                                    # Mark transform as completed
                                    debug_state['transform_debug']['is_active'] = False
                                # Store the transform output
                                debug_state['node_outputs'][node_id] = result.get('output', {})
                                
                                # Mark the node as executed
                                if node_id not in debug_state.get('executed_nodes', []):
                                    debug_state['executed_nodes'].append(node_id)
                                
                                # Find the next node based on edges
                                with get_db_context() as db:
                                    schema_name = get_tenant_schema(current_user, db)

                                with get_tenant_db(schema_name) as tenant_db:
                                    flow = tenant_db.query(Flow).filter(
                                        Flow.flow_id == debug_state.get('flow_id')
                                    ).first()

                                    if flow and flow.flow_definition:
                                        edges = flow.flow_definition.get('edges', [])
                                        nodes = flow.flow_definition.get('nodes', [])

                                        next_nodes = []
                                        for edge in edges:
                                            if edge['source'] == node_id:
                                                for node in nodes:
                                                    if node['id'] == edge['target']:
                                                        next_nodes.append(node)
                                                        break

                                        if next_nodes:
                                            next_node = next_nodes[0]
                                            debug_state['current_node'] = next_node['id']
                                            debug_state['status'] = 'waiting_for_step'
                                            DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, current_user.tenant_id)

                                            await websocket.send_json({
                                                "type": "node_complete",
                                                "node_id": node_id,
                                                "node_type": "transform",
                                                "result": result.get('output', {}),
                                                "variables": {'output': result.get('output', {})}
                                            })
                                            await websocket.send_json({
                                                "type": "waiting_for_step",
                                                "node_id": next_node['id'],
                                                "node_label": next_node.get('data', {}).get('label', next_node['id']),
                                                "executed_nodes": debug_state['executed_nodes']
                                            })
                                        else:
                                            debug_state['status'] = 'completed'
                                            DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, current_user.tenant_id)

                                            await websocket.send_json({
                                                "type": "node_complete",
                                                "node_id": node_id,
                                                "node_type": "transform",
                                                "result": result.get('output', {})
                                            })
                                            await websocket.send_json({
                                                "type": "execution_complete",
                                                "execution_id": execution_id,
                                                "status": "completed"
                                            })
                                    else:
                                        DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, current_user.tenant_id)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "node_id required for transform_continue"
                        })
                
                elif action == "transform_set_breakpoint":
                    # Set a breakpoint in transform code
                    node_id = message.get("node_id")
                    line_no = message.get("line_no")
                    if node_id and line_no is not None:
                        success = transform_debugger.set_breakpoint(execution_id, node_id, line_no)
                        await websocket.send_json({
                            "type": "breakpoint_set",
                            "node_id": node_id,
                            "line_no": line_no,
                            "success": success
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "node_id and line_no required for transform_set_breakpoint"
                        })
                
                elif action == "transform_remove_breakpoint":
                    # Remove a breakpoint from transform code
                    node_id = message.get("node_id")
                    line_no = message.get("line_no")
                    if node_id and line_no is not None:
                        success = transform_debugger.remove_breakpoint(execution_id, node_id, line_no)
                        await websocket.send_json({
                            "type": "breakpoint_removed",
                            "node_id": node_id,
                            "line_no": line_no,
                            "success": success
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "node_id and line_no required for transform_remove_breakpoint"
                        })
                
                elif action == "transform_get_state":
                    # Get current transform debug state
                    node_id = message.get("node_id")
                    if node_id:
                        state = transform_debugger.get_debug_state(execution_id, node_id)
                        # Sanitize state before sending
                        if state:
                            state = DebugExecutionManager._sanitize_for_json(state)
                        await websocket.send_json({
                            "type": "transform_state",
                            "node_id": node_id,
                            "state": state
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "node_id required for transform_get_state"
                        })
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
                    
            except WebSocketDisconnect:
                # WebSocket disconnected, break out of the loop
                logger.info(f"WebSocket disconnected during message processing for execution: {execution_id}")
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except Exception as e:
                import traceback
                logger.error(f"Error processing debug WebSocket message: {e}")
                logger.error(f"Message that caused error: {message if 'message' in locals() else 'Unknown'}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Only try to send error message if WebSocket is still connected
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Error processing message"
                    })
                except:
                    logger.debug("Could not send error message, WebSocket likely disconnected")
                
    except WebSocketDisconnect:
        logger.info(f"Debug WebSocket disconnected for execution: {execution_id}")
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Debug WebSocket error: {e}")
        await manager.disconnect(websocket)


@router.websocket("/public/{execution_id}")
async def public_execution_websocket(
    websocket: WebSocket,
    execution_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for public execution updates (no authentication required).
    Used by public flow apps to get real-time execution progress.
    """
    logger.info(f"Public execution WebSocket connection for execution: {execution_id}")

    try:
        # Get execution details to find the flow and send flow definition
        # Note: websocket.accept() will be called by manager.connect() below
        flow_definition = None
        tenant_id = None
        try:
            # Try to get execution from main schema (for SQLite) or tenant schema (for PostgreSQL)
            # Since public executions use "main" schema, query from main
            from db.database import get_tenant_db

            with get_tenant_db("main") as tenant_db:
                execution = tenant_db.query(FlowExecution).filter(
                    FlowExecution.execution_id == execution_id
                ).first()

                if execution:
                    # Get the flow definition
                    flow = tenant_db.query(Flow).filter(
                        Flow.flow_id == execution.flow_id
                    ).first()

                    if flow:
                        flow_definition = flow.flow_definition
                        tenant_id = flow.tenant_id
                        logger.info(f"Found flow definition for execution {execution_id}, tenant: {tenant_id}")
        except Exception as e:
            logger.error(f"Error getting flow definition: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

        # Connect to WebSocket manager
        # Use the actual tenant_id from the flow, or "main" as fallback
        final_tenant_id = tenant_id or "main"
        logger.info(f"Connecting public WebSocket with tenant_id: {final_tenant_id}")
        await manager.connect(
            websocket,
            tenant_id=final_tenant_id,
            user_id="public",
            user_email="public"
        )

        # Subscribe to this specific execution
        logger.info(f"Subscribing to execution {execution_id}")
        await manager.subscribe_to_execution(websocket, execution_id)
        logger.info(f"✓ Subscribed public WebSocket to execution {execution_id} with tenant {final_tenant_id}")

        # Log current connection stats
        stats = manager.get_connection_stats()
        logger.info(f"WebSocket connection stats after subscription: {stats}")

        # Send initial connection message with flow definition
        initial_message = {
            "type": "connected",
            "execution_id": execution_id,
            "message": "Connected to execution stream"
        }

        if flow_definition:
            initial_message["flow_definition"] = flow_definition
            logger.info(f"Sending flow definition with {len(flow_definition.get('nodes', []))} nodes")
        else:
            logger.warning(f"No flow definition found for execution {execution_id}")

        await websocket.send_json(initial_message)
        logger.info(f"Public WebSocket connected and subscribed to execution {execution_id}, tenant: {tenant_id or 'main'}")

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (like ping/pong)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle ping messages
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })

            except WebSocketDisconnect:
                logger.info(f"Public WebSocket disconnected for execution: {execution_id}")
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from public WebSocket")
            except Exception as e:
                logger.error(f"Error in public WebSocket message loop: {e}")
                break

    except Exception as e:
        logger.error(f"Public WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket)