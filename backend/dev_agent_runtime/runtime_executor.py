"""
Runtime Executor for Agent Execution with Cancellation Support

Handles the actual execution of agents with streaming and cancellation capabilities.
"""

import asyncio
import uuid
import json
import logging
from typing import Any, Dict, Optional, AsyncGenerator
from datetime import datetime

# Import Google ADK components
try:
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    import google.genai as genai
    HAS_GOOGLE_ADK = True
except ImportError:
    HAS_GOOGLE_ADK = False
    Runner = None
    InMemorySessionService = None
    genai = None

from .session_manager import SessionStatus, ExecutionSession

logger = logging.getLogger(__name__)


class RuntimeExecutor:
    """
    Executes agents with cancellation and streaming support
    """

    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.cancelled_sessions: Dict[str, bool] = {}
        self.stream_handlers: Dict[str, Any] = {}

        # Initialize ADK session service if available
        if HAS_GOOGLE_ADK:
            self.adk_session_service = InMemorySessionService()
        else:
            self.adk_session_service = None

    async def execute(
        self,
        agent: Any,
        input_text: str,
        session: ExecutionSession,
        stream_callback: Optional[Any] = None,
        preserve_history: bool = False
    ) -> Dict[str, Any]:
        """
        Execute an agent with the given input.
        If preserve_history is True, maintains conversation context across executions.
        """
        if not HAS_GOOGLE_ADK:
            raise RuntimeError("Google ADK is not installed")

        session_id = session.session_id

        try:
            # Update session status
            session.set_status(SessionStatus.RUNNING)
            session.add_message("user", input_text)

            # Create ADK runner - use agent's own name without modifications
            runner = Runner(
                app_name=agent.name,  # Use agent's actual name
                agent=agent,
                session_service=self.adk_session_service
            )

            # Create ADK session - use consistent IDs to maintain context
            # For persistent sessions, extract the base user_id from session_id
            if preserve_history and "_" in session_id:
                # Session ID format: user_id_agent_id_hash
                user_id = session_id.split("_")[0]
                # Use a stable session ID for conversation persistence
                adk_session_id = f"{user_id}_{session.agent_id}"
            else:
                # Old behavior for non-persistent sessions
                user_id = f"user_{session_id[:8]}"
                adk_session_id = session_id

            # Check if ADK session already exists (for conversation continuation)
            existing_adk_session = None
            if preserve_history:
                try:
                    existing_adk_session = await self.adk_session_service.get_session(
                        app_name=agent.name,
                        user_id=user_id,
                        session_id=adk_session_id
                    )
                    if existing_adk_session:
                        logger.info(f"Found existing ADK session for conversation continuation: {adk_session_id}")
                except:
                    # Session doesn't exist, will create new one
                    pass

            # Create ADK session only if it doesn't exist
            if not existing_adk_session:
                await self.adk_session_service.create_session(
                    app_name=agent.name,  # Use agent's actual name
                    user_id=user_id,
                    session_id=adk_session_id
                )
                logger.info(f"Created new ADK session: {adk_session_id}")

            # Create message for ADK
            message = genai.types.Content(
                parts=[genai.types.Part(text=input_text)],
                role="user"
            )

            # Execute with streaming
            response_text = ""
            all_text_parts = []
            execution_step_count = 0
            session.set_status(SessionStatus.STREAMING)

            logger.info(f"Starting agent execution for session {session_id}")
            event_count = 0

            # Create a cancellable iterator without any special config
            # Let the agent use its default behavior
            runner_iter = runner.run_async(
                user_id=user_id,
                session_id=adk_session_id,
                new_message=message
                # No run_config - use defaults
            )

            # Track if we encountered an error
            encountered_error = False
            error_info = None

            async for event in runner_iter:
                event_count += 1
                logger.info(f"Processing event #{event_count} of type {type(event).__name__} for session {session_id}")

                # Log the actual event to understand its structure
                if hasattr(event, '__class__'):
                    logger.info(f"Event class: {event.__class__.__module__}.{event.__class__.__name__}")

                # Check if cancelled
                if self.cancelled_sessions.get(session_id):
                    logger.info(f"Execution cancelled for session {session_id}")
                    self.session_manager.cancel_session(session_id)

                    # Try to close the ADK runner iterator
                    if hasattr(runner_iter, 'aclose'):
                        try:
                            await runner_iter.aclose()
                        except Exception as e:
                            logger.debug(f"Error closing runner iterator: {e}")

                    # Send cancellation message through stream
                    if stream_callback:
                        await stream_callback(session_id, {
                            "type": "cancelled",
                            "message": "Execution cancelled by user"
                        })

                    break

                # Process event
                event_data = await self._process_event(event, session)
                if event_data:
                    # Check for errors
                    if event_data.get("event_type") == "error":
                        encountered_error = True
                        error_info = {
                            "error_code": event_data.get("error"),
                            "error_message": event_data.get("error_message"),
                            "context_size": event_data.get("context_size")
                        }
                        logger.error(f"Error event in session {session_id}: {error_info}")

                    # Track execution steps
                    if event_data.get("tool_calls") or event_data.get("tool_responses"):
                        execution_step_count += 1

                    # Collect text for final response
                    if event_data.get("text"):
                        text_part = event_data["text"]
                        all_text_parts.append(text_part)
                        response_text = "".join(all_text_parts)
                        logger.info(f"Got text response (length: {len(text_part)} chars)")

                    # Send ALL events to stream callback (including tool calls/responses and errors)
                    if stream_callback:
                        await stream_callback(session_id, event_data)

            # Combine all text parts for final response
            if all_text_parts:
                response_text = "".join(all_text_parts)
                logger.info(f"Final response for session {session_id}: {len(response_text)} chars total")
            else:
                logger.warning(f"No text response collected for session {session_id}, event count: {event_count}")

            # Clean up ADK session only if not preserving history
            if not preserve_history:
                await self.adk_session_service.delete_session(
                    app_name=agent.name,  # Use agent's actual name
                    user_id=user_id,
                    session_id=adk_session_id
                )
                logger.info(f"Deleted ADK session {adk_session_id}")
            else:
                logger.info(f"Preserved ADK session {adk_session_id} for conversation continuation")

            # Add response to session if we got one
            if response_text:
                session.add_message("assistant", response_text)
            else:
                # Check if we encountered an error
                if encountered_error and error_info:
                    error_code = error_info.get("error_code", "UNKNOWN")
                    error_message = error_info.get("error_message", "An error occurred during execution")

                    if error_code == "MALFORMED_FUNCTION_CALL":
                        if execution_step_count > 0:
                            response_text = (
                                f"I executed {execution_step_count} step(s) but encountered an error when trying to complete the task. "
                                f"{error_message}"
                            )
                        else:
                            response_text = f"Error: {error_message}"
                    else:
                        response_text = f"Error ({error_code}): {error_message}"

                    logger.warning(f"Setting error response for session {session_id}: {response_text}")
                # If no response text but we had tool executions, provide a better message
                elif execution_step_count > 0:
                    logger.warning(f"No response text for session {session_id} but had {execution_step_count} execution steps")
                    response_text = f"I've completed the requested operations. {execution_step_count} tool(s) were executed successfully."
                else:
                    logger.warning(f"No response text for session {session_id}, setting default message")
                    response_text = "Agent execution completed but no response was generated. Please check the execution steps above for details."

            # Mark as completed if not cancelled
            if not self.cancelled_sessions.get(session_id):
                self.session_manager.complete_session(session_id)

            return {
                "success": True,
                "response": response_text,
                "session_id": session_id
            }

        except asyncio.CancelledError:
            logger.info(f"Execution task cancelled for session {session_id}")
            self.session_manager.cancel_session(session_id)

            # Send cancellation message through stream
            if stream_callback:
                try:
                    await stream_callback(session_id, {
                        "type": "cancelled",
                        "message": "Execution cancelled by user"
                    })
                except Exception as e:
                    logger.debug(f"Error sending cancellation through stream: {e}")

            raise

        except Exception as e:
            logger.error(f"Execution failed for session {session_id}: {e}", exc_info=True)
            error_message = str(e)

            # Provide more helpful error messages for common issues
            user_friendly_message = error_message
            if "Connection closed" in error_message or "ConnectionClosed" in str(type(e).__name__):
                user_friendly_message = (
                    "Connection to AI service was closed. This usually means:\n"
                    "• Your API key may be invalid or expired\n"
                    "• The AI provider may be experiencing issues\n"
                    "• Network connectivity problems\n\n"
                    "Please check your AI settings and ensure your API key is valid."
                )
                logger.error("Connection closed error - likely API key issue or network problem")
            elif "401" in error_message or "Unauthorized" in error_message:
                user_friendly_message = "API authentication failed. Please check your API key in AI settings."
            elif "403" in error_message or "Forbidden" in error_message:
                user_friendly_message = "API access denied. Your API key may not have access to this model."
            elif "rate limit" in error_message.lower() or "quota" in error_message.lower():
                user_friendly_message = "API rate limit exceeded. Please wait a moment and try again."

            self.session_manager.set_session_error(session_id, error_message)

            # Send error through stream callback if available
            if stream_callback:
                try:
                    await stream_callback(session_id, {
                        "type": "error",
                        "error": user_friendly_message,
                        "message": f"Agent execution failed: {user_friendly_message}"
                    })
                except Exception as stream_error:
                    logger.error(f"Failed to send error through stream: {stream_error}")

            return {
                "success": False,
                "error": user_friendly_message,
                "session_id": session_id
            }

        finally:
            # Clean up
            self._cleanup_session(session_id)

    async def _process_event(self, event: Any, session: ExecutionSession) -> Optional[Dict[str, Any]]:
        """
        Process an ADK event and extract relevant information
        """
        event_data = {
            "type": type(event).__name__,
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Log the event type and structure for debugging
            logger.info(f"Processing event type: {type(event).__name__}, hasattr candidates: {hasattr(event, 'candidates')}")

            # Log available attributes on the event - use INFO level when candidates missing
            if hasattr(event, '__dict__'):
                attrs = list(event.__dict__.keys())
                if not hasattr(event, 'candidates'):
                    logger.info(f"Event attributes (no candidates): {attrs}")
                else:
                    logger.debug(f"Event attributes: {attrs}")

            # Try to dump event as model early if possible - more aggressive for missing candidates
            event_dict = None
            if hasattr(event, 'model_dump'):
                try:
                    event_dict = event.model_dump()
                    # Log for debugging when candidates are missing
                    if not hasattr(event, 'candidates'):
                        logger.info(f"Event model_dump (no candidates): {json.dumps(event_dict, default=str)[:2000]}")
                    else:
                        logger.debug(f"Event model_dump: {json.dumps(event_dict, default=str)[:500]}")
                except Exception as e:
                    logger.debug(f"Could not dump event as model: {e}")

            # Try different ways to extract text from the event
            if hasattr(event, 'content'):
                content = event.content
                if content:
                    # Handle different content types
                    if isinstance(content, str):
                        event_data["text"] = content
                        event_data["is_complete_text"] = True  # Mark as complete text
                        logger.debug(f"Found text as string: {content[:100]}...")
                    elif hasattr(content, 'text') and content.text:
                        event_data["text"] = content.text
                        event_data["is_complete_text"] = True  # Mark as complete text
                        logger.debug(f"Found text in content.text: {content.text[:100]}...")
                    elif hasattr(content, 'parts'):
                        for part in content.parts:
                            if hasattr(part, 'text') and part.text:
                                event_data["text"] = part.text
                                event_data["is_complete_text"] = True  # Mark as complete text
                                logger.debug(f"Found text in content.parts: {part.text[:100]}...")
                                break
                    elif hasattr(content, 'model_dump'):
                        # Try to extract from model dump
                        content_dict = content.model_dump()
                        if 'text' in content_dict:
                            event_data["text"] = content_dict['text']
                            event_data["is_complete_text"] = True  # Mark as complete text
                            logger.debug(f"Found text in model_dump: {content_dict['text'][:100]}...")
                        elif 'parts' in content_dict:
                            for part in content_dict['parts']:
                                if isinstance(part, dict) and 'text' in part:
                                    event_data["text"] = part['text']
                                    event_data["is_complete_text"] = True  # Mark as complete text
                                    logger.debug(f"Found text in model_dump parts: {part['text'][:100]}...")
                                    break

            # Check for candidates (this is how ADK often returns responses)
            if hasattr(event, 'candidates') and event.candidates:
                logger.info(f"Event has {len(event.candidates)} candidates")
                for idx, candidate in enumerate(event.candidates):
                    logger.info(f"Processing candidate {idx}: has content={hasattr(candidate, 'content')}")
                    if hasattr(candidate, 'content'):
                        content = candidate.content
                        logger.info(f"Content type: {type(content)}, has parts={hasattr(content, 'parts')}")
                        if hasattr(content, 'parts'):
                            logger.info(f"Content has {len(content.parts)} parts")
                            # Process all parts - don't break early
                            text_parts = []
                            function_calls = []

                            for part_idx, part in enumerate(content.parts):
                                logger.info(f"Part {part_idx}: has text={hasattr(part, 'text')}, has function_call={hasattr(part, 'function_call')}")
                                # Check for text
                                if hasattr(part, 'text') and part.text:
                                    text_parts.append(part.text)
                                    # Only log text length, not content
                                    logger.debug(f"Found text in part {part_idx} (length: {len(part.text)} chars)")

                                # Check for function calls
                                if hasattr(part, 'function_call'):
                                    func_call = part.function_call
                                    if func_call:
                                        function_calls.append({
                                            "name": getattr(func_call, 'name', 'unknown'),
                                            "args": getattr(func_call, 'args', {})
                                        })
                                        logger.debug(f"Found function call in part {part_idx}: {getattr(func_call, 'name', 'unknown')}")

                            # Set the collected data
                            if text_parts:
                                # Join all text parts for this candidate
                                # ADK typically sends full text in one event, not character by character
                                full_text = "".join(text_parts)
                                event_data["text"] = full_text
                                logger.info(f"Total text extracted from candidate {idx}: {len(full_text)} chars")

                                # If this is a long text, we should stream it in chunks
                                # to show progressive thinking in the UI
                                event_data["is_complete_text"] = True  # Mark that this is complete text

                            if function_calls:
                                event_data["tool_calls"] = function_calls
                                event_data["event_type"] = "tool_call"
                                logger.info(f"Found {len(function_calls)} function call(s) in candidate {idx}")

                    # Use first candidate with content
                    if event_data.get("text") or event_data.get("tool_calls"):
                        logger.info(f"Using candidate {idx} with content")
                        break

            # Also check for direct text on the event
            if not event_data.get("text") and hasattr(event, 'text') and event.text:
                event_data["text"] = event.text
                event_data["is_complete_text"] = True  # Mark as complete text
                logger.info(f"Found direct text on event: {len(event.text)} chars")

            # Fallback: Check for response/message attributes (Gemini 2.5 Flash compatibility)
            if not event_data.get("text"):
                for attr_name in ['response', 'message', 'output', 'result']:
                    if hasattr(event, attr_name):
                        attr_value = getattr(event, attr_name)
                        if attr_value:
                            if isinstance(attr_value, str):
                                event_data["text"] = attr_value
                                event_data["is_complete_text"] = True
                                logger.info(f"Found text in event.{attr_name}: {len(attr_value)} chars")
                                break
                            elif hasattr(attr_value, 'text'):
                                event_data["text"] = attr_value.text
                                event_data["is_complete_text"] = True
                                logger.info(f"Found text in event.{attr_name}.text: {len(attr_value.text)} chars")
                                break

            # Fallback: Try to extract from model_dump if we have it and still no text
            if not event_data.get("text") and event_dict:
                # Try common paths in the model dump
                for path in [
                    ['response', 'text'],
                    ['message', 'text'],
                    ['output'],
                    ['result'],
                    ['text'],
                    ['content', 'text'],
                    ['content', 'parts', 0, 'text']
                ]:
                    try:
                        value = event_dict
                        for key in path:
                            if isinstance(value, dict):
                                value = value.get(key)
                            elif isinstance(value, list) and isinstance(key, int):
                                value = value[key] if key < len(value) else None
                            else:
                                value = None
                                break

                        if value and isinstance(value, str):
                            event_data["text"] = value
                            event_data["is_complete_text"] = True
                            logger.info(f"Found text in model_dump at path {'.'.join(map(str, path))}: {len(value)} chars")
                            break
                    except (KeyError, IndexError, TypeError):
                        continue

            # Check for error events
            if hasattr(event, 'error_code') and event.error_code:
                error_code = event.error_code
                event_data["error"] = error_code
                event_data["event_type"] = "error"

                # Get error message if available
                error_message = getattr(event, 'error_message', None)
                if error_message:
                    event_data["error_message"] = error_message

                # Handle specific error types
                if error_code == "MALFORMED_FUNCTION_CALL":
                    # Extract details from the event
                    logger.error(f"MALFORMED_FUNCTION_CALL error detected in session {session.session_id}")

                    # Try to get more context from the event
                    if hasattr(event, 'usage_metadata') and event.usage_metadata:
                        usage = event.usage_metadata
                        prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                        logger.error(f"Context size at error: {prompt_tokens} prompt tokens")
                        event_data["context_size"] = prompt_tokens

                    # Create a user-friendly error message
                    if not error_message:
                        event_data["error_message"] = (
                            "The model generated an invalid function call. This can happen when "
                            "the context becomes too large or the request is too complex. "
                            "Try simplifying your request or breaking it into smaller steps."
                        )

                    logger.error(f"MALFORMED_FUNCTION_CALL: {event_data.get('error_message', 'No details')}")

                # Log other errors
                else:
                    logger.error(f"Error event: {error_code}, message: {error_message}")

            # Extract and process tool calls if present
            if hasattr(event, 'get_function_calls'):
                function_calls = event.get_function_calls()
                if function_calls:
                    # Process function calls for better formatting
                    formatted_calls = []
                    for call in function_calls:
                        if hasattr(call, 'name') and hasattr(call, 'args'):
                            formatted_calls.append({
                                "name": call.name,
                                "args": call.args
                            })
                        elif isinstance(call, dict):
                            formatted_calls.append(call)
                        else:
                            formatted_calls.append(str(call))

                    event_data["tool_calls"] = formatted_calls
                    event_data["event_type"] = "tool_call"
                    # Only log tool names, not the full args
                    tool_names = [call.get('name', 'unknown') if isinstance(call, dict) else 'unknown' for call in formatted_calls]
                    logger.info(f"Tool calls detected: {tool_names}")

            # Extract and process tool responses if present
            if hasattr(event, 'get_function_responses'):
                function_responses = event.get_function_responses()
                if function_responses:
                    # Process function responses for better formatting
                    formatted_responses = []
                    for response in function_responses:
                        if hasattr(response, 'response'):
                            formatted_responses.append({
                                "name": getattr(response, 'name', 'unknown'),
                                "response": response.response
                            })
                        elif isinstance(response, dict):
                            formatted_responses.append(response)
                        else:
                            formatted_responses.append(str(response))

                    event_data["tool_responses"] = formatted_responses
                    event_data["event_type"] = "tool_response"
                    # Only log tool names, not the full responses
                    response_names = [resp.get('name', 'unknown') if isinstance(resp, dict) else 'unknown' for resp in formatted_responses]
                    logger.info(f"Tool responses received for: {response_names}")

        except Exception as e:
            logger.debug(f"Error processing event: {e}")

        # Return event data if it has meaningful content
        if (event_data.get("text") or
            event_data.get("error") or
            event_data.get("tool_calls") or
            event_data.get("tool_responses")):
            return event_data
        return None

    async def execute_async(
        self,
        agent: Any,
        input_text: str,
        session: ExecutionSession,
        stream_callback: Optional[Any] = None,
        preserve_history: bool = False
    ) -> asyncio.Task:
        """
        Execute agent asynchronously and return the task
        """
        task = asyncio.create_task(
            self.execute(agent, input_text, session, stream_callback, preserve_history)
        )

        # Register the task
        self.active_tasks[session.session_id] = task
        self.session_manager.register_task(session.session_id, task)

        return task

    def cancel_execution(self, session_id: str) -> bool:
        """
        Cancel an active execution
        """
        # Mark as cancelled first (so the loop can check it)
        self.cancelled_sessions[session_id] = True
        logger.info(f"Marked session {session_id} for cancellation")

        # Log current active tasks
        logger.info(f"Active tasks: {list(self.active_tasks.keys())}")

        # Cancel the asyncio task if it exists
        task = self.active_tasks.get(session_id)
        if task:
            logger.info(f"Found task for session {session_id}, task.done()={task.done()}")
            if not task.done():
                # Actually cancel the task to stop execution immediately
                # The flag ensures clean handling, but we need to interrupt the task
                logger.info(f"Cancelling task for session {session_id}")
                task.cancel()
                logger.info(f"Task cancelled for session {session_id}")
                return True
            else:
                logger.info(f"Task already done for session {session_id}")
        else:
            logger.warning(f"No task found for session {session_id} in active_tasks")

        # Even if no active task, return True if we set the flag
        return session_id in self.cancelled_sessions

    def _cleanup_session(self, session_id: str):
        """
        Clean up session resources
        """
        # Remove from active tasks
        if session_id in self.active_tasks:
            del self.active_tasks[session_id]

        # Remove from cancelled sessions
        if session_id in self.cancelled_sessions:
            del self.cancelled_sessions[session_id]

        # Unregister from session manager
        self.session_manager.unregister_task(session_id)

    def register_stream_handler(self, session_id: str, handler: Any):
        """
        Register a stream handler for a session
        """
        self.stream_handlers[session_id] = handler

    def unregister_stream_handler(self, session_id: str):
        """
        Unregister a stream handler
        """
        if session_id in self.stream_handlers:
            del self.stream_handlers[session_id]

    async def stream_event(self, session_id: str, event_data: Dict[str, Any]):
        """
        Stream an event to registered handlers
        """
        handler = self.stream_handlers.get(session_id)
        if handler:
            await handler(event_data)