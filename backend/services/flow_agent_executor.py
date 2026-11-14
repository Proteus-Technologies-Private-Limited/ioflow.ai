"""
Flow Agent Executor for handling AI agent operations using Google ADK
"""
import os
import json
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import logging

from services.service_executors import ServiceExecutor
from services.node_session_service import get_node_session_service

# Import tool registry using absolute import with proper path handling
import sys
import os
import importlib.util

# Get the absolute path to the tool registry module
current_file = os.path.abspath(__file__)
backend_dir = os.path.dirname(os.path.dirname(current_file))
tool_registry_path = os.path.join(backend_dir, "flow-agent", "core", "tool_registry.py")

# Load the module directly from file
spec = importlib.util.spec_from_file_location("tool_registry", tool_registry_path)
tool_registry_module = importlib.util.module_from_spec(spec)
sys.modules["tool_registry"] = tool_registry_module
spec.loader.exec_module(tool_registry_module)

# Import the function we need
get_registry = tool_registry_module.get_registry

# Import Google ADK components
try:
    from google.adk import Runner
    from google.adk.agents import LlmAgent
    from google.adk.sessions import InMemorySessionService
    import google.genai as genai
    HAS_GOOGLE_ADK = True
except ImportError:
    HAS_GOOGLE_ADK = False
    Runner = None
    LlmAgent = None
    InMemorySessionService = None
    genai = None

logger = logging.getLogger(__name__)

# Global session service for all agents
SESSION_SERVICE = InMemorySessionService() if HAS_GOOGLE_ADK else None

# In-memory cache for loaded agents
LOADED_AGENTS: Dict[str, Any] = {}
AGENT_RUNNERS: Dict[str, Any] = {}
AGENT_LAST_USED: Dict[str, datetime] = {}
MAX_AGENT_IDLE_TIME = 300  # 5 minutes


class FlowAgentExecutor(ServiceExecutor):
    """Executor for Flow Agent operations"""

    def __init__(self, service_config: Dict[str, Any], auth_credentials: Dict[str, Any] = None,
                 subscription_id: str = None, auth_config: Dict[str, Any] = None):
        super().__init__(service_config, auth_credentials, subscription_id, auth_config)
        # Use the dynamic tool registry
        self.tool_registry = get_registry()
        logger.info(f"Tool registry initialized with {len(self.tool_registry.tools)} tools: {list(self.tool_registry.tools.keys())}")

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute AI agent operation"""
        if not HAS_GOOGLE_ADK:
            return {
                'error': True,
                'message': 'Google ADK is not installed. Please install it with: pip install google-generativeai-adk'
            }

        try:
            # Get operation type
            operation = parameters.get('operation', 'execute')

            if operation == 'execute':
                return await self._execute_agent(parameters, context)
            elif operation == 'list':
                return await self._list_agents(parameters, context)
            elif operation == 'load':
                return await self._load_agent(parameters, context)
            elif operation == 'unload':
                return await self._unload_agent(parameters, context)
            elif operation == 'create_config':
                return await self._create_agent_config(parameters, context)
            else:
                return {
                    'error': True,
                    'message': f'Unknown operation: {operation}'
                }

        except Exception as e:
            logger.error(f"AI agent operation failed: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': f'AI agent operation failed: {str(e)}'
            }

    async def _execute_agent(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an AI agent with given parameters"""
        logger.info(f"_execute_agent called with parameters: {json.dumps(parameters, default=str)[:500]}")

        # Extract parameters
        agent_id = parameters.get('agent_id')
        input_text = parameters.get('input', '')
        system_prompt = parameters.get('system_prompt', '')
        instruction = parameters.get('instruction', '')
        model = parameters.get('model', 'gemini-2.0-flash-exp')
        tools_param = parameters.get('tools', [])

        # The 'api_key' parameter from frontend is the JWT session token for IOFlow auth
        # Google API key is handled separately by the server configuration
        api_key = parameters.get('api_key') or self.auth_credentials.get('api_key')

        logger.info(f"API key (JWT token) present: {bool(api_key)}, length: {len(api_key) if api_key else 0}")

        # Extract chat session context for conversation continuity
        chat_session_id = context.get('chat_session_id')
        current_node_id = context.get('current_node_id')
        tenant_id = context.get('tenant_id')
        schema_name = context.get('schema_name')
        user_id = context.get('user_id')
        flow_id = context.get('flow_id')

        # Session mapping for ADK session continuity
        adk_session_id = None
        is_new_chat_session = True

        if chat_session_id and current_node_id and tenant_id:
            # Get or create node session mapping for chat continuity
            try:
                node_session_service = get_node_session_service()
                session_info = node_session_service.get_or_create_session(
                    node_id=current_node_id,
                    chat_session_id=chat_session_id,
                    tenant_id=tenant_id,
                    node_type='agent',
                    user_id=user_id,
                    flow_id=flow_id,
                    schema_name=schema_name
                )

                adk_session_id = session_info.get('agent_session_id')
                is_new_chat_session = session_info.get('is_new', True)

                if adk_session_id:
                    logger.info(f"Reusing existing ADK session: {adk_session_id} for chat_session: {chat_session_id[:8]}...")
                else:
                    # Generate new ADK session ID and store mapping
                    adk_session_id = f"session_{uuid.uuid4().hex[:8]}"
                    node_session_service.update_session(
                        node_id=current_node_id,
                        chat_session_id=chat_session_id,
                        tenant_id=tenant_id,
                        agent_session_id=adk_session_id,
                        schema_name=schema_name
                    )
                    logger.info(f"Created new ADK session: {adk_session_id} for chat_session: {chat_session_id[:8]}...")
            except Exception as e:
                logger.error(f"Error managing node session: {e}", exc_info=True)
                # Fall back to ephemeral session
                adk_session_id = f"ephemeral_{uuid.uuid4().hex[:8]}"
        else:
            # Non-chat execution - ephemeral session
            adk_session_id = f"ephemeral_{uuid.uuid4().hex[:8]}"
            logger.info(f"Using ephemeral ADK session: {adk_session_id}")

        # Handle tools parameter - can be list of strings or list of dicts
        tools = []
        if tools_param:
            if isinstance(tools_param, list):
                for tool in tools_param:
                    if isinstance(tool, str):
                        # Simple string tool name
                        tools.append(tool)
                    elif isinstance(tool, dict):
                        # Tool object with name/function field
                        tool_name = tool.get('function') or tool.get('name')
                        if tool_name:
                            tools.append(tool_name)
                    else:
                        logger.warning(f"Invalid tool format: {tool}")

        # Dynamic agent configuration
        use_dynamic = parameters.get('use_dynamic', False)

        try:
            if use_dynamic or not agent_id:
                # Create dynamic agent from parameters
                logger.info(f"Creating dynamic agent with tools: {tools}")
                agent = await self._create_dynamic_agent(
                    name=agent_id or f"dynamic_{uuid.uuid4().hex[:8]}",
                    system_prompt=system_prompt,
                    instruction=instruction,
                    model=model,
                    tools=tools
                )
                agent_id = agent.name
            else:
                # For Python module agents with API key, force reload to pick up new environment
                # This is needed because MCPToolset is created at module import time
                python_module_agents = {'flow_designer', 'flow_design_editor', 'seed_application_designer'}
                should_reload = (
                    agent_id in python_module_agents and
                    api_key and
                    agent_id in LOADED_AGENTS
                )

                if should_reload:
                    logger.info(f"Forcing reload of {agent_id} to pick up new API key")
                    # Clear from cache to force fresh import
                    del LOADED_AGENTS[agent_id]
                    # Also clear from sys.modules to force module-level code re-execution
                    module_path = f"agent.{agent_id}.agent"
                    if module_path in sys.modules:
                        del sys.modules[module_path]

                # Load or get existing agent configuration
                if agent_id not in LOADED_AGENTS:
                    # Try loading from JSON config first
                    agent = await self._load_agent_config(agent_id, api_key)

                    # If JSON config not found, try loading Python module agent
                    if not agent:
                        agent = await self._load_python_module_agent(agent_id, api_key)

                    if not agent:
                        return {
                            'error': True,
                            'message': f'Agent configuration not found: {agent_id} (tried both JSON config and Python module)'
                        }
                else:
                    agent = LOADED_AGENTS[agent_id]

            # Get or create runner
            if agent_id not in AGENT_RUNNERS:
                app_name = f"agent_{agent_id}"
                logger.info(f"Creating new Runner for agent '{agent_id}' with app_name '{app_name}'")
                runner = Runner(
                    app_name=app_name,
                    agent=agent,
                    session_service=SESSION_SERVICE
                )
                AGENT_RUNNERS[agent_id] = runner
                logger.info(f"Runner created and cached for agent '{agent_id}'")
            else:
                runner = AGENT_RUNNERS[agent_id]
                logger.info(f"Using cached runner for agent '{agent_id}'")

            # Update last used time
            AGENT_LAST_USED[agent_id] = datetime.now()

            # Prepend user context to input if available
            context_prefix = self._build_context_prefix(context)
            final_input = f"{context_prefix}{input_text}" if context_prefix else input_text

            logger.info(f"Executing agent with input: {final_input[:100]}...")
            # Execute the agent with session continuity support
            response = await self._run_agent_with_adk(
                agent, runner, final_input,
                session_id=adk_session_id,
                is_new_session=is_new_chat_session
            )
            logger.info(f"Agent execution completed, response length: {len(response) if response else 0}")

            # Clean up if dynamic agent
            if use_dynamic and agent_id.startswith("dynamic_"):
                self._cleanup_agent(agent_id)

            # Return clean, simple structure without duplicates
            result = {
                'success': True,
                'agent_id': agent_id,
                'response': response,
                'model': model,
                'timestamp': datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(f"Failed to execute agent: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': f'Failed to execute agent: {str(e)}'
            }

    async def _create_dynamic_agent(self, name: str, system_prompt: str, instruction: str,
                                   model: str, tools: List[str]) -> Any:
        """Create a dynamic agent from parameters"""
        logger.info(f"Creating dynamic agent '{name}' with model '{model}' and tools: {tools}")

        # Combine prompts
        full_instruction = system_prompt
        if instruction:
            full_instruction += f"\n\n{instruction}"

        # Resolve tools from registry using dynamic tool discovery
        resolved_tools = []
        for tool_name in tools:
            tool_func = self.tool_registry.get_tool(tool_name)
            if tool_func:
                resolved_tools.append(tool_func)
                logger.info(f"Added tool '{tool_name}' to agent")
            else:
                logger.warning(f"Tool '{tool_name}' not found in registry")

        # Create the ADK Agent instance
        logger.info(f"Creating LlmAgent with model: {model}, tools count: {len(resolved_tools)}")

        agent = LlmAgent(
            name=name,
            model=model,
            description=f"Dynamic agent created at {datetime.now().isoformat()}",
            instruction=full_instruction,
            tools=resolved_tools,
            generate_content_config={
                "temperature": 0.7,
                "max_output_tokens": 2048
            }
        )

        logger.info(f"Successfully created agent '{name}' with model: {model}")

        # Cache the agent
        LOADED_AGENTS[name] = agent

        return agent

    async def _load_agent_config(self, agent_id: str, api_key: str) -> Optional[Any]:
        """Load agent configuration from file or database"""
        # First try to load from flow_agent_configs directory
        config_path = Path("backend/flow_agent_configs") / f"{agent_id}.json"

        if not config_path.exists():
            # Try legacy location
            config_path = Path("backend/flow-agent/agents") / f"{agent_id}.json"

        if not config_path.exists():
            logger.error(f"Agent configuration not found: {agent_id}")
            return None

        try:
            with open(config_path, 'r') as f:
                data = json.load(f)

            # Extract configuration
            name = data.get("agent_id", agent_id)
            model_name = data.get("model", "gemini-2.0-flash-exp")
            description = data.get("description", "")
            system_prompt = data.get("system_prompt", "")
            instruction = data.get("instruction", "")
            tools_config = data.get("tools", [])

            # Combine prompts
            full_instruction = system_prompt
            if instruction:
                full_instruction += f"\n\n{instruction}"

            # Resolve tools using the dynamic registry
            tools = self.tool_registry.get_tools_for_config(tools_config)
            logger.info(f"Resolved {len(tools)} tools from configuration")

            # Create the ADK Agent
            agent = LlmAgent(
                name=name,
                model=model_name,
                description=description,
                instruction=full_instruction,
                tools=tools,
                generate_content_config={
                    "temperature": 0.7,
                    "max_output_tokens": 2048
                }
            )

            # Cache the agent
            LOADED_AGENTS[agent_id] = agent
            logger.info(f"Loaded agent '{agent_id}' with {len(tools)} tools")

            return agent

        except Exception as e:
            logger.error(f"Failed to load agent config: {str(e)}", exc_info=True)
            return None

    async def _load_python_module_agent(self, agent_id: str, api_key: str) -> Optional[Any]:
        """Load Python module agent (e.g., flow_designer, flow_design_editor)"""
        try:
            logger.info(f"Attempting to load Python module agent: {agent_id}")

            # IMPORTANT: Set environment variable BEFORE importing module
            # The agent module reads IOFLOW_API_KEY at import time
            if api_key:
                os.environ['IOFLOW_API_KEY'] = api_key
                logger.info(f"Set IOFLOW_API_KEY in environment before module import")

            # Try to import the agent module
            module_path = f"agent.{agent_id}.agent"
            try:
                import importlib
                # Module should be fresh due to cache clearing in load_agent()
                agent_module = importlib.import_module(module_path)
                logger.info(f"Successfully imported module {module_path}")
            except ModuleNotFoundError:
                logger.info(f"Python module not found: {module_path}")
                return None

            # Get the agent object from the module
            if not hasattr(agent_module, 'root_agent') and not hasattr(agent_module, 'agent'):
                logger.error(f"Module {module_path} does not export 'root_agent' or 'agent'")
                return None

            agent = getattr(agent_module, 'root_agent', None) or getattr(agent_module, 'agent', None)

            if agent is None:
                logger.error(f"Could not find agent in module {module_path}")
                return None

            # Cache the agent
            LOADED_AGENTS[agent_id] = agent
            logger.info(f"Successfully loaded Python module agent: {agent_id}")

            return agent

        except Exception as e:
            logger.error(f"Failed to load Python module agent '{agent_id}': {str(e)}", exc_info=True)
            return None

    def _build_context_prefix(self, context: Dict[str, Any]) -> str:
        """Build context prefix to prepend to user input"""
        if not context:
            return ""

        context_parts = []

        # Add user email if available
        if context.get('user_email'):
            context_parts.append(f"Authenticated user email: {context['user_email']}")

        # Add user ID if available
        if context.get('user_id'):
            context_parts.append(f"User ID: {context['user_id']}")

        # Add tenant ID if available
        if context.get('tenant_id'):
            context_parts.append(f"Tenant ID: {context['tenant_id']}")

        if not context_parts:
            return ""

        # Build prefix with clear separation
        prefix = "[SYSTEM CONTEXT]\n" + "\n".join(context_parts) + "\n\n[USER REQUEST]\n"
        logger.info(f"Built context prefix: {prefix}")
        return prefix

    async def _run_agent_with_adk(
        self,
        agent: Any,
        runner: Any,
        user_input: str,
        session_id: Optional[str] = None,
        is_new_session: bool = True
    ) -> str:
        """
        Execute an agent using ADK's Runner.

        Args:
            agent: The ADK agent instance
            runner: The ADK Runner instance
            user_input: The user's input message
            session_id: Optional session ID for conversation continuity
            is_new_session: Whether this is a new session (create) or existing (reuse)

        Returns:
            The agent's response text
        """
        try:
            # Use provided session_id or generate a unique one
            if not session_id:
                session_id = f"session_{uuid.uuid4().hex[:8]}"
                is_new_session = True

            # For chat sessions, use a consistent user_id derived from session
            # For ephemeral sessions, generate unique user_id
            if session_id.startswith("ephemeral_"):
                user_id = f"user_{uuid.uuid4().hex[:8]}"
                is_ephemeral = True
            else:
                # Derive user_id from session_id for consistency across invocations
                user_id = f"user_{session_id.split('_')[-1]}"
                is_ephemeral = False

            app_name = f"agent_{agent.name}"

            logger.info(f"=== Starting ADK agent execution ===")
            logger.info(f"Agent: {agent.name}")
            logger.info(f"Model: {agent.model}")
            logger.info(f"Input: {user_input[:200]}")
            logger.info(f"Session: {session_id}, is_new: {is_new_session}, is_ephemeral: {is_ephemeral}")

            # Only create session if it's new
            if is_new_session:
                await SESSION_SERVICE.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                logger.info(f"New ADK session created: {session_id}")
            else:
                logger.info(f"Reusing existing ADK session: {session_id}")

            # Create message with explicit user role
            message = genai.types.Content(
                parts=[genai.types.Part(text=user_input)],
                role="user"
            )
            logger.info(f"Message created with role='user', text length: {len(user_input)}")

            # Execute the agent and collect response
            response_text = ""
            all_responses = []
            event_count = 0

            logger.info(f"Starting runner.run_async...")
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message
            ):
                event_count += 1
                event_type = type(event).__name__
                logger.info(f"Event #{event_count}: Type={event_type}")

                # Log all attributes of the event for debugging
                event_attrs = [attr for attr in dir(event) if not attr.startswith('_')]
                logger.info(f"Event attributes: {event_attrs}")

                # Try to get string representation
                try:
                    event_str = str(event)
                    logger.debug(f"Event as string: {event_str[:500]}")
                except:
                    logger.debug(f"Could not convert event to string")

                # Check for content attribute first (most common)
                if hasattr(event, 'content'):
                    content = event.content
                    logger.info(f"Event has content attribute, type: {type(content)}")

                    # Try to access as a model/object first
                    if content is not None:
                        # Try to convert to dict to inspect structure
                        try:
                            if hasattr(content, 'model_dump'):
                                content_dict = content.model_dump()
                                logger.info(f"Content as dict: {json.dumps(content_dict, default=str)[:500]}")

                                # Look for text in the dict
                                if 'text' in content_dict and content_dict['text']:
                                    all_responses.append(content_dict['text'])
                                    response_text = content_dict['text']
                                    logger.info(f"Captured text from content dict: {content_dict['text'][:200]}")
                                elif 'parts' in content_dict and content_dict['parts']:
                                    for part in content_dict['parts']:
                                        if isinstance(part, dict) and 'text' in part and part['text']:
                                            all_responses.append(part['text'])
                                            response_text = part['text']
                                            logger.info(f"Captured text from content dict parts: {part['text'][:200]}")
                        except Exception as e:
                            logger.debug(f"Could not convert content to dict: {e}")

                        # Check if content is a string
                        if isinstance(content, str):
                            if content.strip():
                                all_responses.append(content)
                                response_text = content
                                logger.info(f"Captured text from content (string): {content[:200]}")
                        # Check if content has text attribute
                        elif hasattr(content, 'text'):
                            if content.text:
                                all_responses.append(content.text)
                                response_text = content.text
                                logger.info(f"Captured text from content.text: {content.text[:200]}")
                        # Check if content has parts
                        elif hasattr(content, 'parts'):
                            if content.parts:
                                for part in content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        all_responses.append(part.text)
                                        response_text = part.text
                                        logger.info(f"Captured text from content.parts: {part.text[:200]}")
                        else:
                            logger.debug(f"Content type: {type(content)}, str: {str(content)[:500]}")

                # Check for text attribute
                if hasattr(event, 'text') and event.text:
                    logger.info(f"Event has text attribute")
                    all_responses.append(event.text)
                    response_text = event.text
                    logger.info(f"Captured text from event.text: {event.text[:200]}")

                # Check for candidates (Gemini specific)
                if hasattr(event, 'candidates') and event.candidates:
                    logger.info(f"Event has candidates attribute")
                    for i, candidate in enumerate(event.candidates):
                        if hasattr(candidate, 'content'):
                            content = candidate.content
                            if hasattr(content, 'parts'):
                                for part in content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        all_responses.append(part.text)
                                        response_text = part.text
                                        logger.info(f"Captured text from candidate {i}: {part.text[:200]}")

                # Try to get the event as dict to inspect
                try:
                    if hasattr(event, 'model_dump'):
                        event_dict = event.model_dump()
                        logger.info(f"Full event as dict: {json.dumps(event_dict, default=str)[:1000]}")

                        # Check for errors first
                        if event_dict.get('error_code') == 'UNEXPECTED_TOOL_CALL':
                            error_msg = "Agent tried to call tools that are not available. Please ensure tools are properly registered or remove them from the configuration."
                            logger.warning(f"Tool call error: {error_msg}")
                            # Return a helpful message
                            response_text = f"I cannot access weather tools at the moment. The weather tools (get_weather, get_current_time) are not currently available."
                            all_responses.append(response_text)
                            logger.info(f"Generated fallback response for UNEXPECTED_TOOL_CALL")

                        # Look for response in various places
                        elif 'content' in event_dict and event_dict['content']:
                            if isinstance(event_dict['content'], str):
                                if not response_text and event_dict['content'].strip():
                                    response_text = event_dict['content']
                                    all_responses.append(response_text)
                                    logger.info(f"Found text in event_dict['content']: {response_text[:200]}")
                            elif isinstance(event_dict['content'], dict):
                                if 'text' in event_dict['content'] and event_dict['content']['text']:
                                    if not response_text:
                                        response_text = event_dict['content']['text']
                                        all_responses.append(response_text)
                                        logger.info(f"Found text in event_dict['content']['text']: {response_text[:200]}")
                except Exception as e:
                    logger.debug(f"Could not dump event to dict: {e}")

                # Log tool invocations for debugging
                if hasattr(event, 'get_function_calls'):
                    function_calls = event.get_function_calls()
                    if function_calls:
                        logger.info(f"Tool call requested: {function_calls}")

                if hasattr(event, 'get_function_responses'):
                    function_responses = event.get_function_responses()
                    if function_responses:
                        logger.info(f"Tool response received: {function_responses}")

            # If we collected multiple responses, join them
            if all_responses and not response_text:
                response_text = " ".join(all_responses)

            logger.info(f"=== ADK execution completed ===")
            logger.info(f"Total events processed: {event_count}")
            logger.info(f"Total responses collected: {len(all_responses)}")
            logger.info(f"Final response_text: {response_text[:200] if response_text else 'None'}")

            # Log all responses for debugging
            if all_responses:
                for i, resp in enumerate(all_responses):
                    logger.debug(f"Response {i+1}: {resp[:100]}")

            # Only clean up ephemeral sessions - chat sessions persist for continuity
            if is_ephemeral:
                await SESSION_SERVICE.delete_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                logger.info(f"Ephemeral session cleaned up: {session_id}")
            else:
                logger.info(f"Chat session preserved for continuity: {session_id}")

            # Return the response or a more informative message
            if response_text:
                logger.info(f"Returning response of length: {len(response_text)}")
                return response_text
            else:
                error_msg = f"No response generated after {event_count} events. Check: 1) API key validity, 2) Model '{agent.model}' availability, 3) Network connectivity"
                logger.warning(error_msg)
                return error_msg

        except Exception as e:
            logger.error(f"Error running ADK agent: {str(e)}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return f"Error: {str(e)}"

    async def _list_agents(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """List available agents"""
        agents = []

        # List from flow_agent_configs directory
        config_dir = Path("backend/flow_agent_configs")
        if config_dir.exists():
            for file in config_dir.glob("*.json"):
                agent_id = file.stem
                try:
                    with open(file, 'r') as f:
                        data = json.load(f)
                        agents.append({
                            'agent_id': agent_id,
                            'description': data.get('description', ''),
                            'model': data.get('model', 'unknown'),
                            'is_loaded': agent_id in LOADED_AGENTS
                        })
                except Exception as e:
                    logger.error(f"Error reading agent file {file}: {e}")

        # Also check legacy location
        legacy_dir = Path("backend/flow-agent/agents")
        if legacy_dir.exists():
            for file in legacy_dir.glob("*.json"):
                agent_id = file.stem
                # Skip if already listed
                if any(a['agent_id'] == agent_id for a in agents):
                    continue
                try:
                    with open(file, 'r') as f:
                        data = json.load(f)
                        agents.append({
                            'agent_id': agent_id,
                            'description': data.get('description', ''),
                            'model': data.get('model', 'unknown'),
                            'is_loaded': agent_id in LOADED_AGENTS
                        })
                except Exception as e:
                    logger.error(f"Error reading agent file {file}: {e}")

        return {
            'success': True,
            'agents': agents,
            'total': len(agents),
            'loaded_count': len(LOADED_AGENTS)
        }

    async def _load_agent(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-load an agent into memory"""
        agent_id = parameters.get('agent_id')
        if not agent_id:
            return {'error': True, 'message': 'agent_id is required'}

        if agent_id in LOADED_AGENTS:
            AGENT_LAST_USED[agent_id] = datetime.now()
            return {
                'success': True,
                'message': f"Agent '{agent_id}' is already loaded"
            }

        # Get API key (JWT token) for authentication
        api_key = parameters.get('api_key') or self.auth_credentials.get('api_key')
        if not api_key:
            api_key = os.environ.get('IOFLOW_API_KEY')

        agent = await self._load_agent_config(agent_id, api_key)
        if not agent:
            return {
                'error': True,
                'message': f"Failed to load agent '{agent_id}'"
            }

        return {
            'success': True,
            'message': f"Agent '{agent_id}' loaded successfully"
        }

    async def _unload_agent(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Unload an agent from memory"""
        agent_id = parameters.get('agent_id')
        if not agent_id:
            return {'error': True, 'message': 'agent_id is required'}

        if agent_id not in LOADED_AGENTS:
            return {
                'error': True,
                'message': f"Agent '{agent_id}' is not loaded"
            }

        self._cleanup_agent(agent_id)

        return {
            'success': True,
            'message': f"Agent '{agent_id}' unloaded from memory"
        }

    def _cleanup_agent(self, agent_id: str):
        """Clean up an agent from memory"""
        if agent_id in LOADED_AGENTS:
            del LOADED_AGENTS[agent_id]
        if agent_id in AGENT_RUNNERS:
            del AGENT_RUNNERS[agent_id]
        if agent_id in AGENT_LAST_USED:
            del AGENT_LAST_USED[agent_id]
        logger.info(f"Cleaned up agent '{agent_id}'")

    async def _create_agent_config(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new agent configuration"""
        agent_id = parameters.get('agent_id')
        if not agent_id:
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"

        config = {
            "agent_id": agent_id,
            "model": parameters.get('model', 'gemini-2.0-flash-exp'),
            "description": parameters.get('description', ''),
            "system_prompt": parameters.get('system_prompt', ''),
            "instruction": parameters.get('instruction', ''),
            "tools": parameters.get('tools', [])
        }

        # Save to flow_agent_configs directory
        config_dir = Path("backend/flow_agent_configs")
        config_dir.mkdir(exist_ok=True)

        config_path = config_dir / f"{agent_id}.json"

        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            return {
                'success': True,
                'agent_id': agent_id,
                'message': f"Agent configuration created: {agent_id}",
                'path': str(config_path)
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Failed to create agent configuration: {str(e)}"
            }

    def cleanup_idle_agents(self):
        """Remove agents that have been idle for too long"""
        current_time = datetime.now()
        agents_to_remove = []

        for agent_id, last_used in AGENT_LAST_USED.items():
            if (current_time - last_used).total_seconds() > MAX_AGENT_IDLE_TIME:
                agents_to_remove.append(agent_id)

        for agent_id in agents_to_remove:
            self._cleanup_agent(agent_id)
            logger.info(f"Auto-unloaded idle agent '{agent_id}'")