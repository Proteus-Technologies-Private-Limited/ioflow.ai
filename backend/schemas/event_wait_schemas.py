"""Pydantic schemas for Event Wait feature."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class EventWaitResponse(BaseModel):
    wait_id: str
    tenant_id: str
    execution_id: str
    flow_id: str
    node_id: str
    app_id: str
    event_name: str
    event_id: Optional[str] = None
    match_mode: str
    correlation_config: Optional[Dict[str, Any]] = None
    callback_token: str
    status: str
    timeout_at: Optional[datetime] = None
    timeout_action: str = 'fail'
    default_data: Optional[Dict[str, Any]] = None
    event_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    matched_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    flow_name: Optional[str] = None
    app_name: Optional[str] = None


class EventWaitCompleteRequest(BaseModel):
    event_data: Dict[str, Any]


class EventWaitListResponse(BaseModel):
    waits: List[EventWaitResponse]
    total: int
    limit: int
    offset: int
