"""
Collaboration API endpoints for real-time flow editing
"""
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import json
import logging
import uuid

from db.database import get_db, get_tenant_db, get_db_context
from api.auth import get_current_user_ws
from core.auth_utils import get_current_user
from api.flows import get_tenant_schema
from services.collaboration_manager import collaboration_manager
from db.collaboration_models import (
    CollaborationSession, CollaborationParticipant,
    CollaborationEvent, CollaborationMessage, CollaborationInvite,
    CollaborationRole
)
from core.config import settings

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import Flow, FlowExecution, User
else:
    from db.models import Flow, FlowExecution, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/collaborate", tags=["collaboration"])

# Request/Response schemas
from pydantic import BaseModel
from typing import Dict, Any

class CreateSessionRequest(BaseModel):
    duration_hours: int = 24
    allow_anonymous: bool = True
    max_participants: int = 10
    enable_chat: bool = True
    enable_voice: bool = False
    enable_video: bool = False
    origin_url: Optional[str] = None  # Frontend origin for generating share links

class JoinSessionRequest(BaseModel):
    display_name: str
    role: str = "editor"

class InviteRequest(BaseModel):
    email: Optional[str] = None
    role: str = "editor"
    expires_hours: int = 24
    max_uses: int = 1
    origin_url: Optional[str] = None  # Frontend origin for generating invite links

class SessionResponse(BaseModel):
    session_id: str
    flow_id: str
    access_token: str
    share_link: str
    expires_at: datetime
    participant_count: int
    is_active: bool

class ParticipantResponse(BaseModel):
    participant_id: str
    display_name: str
    color: str
    role: str
    joined_at: datetime
    is_online: bool

@router.post("/flows/{flow_id}/invite", response_model=SessionResponse)
async def create_collaboration_session(
    flow_id: str,
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new collaboration session for a flow"""
    try:
        # Get tenant schema
        with get_db_context() as db_ctx:
            schema_name = get_tenant_schema(current_user, db_ctx)
        
        # Verify user has access to the flow
        with get_tenant_db(schema_name) as tenant_db:
            flow = tenant_db.query(Flow).filter(
                Flow.flow_id == flow_id
            ).first()
            
            if not flow:
                raise HTTPException(status_code=404, detail="Flow not found")
            
            # Check permissions (user should be flow creator or have appropriate role)
            from db.models import UserRole
            admin_roles = [UserRole.TENANT_ADMIN, UserRole.INSTANCE_ADMIN]
            if flow.created_by != str(current_user.user_id) and current_user.role not in admin_roles:
                raise HTTPException(status_code=403, detail="Insufficient permissions to create collaboration session")
            
            # Store flow definition for later use
            flow_definition = flow.flow_definition
        
        # Create collaboration session
        session = CollaborationSession(
            flow_id=flow_id,
            tenant_id=current_user.tenant_id,
            created_by=str(current_user.user_id),
            expires_at=datetime.utcnow() + timedelta(hours=request.duration_hours),
            allow_anonymous=request.allow_anonymous,
            max_participants=request.max_participants,
            enable_chat=request.enable_chat,
            enable_voice=request.enable_voice,
            enable_video=request.enable_video,
            initial_flow_snapshot=flow_definition
        )
        
        # Save to database (use main db for collaboration, not tenant db)
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Initialize session in collaboration manager
        await collaboration_manager.create_session(
            flow_id=flow_id,
            tenant_id=current_user.tenant_id,
            created_by=str(current_user.user_id),
            initial_flow_state=flow_definition or {},
            duration=timedelta(hours=request.duration_hours)
        )
        
        # Generate share link - use origin from request or configured server URL
        # Priority: request origin > frontend_url > server_url > base_url > fallback
        if request.origin_url:
            # Use the origin provided by the frontend (current browser location)
            base_url = request.origin_url
        else:
            # Fall back to configured URLs
            base_url = settings.frontend_url or settings.server_url or settings.base_url or 'http://localhost:7001'
        
        # Remove trailing slash if present
        base_url = base_url.rstrip('/')
        share_link = f"{base_url}/collaborate/join?token={session.access_token}"
        
        return SessionResponse(
            session_id=session.session_id,
            flow_id=flow_id,
            access_token=session.access_token,
            share_link=share_link,
            expires_at=session.expires_at,
            participant_count=0,
            is_active=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collaboration session: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/join/{token}")
async def get_session_by_token(
    token: str,
    db: Session = Depends(get_db)
):
    """Get collaboration session details by access token"""
    # Find session by token
    session = db.query(CollaborationSession).filter(
        CollaborationSession.access_token == token,
        CollaborationSession.is_active == True,
        CollaborationSession.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    # Get flow details
    with get_tenant_db(session.tenant_id) as tenant_db:
        flow = tenant_db.query(Flow).filter(
            Flow.flow_id == session.flow_id
        ).first()
    
    return {
        "session_id": session.session_id,
        "flow_id": session.flow_id,
        "flow_name": flow.flow_name if flow else "Unknown",
        "expires_at": session.expires_at,
        "participant_count": session.participant_count,
        "enable_chat": session.enable_chat,
        "enable_voice": session.enable_voice,
        "enable_video": session.enable_video,
        "is_active": session.is_active
    }

@router.post("/session/{session_id}/join")
async def join_collaboration_session(
    session_id: str,
    request: JoinSessionRequest,
    token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Join a collaboration session"""
    # Find session
    session = db.query(CollaborationSession).filter(
        CollaborationSession.session_id == session_id,
        CollaborationSession.is_active == True,
        CollaborationSession.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    # Verify access (either authenticated user or valid token)
    if not current_user and not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if token and token != session.access_token:
        raise HTTPException(status_code=403, detail="Invalid access token")
    
    # Check participant limit
    if session.participant_count >= session.max_participants:
        raise HTTPException(status_code=403, detail="Session is full")
    
    # Create participant record - always create a new one for each connection
    # This allows the same user to join from multiple browser sessions
    # For authenticated users, prefer their actual username over the request display_name
    if current_user:
        display_name = current_user.user_name
    else:
        display_name = request.display_name or "Anonymous"
    
    participant = CollaborationParticipant(
        session_id=session_id,
        user_id=str(current_user.user_id) if current_user else None,
        display_name=display_name,
        email=current_user.email if current_user else None,
        role=CollaborationRole[request.role.upper()],
        color=generate_participant_color()
    )
    
    # Always add as new participant (allows multiple connections per user)
    db.add(participant)
    session.participant_count += 1
    db.commit()
    
    return {
        "participant_id": participant.participant_id,
        "session_id": session_id,
        "display_name": participant.display_name,
        "color": participant.color,
        "role": participant.role.value
    }

@router.get("/session/{session_id}/participants", response_model=List[ParticipantResponse])
async def get_session_participants(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of participants in a collaboration session"""
    # Verify session exists and user has access
    session = db.query(CollaborationSession).filter(
        CollaborationSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get participants
    participants = db.query(CollaborationParticipant).filter(
        CollaborationParticipant.session_id == session_id
    ).all()
    
    # Get active participants from manager
    active_participants = await collaboration_manager.get_active_participants(session_id)
    active_ids = {p["id"] for p in active_participants}
    
    return [
        ParticipantResponse(
            participant_id=p.participant_id,
            display_name=p.display_name,
            color=p.color,
            role=p.role.value,
            joined_at=p.joined_at,
            is_online=p.participant_id in active_ids
        )
        for p in participants
    ]

@router.post("/session/{session_id}/leave")
async def leave_collaboration_session(
    session_id: str,
    participant_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Leave a collaboration session"""
    # Find participant
    participant = db.query(CollaborationParticipant).filter(
        CollaborationParticipant.session_id == session_id,
        CollaborationParticipant.participant_id == participant_id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    # Verify ownership (if authenticated)
    if current_user and participant.user_id and participant.user_id != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Cannot leave session for another user")
    
    # Remove participant record (since we create new ones for each connection)
    db.delete(participant)
    
    # Update session participant count
    session = db.query(CollaborationSession).filter(
        CollaborationSession.session_id == session_id
    ).first()
    if session and session.participant_count > 0:
        session.participant_count -= 1
    
    db.commit()
    
    return {"message": "Successfully left the session"}

@router.post("/session/{session_id}/invite")
async def create_invite(
    session_id: str,
    request: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create an invitation to join a collaboration session"""
    # Verify session exists and user has permission
    session = db.query(CollaborationSession).filter(
        CollaborationSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if user is session creator or has invite permission
    participant = db.query(CollaborationParticipant).filter(
        CollaborationParticipant.session_id == session_id,
        CollaborationParticipant.user_id == str(current_user.user_id)
    ).first()
    
    if session.created_by != str(current_user.user_id) and (not participant or not participant.can_invite):
        raise HTTPException(status_code=403, detail="No permission to create invites")
    
    # Create invite
    invite = CollaborationInvite(
        session_id=session_id,
        invited_by=str(current_user.user_id),
        invited_email=request.email,
        role=CollaborationRole[request.role.upper()],
        expires_at=datetime.utcnow() + timedelta(hours=request.expires_hours),
        max_uses=request.max_uses
    )
    
    db.add(invite)
    db.commit()
    
    # Generate invite link - use origin from request or configured server URL
    # Priority: request origin > frontend_url > server_url > base_url > fallback
    if request.origin_url:
        # Use the origin provided by the frontend (current browser location)
        base_url = request.origin_url
    else:
        # Fall back to configured URLs
        base_url = settings.frontend_url or settings.server_url or settings.base_url or 'http://localhost:7001'
    
    # Remove trailing slash if present
    base_url = base_url.rstrip('/')
    invite_link = f"{base_url}/collaborate/invite?token={invite.invite_token}"
    
    return {
        "invite_id": invite.invite_id,
        "invite_token": invite.invite_token,
        "invite_link": invite_link,
        "expires_at": invite.expires_at,
        "role": invite.role.value
    }

@router.websocket("/ws/{session_id}")
async def collaboration_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    participant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time collaboration"""
    logger.info(f"Collaboration WebSocket connection attempt for session {session_id}")
    
    # Verify session exists and is active
    session = db.query(CollaborationSession).filter(
        CollaborationSession.session_id == session_id,
        CollaborationSession.is_active == True,
        CollaborationSession.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        logger.error(f"Session {session_id} not found or expired")
        await websocket.close(code=4004, reason="Session not found or expired")
        return
    
    # Authenticate participant
    participant = None
    if participant_id:
        participant = db.query(CollaborationParticipant).filter(
            CollaborationParticipant.participant_id == participant_id,
            CollaborationParticipant.session_id == session_id
        ).first()
    
    if not participant:
        # Check if the token is the session's access token (collaboration token)
        if token == session.access_token:
            # This is a collaboration participant joining with the invite token
            # For anonymous collaboration participants, we should have already created
            # the participant when they called the join endpoint
            # But if not, create one now
            if session.allow_anonymous:
                # Create anonymous participant
                participant = CollaborationParticipant(
                    session_id=session_id,
                    user_id=None,
                    display_name="Anonymous",
                    email=None,
                    role=CollaborationRole.EDITOR,
                    color=generate_participant_color()
                )
                db.add(participant)
                session.participant_count += 1
                db.commit()
        else:
            # Try to authenticate with token as JWT/API key
            try:
                current_user = await get_current_user_ws(token, db)
                if current_user:
                    # Auto-create a new participant for authenticated user
                    # Don't reuse existing participant to allow multiple connections
                    participant = CollaborationParticipant(
                        session_id=session_id,
                        user_id=str(current_user.user_id),
                        display_name=current_user.user_name,
                        email=current_user.email,
                        role=CollaborationRole.EDITOR,
                        color=generate_participant_color()
                    )
                    db.add(participant)
                    session.participant_count += 1
                    db.commit()
            except:
                # Check if anonymous access is allowed
                if not session.allow_anonymous:
                    logger.error("Anonymous access not allowed for this session")
                    await websocket.close(code=4001, reason="Authentication required")
                    return
    
    if not participant:
        logger.error("Could not authenticate participant")
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Accept connection
    await websocket.accept()
    
    # Join collaboration session
    await collaboration_manager.join_session(
        websocket=websocket,
        session_id=session_id,
        participant_id=participant.participant_id,
        user_id=participant.user_id,
        display_name=participant.display_name,
        email=participant.email,
        role=participant.role.value,
        color=participant.color
    )
    
    try:
        # Handle messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "operation":
                # Handle flow operation
                await collaboration_manager.handle_operation(websocket, message.get("data", {}))
                
            elif message_type == "cursor_move":
                # Handle cursor movement
                await collaboration_manager.handle_cursor_move(websocket, message.get("position", {}))
                
            elif message_type == "selection_change":
                # Handle selection change
                await collaboration_manager.handle_selection_change(websocket, message.get("selection", {}))
                
            elif message_type == "chat_message":
                # Handle chat message
                await collaboration_manager.handle_chat_message(
                    websocket,
                    message.get("content", ""),
                    message.get("mentions"),
                    message.get("node_references")
                )
                
            elif message_type == "ping":
                # Respond to ping
                await websocket.send_json({"type": "pong"})
                
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
                
    except WebSocketDisconnect:
        await collaboration_manager.leave_session(websocket)
        # Clean up participant record on disconnect
        if participant:
            db.delete(participant)
            if session and session.participant_count > 0:
                session.participant_count -= 1
            db.commit()
    except Exception as e:
        logger.error(f"Collaboration WebSocket error: {e}")
        await collaboration_manager.leave_session(websocket)
        # Clean up participant record on error
        if participant:
            db.delete(participant)
            if session and session.participant_count > 0:
                session.participant_count -= 1
            db.commit()

@router.get("/stats")
async def get_collaboration_stats(
    current_user: User = Depends(get_current_user)
):
    """Get collaboration statistics (admin only)"""
    if current_user.role not in ["INSTANCE_ADMIN", "TENANT_ADMIN"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return collaboration_manager.get_session_stats()

# Helper function
def generate_participant_color():
    """Generate a unique color for a participant"""
    import random
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2',
        '#F8B739', '#52B788', '#E56B6F', '#B56576', '#6D597A'
    ]
    return random.choice(colors)