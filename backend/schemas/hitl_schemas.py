"""Pydantic schemas for Human in the Loop (HITL) feature."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# HITL Role Schemas
# ============================================================================

class HITLRoleCreate(BaseModel):
    role_name: str
    role_description: Optional[str] = None

class HITLRoleUpdate(BaseModel):
    role_name: Optional[str] = None
    role_description: Optional[str] = None
    is_active: Optional[bool] = None

class HITLRoleResponse(BaseModel):
    role_id: str
    tenant_id: str
    role_name: str
    role_description: Optional[str] = None
    created_by: str
    created_at: datetime
    is_active: bool
    user_count: Optional[int] = 0

class HITLUserRoleAssign(BaseModel):
    user_ids: List[str]

class HITLRoleUserResponse(BaseModel):
    user_id: str
    user_name: str
    email: str
    assigned_at: datetime


# ============================================================================
# HITL Task Schemas
# ============================================================================

class HITLTaskAssignmentResponse(BaseModel):
    id: str
    assignee_type: str
    assignee_id: str
    assignee_name: Optional[str] = None
    notified_at: Optional[datetime] = None

class HITLTaskResponse(BaseModel):
    task_id: str
    tenant_id: str
    execution_id: str
    flow_id: str
    node_id: str
    task_type: str
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    input_data: Optional[Dict[str, Any]] = None
    display_config: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    response_action: Optional[str] = None
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    timeout_at: Optional[datetime] = None
    escalation_level: int = 0
    metadata: Optional[Dict[str, Any]] = None
    assignments: Optional[List[HITLTaskAssignmentResponse]] = None
    flow_name: Optional[str] = None
    completed_by_name: Optional[str] = None

class HITLTaskCompleteRequest(BaseModel):
    response_action: str  # 'approved', 'rejected', 'edited', 'reviewed'
    response_data: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None

class HITLTaskReassignRequest(BaseModel):
    assignee_type: str  # 'user' or 'hitl_role'
    assignee_ids: List[str]

class HITLTaskListResponse(BaseModel):
    tasks: List[HITLTaskResponse]
    total: int
    limit: int
    offset: int

class HITLTaskStatsResponse(BaseModel):
    pending: int = 0
    completed: int = 0
    expired: int = 0
    escalated: int = 0
    cancelled: int = 0
    urgent: int = 0  # High/critical priority pending tasks
