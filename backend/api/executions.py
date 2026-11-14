from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import logging

from db.database import get_db, get_tenant_db
from db.db_compat import table_ref, is_sqlite
from db.models import User, FlowExecution, ExecutionLog, AsyncCallback, ExecutionStatus, Flow, Tenant
from api.auth import get_current_user
from api.flows import get_tenant_schema
from services.debug_coordinator import debug_coordinator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])

# Pydantic models
class ExecutionResponse(BaseModel):
    execution_id: str
    flow_id: str
    flow_name: str
    flow_description: Optional[str] = None
    trigger_type: str
    trigger_data: dict
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    current_step: Optional[str]
    execution_data: dict
    is_simulation: Optional[bool] = False
    result_data: Optional[Union[dict, list, str]] = None
    response_status: Optional[int] = None
    response_headers: Optional[dict] = None
    node_outputs: Optional[dict] = None

class ExecutionLogResponse(BaseModel):
    log_id: str
    execution_id: str
    step_id: Optional[str]
    timestamp: datetime
    level: str
    message: str
    data: dict

class CallbackResponse(BaseModel):
    callback_id: str
    execution_id: str
    step_id: str
    callback_token: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    response_data: Optional[dict]

class CallbackData(BaseModel):
    response_data: Dict[str, Any]
    status: str = "success"

@router.get("/")
async def list_executions(
    flow_id: Optional[str] = None,
    status: Optional[ExecutionStatus] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None
):
    """List flow executions with visibility rules based on flow scope."""
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        # Apply execution visibility rules based on user role
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        
        # Start with base query
        query = tenant_db.query(FlowExecution).join(Flow)
        
        if user_role == "INSTANCE_ADMIN":
            # Instance admin can see all executions across all tenants
            # No tenant filter applied
            pass
        elif user_role == "TENANT_ADMIN":
            # Tenant admin can see all executions in their tenant only
            query = query.filter(Flow.tenant_id == current_user.tenant_id)
        elif user_role == "FLOW_DESIGNER" or user_role == "FLOW_EDITOR":
            # Flow designers can only see executions of:
            # - Flows they created (regardless of scope)
            query = query.filter(
                Flow.tenant_id == current_user.tenant_id,
                Flow.created_by == current_user.user_id
            )
        elif user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            # Execution monitors and flow executors can see executions for all flows they have access to in their tenant:
            # - Global flows
            # - Tenant flows
            # - Their own user flows
            from sqlalchemy import or_, and_
            query = query.filter(
                Flow.tenant_id == current_user.tenant_id,
                or_(
                    Flow.flow_scope == 'global',
                    Flow.flow_scope == 'tenant',
                    and_(Flow.flow_scope == 'user', Flow.created_by == current_user.user_id)
                )
            )
        else:
            # Regular users can only see their own executions (that they triggered)
            # Check if the execution was triggered by this user
            from sqlalchemy import or_, and_
            query = query.filter(
                Flow.tenant_id == current_user.tenant_id,
                or_(
                    FlowExecution.trigger_data.contains(f'"user_id": "{current_user.user_id}"'),
                    FlowExecution.trigger_data.contains(f'"triggered_by": "{current_user.user_id}"'),
                    FlowExecution.trigger_type == 'manual'  # For manual triggers by the user
                )
            )
        
        if flow_id:
            query = query.filter(FlowExecution.flow_id == flow_id)
        
        if status:
            query = query.filter(FlowExecution.status == status)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Order by most recent first
        query = query.order_by(desc(FlowExecution.started_at))
        
        # Apply pagination
        executions = query.offset(offset).limit(limit).all()
        
        # Add total count to response headers
        if response:
            response.headers["X-Total-Count"] = str(total_count)
            response.headers["X-Limit"] = str(limit)
            response.headers["X-Offset"] = str(offset)
        
        # Import deserialize function for SQLite JSON fields
        from api.applications import deserialize_json_field
        from core.config import settings
        
        result = []
        for exec in executions:
            # Deserialize JSON fields for SQLite
            if settings.database_url.startswith("sqlite"):
                result_data = deserialize_json_field(exec.result_data) if exec.result_data else None
                trigger_data = deserialize_json_field(exec.trigger_data) if exec.trigger_data else {}
                execution_data = deserialize_json_field(exec.execution_data) if exec.execution_data else {}
                response_headers = deserialize_json_field(exec.response_headers) if exec.response_headers else None
            else:
                result_data = exec.result_data
                trigger_data = exec.trigger_data or {}
                execution_data = exec.execution_data or {}
                response_headers = exec.response_headers

            # Fix: If result_data is an integer (status code), convert it to a dict
            if isinstance(result_data, int):
                logger.warning(f"result_data is an integer ({result_data}), converting to dict")
                result_data = {"status_code": result_data}
                
            # Handle response_status - ensure it's an integer or None
            response_status = exec.response_status
            if response_status is not None:
                if isinstance(response_status, str):
                    # Try to convert string to integer, use None if it fails
                    try:
                        # Check if it's a template string that wasn't processed
                        if '{{' in response_status and '}}' in response_status:
                            logger.warning(f"Found unprocessed template in response_status: {response_status}, setting to None")
                            response_status = None
                        else:
                            response_status = int(response_status)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert response_status '{response_status}' to integer, setting to None")
                        response_status = None
                elif not isinstance(response_status, int):
                    logger.warning(f"Invalid response_status type: {type(response_status)}, setting to None")
                    response_status = None
            
            result.append(ExecutionResponse(
                execution_id=exec.execution_id,
                flow_id=exec.flow_id,
                flow_name=exec.flow.flow_name,
                trigger_type=exec.trigger_type,
                trigger_data=trigger_data,
                status=exec.status.value,
                started_at=exec.started_at,
                completed_at=exec.completed_at,
                current_step=exec.current_step,
                execution_data=execution_data,
                is_simulation=execution_data.get('is_simulation', False),
                result_data=result_data,
                response_status=response_status,
                response_headers=response_headers
            ))
        
        return result

@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get execution details with visibility checks."""
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        # Apply visibility checks based on user role
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        
        # Build query based on role
        query = tenant_db.query(FlowExecution).join(Flow).filter(
            FlowExecution.execution_id == execution_id
        )
        
        # Apply tenant filter for non-instance admins
        if user_role != "INSTANCE_ADMIN":
            query = query.filter(Flow.tenant_id == current_user.tenant_id)
        
        execution = query.first()
        
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        
        if user_role == "INSTANCE_ADMIN":
            # Instance admin can see all executions
            pass
        elif user_role == "TENANT_ADMIN":
            # Tenant admin can see all executions in their tenant
            # Already filtered by tenant via get_tenant_db
            pass
        elif user_role in ["FLOW_DESIGNER", "FLOW_EDITOR"]:
            # Flow designers can only see executions of flows they created
            if execution.flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view executions of flows you created"
                )
        elif user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            # Execution monitors and flow executors can see executions of flows they have access to
            flow_scope = execution.flow.flow_scope or 'user'
            if flow_scope == 'user' and execution.flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view this execution"
                )
        else:
            # Regular users can only see their own executions
            trigger_data = deserialize_json_field(execution.trigger_data) if execution.trigger_data else {}
            user_triggered = (
                trigger_data.get('user_id') == current_user.user_id or
                trigger_data.get('triggered_by') == current_user.user_id
            )
            if not user_triggered:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view executions you triggered"
                )
        
        # Deserialize JSON fields for SQLite
        from api.applications import deserialize_json_field
        from core.config import settings
        
        node_outputs = None
        if execution.node_outputs:
            node_outputs = deserialize_json_field(execution.node_outputs)
        
        # Deserialize other JSON fields for SQLite
        if settings.database_url.startswith("sqlite"):
            result_data = deserialize_json_field(execution.result_data) if execution.result_data else None
            trigger_data = deserialize_json_field(execution.trigger_data) if execution.trigger_data else {}
            execution_data = deserialize_json_field(execution.execution_data) if execution.execution_data else {}
            response_headers = deserialize_json_field(execution.response_headers) if execution.response_headers else None
        else:
            result_data = execution.result_data
            trigger_data = execution.trigger_data or {}
            execution_data = execution.execution_data or {}
            response_headers = execution.response_headers

        # Fix: If result_data is an integer (status code), convert it to a dict
        if isinstance(result_data, int):
            logger.warning(f"result_data is an integer ({result_data}), converting to dict")
            result_data = {"status_code": result_data}
        
        return ExecutionResponse(
            execution_id=execution.execution_id,
            flow_id=execution.flow_id,
            flow_name=execution.flow.flow_name,
            flow_description=execution.flow.description,
            trigger_type=execution.trigger_type,
            trigger_data=trigger_data,
            status=execution.status.value,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            current_step=execution.current_step,
            execution_data=execution_data,
            result_data=result_data,
            response_status=execution.response_status,
            response_headers=response_headers,
            node_outputs=node_outputs
        )

@router.get("/{execution_id}/logs")
async def get_execution_logs(
    execution_id: str,
    level: Optional[str] = None,
    log_id: Optional[str] = Query(None, description="Filter by specific log ID"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_data: bool = Query(False, description="Include log data field"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to include"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get execution logs with visibility checks and pagination support.
    
    Query parameters:
    - log_id: Filter by specific log ID
    - include_data: Whether to include the potentially large 'data' field (default: False)
    - fields: Comma-separated list of fields to include (e.g., "log_id,timestamp,message")
    """
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        # Apply same visibility checks as get_execution
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        
        # Build query based on role
        query = tenant_db.query(FlowExecution).join(Flow).filter(
            FlowExecution.execution_id == execution_id
        )
        
        # Apply tenant filter for non-instance admins
        if user_role != "INSTANCE_ADMIN":
            query = query.filter(Flow.tenant_id == current_user.tenant_id)
        
        execution = query.first()
        
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        
        if user_role == "INSTANCE_ADMIN":
            # Instance admin can see all execution logs
            pass
        elif user_role == "TENANT_ADMIN":
            # Tenant admin can see all execution logs in their tenant
            pass
        elif user_role in ["FLOW_DESIGNER", "FLOW_EDITOR"]:
            # Flow designers can only see logs of flows they created
            if execution.flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view logs of flows you created"
                )
        elif user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            # Execution monitors and flow executors can see logs of flows they have access to
            flow_scope = execution.flow.flow_scope or 'user'
            if flow_scope == 'user' and execution.flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view these logs"
                )
        else:
            # Regular users can only see logs of their own executions
            from api.applications import deserialize_json_field
            trigger_data = deserialize_json_field(execution.trigger_data) if execution.trigger_data else {}
            user_triggered = (
                trigger_data.get('user_id') == current_user.user_id or
                trigger_data.get('triggered_by') == current_user.user_id
            )
            if not user_triggered:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view logs of executions you triggered"
                )
        
        # Query logs
        query = tenant_db.query(ExecutionLog).filter(
            ExecutionLog.execution_id == execution_id
        )
        
        # Filter by specific log_id if provided
        if log_id:
            query = query.filter(ExecutionLog.log_id == log_id)
        
        if level:
            query = query.filter(ExecutionLog.level == level)
        
        # Get total count for pagination info
        total_count = query.count()
        
        # Order by timestamp
        query = query.order_by(ExecutionLog.timestamp)
        
        # Apply pagination
        logs = query.offset(offset).limit(limit).all()
        
        # Parse requested fields
        requested_fields = None
        if fields:
            requested_fields = set(fields.split(','))
        
        # Build log responses with field filtering
        log_responses = []
        for log in logs:
            # Start with basic fields
            log_dict = {
                "log_id": log.log_id,
                "execution_id": log.execution_id,
                "timestamp": log.timestamp,
                "level": log.level,
                "message": log.message
            }
            
            # Add optional fields
            if log.step_id:
                log_dict["step_id"] = log.step_id
            
            # Only include data field if explicitly requested or if specific fields are requested
            if include_data or (requested_fields and "data" in requested_fields):
                # Deserialize JSON for SQLite if needed
                from api.applications import deserialize_json_field
                from core.config import settings
                
                if settings.database_url.startswith("sqlite"):
                    log_dict["data"] = deserialize_json_field(log.data) if log.data else {}
                else:
                    log_dict["data"] = log.data or {}
            
            # Filter to only requested fields if specified
            if requested_fields:
                log_dict = {k: v for k, v in log_dict.items() if k in requested_fields}
            
            log_responses.append(log_dict)
        
        # Return with pagination metadata
        return {
            "logs": log_responses,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }

@router.post("/callback/{callback_token}", response_model=Dict[str, str])
async def handle_async_callback(
    callback_token: str,
    callback_data: CallbackData,
    db: Session = Depends(get_db)
):
    """Handle async callback from external service."""
    # Find the callback across all tenant schemas
    # This is a special endpoint that doesn't require authentication

    callback = None
    schema_name = None

    if is_sqlite:
        # SQLite: All data in one database, just query directly
        callback = db.query(AsyncCallback).filter(
            AsyncCallback.callback_token == callback_token,
            AsyncCallback.status == 'pending'
        ).first()
        schema_name = 'default'
    else:
        # PostgreSQL: Get all tenant schemas and search
        tenants = db.execute(
            text(f"SELECT schema_name FROM {table_ref('tenants')} WHERE status = 'active'")
        ).fetchall()

        # Search for callback in each tenant schema
        for tenant in tenants:
            with get_tenant_db(tenant[0]) as tenant_db:
                callback = tenant_db.query(AsyncCallback).filter(
                    AsyncCallback.callback_token == callback_token,
                    AsyncCallback.status == 'pending'
                ).first()

                if callback:
                    schema_name = tenant[0]
                    break
    
    if not callback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Callback token not found or already processed"
        )
    
    # Update callback
    with get_tenant_db(schema_name) as tenant_db:
        callback = tenant_db.query(AsyncCallback).filter(
            AsyncCallback.callback_token == callback_token
        ).first()
        
        callback.status = 'completed'
        callback.completed_at = datetime.utcnow()
        callback.response_data = callback_data.response_data
        
        # Update execution status
        execution = tenant_db.query(FlowExecution).filter(
            FlowExecution.execution_id == callback.execution_id
        ).first()
        
        if execution and execution.status == ExecutionStatus.PAUSED:
            # Resume execution
            execution.status = ExecutionStatus.RUNNING
            
            # Log the callback
            log = ExecutionLog(
                execution_id=execution.execution_id,
                step_id=callback.step_id,
                level='info',
                message=f'Async callback received for step {callback.step_id}',
                data={'callback_status': callback_data.status, 'response': callback_data.response_data}
            )
            tenant_db.add(log)
        
        tenant_db.commit()
    
    # TODO: Trigger execution engine to continue processing
    
    return {"message": "Callback processed successfully"}

@router.get("/stats/summary")
async def get_execution_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get execution statistics for the tenant."""
    schema_name = get_tenant_schema(current_user, db)
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    with get_tenant_db(schema_name) as tenant_db:
        # Get execution counts by status - filter by tenant
        status_counts = {}
        for status in ExecutionStatus:
            count = tenant_db.query(FlowExecution).join(Flow).filter(
                Flow.tenant_id == current_user.tenant_id,  # CRITICAL: Filter by tenant
                FlowExecution.status == status,
                FlowExecution.started_at >= start_date
            ).count()
            status_counts[status.value] = count
        
        # Get total executions - filter by tenant
        total = tenant_db.query(FlowExecution).join(Flow).filter(
            Flow.tenant_id == current_user.tenant_id,  # CRITICAL: Filter by tenant
            FlowExecution.started_at >= start_date
        ).count()
        
        # Get average execution time for completed flows - filter by tenant
        completed_executions = tenant_db.query(FlowExecution).join(Flow).filter(
            Flow.tenant_id == current_user.tenant_id,  # CRITICAL: Filter by tenant
            FlowExecution.status == ExecutionStatus.COMPLETED,
            FlowExecution.started_at >= start_date,
            FlowExecution.completed_at.isnot(None)
        ).all()
        
        avg_execution_time = None
        if completed_executions:
            total_time = sum(
                (exec.completed_at - exec.started_at).total_seconds()
                for exec in completed_executions
            )
            avg_execution_time = total_time / len(completed_executions)
        
        # Get most active flows - filter by tenant
        flow_execution_counts = tenant_db.execute(
            text("""
                SELECT f.flow_id, f.flow_name, COUNT(fe.execution_id) as execution_count
                FROM flows f
                LEFT JOIN flow_executions fe ON f.flow_id = fe.flow_id
                WHERE f.tenant_id = :tenant_id
                  AND fe.started_at >= :start_date
                GROUP BY f.flow_id, f.flow_name
                ORDER BY execution_count DESC
                LIMIT 5
            """),
            {"tenant_id": current_user.tenant_id, "start_date": start_date}
        ).fetchall()
        
        most_active_flows = [
            {
                "flow_id": row[0],
                "flow_name": row[1],
                "execution_count": row[2]
            }
            for row in flow_execution_counts
        ]
        
        return {
            "period_days": days,
            "total_executions": total,
            "status_breakdown": status_counts,
            "average_execution_time_seconds": avg_execution_time,
            "most_active_flows": most_active_flows
        }

@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a running execution."""
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit cancelling executions"
        )
    
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        execution = tenant_db.query(FlowExecution).join(Flow).filter(
            FlowExecution.execution_id == execution_id,
            Flow.tenant_id == current_user.tenant_id  # CRITICAL: Ensure execution belongs to current tenant
        ).first()
        
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        
        if execution.status not in [ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel execution with status {execution.status.value}"
            )
        
        # Update execution status
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = datetime.utcnow()
        
        # Add cancellation log
        log = ExecutionLog(
            execution_id=execution.execution_id,
            step_id=execution.current_step,
            level='warning',
            message='Execution cancelled by user',
            data={'cancelled_by': current_user.user_id}
        )
        tenant_db.add(log)
        
        tenant_db.commit()
        
        # TODO: Signal execution engine to stop processing
        
        return {"message": "Execution cancelled successfully"}

@router.post("/{execution_id}/step")
async def step_debug_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Step to the next node in debug mode using state-based approach."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Step endpoint called for execution {execution_id}")
    
    # Get tenant info
    from api.flows import get_tenant_info
    schema_name, tenant_id = get_tenant_info(current_user, db)
    
    # Import the state-based debug manager
    from services.debug_execution_manager import DebugExecutionManager
    
    try:
        # Execute the next step
        result = await DebugExecutionManager.execute_next_step(
            tenant_schema=schema_name,
            tenant_id=tenant_id,
            execution_id=execution_id
        )
        
        logger.info(f"Step executed successfully for {execution_id}: {result}")
        
        # Handle case where execution is already completed
        if result.get("status") == "completed" and "message" in result:
            return {
                "success": True,
                "status": "completed",
                "current_node": None,
                "executed_nodes": [],
                "message": result.get("message", "Execution completed")
            }
        
        return {
            "success": True,
            "status": result["status"],
            "current_node": result.get("current_node"),
            "executed_nodes": result.get("executed_nodes", []),
            "last_output": result.get("last_output"),
            "message": result.get("message", "Step executed successfully")
        }
    except ValueError as e:
        logger.warning(f"Failed to execute step for {execution_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error executing step for {execution_id}: {e}", exc_info=True)
        # Check if it's a node execution error (which is expected in debug mode)
        error_msg = str(e)
        if "execution failed" in error_msg or "API Error" in error_msg:
            # This is a normal execution error, return it as part of the response
            return {
                "success": False,
                "status": "error",
                "error": error_msg,
                "message": f"Node execution failed: {error_msg}"
            }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute step"
        )

@router.post("/{execution_id}/resume")
async def resume_debug_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resume execution in debug mode (run to completion)."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Resume endpoint called for execution {execution_id}")
    
    # Get tenant info
    from api.flows import get_tenant_info
    schema_name, tenant_id = get_tenant_info(current_user, db)
    
    # Import the state-based debug manager
    from services.debug_execution_manager import DebugExecutionManager
    
    # Get current debug state
    debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id, tenant_id)
    if not debug_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No debug session found for this execution"
        )
    
    if debug_state.get('status') == 'completed':
        return {"message": "Execution already completed", "status": "completed"}
    
    # Execute all remaining steps until completion
    steps_executed = 0
    max_steps = 100  # Safety limit
    
    try:
        while debug_state.get('status') != 'completed' and steps_executed < max_steps:
            result = await DebugExecutionManager.execute_next_step(
                tenant_schema=schema_name,
                tenant_id=tenant_id,
                execution_id=execution_id
            )
            steps_executed += 1
            debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id, tenant_id)
            
            if result.get('status') == 'completed':
                break
        
        logger.info(f"Execution resumed and completed {steps_executed} steps for {execution_id}")
        
        return {
            "message": "Execution resumed and completed",
            "steps_executed": steps_executed,
            "status": debug_state.get('status', 'unknown')
        }
    except Exception as e:
        logger.error(f"Error resuming execution {execution_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume execution"
        )

@router.post("/{execution_id}/stop")
async def stop_debug_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop a debug execution."""
    # Reuse the cancel endpoint logic
    return await cancel_execution(execution_id, current_user, db)

@router.post("/{execution_id}/transform/step-into")
async def step_into_transform(
    execution_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Step into transform node for line-by-line debugging."""
    try:
        from api.flows import get_tenant_info
        from services.debug_coordinator import debug_coordinator
        
        schema_name, tenant_id = get_tenant_info(current_user, db)
        node_id = request.get('node_id')
        
        if not node_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_id is required"
            )
        
        # Set transform debug mode
        if not debug_coordinator.session_exists(execution_id):
            debug_coordinator.create_session(execution_id)
        
        debug_coordinator.set_transform_debug_mode(execution_id, node_id, 'step_into')
        
        return {"message": "Transform debug mode enabled", "node_id": node_id}
        
    except Exception as e:
        logger.error(f"Error enabling transform debug: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{execution_id}/transform/step")
async def step_transform_line(
    execution_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Step to next line in transform debug mode."""
    try:
        from api.flows import get_tenant_info
        from services.debug_execution_manager import DebugExecutionManager
        
        schema_name, tenant_id = get_tenant_info(current_user, db)
        node_id = request.get('node_id')
        
        if not node_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_id is required"
            )
        
        # Execute next line
        result = await DebugExecutionManager.step_transform_line(
            schema_name, tenant_id, execution_id, node_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error stepping transform line: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{execution_id}/transform/continue")
async def continue_transform(
    execution_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Continue transform execution to completion."""
    try:
        from api.flows import get_tenant_info
        from services.debug_execution_manager import DebugExecutionManager
        
        schema_name, tenant_id = get_tenant_info(current_user, db)
        node_id = request.get('node_id')
        
        if not node_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_id is required"
            )
        
        # Continue execution
        result = await DebugExecutionManager.continue_transform(
            schema_name, tenant_id, execution_id, node_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error continuing transform: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{execution_id}/transform/breakpoint")
async def set_transform_breakpoint(
    execution_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set a breakpoint in transform code."""
    try:
        from services.debug_execution_manager import DebugExecutionManager
        
        node_id = request.get('node_id')
        line_number = request.get('line_number')
        action = request.get('action', 'set')  # set or clear
        
        if not node_id or line_number is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_id and line_number are required"
            )
        
        if action == 'set':
            result = await DebugExecutionManager.set_transform_breakpoint(
                execution_id, node_id, line_number
            )
        else:
            result = await DebugExecutionManager.clear_transform_breakpoint(
                execution_id, node_id, line_number
            )
        
        return {"success": result, "action": action, "line_number": line_number}
        
    except Exception as e:
        logger.error(f"Error setting transform breakpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{execution_id}/re-execute-node")
async def re_execute_debug_node(
    execution_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-execute a specific node with updated configuration in debug mode."""
    try:
        # Get tenant info
        from api.flows import get_tenant_info
        schema_name, tenant_id = get_tenant_info(current_user, db)
        
        # Import the state-based debug manager
        from services.debug_execution_manager import DebugExecutionManager
        
        # Get current debug state
        debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id)
        if not debug_state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No debug session found for this execution"
            )
        
        node_id = request.get('node_id')
        updated_config = request.get('config', {})
        
        if not node_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_id is required"
            )
        
        # Ensure debug session exists in coordinator
        DebugExecutionManager.ensure_debug_session(execution_id)
        
        # Update node configuration in debug coordinator
        if not debug_coordinator.session_exists(execution_id):
            debug_coordinator.create_session(execution_id)
        
        success = debug_coordinator.update_node_config(
            execution_id, node_id, updated_config, {}
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update node configuration"
            )
        
        # Set the current node to the one we want to re-execute
        debug_state['current_node'] = node_id
        debug_state['status'] = 'waiting_for_step'
        
        # Remove the node from executed_nodes if it's there
        if node_id in debug_state.get('executed_nodes', []):
            debug_state['executed_nodes'].remove(node_id)
        
        # CRITICAL: Clear the output of the node being re-executed FIRST
        # This ensures it generates fresh output when re-executed
        if node_id in debug_state.get('node_outputs', {}):
            logger.info(f"Clearing output for re-executed node {node_id}, previous output was: {debug_state['node_outputs'][node_id]}")
            del debug_state['node_outputs'][node_id]
            logger.info(f"Node {node_id} output cleared successfully")
        
        # Clear outputs of downstream nodes that depend on this node
        # This ensures they will use the updated output when they re-execute
        flow_definition = debug_state.get('flow_definition', {})
        edges = flow_definition.get('edges', [])
        
        # Find all downstream nodes
        downstream_nodes = set()
        nodes_to_check = [node_id]
        while nodes_to_check:
            current = nodes_to_check.pop(0)
            for edge in edges:
                if edge['source'] == current and edge['target'] not in downstream_nodes:
                    downstream_nodes.add(edge['target'])
                    nodes_to_check.append(edge['target'])
        
        # Clear ONLY outputs for downstream nodes, and track them for re-execution
        # Also remove them from executed_nodes so they can be re-executed with fresh data
        first_downstream = None
        for downstream_node in downstream_nodes:
            if downstream_node in debug_state.get('node_outputs', {}):
                logger.info(f"Clearing output for downstream node {downstream_node}")
                del debug_state['node_outputs'][downstream_node]
            if downstream_node in debug_state.get('executed_nodes', []):
                debug_state['executed_nodes'].remove(downstream_node)
                if first_downstream is None:
                    # Track the first downstream node to potentially set as next
                    for edge in edges:
                        if edge['source'] == node_id and edge['target'] == downstream_node:
                            first_downstream = downstream_node
                            break
        
        # IMPORTANT: Also clear the context_data to force downstream nodes to use the new output
        # The context_data is what gets passed between nodes, so we need to ensure it's cleared
        if 'context_data' in debug_state:
            logger.info(f"Clearing context_data to ensure downstream nodes use updated output")
            # We'll let the re-executed node set the new context_data
            debug_state['context_data'] = {}
        
        # Clear any global variables that might have been set by downstream nodes
        # This ensures transforms don't use stale global variable values
        if 'variables' in debug_state:
            # Reset to original trigger variables if available
            trigger_data = debug_state.get('trigger_data', {})
            if 'variables' in trigger_data:
                debug_state['variables'] = trigger_data['variables'].copy()
                logger.info(f"Reset global variables to trigger values: {list(debug_state['variables'].keys())}")
        
        # Send WebSocket notification to clear downstream node results in UI
        from services.websocket_manager import manager as ws_manager
        await ws_manager.send_execution_update(
            execution_id=execution_id,
            tenant_id=tenant_id,
            update_data={
                'type': 'clear_downstream_nodes',
                'node_id': node_id,
                'downstream_nodes': list(downstream_nodes)
            }
        )
        
        logger.info(f"Re-executing node {node_id}, cleared outputs for {len(downstream_nodes)} downstream nodes: {downstream_nodes}")
        
        # Save the updated state
        DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, tenant_id)
        
        # If re_execute is True, execute the node immediately
        if re_execute:
            # Execute the node with updated configuration
            result = await DebugExecutionManager.execute_next_step(
                tenant_schema=schema_name,
                tenant_id=tenant_id,
                execution_id=execution_id
            )
            
            return {
                "success": True,
                "message": f"Node {node_id} re-executed with updated configuration",
                "result": result
            }
        else:
            # Just update the configuration without executing
            return {
                "success": True,
                "message": f"Node {node_id} configuration updated. Ready to re-execute.",
                "current_node": node_id,
                "downstream_cleared": list(downstream_nodes)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error re-executing debug node: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to re-execute node"
        )

@router.post("/{execution_id}/update-node")
async def update_debug_node(
    execution_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update node configuration during debug and optionally re-execute."""
    try:
        # Get tenant schema
        schema_name = get_tenant_schema(current_user, db)
        
        # Verify execution exists, belongs to current tenant, and is in debug mode
        with get_tenant_db(schema_name) as tenant_db:
            execution = tenant_db.query(FlowExecution).join(Flow).filter(
                FlowExecution.execution_id == execution_id,
                Flow.tenant_id == current_user.tenant_id  # CRITICAL: Ensure execution belongs to current tenant
            ).first()
            
            if not execution:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Execution not found"
                )
            
            # Check if execution is in debug mode
            execution_data = execution.execution_data or {}
        if not execution_data.get('debug_mode'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution is not in debug mode"
            )
        
        node_id = request.get('node_id')
        updated_config = request.get('config', {})
        re_execute = request.get('re_execute', False)
        update_variables = request.get('variables', {})
        
        if not node_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_id is required"
            )
        
        # Ensure debug session exists (it might have been lost or not created)
        if not debug_coordinator.session_exists(execution_id):
            logger.info(f"Creating debug session for execution {execution_id}")
            debug_coordinator.create_session(execution_id)
        
        # Update node configuration in debug session
        success = debug_coordinator.update_node_config(
            execution_id, node_id, updated_config, update_variables
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update node configuration"
            )
        
        # If re-execute is requested, we need to handle it properly for state-based debug mode
        if re_execute:
            # Get tenant info
            from api.flows import get_tenant_info
            schema_name, tenant_id = get_tenant_info(current_user, db)
            
            # Import the state-based debug manager
            from services.debug_execution_manager import DebugExecutionManager
            
            # Get current debug state
            debug_state = DebugExecutionManager.get_debug_state(schema_name, execution_id, tenant_id)
            if debug_state:
                # State-based debug mode - set node as current and execute
                debug_state['current_node'] = node_id
                debug_state['status'] = 'waiting_for_step'
                
                # Remove the node from executed_nodes if it's there to allow re-execution
                if node_id in debug_state.get('executed_nodes', []):
                    debug_state['executed_nodes'].remove(node_id)
                
                # CRITICAL: Clear the output of the node being re-executed FIRST
                # This ensures it generates fresh output when re-executed
                if node_id in debug_state.get('node_outputs', {}):
                    logger.info(f"Clearing output for re-executed node {node_id}")
                    del debug_state['node_outputs'][node_id]
                
                # Clear outputs of downstream nodes that depend on this node
                # This ensures they will use the updated output when they re-execute
                flow_definition = debug_state.get('flow_definition', {})
                edges = flow_definition.get('edges', [])
                
                # Find all downstream nodes
                downstream_nodes = set()
                nodes_to_check = [node_id]
                while nodes_to_check:
                    current = nodes_to_check.pop(0)
                    for edge in edges:
                        if edge['source'] == current and edge['target'] not in downstream_nodes:
                            downstream_nodes.add(edge['target'])
                            nodes_to_check.append(edge['target'])
                
                # Clear outputs for downstream nodes and remove from executed_nodes
                # This allows them to be re-executed with fresh data
                for downstream_node in downstream_nodes:
                    if downstream_node in debug_state.get('node_outputs', {}):
                        logger.info(f"Clearing output for downstream node {downstream_node}")
                        del debug_state['node_outputs'][downstream_node]
                    if downstream_node in debug_state.get('executed_nodes', []):
                        debug_state['executed_nodes'].remove(downstream_node)
                
                # Clear any global variables that might have been set by downstream nodes
                # This ensures transforms don't use stale global variable values
                if 'variables' in debug_state:
                    # Reset to original trigger variables if available
                    trigger_data = debug_state.get('trigger_data', {})
                    if 'variables' in trigger_data:
                        debug_state['variables'] = trigger_data['variables'].copy()
                        logger.info(f"Reset global variables to trigger values: {list(debug_state['variables'].keys())}")
                
                logger.info(f"Re-executing node {node_id}, cleared outputs for {len(downstream_nodes)} downstream nodes: {downstream_nodes}")
                
                # Save the updated state
                DebugExecutionManager.save_debug_state(schema_name, execution_id, debug_state, tenant_id)
                
                # Execute the node with updated configuration
                result = await DebugExecutionManager.execute_next_step(
                    tenant_schema=schema_name,
                    tenant_id=tenant_id,
                    execution_id=execution_id
                )
                
                return {
                    "success": True,
                    "message": f"Node {node_id} re-executed with updated configuration",
                    "result": result
                }
            else:
                # Regular debug mode - send step signal
                debug_coordinator.send_step_signal(execution_id)
                return {
                    "success": True,
                    "message": f"Node {node_id} configuration updated",
                    "re_execute": re_execute
                }
        
        return {
            "success": True,
            "message": f"Node {node_id} configuration updated",
            "re_execute": re_execute
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating debug node: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update node configuration"
        )