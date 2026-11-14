"""
WebSocket Streaming Handler for Real-time Agent Responses

Handles WebSocket connections for streaming agent execution updates.
"""

import json
import asyncio
import logging
from typing import Dict, Set, Any
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from agent_pack import get_agent as _pack_agent

logger = logging.getLogger(__name__)


async def verified_caller(token):
    """The User a WebSocket message's token really belongs to, else None.

    Messages carry the caller's JWT (or ``ioflow_`` key) in the body. It used to
    be decoded only to LOOK UP a user id, and a missing/bad token simply ran the
    agent anonymously; now an unverifiable token means no agent run.
    """
    if not token:
        return None
    from db.database import get_db
    from core.auth_utils import authenticate_api_key, authenticate_jwt_token
    db = next(get_db())
    try:
        if str(token).startswith("ioflow_"):
            return await authenticate_api_key(token, db)
        return await authenticate_jwt_token(token, db)
    except Exception:
        return None
    finally:
        db.close()


class StreamingHandler:
    """
    Manages WebSocket connections for streaming agent responses
    """

    def __init__(self, runtime_manager):
        self.runtime_manager = runtime_manager
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.session_websockets: Dict[str, WebSocket] = {}
        # Map WebSocket session IDs to persistent session IDs for user-agent combinations
        self.websocket_to_persistent_session: Dict[str, str] = {}
        # Track Claude Code streaming tasks for cancellation
        self._claude_code_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """
        Accept a new WebSocket connection for a session
        """
        await websocket.accept()

        # Add to active connections
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)
        self.session_websockets[session_id] = websocket

        logger.info(f"WebSocket connected for session {session_id}")

        # Create session if it doesn't exist
        session = self.runtime_manager.session_manager.get_session(session_id)
        if not session:
            # Create a new session
            session = self.runtime_manager.session_manager.create_session(
                session_id=session_id,
                agent_id="",  # Will be set when agent is selected
                model=""  # Will be set when model is selected
            )
            logger.info(f"Created new session {session_id}")

        # Send session info
        await self.send_message(websocket, {
            "type": "session_info",
            "data": session.to_dict()
        })

    async def disconnect(self, websocket: WebSocket, session_id: str):
        """
        Handle WebSocket disconnection
        """
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        if session_id in self.session_websockets and self.session_websockets[session_id] == websocket:
            del self.session_websockets[session_id]

        # Clean up websocket-to-persistent session mapping
        if session_id in self.websocket_to_persistent_session:
            del self.websocket_to_persistent_session[session_id]

        logger.info(f"WebSocket disconnected for session {session_id}")

    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Send a message through WebSocket with proper serialization
        """
        try:
            # Ensure the message is JSON serializable
            import json

            def make_serializable(obj):
                """Recursively convert non-serializable objects"""
                if hasattr(obj, '__dict__'):
                    # Convert objects with __dict__ to dict
                    return {k: make_serializable(v) for k, v in obj.__dict__.items()}
                elif isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [make_serializable(item) for item in obj]
                elif hasattr(obj, 'model_dump'):
                    # Handle Pydantic models
                    return obj.model_dump()
                elif hasattr(obj, 'to_dict'):
                    # Handle objects with to_dict method
                    return obj.to_dict()
                else:
                    # Try to convert to string as last resort
                    try:
                        json.dumps(obj)
                        return obj
                    except (TypeError, ValueError):
                        return str(obj)

            # Make the message serializable
            serializable_message = make_serializable(message)

            await websocket.send_json(serializable_message)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            # Log more details for debugging
            logger.debug(f"Message type: {type(message)}")
            if isinstance(message, dict):
                for key, value in message.items():
                    logger.debug(f"  {key}: {type(value)}")

    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]):
        """
        Broadcast a message to all connections for a session
        """
        if session_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[session_id]:
                try:
                    await self.send_message(websocket, message)
                except Exception:
                    disconnected.append(websocket)

            # Remove disconnected websockets
            for ws in disconnected:
                self.active_connections[session_id].discard(ws)

    async def handle_stream_event(self, session_id: str, event_data: Dict[str, Any]):
        """
        Handle a streaming event from agent execution
        """
        # Check for cancellation event first
        if event_data.get("type") == "cancelled":
            # Send cancellation event immediately
            message = {
                "type": "stream_event",
                "data": event_data,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            await self.broadcast_to_session(session_id, message)
            logger.info(f"Sent cancellation event for session {session_id}")
            return

        # Log the event for debugging
        if event_data.get("text"):
            logger.info(f"Streaming text event for session {session_id}: is_complete_text={event_data.get('is_complete_text')}, text_length={len(event_data.get('text', ''))}")

        # First, check if there's text that should be streamed (send text BEFORE tool calls)
        if event_data.get("is_complete_text") and event_data.get("text"):
            text = event_data["text"]
            logger.info(f"Processing complete text for chunking: {len(text)} chars")

            # For long texts, break into sentences or chunks for progressive display
            # This simulates the streaming effect when ADK sends complete text
            if len(text) > 50:  # Lower threshold for chunking
                import re
                # First try to split by newlines for better logical separation
                lines = text.split('\n')
                chunks = []

                for line in lines:
                    if line.strip():
                        # For long lines, split by sentences
                        if len(line) > 100:
                            # Split by sentences (period, exclamation, question mark followed by space)
                            sentences = re.split(r'(?<=[.!?])\s+', line)
                            chunks.extend(sentences)
                        else:
                            chunks.append(line)

                # Filter out empty chunks
                sentences = [chunk for chunk in chunks if chunk.strip()]

                logger.info(f"Breaking text into {len(sentences)} chunks for streaming")

                # Send each sentence as a separate event for progressive display
                for i, sentence in enumerate(sentences):
                    if sentence.strip():  # Skip empty sentences
                        chunk_data = {
                            "text": sentence + (" " if i < len(sentences) - 1 else ""),
                            "type": event_data.get("type"),
                            "timestamp": event_data.get("timestamp"),
                            "is_chunk": True
                        }

                        message = {
                            "type": "stream_event",
                            "data": chunk_data,
                            "session_id": session_id,
                            "timestamp": datetime.now().isoformat()
                        }

                        await self.broadcast_to_session(session_id, message)

                        # Very small delay between chunks for natural streaming feel
                        # Reduced from 0.05 to 0.01 for faster streaming
                        await asyncio.sleep(0.01)
            else:
                # For short texts, send as-is
                message = {
                    "type": "stream_event",
                    "data": event_data,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                }
                await self.broadcast_to_session(session_id, message)

        # After text (if any), send tool calls/responses if present
        if event_data.get("tool_calls") or event_data.get("tool_responses"):
            # Small delay after text to ensure proper ordering
            if event_data.get("text"):
                await asyncio.sleep(0.02)

            # Send tool-related events after text
            tool_message = {
                "type": "stream_event",
                "data": {
                    "event_type": event_data.get("event_type"),
                    "tool_calls": event_data.get("tool_calls"),
                    "tool_responses": event_data.get("tool_responses"),
                    "timestamp": event_data.get("timestamp")
                },
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            await self.broadcast_to_session(session_id, tool_message)
            logger.info(f"Sent tool event for session {session_id}: {event_data.get('event_type')}")
        elif not event_data.get("text") and not event_data.get("tool_calls") and not event_data.get("tool_responses"):
            # For other events that are neither text nor tool-related, send as-is
            # This includes error events
            event_type = event_data.get("event_type", "unknown")
            logger.info(f"Sending non-text/non-tool event for session {session_id}: event_type={event_type}, has_error={bool(event_data.get('error'))}")

            message = {
                "type": "stream_event",
                "data": event_data,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            await self.broadcast_to_session(session_id, message)

            if event_type == "error":
                logger.error(f"Sent error event to frontend for session {session_id}: {event_data.get('error')} - {event_data.get('error_message')}")

    async def handle_websocket(self, websocket: WebSocket, session_id: str):
        """
        Handle WebSocket communication for a session
        """
        await self.connect(websocket, session_id)

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                await self.process_client_message(websocket, session_id, data)

        except WebSocketDisconnect:
            await self.disconnect(websocket, session_id)
        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {e}")
            await self.disconnect(websocket, session_id)

    async def process_client_message(
        self,
        websocket: WebSocket,
        session_id: str,
        data: Dict[str, Any]
    ):
        """
        Process a message received from the client
        """
        message_type = data.get("type")

        if message_type == "ping":
            # Respond to ping
            await self.send_message(websocket, {"type": "pong"})

        elif message_type == "cancel":
            # Cancel execution
            logger.info(f"Received cancel request for WebSocket session {session_id}")

            # Get the agent_id from the message if provided
            agent_id = data.get("agent_id")
            user_id = None

            # Extract user_id from token if provided
            token = data.get("token")
            if token:
                try:
                    from backend.auth.jwt_handler import decode_token
                    payload = decode_token(token)
                    user_id = payload.get("user_id")
                except Exception as e:
                    logger.warning(f"Failed to decode token for cancel request: {e}")

            # Determine the correct session to cancel
            cancel_session_id = session_id

            # If we have user_id and agent_id, find the persistent session
            if user_id and agent_id:
                # Try to find the persistent session for this user-agent combination
                persistent_session = self.runtime_manager.session_manager.get_user_agent_session(user_id, agent_id)
                if persistent_session:
                    cancel_session_id = persistent_session.session_id
                    logger.info(f"Found persistent session {cancel_session_id} for user {user_id} and agent {agent_id}")
            elif session_id in self.websocket_to_persistent_session:
                # Use the mapped persistent session if available
                cancel_session_id = self.websocket_to_persistent_session[session_id]
                logger.info(f"Using mapped persistent session {cancel_session_id} for WebSocket session {session_id}")

            logger.info(f"Cancelling execution for session {cancel_session_id}")

            # Check for Claude Code task first
            cc_task = self._claude_code_tasks.get(session_id)
            if cc_task and not cc_task.done():
                logger.info(f"Cancelling Claude Code task for session {session_id}")
                cc_task.cancel()
                success = {"success": True, "message": "Claude Code execution cancelled"}
            else:
                success = self.runtime_manager.cancel_execution(cancel_session_id)
            logger.info(f"Cancel execution returned success={success} for session {cancel_session_id}")

            # Only send cancellation response - the actual cancelled event will come from the executor
            await self.send_message(websocket, {
                "type": "cancel_response",
                "success": success
            })

        elif message_type == "get_status":
            # Get session status
            status = self.runtime_manager.get_session_status(session_id)
            await self.send_message(websocket, {
                "type": "status_response",
                "data": status
            })

        elif message_type == "send_message":
            # Handle new message in ongoing conversation
            input_text = data.get("text", "")
            if input_text:
                # Run the agent execution in the background to avoid blocking message reception
                asyncio.create_task(self.handle_new_message(websocket, session_id, input_text, data))

        else:
            logger.warning(f"Unknown message type: {message_type}")

    async def handle_new_message(
        self,
        websocket: WebSocket,
        session_id: str,
        input_text: str,
        data: Dict[str, Any]
    ):
        """
        Handle a new message from the user
        """
        caller = await verified_caller((data or {}).get("token"))
        if caller is None:
            await self.send_message(websocket, {"type": "error", "message": "Sign in to use the IOFlow Assistant"})
            await self.send_message(websocket, {"type": "execution_complete", "data": {
                "success": False, "error": "unauthenticated", "session_id": session_id}})
            return
        # The identity used for the agent's IOFlow tools is ALWAYS the verified
        # caller's, never ids the client put in the message.
        data = {**data, "user_id": str(caller.user_id), "tenant_id": str(caller.tenant_id) if caller.tenant_id else None}

        session = self.runtime_manager.session_manager.get_session(session_id)
        if not session:
            # Create session if it doesn't exist
            session = self.runtime_manager.session_manager.create_session(
                session_id=session_id,
                agent_id=data.get("agent_id", ""),
                model=data.get("model", "gemini-2.0-flash-exp")
            )
            logger.info(f"Created session {session_id} for message handling")

        # Extract configuration from data
        api_key = data.get("api_key")
        model = data.get("model", session.model or "gemini-2.0-flash-exp")
        agent_id = data.get("agent_id", session.agent_id)
        provider = data.get("provider", None)
        _agent_framework = 'google_adk'  # Default; overridden from user settings below

        # Check if we need to get API key from user's AI settings
        if api_key == "USE_FROM_SETTINGS":
            logger.info("API key is USE_FROM_SETTINGS, fetching from user's AI settings...")

            # Import required modules for database access
            from db.database import get_db
            from db.user_settings_models import UserSettingsHelper
            from utils.crypto_utils import decrypt_data
            from api.auth import get_current_user
            from jose import jwt
            from db.models import User
            from core.config import settings as core_settings

            # Get database session
            db = next(get_db())
            try:
                # Get user ID from the WebSocket data (should be passed from frontend)
                user_id = data.get("user_id")
                tenant_id = data.get("tenant_id")

                if not user_id:
                    # Try to extract from token if provided
                    token = data.get("token")
                    if token:
                        logger.info(f"Token provided (first 20 chars): {token[:20] if token else 'EMPTY'}...")
                        try:
                            # Decode JWT token directly to get user ID
                            payload = jwt.decode(
                                token,
                                core_settings.secret_key,
                                algorithms=["HS256"]
                            )
                            user_id = payload.get("sub")

                            if user_id:
                                # Get user from database
                                user = db.query(User).filter(User.user_id == user_id).first()
                                if user:
                                    user_id = user.user_id
                                    tenant_id = user.tenant_id
                                    logger.info(f"Identified user: {user_id}, tenant: {tenant_id}")
                                else:
                                    logger.error(f"User not found in database: {user_id}")
                            else:
                                logger.error(f"No user ID in JWT payload")
                        except jwt.ExpiredSignatureError:
                            logger.error("JWT token has expired")
                        except jwt.InvalidTokenError as e:
                            logger.error(f"Invalid JWT token: {e}")
                        except Exception as e:
                            logger.error(f"Exception while identifying user from token: {e}")

                if user_id:
                    # First check for assistant-specific configuration
                    assistant_config = UserSettingsHelper.get_assistant_config(db, user_id)
                    logger.info(f"Assistant Config: {assistant_config}")

                    # Check agent_framework from AI config early
                    _ai_config_for_framework = UserSettingsHelper.get_ai_config(db, user_id)
                    _agent_framework = _ai_config_for_framework.get('agent_framework', 'google_adk')
                    logger.info(f"Agent framework from AI settings: {_agent_framework}")

                    # Check if assistant has custom settings and API key
                    if assistant_config and not assistant_config.get("use_defaults") and assistant_config.get("custom_api_key_hash"):
                        # Use assistant's custom API key
                        api_key_hash = assistant_config.get('custom_api_key_hash')
                        api_key = decrypt_data(api_key_hash)
                        logger.info(f"Successfully retrieved custom API key from assistant settings for provider: {assistant_config.get('provider')}")

                        # Use assistant's provider and model
                        if assistant_config.get('provider'):
                            provider = assistant_config.get('provider')
                        if assistant_config.get('model'):
                            model = assistant_config.get('model')
                    else:
                        # Fall back to user's default AI config
                        ai_config = UserSettingsHelper.get_ai_config(db, user_id)
                        if ai_config:
                            api_key_hash = ai_config.get('api_key_hash')
                            if api_key_hash:
                                # Decrypt the API key
                                api_key = decrypt_data(api_key_hash)
                                logger.info(f"Successfully retrieved API key from user settings for provider: {ai_config.get('provider')}")

                                # Also update provider and model if using defaults
                                if not provider:
                                    provider = ai_config.get('provider')
                                if model == "gemini-2.0-flash-exp" and ai_config.get('model'):
                                    model = ai_config.get('model')
                            elif _agent_framework != 'claude_code':
                                logger.error("No API key hash found in user's AI settings")
                                await self.send_message(websocket, {
                                    "type": "error",
                                    "message": "No API key configured in AI settings. Please configure your AI settings first."
                                })
                                return
                        elif _agent_framework != 'claude_code':
                            logger.error("No AI configuration found for user")
                            await self.send_message(websocket, {
                                "type": "error",
                                "message": "No AI configuration found. Please configure your AI settings first."
                            })
                            return
                else:
                    logger.error("Unable to identify user for API key retrieval")
                    await self.send_message(websocket, {
                        "type": "error",
                        "message": "Unable to retrieve user settings. Please ensure you are logged in."
                    })
                    return
            finally:
                db.close()

        # ---- Claude Code shortcut: bypass ADK entirely ----
        if _agent_framework == 'claude_code':
            logger.info("Agent framework is claude_code, routing to Claude Code CLI")
            # Don't pass non-Claude models to Claude Code CLI — it only works with Anthropic models.
            import os
            claude_model = os.environ.get("CLAUDE_CODE_MODEL") or None
            # Run as a tracked asyncio task so cancel requests can kill it
            task = asyncio.create_task(self._execute_with_claude_code_ws(
                websocket=websocket,
                session_id=session_id,
                session=session,
                agent_id=agent_id,
                input_text=input_text,
                model=claude_model,
                data=data,
            ))
            self._claude_code_tasks[session_id] = task
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Claude Code task cancelled for session {session_id}")
                await self.send_message(websocket, {
                    "type": "execution_complete",
                    "data": {
                        "success": False,
                        "cancelled": True,
                        "message": "Execution cancelled by user",
                        "session_id": session_id,
                    }
                })
            finally:
                self._claude_code_tasks.pop(session_id, None)
            return

        # Update session with latest agent and model info
        if agent_id and agent_id != session.agent_id:
            session.agent_id = agent_id
        if model and model != session.model:
            session.model = model

        if not api_key:
            await self.send_message(websocket, {
                "type": "error",
                "message": "API key is required"
            })
            return

        # Send acknowledgment
        await self.send_message(websocket, {
            "type": "message_received",
            "text": input_text
        })

        # Send acknowledgment that we're starting execution
        await self.send_message(websocket, {
            "type": "execution_started",
            "agent_id": agent_id,
            "model": model
        })

        # Store the original WebSocket session ID for message routing
        # Define early so it's available in all exception handlers
        original_session_id = session_id

        try:
            # Get user_id for conversation persistence
            user_id = None
            token = data.get("token")
            if token:
                try:
                    from jose import jwt
                    from core.config import settings as core_settings
                    payload = jwt.decode(
                        token,
                        core_settings.secret_key,
                        algorithms=["HS256"]
                    )
                    user_id = payload.get("sub")
                    logger.info(f"Using user_id {user_id} for conversation persistence")
                except Exception as e:
                    logger.debug(f"Could not extract user_id from token: {e}")

            # Execute agent directly with proper streaming
            # Provider should already be set if using USE_FROM_SETTINGS
            # Pass LLM API key to runtime_manager, and set JWT token for MCP authentication
            # The agent module builds its MCP toolset inside this task and reads
            # the caller's token from the request ContextVar (never os.environ,
            # which every concurrent session shared).
            from agent_pack.runtime import set_request_token
            set_request_token(data.get("token"))

            agent = await self.runtime_manager.load_agent(agent_id, api_key, model, provider)

            # Get or create persistent session for user-agent combination
            if user_id:
                session = self.runtime_manager.session_manager.get_or_create_user_agent_session(
                    user_id=user_id,
                    agent_id=agent_id,
                    model=model,
                    force_new=False  # Don't force new, reuse existing
                )
                persistent_session_id = session.session_id
                logger.info(f"Using persistent session {persistent_session_id} for user {user_id} and agent {agent_id}")
                # Map the persistent session to the WebSocket session
                if original_session_id != persistent_session_id:
                    # Store mapping for message routing and cancellation
                    self.session_websockets[persistent_session_id] = websocket
                    self.active_connections[persistent_session_id] = self.active_connections.get(original_session_id, set())
                    # Store the mapping for cancellation
                    self.websocket_to_persistent_session[original_session_id] = persistent_session_id
            else:
                # Get or update the session (old behavior)
                session = self.runtime_manager.session_manager.get_session(session_id)
                if session:
                    session.agent_id = agent_id
                    session.model = model
                persistent_session_id = session_id

            # Create a streaming callback that routes to the original WebSocket session
            async def stream_callback(sess_id: str, event_data: Dict[str, Any]):
                # Route messages to the original WebSocket session ID
                await self.handle_stream_event(original_session_id, event_data)

            # Execute with streaming using execute_async to enable cancellation
            task = await self.runtime_manager.executor.execute_async(
                agent=agent,
                input_text=input_text,
                session=session,
                stream_callback=stream_callback,
                preserve_history=bool(user_id)  # Preserve history when user_id is available
            )

            # Wait for the task to complete
            result = await task
            logger.info(f"Execution completed for session {original_session_id}, result: success={result.get('success')}, has_response={bool(result.get('response'))}")

            # Send the final response using the original session ID
            if result.get("success") and result.get("response"):
                logger.info(f"Sending execution_complete for session {original_session_id}")
                await self.send_message(websocket, {
                    "type": "execution_complete",
                    "data": {
                        "success": True,
                        "response": result["response"],
                        "session_id": original_session_id
                    }
                })
            else:
                # Execution failed - send error details
                error_msg = result.get("error", "Unknown error occurred")
                logger.error(f"Execution failed with result: {result}")

                # Send error message
                await self.send_message(websocket, {
                    "type": "error",
                    "message": error_msg
                })

                # Also send execution_complete with error
                await self.send_message(websocket, {
                    "type": "execution_complete",
                    "data": {
                        "success": False,
                        "error": error_msg,
                        "session_id": original_session_id
                    }
                })

        except asyncio.CancelledError:
            # Handle task cancellation
            logger.info(f"Execution cancelled for session {original_session_id}")

            # Don't send duplicate cancelled messages - the executor already handles it
            # Just send execution_complete to indicate we're done
            await self.send_message(websocket, {
                "type": "execution_complete",
                "data": {
                    "success": False,
                    "cancelled": True,
                    "message": "Execution cancelled by user",
                    "session_id": original_session_id
                }
            })

            # Don't re-raise - we've handled it
            # raise

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            error_msg = str(e)

            # Provide more helpful error messages for common issues
            if "Connection closed" in error_msg or "ConnectionClosed" in str(type(e).__name__):
                # This typically happens when the LLM API connection fails
                error_msg = (
                    "Connection to AI service was closed. This usually means:\n"
                    "• Your API key may be invalid or expired\n"
                    "• The AI provider may be experiencing issues\n"
                    "• Network connectivity problems\n\n"
                    "Please check your AI settings and ensure your API key is valid."
                )
                logger.error("Connection closed error - likely API key issue or network problem")
            elif "API key" in error_msg.lower() or "apikey" in error_msg.lower():
                error_msg = (
                    "API key error. Please verify your AI settings have a valid API key configured."
                )
            elif "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                error_msg = (
                    "API rate limit or quota exceeded. Please wait a moment and try again, "
                    "or check your API plan limits."
                )

            # Send error message
            await self.send_message(websocket, {
                "type": "error",
                "message": error_msg
            })

            # Also send execution_complete with error
            await self.send_message(websocket, {
                "type": "execution_complete",
                "data": {
                    "success": False,
                    "error": error_msg,
                    "session_id": original_session_id
                }
            })

        finally:
            # Unregister stream handler
            self.runtime_manager.executor.unregister_stream_handler(session_id)

    async def _execute_with_claude_code_ws(
        self,
        websocket: WebSocket,
        session_id: str,
        session,
        agent_id: str,
        input_text: str,
        model: str = "",
        data: dict = None,
    ):
        """
        Execute agent using Claude Code CLI and stream results over WebSocket.
        This replaces the entire ADK execution path when agent_framework is claude_code.
        """
        import os
        import tempfile
        from pathlib import Path
        from services.claude_code_service import ClaudeCodeService, DEFAULT_ALLOWED_TOOLS

        claude_path = os.environ.get("CLAUDE_CODE_PATH", "")
        service = ClaudeCodeService(claude_path=claude_path)

        if not service.is_available():
            await self.send_message(websocket, {
                "type": "error",
                "message": "Claude Code CLI is not installed. Install with: npm install -g @anthropic-ai/claude-code"
            })
            await self.send_message(websocket, {
                "type": "execution_complete",
                "data": {
                    "success": False,
                    "error": "Claude Code CLI not installed",
                    "session_id": session_id,
                }
            })
            return

        # Send acknowledgment
        await self.send_message(websocket, {
            "type": "message_received",
            "text": input_text
        })
        await self.send_message(websocket, {
            "type": "execution_started",
            "agent_id": agent_id,
            "model": model or "claude-code"
        })

        # ---- Load agent's system prompt and instruction ----
        agent_system_prompt = ""
        agent_description = ""
        for agent_info in self.runtime_manager.agent_registry:
            if agent_info["id"] == agent_id:
                agent_description = agent_info.get("description", "")
                agent_path = agent_info.get("path", "")
                agent_type = agent_info.get("type", "")

                if agent_type == "json" and agent_path:
                    try:
                        import json as _json
                        with open(agent_path, 'r') as f:
                            config = _json.load(f)
                        agent_system_prompt = config.get("system_prompt", "")
                        if config.get("instruction"):
                            agent_system_prompt = f"{agent_system_prompt}\n\n{config['instruction']}" if agent_system_prompt else config["instruction"]
                    except Exception:
                        pass
                elif agent_type == "python" and _pack_agent(agent_id):
                    # Pack agents: the one definition (backend/agent_pack).
                    agent_system_prompt = _pack_agent(agent_id)["prompt"]
                    agent_description = _pack_agent(agent_id)["description"]
                elif agent_type == "python" and agent_path:
                    # For Python agents, read the instruction from the module source
                    try:
                        agent_module_path = os.path.join(agent_path, "agent.py")
                        if os.path.exists(agent_module_path):
                            with open(agent_module_path, 'r') as f:
                                source = f.read()
                            # Extract instruction string from source (between instruction=""" and """,)
                            import re
                            instr_match = re.search(r'instruction\s*=\s*"""(.*?)"""', source, re.DOTALL)
                            if instr_match:
                                agent_system_prompt = instr_match.group(1).strip()
                            # Also extract description
                            desc_match = re.search(r'description\s*=\s*"""(.*?)"""', source, re.DOTALL)
                            if desc_match:
                                agent_description = desc_match.group(1).strip()
                    except Exception:
                        pass
                break

        # ---- Extract user context from token ----
        user_id = None
        token = (data or {}).get("token")
        if token:
            try:
                from jose import jwt
                from core.config import settings as core_settings
                payload = jwt.decode(token, core_settings.secret_key, algorithms=["HS256"])
                user_id = payload.get("sub")
            except Exception:
                pass

        # ---- Working directory ----
        base_dir = os.path.join(tempfile.gettempdir(), "ioflow_claude_agent")
        working_dir = os.path.join(base_dir, user_id or "anonymous", agent_id or "default")
        os.makedirs(working_dir, exist_ok=True)

        # Determine max turns: flow design agents need more turns than info queries
        complex_agents = {"flow_designer", "flow_design_editor", "seed_application_designer"}
        default_max_turns = 15 if agent_id in complex_agents else 8
        max_turns = int(os.environ.get("CLAUDE_CODE_MAX_TURNS", str(default_max_turns)))

        # ---- Build system prompt and MCP config ----
        base_url = os.environ.get("IOFLOW_BASE_URL", "http://localhost:7001")
        auth_header = f"Bearer {token}" if token else ""
        mcp_config_path = None

        if agent_id in complex_agents:
            # --- MCP-native path: the bridge's tools via bridge_proxy, limited to
            # the agent-pack agent's tools, authenticated as the verified caller.
            from agent_pack.runtime import claude_mcp_config
            mcp_config = claude_mcp_config(agent_id, token or "")

            mcp_config_path = os.path.join(working_dir, ".mcp_config.json")
            import json as _json
            fd = os.open(mcp_config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                _json.dump(mcp_config, f, indent=2)
            os.chmod(mcp_config_path, 0o600)
            logger.info(f"Generated MCP config at {mcp_config_path} for agent {agent_id}")

            # Use agent's own system prompt (extracted from agent.py instruction)
            # This is the same prompt Google ADK uses — tools are called natively via MCP
            full_system_prompt = ""
            if agent_system_prompt:
                full_system_prompt = agent_system_prompt
            elif agent_description:
                full_system_prompt = f"You are {agent_id}. {agent_description}"

            # Add Claude-Code-specific instruction: use MCP tools only, no direct API calls
            full_system_prompt += """

## IMPORTANT: Tool Usage Rules
- You have MCP tools available (e.g. validate_and_save_flow, list_applications, etc.) — call them directly as tool calls.
- Do NOT use Bash/curl to call IOFlow APIs. You do not have API credentials for direct HTTP calls.
- All IOFlow operations MUST go through the MCP tools which handle authentication automatically.
- Use Bash only for non-API tasks like file operations if needed."""
        else:
            # --- Curl-based path (for simple info/analyst agents) ---
            mcp_instructions = f"""
## IOFlow MCP API Access

You are an IOFlow assistant agent. You can query IOFlow's backend via the MCP bridge endpoint using Bash with curl.

**IMPORTANT RULES:**
- The ONLY valid endpoint is `POST {base_url}/api/mcp/tools/execute`. No other URLs exist.
- If a tool returns an error, tell the user. Do NOT retry with different URLs.
- Be concise. For info queries, 1-2 tool calls max.

### How to call:
```bash
curl -s -X POST "{base_url}/api/mcp/tools/execute" -H "Content-Type: application/json" -H "Authorization: {auth_header}" -d '{{"tool": "TOOL_NAME", "parameters": {{}}}}'
```

### Information tools:
- `get_application_categories` `{{}}` — List all app categories with counts
- `list_applications` `{{}}` — List all subscribed applications (use `{{"app_names":"gmail,slack"}}` for specific apps)
- `search_applications` `{{"query": "..."}}` — Search apps by name
- `get_application_services_list` `{{"app_id": "UUID"}}` — List services for an app
- `get_service_information` `{{"app_key": "UUID", "service_name": "..."}}` — Service parameter details
- `search_services` `{{"query": "..."}}` — Search services
- `search_flows` `{{"query": "..."}}` — Search flows
- `get_seed_application` `{{"app_key": "..."}}` — Seed app details (e.g. "openai", "gmail")
- `ioflow_get_app_guide` `{{}}` — IOFlow documentation

**IMPORTANT:** Always call the guide tools first. They return the exact field names and valid enum values. Do NOT guess the JSON format.
"""
            full_system_prompt = ""
            if agent_system_prompt:
                full_system_prompt = agent_system_prompt + "\n\n"
            elif agent_description:
                full_system_prompt = f"You are {agent_id}. {agent_description}\n\n"
            full_system_prompt += mcp_instructions

        # ---- Stream Claude Code execution ----
        accumulated_text = ""
        _text_buffer = ""
        try:
            async for event in service.stream_prompt(
                prompt=input_text,
                cwd=working_dir,
                system_prompt=full_system_prompt,
                allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
                max_budget_usd=float(os.environ.get("CLAUDE_CODE_MAX_BUDGET_USD", "5.0")),
                model=model or os.environ.get("CLAUDE_CODE_MODEL") or None,
                max_turns=max_turns,
                mcp_config_path=mcp_config_path,
            ):
                event_type = event.get("type", "")

                if event_type == "assistant_text":
                    text_chunk = event.get("content", "")
                    if text_chunk:
                        accumulated_text += text_chunk
                        _text_buffer += text_chunk

                        # Flush on complete lines (newline) so markdown formatting stays intact.
                        # Only flush mid-line if buffer is very large (safety valve).
                        if '\n' in _text_buffer:
                            # Split on the last newline: send everything up to it,
                            # keep the remainder for the next flush.
                            last_nl = _text_buffer.rfind('\n')
                            to_send = _text_buffer[:last_nl + 1]
                            _text_buffer = _text_buffer[last_nl + 1:]
                            if to_send:
                                await self.send_message(websocket, {
                                    "type": "stream_event",
                                    "data": {
                                        "text": to_send,
                                        "is_chunk": True,
                                        "timestamp": datetime.now().isoformat(),
                                    },
                                    "session_id": session_id,
                                    "timestamp": datetime.now().isoformat(),
                                })
                        elif len(_text_buffer) > 500:
                            # Safety valve for very long lines without newlines
                            await self.send_message(websocket, {
                                "type": "stream_event",
                                "data": {
                                    "text": _text_buffer,
                                    "is_chunk": True,
                                    "timestamp": datetime.now().isoformat(),
                                },
                                "session_id": session_id,
                                "timestamp": datetime.now().isoformat(),
                            })
                            _text_buffer = ""

                elif event_type == "tool_activity":
                    # Flush any pending text before tool activity
                    if _text_buffer:
                        await self.send_message(websocket, {
                            "type": "stream_event",
                            "data": {
                                "text": _text_buffer,
                                "is_chunk": True,
                                "timestamp": datetime.now().isoformat(),
                            },
                            "session_id": session_id,
                            "timestamp": datetime.now().isoformat(),
                        })
                        _text_buffer = ""

                    tool_name = event.get("tool", "")
                    file_path = event.get("file", "")
                    await self.send_message(websocket, {
                        "type": "stream_event",
                        "data": {
                            "event_type": "tool_call",
                            "tool_calls": [{
                                "name": tool_name,
                                "args": file_path if file_path else "",
                            }],
                            "timestamp": datetime.now().isoformat(),
                        },
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                    })

                elif event_type == "tool_detail":
                    # Rich tool detail with full input - sent at content_block_stop
                    tool_name = event.get("tool", "")
                    file_path = event.get("file", "")
                    tool_input = event.get("input", {})
                    await self.send_message(websocket, {
                        "type": "stream_event",
                        "data": {
                            "event_type": "tool_detail",
                            "tool_name": tool_name,
                            "file": file_path,
                            "input": tool_input,
                            "timestamp": datetime.now().isoformat(),
                        },
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                    })

                elif event_type == "error":
                    await self.send_message(websocket, {
                        "type": "error",
                        "message": event.get("message", "Unknown error"),
                    })

            # Flush remaining buffer
            if _text_buffer:
                await self.send_message(websocket, {
                    "type": "stream_event",
                    "data": {
                        "text": _text_buffer,
                        "is_chunk": True,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                })

            # Send execution complete
            await self.send_message(websocket, {
                "type": "execution_complete",
                "data": {
                    "success": True,
                    "response": accumulated_text,
                    "session_id": session_id,
                }
            })

        except Exception as e:
            logger.error(f"Claude Code WS execution failed: {e}", exc_info=True)
            await self.send_message(websocket, {
                "type": "error",
                "message": f"Claude Code execution failed: {str(e)}",
            })
            await self.send_message(websocket, {
                "type": "execution_complete",
                "data": {
                    "success": False,
                    "error": str(e),
                    "session_id": session_id,
                }
            })

    async def send_typing_indicator(self, session_id: str, is_typing: bool):
        """
        Send typing indicator to clients
        """
        message = {
            "type": "typing_indicator",
            "is_typing": is_typing,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_session(session_id, message)