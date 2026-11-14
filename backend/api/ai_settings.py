"""
AI Settings Management API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging

from db.database import get_db
from core.config import settings
from utils.crypto_utils import encrypt_data, decrypt_data

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import User, UserSettings
else:
    from db.models import User, UserSettings

from db.user_settings_models import UserSettingsHelper, AISettingsData

from schemas.ai_settings_schemas import (
    AIModelConfig, AISettingsResponse, AISettingsUpdate,
    AITransformRequest, AITransformResponse, AITestConnectionResponse,
    AITestConnectionRequest, AIConversationRequest, AIFollowupRequest,
    AIConversationResponse, AIConversationHistoryResponse, AIApplyCodeRequest,
    AIClearConversationRequest, AIConversationSummary, AIConversationMessage,
    AISystemPromptRequest, AISystemPromptResponse
)
from core.auth_utils import get_current_user_required as get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/ai-settings",
    tags=["ai-settings"]
)


@router.get("/", response_model=AISettingsResponse)
async def get_ai_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's AI settings (without sensitive data)"""
    try:
        # Get AI configuration from user_settings table
        ai_config = UserSettingsHelper.get_ai_config(db, current_user.user_id)
        
        return AISettingsResponse(
            provider=ai_config.get('provider'),
            model_name=ai_config.get('model_name'),
            api_endpoint=ai_config.get('api_endpoint'),
            temperature=ai_config.get('model_config', {}).get('temperature'),
            max_tokens=ai_config.get('model_config', {}).get('max_tokens'),
            top_p=ai_config.get('model_config', {}).get('top_p'),
            has_api_key=bool(ai_config.get('api_key_hash')),
            extra_settings=ai_config.get('extra_settings', {}),
            agent_framework=ai_config.get('agent_framework', 'google_adk')
        )

    except Exception as e:
        logger.error(f"Error getting AI settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI settings")


@router.put("/", response_model=AISettingsResponse)
async def update_ai_settings(
    settings_update: AISettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's AI settings"""
    try:
        # Get current AI configuration
        current_config = UserSettingsHelper.get_ai_config(db, current_user.user_id)
        
        # Update fields that are provided
        if settings_update.provider is not None:
            current_config['provider'] = settings_update.provider
        
        if settings_update.model_name is not None:
            current_config['model_name'] = settings_update.model_name
        
        if settings_update.api_key is not None:
            # Encrypt the API key before storing
            current_config['api_key_hash'] = encrypt_data(settings_update.api_key)
        
        if settings_update.api_endpoint is not None:
            current_config['api_endpoint'] = settings_update.api_endpoint
        
        # Update model configuration
        model_config = current_config.get('model_config', {})
        
        if settings_update.temperature is not None:
            model_config['temperature'] = settings_update.temperature
        
        if settings_update.max_tokens is not None:
            model_config['max_tokens'] = settings_update.max_tokens
        
        if settings_update.top_p is not None:
            model_config['top_p'] = settings_update.top_p
        
        current_config['model_config'] = model_config
        
        if settings_update.extra_settings is not None:
            current_config['extra_settings'] = settings_update.extra_settings

        if settings_update.agent_framework is not None:
            current_config['agent_framework'] = settings_update.agent_framework

        # Save updated configuration
        UserSettingsHelper.set_setting(db, current_user.user_id, 'ai_config', current_config)

        return AISettingsResponse(
            provider=current_config.get('provider'),
            model_name=current_config.get('model_name'),
            api_endpoint=current_config.get('api_endpoint'),
            temperature=model_config.get('temperature'),
            max_tokens=model_config.get('max_tokens'),
            top_p=model_config.get('top_p'),
            has_api_key=bool(current_config.get('api_key_hash')),
            extra_settings=current_config.get('extra_settings', {}),
            agent_framework=current_config.get('agent_framework', 'google_adk')
        )
    
    except Exception as e:
        logger.error(f"Error updating AI settings: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update AI settings")


@router.delete("/")
async def delete_ai_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user's AI settings"""
    try:
        # Delete AI configuration from user_settings table
        UserSettingsHelper.delete_setting(db, current_user.user_id, 'ai_config')
        
        return {"message": "AI settings deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting AI settings: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete AI settings")


@router.post("/test-connection", response_model=AITestConnectionResponse)
async def test_ai_connection(
    test_request: AITestConnectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test connection to AI service with provided settings (does not save)"""
    try:
        # Import and test connection using the provided settings
        from services.ai_transformation_service import AITransformationService
        
        # Create a temporary AI service instance with the test settings
        # We'll modify the service to accept temporary settings for testing
        ai_service = AITransformationService(current_user.user_id, db)
        
        # Test connection with the provided settings (not saved settings)
        test_result = await ai_service.test_connection_with_settings(
            provider=test_request.provider,
            model_name=test_request.model_name,
            api_key=test_request.api_key,
            api_endpoint=test_request.api_endpoint,
            temperature=test_request.temperature,
            max_tokens=test_request.max_tokens,
            top_p=test_request.top_p
        )
        
        return AITestConnectionResponse(
            success=test_result['success'],
            message=test_result['message'],
            model_info=test_result.get('model_info')
        )
    
    except Exception as e:
        logger.error(f"Error testing AI connection: {str(e)}")
        return AITestConnectionResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )


@router.post("/generate-transform", response_model=AITransformResponse)
async def generate_transform_code(
    request: AITransformRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate transform code using AI based on natural language description"""
    try:
        # Get AI configuration
        ai_config = UserSettingsHelper.get_ai_config(db, current_user.user_id)
        
        if not ai_config.get('provider') or not ai_config.get('api_key_hash'):
            raise HTTPException(status_code=400, detail="AI provider and API key must be configured")
        
        # Import and use AI service to generate code
        from services.ai_transformation_service import AITransformationService
        
        ai_service = AITransformationService(current_user.user_id, db)
        result = await ai_service.generate_transform_code(
            natural_language_prompt=request.natural_language_prompt,
            input_schema=request.input_schema,
            available_variables=request.available_variables,
            flow_context=request.flow_context
        )
        
        return AITransformResponse(
            generated_code=result['code'],
            explanation=result['explanation'],
            test_cases=result.get('test_cases', []),
            warnings=result.get('warnings', [])
        )
    
    except Exception as e:
        logger.error(f"Error generating transform code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate transform code: {str(e)}")


@router.get("/providers")
async def get_available_providers():
    """Get list of available AI providers and their supported models"""
    from config.models_config import AIModelsConfig

    providers_data = {}
    for provider_id, provider_info in AIModelsConfig.get_providers().items():
        providers_data[provider_id] = {
            "name": provider_info["name"],
            "models": AIModelsConfig.get_provider_models(provider_id),
            "requires_endpoint": provider_info.get("requires_endpoint", False),
            "default_model": provider_info["default_model"],
            "description": provider_info["description"]
        }

    return {"providers": providers_data}


# =============================================
# CONVERSATION HISTORY ENDPOINTS
# =============================================

@router.post("/conversation", response_model=AIConversationResponse)
async def start_ai_conversation(
    request: AIConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start or continue an AI conversation for transform code generation"""
    
    try:
        # Import services
        from services.ai_conversation_service import AIConversationService
        from services.ai_transformation_service import AITransformationService
        
        # Get AI configuration
        ai_config = UserSettingsHelper.get_ai_config(db, current_user.user_id)
        if not ai_config.get('provider') or not ai_config.get('api_key_hash'):
            raise HTTPException(status_code=400, detail="AI provider and API key must be configured")
        
        # Initialize services
        conv_service = AIConversationService(current_user.user_id, db)
        ai_service = AITransformationService(current_user.user_id, db)
        
        # Get or create conversation
        conversation = conv_service.get_or_create_conversation(
            flow_id=request.flow_id,
            node_id=request.node_id,
            flow_name=request.flow_name,
            node_name=request.node_name,
            initial_context={
                "input_schema": request.input_schema,
                "available_variables": request.available_variables,
                "flow_context": request.flow_context,
                "next_node_info": request.next_node_info,
                "custom_system_prompt": request.custom_system_prompt
            }
        )
        
        # Add user message
        user_message = conv_service.add_user_message(
            conversation.conversation_id,
            request.prompt
        )
        
        # Get conversation history for context
        history = conv_service.get_conversation_history(conversation.conversation_id)
        
        # Generate AI response with conversation context
        import time
        start_time = time.time()
        
        # Debug logging for available variables
        node_outputs = request.available_variables.get('node_outputs', {})
        logger.info(f"AI Transform Request - Node outputs: {len(node_outputs)} nodes available: {list(node_outputs.keys())}")
        if node_outputs:
            for node_id, data in list(node_outputs.items())[:2]:  # Log first 2 nodes
                logger.info(f"Node {node_id} output keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
        
        ai_result = await ai_service.generate_transform_code(
            natural_language_prompt=request.prompt,
            input_schema=request.input_schema,
            available_variables=request.available_variables,
            flow_context=request.flow_context,
            conversation_history=history[:-1],  # Exclude the current user message
            next_node_info=request.next_node_info,
            custom_system_prompt=request.custom_system_prompt
        )
        
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        # Add AI response to conversation
        ai_message = conv_service.add_ai_response(
            conversation.conversation_id,
            ai_result,
            ai_provider=ai_config.get('provider'),
            ai_model=ai_config.get('model_name'),
            generation_time_ms=generation_time_ms
        )
        
        # Get updated conversation history
        updated_history = conv_service.get_conversation_history(conversation.conversation_id)
        
        # Convert to response format
        history_messages = []
        for msg in updated_history:
            history_messages.append(AIConversationMessage(
                message_id=msg["message_id"],
                sequence_number=msg["sequence_number"],
                message_type=msg["message_type"],
                content=msg["content"],
                created_at=msg["created_at"],
                generated_code=msg.get("generated_code"),
                explanation=msg.get("explanation"),
                warnings=msg.get("warnings"),
                test_cases=msg.get("test_cases"),
                ai_provider=msg.get("ai_provider"),
                ai_model=msg.get("ai_model"),
                was_applied=msg.get("was_applied"),
                applied_at=msg.get("applied_at"),
                generation_time_ms=msg.get("generation_time_ms")
            ))
        
        return AIConversationResponse(
            conversation_id=conversation.conversation_id,
            message_id=ai_message.message_id,
            generated_code=ai_result["code"],
            explanation=ai_result["explanation"],
            warnings=ai_result.get("warnings", []),
            test_cases=ai_result.get("test_cases", []),
            conversation_history=history_messages
        )
        
    except Exception as e:
        logger.error(f"Error in AI conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process conversation: {str(e)}")


@router.post("/conversation/followup", response_model=AIConversationResponse)
async def followup_ai_conversation(
    request: AIFollowupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a follow-up prompt in an existing conversation"""
    
    try:
        # Import services
        from services.ai_conversation_service import AIConversationService
        from services.ai_transformation_service import AITransformationService
        
        # Get AI configuration
        ai_config = UserSettingsHelper.get_ai_config(db, current_user.user_id)
        if not ai_config.get('provider') or not ai_config.get('api_key_hash'):
            raise HTTPException(status_code=400, detail="AI provider and API key must be configured")
        
        # Initialize services
        conv_service = AIConversationService(current_user.user_id, db)
        ai_service = AITransformationService(current_user.user_id, db)
        
        # Add user follow-up message
        user_message = conv_service.add_user_message(
            request.conversation_id,
            request.followup_prompt
        )
        
        # Get full conversation history
        history = conv_service.get_conversation_history(request.conversation_id)
        
        # Get conversation details for context
        from db.ai_conversation_models import AITransformConversation
        conversation = db.query(AITransformConversation).filter(
            AITransformConversation.conversation_id == request.conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        initial_context = conversation.initial_context or {}
        
        # Generate AI response with full conversation context
        import time
        start_time = time.time()
        
        ai_result = await ai_service.generate_followup_transform_code(
            followup_prompt=request.followup_prompt,
            conversation_history=history[:-1],  # Exclude the current user message
            input_schema=initial_context.get("input_schema", {}),
            available_variables=initial_context.get("available_variables", {}),
            flow_context=initial_context.get("flow_context", {}),
            next_node_info=initial_context.get("next_node_info", {}),
            custom_system_prompt=initial_context.get("custom_system_prompt")
        )
        
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        # Add AI response to conversation
        ai_message = conv_service.add_ai_response(
            request.conversation_id,
            ai_result,
            ai_provider=ai_config.get('provider'),
            ai_model=ai_config.get('model_name'),
            generation_time_ms=generation_time_ms
        )
        
        # Get updated conversation history
        updated_history = conv_service.get_conversation_history(request.conversation_id)
        
        # Convert to response format
        history_messages = []
        for msg in updated_history:
            history_messages.append(AIConversationMessage(
                message_id=msg["message_id"],
                sequence_number=msg["sequence_number"],
                message_type=msg["message_type"],
                content=msg["content"],
                created_at=msg["created_at"],
                generated_code=msg.get("generated_code"),
                explanation=msg.get("explanation"),
                warnings=msg.get("warnings"),
                test_cases=msg.get("test_cases"),
                ai_provider=msg.get("ai_provider"),
                ai_model=msg.get("ai_model"),
                was_applied=msg.get("was_applied"),
                applied_at=msg.get("applied_at"),
                generation_time_ms=msg.get("generation_time_ms")
            ))
        
        return AIConversationResponse(
            conversation_id=request.conversation_id,
            message_id=ai_message.message_id,
            generated_code=ai_result["code"],
            explanation=ai_result["explanation"],
            warnings=ai_result.get("warnings", []),
            test_cases=ai_result.get("test_cases", []),
            conversation_history=history_messages
        )
        
    except Exception as e:
        logger.error(f"Error in AI followup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process followup: {str(e)}")


@router.get("/conversation/{conversation_id}", response_model=AIConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full conversation history"""
    
    try:
        from services.ai_conversation_service import AIConversationService
        from db.ai_conversation_models import AITransformConversation
        
        conv_service = AIConversationService(current_user.user_id, db)
        
        # Get conversation details
        conversation = db.query(AITransformConversation).filter(
            AITransformConversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get conversation history
        history = conv_service.get_conversation_history(conversation_id)
        
        # Convert to response format
        history_messages = []
        for msg in history:
            history_messages.append(AIConversationMessage(
                message_id=msg["message_id"],
                sequence_number=msg["sequence_number"],
                message_type=msg["message_type"],
                content=msg["content"],
                created_at=msg["created_at"],
                generated_code=msg.get("generated_code"),
                explanation=msg.get("explanation"),
                warnings=msg.get("warnings"),
                test_cases=msg.get("test_cases"),
                ai_provider=msg.get("ai_provider"),
                ai_model=msg.get("ai_model"),
                was_applied=msg.get("was_applied"),
                applied_at=msg.get("applied_at"),
                generation_time_ms=msg.get("generation_time_ms")
            ))
        
        return AIConversationHistoryResponse(
            conversation_id=conversation.conversation_id,
            title=conversation.title,
            flow_id=conversation.flow_id,
            node_id=conversation.node_id,
            flow_name=conversation.flow_name,
            node_name=conversation.node_name,
            message_count=conversation.message_count,
            status=conversation.status,
            messages=history_messages,
            created_at=conversation.created_at,
            last_activity_at=conversation.last_activity_at
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")


@router.get("/conversations/{flow_id}/{node_id}")
async def get_node_conversations(
    flow_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for a specific node"""
    
    try:
        from services.ai_conversation_service import AIConversationService
        
        conv_service = AIConversationService(current_user.user_id, db)
        conversations = conv_service.get_node_conversations(flow_id, node_id)
        
        return {
            "flow_id": flow_id,
            "node_id": node_id,
            "conversations": conversations
        }
        
    except Exception as e:
        logger.error(f"Error getting node conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")


@router.post("/conversation/apply-code")
async def apply_generated_code(
    request: AIApplyCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark generated code as applied"""
    
    try:
        from services.ai_conversation_service import AIConversationService
        
        conv_service = AIConversationService(current_user.user_id, db)
        success = conv_service.mark_code_applied(request.message_id)
        
        if success:
            return {"message": "Code marked as applied", "message_id": request.message_id}
        else:
            raise HTTPException(status_code=404, detail="Message not found")
            
    except Exception as e:
        logger.error(f"Error applying code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply code: {str(e)}")


@router.post("/conversation/clear")
async def clear_conversation_history(
    request: AIClearConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear/archive a conversation history"""
    
    try:
        from services.ai_conversation_service import AIConversationService
        
        conv_service = AIConversationService(current_user.user_id, db)
        success = conv_service.clear_conversation_history(request.conversation_id)
        
        if success:
            return {"message": "Conversation history cleared", "conversation_id": request.conversation_id}
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
    except Exception as e:
        logger.error(f"Error clearing conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear conversation: {str(e)}")


@router.post("/system-prompt/preview", response_model=AISystemPromptResponse)
async def preview_system_prompt(
    request: AISystemPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the default system prompt with current context for preview/editing"""
    
    try:
        # Import AI transformation service
        from services.ai_transformation_service import AITransformationService
        
        # Get AI configuration
        ai_config = UserSettingsHelper.get_ai_config(db, current_user.user_id)
        if not ai_config.get('provider'):
            raise HTTPException(status_code=400, detail="AI provider must be configured")
        
        # Initialize AI service (API key not required for system prompt generation)
        ai_service = AITransformationService(current_user.user_id, db)
        
        # Generate the default system prompt
        system_prompt = ai_service.get_default_system_prompt(
            input_schema=request.input_schema,
            available_variables=request.available_variables,
            flow_context=request.flow_context,
            next_node_info=request.next_node_info
        )
        
        # Calculate metrics
        variables_count = len(request.available_variables.get('node_outputs', {})) + len(request.available_variables.get('global', {}))
        next_node_connected = bool(request.next_node_info and request.next_node_info.get('node_type'))
        
        return AISystemPromptResponse(
            system_prompt=system_prompt,
            prompt_length=len(system_prompt),
            variables_count=variables_count,
            next_node_connected=next_node_connected
        )
        
    except Exception as e:
        logger.error(f"Error generating system prompt preview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate system prompt: {str(e)}")


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permanently delete a conversation"""
    
    try:
        from services.ai_conversation_service import AIConversationService
        
        conv_service = AIConversationService(current_user.user_id, db)
        success = conv_service.delete_conversation(conversation_id)
        
        if success:
            return {"message": "Conversation deleted", "conversation_id": conversation_id}
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")


@router.get("/conversation-stats")
async def get_conversation_stats(
    flow_id: Optional[str] = None,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get conversation statistics"""
    
    try:
        from services.ai_conversation_service import AIConversationService
        
        conv_service = AIConversationService(current_user.user_id, db)
        stats = conv_service.get_conversation_stats(flow_id=flow_id, days=days)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting conversation stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")