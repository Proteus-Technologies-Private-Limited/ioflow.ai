"""
Human in the Loop (HITL) API Routes.
Handles workflow role management and task operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import Optional, List
from datetime import datetime
import uuid
import logging

from db.database import get_db, get_tenant_db
from db.models import (
    User, HITLRole, HITLUserRole, HITLTask, HITLTaskAssignment,
    FlowExecution, Flow, ExecutionStatus
)
from core.auth_utils import get_current_user_required as get_current_user
from api.flows import get_tenant_schema
from schemas.hitl_schemas import (
    HITLRoleCreate, HITLRoleUpdate, HITLRoleResponse,
    HITLUserRoleAssign, HITLRoleUserResponse,
    HITLTaskResponse, HITLTaskAssignmentResponse,
    HITLTaskCompleteRequest, HITLTaskReassignRequest,
    HITLTaskListResponse, HITLTaskStatsResponse,
)
from services.hitl_service import hitl_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hitl", tags=["hitl"])


# ============================================================================
# Workflow Role Management
# ============================================================================

@router.post("/roles", response_model=HITLRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: HITLRoleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new workflow role for the tenant."""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN'):
        raise HTTPException(status_code=403, detail="Only admins can create workflow roles")

    # Check for duplicate name
    existing = db.query(HITLRole).filter(
        HITLRole.tenant_id == current_user.tenant_id,
        HITLRole.role_name == role_data.role_name,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Role '{role_data.role_name}' already exists")

    role = HITLRole(
        role_id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        role_name=role_data.role_name,
        role_description=role_data.role_description,
        created_by=current_user.user_id,
    )
    db.add(role)
    db.commit()
    db.refresh(role)

    return HITLRoleResponse(
        role_id=role.role_id,
        tenant_id=role.tenant_id,
        role_name=role.role_name,
        role_description=role.role_description,
        created_by=role.created_by,
        created_at=role.created_at,
        is_active=role.is_active,
        user_count=0,
    )


@router.get("/roles", response_model=List[HITLRoleResponse])
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all workflow roles for the tenant."""
    roles = db.query(HITLRole).filter(
        HITLRole.tenant_id == current_user.tenant_id,
        HITLRole.is_active == True,
    ).order_by(HITLRole.role_name).all()

    result = []
    for role in roles:
        user_count = db.query(HITLUserRole).filter(
            HITLUserRole.hitl_role_id == role.role_id
        ).count()
        result.append(HITLRoleResponse(
            role_id=role.role_id,
            tenant_id=role.tenant_id,
            role_name=role.role_name,
            role_description=role.role_description,
            created_by=role.created_by,
            created_at=role.created_at,
            is_active=role.is_active,
            user_count=user_count,
        ))
    return result


@router.put("/roles/{role_id}", response_model=HITLRoleResponse)
async def update_role(
    role_id: str,
    role_data: HITLRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a workflow role."""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN'):
        raise HTTPException(status_code=403, detail="Only admins can update workflow roles")

    role = db.query(HITLRole).filter(
        HITLRole.role_id == role_id,
        HITLRole.tenant_id == current_user.tenant_id,
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role_data.role_name is not None:
        role.role_name = role_data.role_name
    if role_data.role_description is not None:
        role.role_description = role_data.role_description
    if role_data.is_active is not None:
        role.is_active = role_data.is_active

    db.commit()
    db.refresh(role)

    user_count = db.query(HITLUserRole).filter(
        HITLUserRole.hitl_role_id == role.role_id
    ).count()

    return HITLRoleResponse(
        role_id=role.role_id,
        tenant_id=role.tenant_id,
        role_name=role.role_name,
        role_description=role.role_description,
        created_by=role.created_by,
        created_at=role.created_at,
        is_active=role.is_active,
        user_count=user_count,
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate a workflow role."""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN'):
        raise HTTPException(status_code=403, detail="Only admins can delete workflow roles")

    role = db.query(HITLRole).filter(
        HITLRole.role_id == role_id,
        HITLRole.tenant_id == current_user.tenant_id,
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role.is_active = False
    db.commit()


@router.post("/roles/{role_id}/users", status_code=status.HTTP_201_CREATED)
async def assign_users_to_role(
    role_id: str,
    data: HITLUserRoleAssign,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign users to a workflow role."""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN'):
        raise HTTPException(status_code=403, detail="Only admins can assign users to workflow roles")

    role = db.query(HITLRole).filter(
        HITLRole.role_id == role_id,
        HITLRole.tenant_id == current_user.tenant_id,
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    added = 0
    for uid in data.user_ids:
        # Check user exists and belongs to same tenant
        user = db.query(User).filter(
            User.user_id == uid,
            User.tenant_id == current_user.tenant_id,
        ).first()
        if not user:
            continue

        # Check if already assigned
        existing = db.query(HITLUserRole).filter(
            HITLUserRole.user_id == uid,
            HITLUserRole.hitl_role_id == role_id,
        ).first()
        if existing:
            continue

        user_role_record = HITLUserRole(
            id=str(uuid.uuid4()),
            user_id=uid,
            hitl_role_id=role_id,
            tenant_id=current_user.tenant_id,
            assigned_by=current_user.user_id,
        )
        db.add(user_role_record)
        added += 1

    db.commit()
    return {"message": f"{added} user(s) assigned to role", "added": added}


@router.delete("/roles/{role_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_role(
    role_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a user from a workflow role."""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN'):
        raise HTTPException(status_code=403, detail="Only admins can manage workflow role assignments")

    record = db.query(HITLUserRole).filter(
        HITLUserRole.user_id == user_id,
        HITLUserRole.hitl_role_id == role_id,
        HITLUserRole.tenant_id == current_user.tenant_id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="User role assignment not found")

    db.delete(record)
    db.commit()


@router.get("/roles/{role_id}/users", response_model=List[HITLRoleUserResponse])
async def list_role_users(
    role_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List users assigned to a workflow role."""
    role = db.query(HITLRole).filter(
        HITLRole.role_id == role_id,
        HITLRole.tenant_id == current_user.tenant_id,
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    user_roles = db.query(HITLUserRole).filter(
        HITLUserRole.hitl_role_id == role_id
    ).all()

    result = []
    for ur in user_roles:
        user = db.query(User).filter(User.user_id == ur.user_id).first()
        if user:
            result.append(HITLRoleUserResponse(
                user_id=user.user_id,
                user_name=user.user_name,
                email=user.email,
                assigned_at=ur.assigned_at,
            ))
    return result


@router.get("/users/{user_id}/roles", response_model=List[HITLRoleResponse])
async def list_user_workflow_roles(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List workflow roles assigned to a specific user."""
    user_roles = db.query(HITLUserRole).filter(
        HITLUserRole.user_id == user_id,
        HITLUserRole.tenant_id == current_user.tenant_id,
    ).all()

    result = []
    for ur in user_roles:
        role = db.query(HITLRole).filter(
            HITLRole.role_id == ur.hitl_role_id,
            HITLRole.is_active == True,
        ).first()
        if role:
            user_count = db.query(HITLUserRole).filter(
                HITLUserRole.hitl_role_id == role.role_id
            ).count()
            result.append(HITLRoleResponse(
                role_id=role.role_id,
                tenant_id=role.tenant_id,
                role_name=role.role_name,
                role_description=role.role_description,
                created_by=role.created_by,
                created_at=role.created_at,
                is_active=role.is_active,
                user_count=user_count,
            ))
    return result


# ============================================================================
# HITL Task Management
# ============================================================================

def _build_task_response(task: HITLTask, db: Session, include_assignments: bool = True) -> HITLTaskResponse:
    """Build a task response with enriched data."""
    assignments = []
    if include_assignments:
        for a in task.assignments:
            name = None
            if a.assignee_type == 'user':
                user = db.query(User).filter(User.user_id == a.assignee_id).first()
                name = user.user_name if user else None
            elif a.assignee_type == 'hitl_role':
                role = db.query(HITLRole).filter(HITLRole.role_id == a.assignee_id).first()
                name = role.role_name if role else None
            assignments.append(HITLTaskAssignmentResponse(
                id=a.id,
                assignee_type=a.assignee_type,
                assignee_id=a.assignee_id,
                assignee_name=name,
                notified_at=a.notified_at,
            ))

    # Get flow name
    flow_name = None
    if task.task_metadata and task.task_metadata.get('flow_name'):
        flow_name = task.task_metadata['flow_name']
    else:
        flow = db.query(Flow).filter(Flow.flow_id == task.flow_id).first()
        if flow:
            flow_name = flow.flow_name

    # Get completed_by name
    completed_by_name = None
    if task.completed_by:
        completer = db.query(User).filter(User.user_id == task.completed_by).first()
        if completer:
            completed_by_name = completer.user_name

    return HITLTaskResponse(
        task_id=task.task_id,
        tenant_id=task.tenant_id,
        execution_id=task.execution_id,
        flow_id=task.flow_id,
        node_id=task.node_id,
        task_type=task.task_type,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        input_data=task.input_data,
        display_config=task.display_config,
        response_data=task.response_data,
        response_action=task.response_action,
        completed_by=task.completed_by,
        completed_at=task.completed_at,
        created_at=task.created_at,
        timeout_at=task.timeout_at,
        escalation_level=task.escalation_level,
        metadata=task.task_metadata,
        assignments=assignments,
        flow_name=flow_name,
        completed_by_name=completed_by_name,
    )


@router.get("/tasks", response_model=HITLTaskListResponse)
async def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """List HITL tasks assigned to the current user."""
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        tasks, total = hitl_service.get_user_tasks(
            user_id=current_user.user_id,
            tenant_id=current_user.tenant_id,
            db=tenant_db,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

        task_responses = [_build_task_response(t, tenant_db) for t in tasks]

    return HITLTaskListResponse(
        tasks=task_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/stats", response_model=HITLTaskStatsResponse)
async def get_task_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get task statistics for the current user."""
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        stats = hitl_service.get_task_stats(
            user_id=current_user.user_id,
            tenant_id=current_user.tenant_id,
            db=tenant_db,
        )

    return HITLTaskStatsResponse(**stats)


@router.get("/tasks/{task_id}", response_model=HITLTaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific HITL task."""
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        task = tenant_db.query(HITLTask).filter(
            HITLTask.task_id == task_id,
            HITLTask.tenant_id == current_user.tenant_id,
        ).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Verify user is assigned (or is admin)
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN'):
            if not hitl_service.is_user_assigned(task, current_user.user_id, tenant_db):
                raise HTTPException(status_code=403, detail="Not assigned to this task")

        return _build_task_response(task, tenant_db)


@router.post("/tasks/{task_id}/complete", response_model=HITLTaskResponse)
async def complete_task(
    task_id: str,
    data: HITLTaskCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete a HITL task and resume flow execution."""
    schema_name = get_tenant_schema(current_user, db)

    try:
        task = await hitl_service.complete_task(
            task_id=task_id,
            user_id=current_user.user_id,
            response_action=data.response_action,
            response_data=data.response_data,
            comment=data.comment,
            tenant_id=current_user.tenant_id,
            schema_name=schema_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    with get_tenant_db(schema_name) as tenant_db:
        task = tenant_db.query(HITLTask).filter(HITLTask.task_id == task_id).first()
        return _build_task_response(task, tenant_db)


@router.post("/tasks/{task_id}/reassign", response_model=HITLTaskResponse)
async def reassign_task(
    task_id: str,
    data: HITLTaskReassignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reassign a HITL task to different users/roles."""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN', 'FLOW_DESIGNER'):
        raise HTTPException(status_code=403, detail="Insufficient permissions to reassign tasks")

    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        try:
            task = hitl_service.reassign_task(
                task_id=task_id,
                tenant_id=current_user.tenant_id,
                assignee_type=data.assignee_type,
                assignee_ids=data.assignee_ids,
                db=tenant_db,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return _build_task_response(task, tenant_db)


@router.post("/tasks/{task_id}/cancel", response_model=HITLTaskResponse)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a HITL task and fail the execution."""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role not in ('INSTANCE_ADMIN', 'TENANT_ADMIN', 'FLOW_DESIGNER'):
        raise HTTPException(status_code=403, detail="Insufficient permissions to cancel tasks")

    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        try:
            task = hitl_service.cancel_task(
                task_id=task_id,
                tenant_id=current_user.tenant_id,
                db=tenant_db,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return _build_task_response(task, tenant_db)


@router.post("/tasks/token/{task_token}/complete")
async def complete_task_by_token(
    task_token: str,
    data: HITLTaskCompleteRequest,
):
    """Complete a HITL task using a secure token (for email-based actions)."""
    # Find the task by token to get the schema
    from db.database import get_db as get_main_db
    db = next(get_main_db())
    try:
        task = db.query(HITLTask).filter(HITLTask.task_token == task_token).first()
        if not task:
            raise HTTPException(status_code=404, detail="Invalid task token")

        from db.models import Tenant
        tenant = db.query(Tenant).filter(Tenant.tenant_id == task.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        schema_name = tenant.schema_name
    finally:
        db.close()

    try:
        await hitl_service.complete_task_by_token(
            task_token=task_token,
            response_action=data.response_action,
            response_data=data.response_data,
            schema_name=schema_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Task completed successfully"}
