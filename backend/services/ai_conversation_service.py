"""
AI Conversation Service
Manages conversation history for AI-generated transformations
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from core.config import settings
from db.database import get_db

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import User
else:
    from db.models import User

from db.ai_conversation_models import (
    AITransformConversation, AITransformMessage, AITransformSnapshot, ConversationStatus
)

logger = logging.getLogger(__name__)

class AIConversationService:
    """Service for managing AI transformation conversation history"""
    
    def __init__(self, user_id: str, db: Session):
        self.user_id = user_id
        self.db = db
        
        # Get user and tenant info
        self.user = db.query(User).filter(User.user_id == user_id).first()
        if not self.user:
            raise ValueError(f"User not found: {user_id}")
        
        self.tenant_id = self.user.tenant_id
        if not self.tenant_id:
            raise ValueError(f"User has no tenant: {user_id}")
    
    def get_or_create_conversation(self, flow_id: str, node_id: str, 
                                 flow_name: str = None, node_name: str = None,
                                 initial_context: Dict = None) -> AITransformConversation:
        """Get existing conversation or create new one for a transform node"""
        
        # Try to find existing active conversation
        conversation = self.db.query(AITransformConversation).filter(
            and_(
                AITransformConversation.user_id == self.user_id,
                AITransformConversation.flow_id == flow_id,
                AITransformConversation.node_id == node_id,
                AITransformConversation.status == ConversationStatus.ACTIVE.value
            )
        ).first()
        
        if conversation:
            # Update last activity
            conversation.last_activity_at = datetime.utcnow()
            self.db.commit()
            return conversation
        
        # Create new conversation
        conversation = AITransformConversation(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            flow_id=flow_id,
            node_id=node_id,
            flow_name=flow_name,
            node_name=node_name,
            initial_context=initial_context or {},
            message_count=0
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(f"Created new AI conversation {conversation.conversation_id} for node {node_id}")
        return conversation
    
    def add_user_message(self, conversation_id: str, prompt: str) -> AITransformMessage:
        """Add user prompt message to conversation"""
        
        conversation = self.db.query(AITransformConversation).filter(
            AITransformConversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Get next sequence number
        sequence_number = conversation.message_count + 1
        
        # Create user message
        message = AITransformMessage(
            conversation_id=conversation_id,
            sequence_number=sequence_number,
            message_type='user_prompt',
            content=prompt
        )
        
        self.db.add(message)
        
        # Update conversation
        conversation.message_count = sequence_number
        conversation.last_activity_at = datetime.utcnow()
        
        # Set title from first user message if not set
        if sequence_number == 1 and not conversation.title:
            # Create title from first 50 chars of prompt
            title = prompt[:50].strip()
            if len(prompt) > 50:
                title += "..."
            conversation.title = title
        
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(f"Added user message to conversation {conversation_id}")
        return message
    
    def add_ai_response(self, conversation_id: str, ai_response: Dict[str, Any],
                       ai_provider: str = None, ai_model: str = None,
                       generation_time_ms: int = None, token_count: int = None) -> AITransformMessage:
        """Add AI response message to conversation"""
        
        conversation = self.db.query(AITransformConversation).filter(
            AITransformConversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Get next sequence number
        sequence_number = conversation.message_count + 1
        
        # Create AI response message
        message = AITransformMessage(
            conversation_id=conversation_id,
            sequence_number=sequence_number,
            message_type='ai_response',
            content=ai_response.get('explanation', ''),
            generated_code=ai_response.get('code', ''),
            explanation=ai_response.get('explanation', ''),
            warnings=ai_response.get('warnings', []),
            test_cases=ai_response.get('test_cases', []),
            ai_provider=ai_provider,
            ai_model=ai_model,
            generation_time_ms=generation_time_ms,
            token_count=token_count
        )
        
        self.db.add(message)
        
        # Update conversation
        conversation.message_count = sequence_number
        conversation.last_activity_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(f"Added AI response to conversation {conversation_id}")
        return message
    
    def mark_code_applied(self, message_id: str) -> bool:
        """Mark that generated code from a message was applied"""
        
        message = self.db.query(AITransformMessage).filter(
            AITransformMessage.message_id == message_id
        ).first()
        
        if not message:
            return False
        
        message.was_applied = True
        message.applied_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Marked code applied for message {message_id}")
        return True
    
    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history with messages"""
        
        conversation = self.db.query(AITransformConversation).filter(
            AITransformConversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            return []
        
        # Get messages in sequence order
        messages = self.db.query(AITransformMessage).filter(
            AITransformMessage.conversation_id == conversation_id
        ).order_by(AITransformMessage.sequence_number).limit(limit).all()
        
        result = []
        for message in messages:
            message_data = {
                "message_id": message.message_id,
                "sequence_number": message.sequence_number,
                "message_type": message.message_type,
                "content": message.content,
                "created_at": message.created_at.isoformat() if message.created_at else None
            }
            
            # Add AI-specific fields for AI responses
            if message.message_type == 'ai_response':
                message_data.update({
                    "generated_code": message.generated_code,
                    "explanation": message.explanation,
                    "warnings": message.warnings or [],
                    "test_cases": message.test_cases or [],
                    "ai_provider": message.ai_provider,
                    "ai_model": message.ai_model,
                    "was_applied": message.was_applied,
                    "applied_at": message.applied_at.isoformat() if message.applied_at else None,
                    "generation_time_ms": message.generation_time_ms,
                    "token_count": message.token_count
                })
            
            result.append(message_data)
        
        return result
    
    def get_node_conversations(self, flow_id: str, node_id: str) -> List[Dict[str, Any]]:
        """Get all conversations for a specific transform node"""
        
        conversations = self.db.query(AITransformConversation).filter(
            and_(
                AITransformConversation.user_id == self.user_id,
                AITransformConversation.flow_id == flow_id,
                AITransformConversation.node_id == node_id,
                AITransformConversation.status == ConversationStatus.ACTIVE.value
            )
        ).order_by(desc(AITransformConversation.last_activity_at)).all()
        
        result = []
        for conv in conversations:
            result.append({
                "conversation_id": conv.conversation_id,
                "title": conv.title,
                "message_count": conv.message_count,
                "last_activity_at": conv.last_activity_at.isoformat() if conv.last_activity_at else None,
                "created_at": conv.created_at.isoformat() if conv.created_at else None
            })
        
        return result
    
    def clear_conversation_history(self, conversation_id: str) -> bool:
        """Clear/archive a conversation history"""
        
        conversation = self.db.query(AITransformConversation).filter(
            and_(
                AITransformConversation.conversation_id == conversation_id,
                AITransformConversation.user_id == self.user_id
            )
        ).first()
        
        if not conversation:
            return False
        
        # Archive the conversation instead of deleting
        conversation.status = ConversationStatus.ARCHIVED.value
        self.db.commit()
        
        logger.info(f"Archived conversation {conversation_id}")
        return True
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Permanently delete a conversation"""
        
        conversation = self.db.query(AITransformConversation).filter(
            and_(
                AITransformConversation.conversation_id == conversation_id,
                AITransformConversation.user_id == self.user_id
            )
        ).first()
        
        if not conversation:
            return False
        
        # Delete will cascade to messages due to relationship
        self.db.delete(conversation)
        self.db.commit()
        
        logger.info(f"Deleted conversation {conversation_id}")
        return True
    
    def create_code_snapshot(self, conversation_id: str, transform_code: str,
                           snapshot_name: str = None, description: str = None,
                           message_id: str = None) -> AITransformSnapshot:
        """Create a snapshot of transform code at a specific point"""
        
        conversation = self.db.query(AITransformConversation).filter(
            AITransformConversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        snapshot = AITransformSnapshot(
            conversation_id=conversation_id,
            message_id=message_id,
            snapshot_name=snapshot_name,
            description=description,
            transform_code=transform_code,
            context_snapshot=conversation.initial_context
        )
        
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        
        logger.info(f"Created code snapshot {snapshot.snapshot_id}")
        return snapshot
    
    def get_conversation_stats(self, flow_id: str = None, days: int = 30) -> Dict[str, Any]:
        """Get statistics about AI conversations"""
        
        base_query = self.db.query(AITransformConversation).filter(
            AITransformConversation.user_id == self.user_id
        )
        
        if flow_id:
            base_query = base_query.filter(AITransformConversation.flow_id == flow_id)
        
        # Date filter
        since_date = datetime.utcnow() - timedelta(days=days)
        base_query = base_query.filter(AITransformConversation.created_at >= since_date)
        
        conversations = base_query.all()
        
        total_conversations = len(conversations)
        total_messages = sum(conv.message_count for conv in conversations)
        
        # Count by status
        active_conversations = sum(1 for conv in conversations 
                                 if conv.status == ConversationStatus.ACTIVE.value)
        archived_conversations = sum(1 for conv in conversations 
                                   if conv.status == ConversationStatus.ARCHIVED.value)
        
        return {
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "archived_conversations": archived_conversations,
            "total_messages": total_messages,
            "avg_messages_per_conversation": total_messages / max(total_conversations, 1),
            "days_range": days
        }