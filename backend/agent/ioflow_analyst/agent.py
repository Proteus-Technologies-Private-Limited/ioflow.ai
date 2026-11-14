#!/usr/bin/env python3
"""
IOFlow Analyst Agent for ADK Web Interface

This agent provides comprehensive analysis, documentation, and technical guidance for IOFlow.
It can search, analyze service configurations, explain flow components, and provide detailed technical information.
"""

import os
import sys
import json
import httpx
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from google import adk
from google.adk.tools.function_tool import FunctionTool
from dotenv import load_dotenv

# Load environment variables from .env file
# Try to load from project root first, then from current directory
env_path = Path(__file__).resolve().parents[3] / '.env'  # Goes up to IOFlow root
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Load from current directory if root .env doesn't exist

# Import the flow_designer agent to use as a sub-agent
sys.path.append(str(Path(__file__).parent.parent))
from flow_designer.agent import root_agent as flow_designer_agent

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get API keys from environment
api_key = os.getenv("IOFLOW_API_KEY", "")
base_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")

# Base function for calling MCP tools (not decorated)
async def _call_mcp_tool_impl(tool_name: str, parameters_json: str) -> str:
    """
    Internal implementation for calling MCP tools.
    """
    logger.debug(f"_call_mcp_tool_impl called with tool_name={tool_name}, parameters_json={parameters_json}")
    
    try:
        parameters = json.loads(parameters_json) if parameters_json else {}
        logger.debug(f"Parsed parameters: {parameters}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return json.dumps({"error": "Invalid parameters JSON"})
    
    logger.debug(f"Creating HTTP client with 60s timeout, base_url={base_url}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            url = f"{base_url}/api/mcp/tools/execute"
            payload = {
                "tool": tool_name,
                "parameters": parameters
            }
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            
            logger.debug(f"Making POST request to {url} with payload: {payload}")
            response = await client.post(url, json=payload, headers=headers)
            logger.debug(f"Response status: {response.status_code}")
            
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Response data: {result}")
            
            return json.dumps(result)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return json.dumps({
                "error": f"HTTP error: {e.response.status_code}",
                "details": e.response.text
            })
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return json.dumps({"error": str(e)})

# Decorated wrapper functions for each tool - using proper FunctionTool syntax without parameters
@FunctionTool
async def list_applications() -> str:
    """
    List all available applications in the system.
    
    Returns:
        JSON string with list of applications
    """
    logger.info("Listing applications")
    return await _call_mcp_tool_impl("list_applications", "{}")

@FunctionTool
async def search_applications(query: str) -> str:
    """
    Search for applications by name or description.
    
    Args:
        query: Search query for applications
    
    Returns:
        JSON string with matching applications
    """
    logger.info(f"Searching applications with query: {query}")
    return await _call_mcp_tool_impl("search_applications", json.dumps({"query": query}))

@FunctionTool
async def get_application_details(application_id: str) -> str:
    """
    Get details of a specific application.
    
    Args:
        application_id: The ID of the application
    
    Returns:
        JSON string with application details
    """
    logger.info(f"Getting details for application: {application_id}")
    return await _call_mcp_tool_impl("get_application", json.dumps({"application_id": application_id}))

@FunctionTool
async def search_services(query: str, application_id: Optional[str] = None) -> str:
    """
    Search for services across all applications.
    
    Args:
        query: Search query for services
        application_id: Optional filter by application ID
    
    Returns:
        JSON string with matching services
    """
    logger.info(f"Searching services with query: {query}, app_id: {application_id}")
    params = {"query": query}
    if application_id:
        params["application_id"] = application_id
    return await _call_mcp_tool_impl("search_services", json.dumps(params))

@FunctionTool
async def get_application_services_list(app_id: str) -> str:
    """
    Get basic service information for a specific application.
    
    Args:
        app_id: Application ID (UUID) from list_applications() - e.g., '351850ab-cf3c-438c-b276-e88567f3ad63'
    
    Returns:
        JSON string with list of services (basic info only - service_id, name, description, type)
        
    Note: For detailed parameter schemas and mapping information, use get_service_information()
    """
    logger.info(f"Getting services for application: {app_id}")
    return await _call_mcp_tool_impl("get_application_services_list", json.dumps({"app_id": app_id}))

@FunctionTool
async def search_flows(query: str) -> str:
    """
    Search for flows by name or description.
    
    Args:
        query: Search query for flows
    
    Returns:
        JSON string with matching flows
    """
    logger.info(f"Searching flows with query: {query}")
    return await _call_mcp_tool_impl("search_flows", json.dumps({"query": query}))

@FunctionTool
async def get_ioflow_documentation(doc_type: Optional[str] = None) -> str:
    """
    Get comprehensive IOFlow documentation including service creation guides, event types, and best practices.
    
    Args:
        doc_type: Optional type of documentation to retrieve (service_docs, event_docs, app_guide, or leave empty for overview)
    
    Returns:
        JSON string with documentation content
    """
    logger.info(f"Getting IOFlow documentation: {doc_type}")
    
    tool_name = "ioflow_get_app_guide"  # Default to complete guide
    params = {}
    
    if doc_type == "service_docs":
        tool_name = "ioflow_get_service_docs"
    elif doc_type == "event_docs":
        tool_name = "ioflow_get_event_docs"
    elif doc_type in ["api_call", "webhook", "database_query", "email_send", "llm_api_call", "mcp_call"]:
        tool_name = "ioflow_get_service_docs"
        params = {"service_type": doc_type}
    elif doc_type in ["webhook_event", "schedule", "polling", "manual", "email", "form"]:
        tool_name = "ioflow_get_event_docs"
        params = {"event_type": doc_type.replace("_event", "")}
    
    return await _call_mcp_tool_impl(tool_name, json.dumps(params))

@FunctionTool
async def explore_seed_applications(category: Optional[str] = None) -> str:
    """
    Explore available seed applications in IOFlow that can be installed.
    
    Args:
        category: Optional category filter (e.g., "Integration", "AI", "Communication")
    
    Returns:
        JSON string with list of seed applications
    """
    logger.info(f"Exploring seed applications, category: {category}")
    params = {"category": category} if category else {}
    return await _call_mcp_tool_impl("explore_seed_applications", json.dumps(params))

@FunctionTool
async def get_seed_application_details(app_key: str) -> str:
    """
    Get detailed information about a specific seed application including services and configuration.
    
    Args:
        app_key: The unique key of the seed application (e.g., "openai", "stripe", "gmail")
    
    Returns:
        JSON string with complete application details
    """
    logger.info(f"Getting seed application details for: {app_key}")
    return await _call_mcp_tool_impl("get_seed_application", json.dumps({"app_key": app_key}))

@FunctionTool
async def get_application_categories() -> str:
    """
    Get all available application categories in IOFlow.
    
    Returns:
        JSON string with list of categories and their descriptions
    """
    logger.info("Getting application categories")
    return await _call_mcp_tool_impl("get_application_categories", json.dumps({}))

@FunctionTool
async def search_ioflow_docs(query: str) -> str:
    """
    Search IOFlow documentation for specific terms or concepts.
    
    Args:
        query: Search query for documentation
    
    Returns:
        JSON string with search results from documentation
    """
    logger.info(f"Searching IOFlow docs with query: {query}")
    return await _call_mcp_tool_impl("ioflow_search_docs", json.dumps({"query": query}))

@FunctionTool
async def compare_applications(app_keys: str) -> str:
    """
    Compare multiple applications side by side to understand their differences.
    
    Args:
        app_keys: Comma-separated list of application keys to compare (e.g., "openai,anthropic,google_gemini")
    
    Returns:
        JSON string with comparison table
    """
    logger.info(f"Comparing applications: {app_keys}")
    keys_list = [key.strip() for key in app_keys.split(",")]
    
    # Get details for each application
    comparisons = []
    for key in keys_list:
        try:
            result = await _call_mcp_tool_impl("get_seed_application", json.dumps({"app_key": key}))
            comparisons.append(json.loads(result))
        except:
            comparisons.append({"error": f"Could not get details for {key}"})
    
    return json.dumps({
        "comparison": comparisons,
        "app_keys": keys_list
    })

# REMOVED: get_flow_design_structure - Flow design tasks should be delegated to flow_designer

@FunctionTool
async def get_service_information(app_key: str, service_name: str) -> str:
    """
    Get detailed information about a specific service including parameter schemas.
    
    Args:
        app_key: Application ID (UUID) from list_applications() - e.g., '351850ab-cf3c-438c-b276-e88567f3ad63'
        service_name: The name of the service (e.g., 'send_email', 'execute_query', 'generate_content', 'chat_completion')
    
    Returns:
        JSON string with detailed service information including:
        - Complete parameter schema with types, descriptions, and constraints
        - Parameter mapping hints and examples
        - Service configuration details
        - Usage guidance and best practices
    """
    logger.info(f"Getting service information for app: {app_key}, service: {service_name}")
    return await _call_mcp_tool_impl("get_service_information", json.dumps({
        "app_key": app_key,
        "service_name": service_name
    }))

@FunctionTool
async def get_transform_node_guide() -> str:
    """
    Get comprehensive guide for transform nodes including available Python modules and examples.
    
    Returns:
        JSON string with transform environment details, available modules like:
        - json, datetime, re, math, random
        - reportlab for PDF generation
        - pandas for data processing
        - Code examples for data transformation and PDF generation
    """
    logger.info("Getting transform node guide")
    return await _call_mcp_tool_impl("get_transform_node_guide", json.dumps({}))

@FunctionTool
async def get_parameter_mapping_guide() -> str:
    """
    Get comprehensive guide for parameter mapping in action nodes.
    
    Returns:
        JSON string with parameter mapping formats including:
        - Static vs variable source types
        - Array and object mapping patterns
        - Conditional mapping examples
        - Legacy format compatibility
    """
    logger.info("Getting parameter mapping guide")
    return await _call_mcp_tool_impl("get_parameter_mapping_guide", json.dumps({}))

@FunctionTool
async def get_variable_reference_guide() -> str:
    """
    Get comprehensive guide for variable references and scopes in flows.
    
    Returns:
        JSON string with variable scopes including:
        - input variables from triggers
        - node_outputs from previous nodes
        - global_vars set by transform nodes
        - loop variables (item, index, isFirst, isLast)
        - Path resolution examples
    """
    logger.info("Getting variable reference guide")
    return await _call_mcp_tool_impl("get_variable_reference_guide", json.dumps({}))

@FunctionTool
async def get_pdf_generation_guide() -> str:
    """
    Get comprehensive guide for PDF generation using ReportLab in transform nodes.
    
    Returns:
        JSON string with PDF generation examples including:
        - Basic PDF with canvas
        - Advanced PDFs with tables and styling
        - Available components and units
        - Base64 encoding for output
    """
    logger.info("Getting PDF generation guide")
    return await _call_mcp_tool_impl("get_pdf_generation_guide", json.dumps({}))

@FunctionTool
async def get_node_examples() -> str:
    """
    Get working examples for each node type in flows.
    
    Returns:
        JSON string with examples for:
        - Action nodes with parameter mapping
        - Transform nodes with Python scripts
        - Loop nodes for iteration
        - Condition nodes for branching
        - Response nodes for returning data
    """
    logger.info("Getting node examples")
    return await _call_mcp_tool_impl("get_node_examples", json.dumps({}))

# REMOVED: validate_flow_design - Flow validation should be delegated to flow_designer

@FunctionTool
async def create_flow_design(
    flow_name: str,
    flow_json: str
) -> str:
    """
    Create a new flow design file for the authenticated user using MCP tool.
    
    Args:
        flow_name: Name for the flow design
        flow_json: Flow design JSON string
    
    Returns:
        JSON with file details including path, filename, and size
    """
    logger.info(f"Creating flow design: {flow_name}")
    return await _call_mcp_tool_impl("create_flow_design", json.dumps({
        "flow_name": flow_name,
        "flow_json": flow_json
    }))

@FunctionTool
async def replace_flow_design(
    flow_name: str,
    flow_json: str,
    original_filename: Optional[str] = None
) -> str:
    """
    Replace an existing flow design or create a new version for the authenticated user.
    
    Args:
        flow_name: Name for the flow design
        flow_json: Flow design JSON string
        original_filename: Optional original filename to replace
    
    Returns:
        JSON with file details including path, filename, and backup status
    """
    logger.info(f"Replacing flow design: {flow_name}")
    params = {
        "flow_name": flow_name,
        "flow_json": flow_json
    }
    if original_filename:
        params["original_filename"] = original_filename
    return await _call_mcp_tool_impl("replace_flow_design", json.dumps(params))

@FunctionTool
async def list_user_flow_designs() -> str:
    """
    List all flow designs for the authenticated user.
    
    Returns:
        JSON with list of flow design files including paths and metadata
    """
    logger.info(f"Listing flow designs for authenticated user")
    return await _call_mcp_tool_impl("list_user_flow_designs", json.dumps({}))

# REMOVED: _save_and_display_flow_impl - Flow saving is now handled by flow_designer
# The flow_designer agent now saves flows directly and returns the result

async def _deprecated_save_and_display_flow_impl(flow_data: str) -> str:
    """
    DEPRECATED: This function is no longer used. Flow saving is handled by flow_designer.
    """
    logger.info("DEPRECATED: save_and_display_flow called - should use flow_designer instead")
    try:
        # Parse the response - could be in different formats
        response = None
        
        # Check if it's a string that might contain JSON
        if isinstance(flow_data, str):
            # Try to extract JSON from code blocks
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', flow_data, re.DOTALL)
            if json_match:
                try:
                    response = json.loads(json_match.group(1))
                    logger.info("Extracted JSON from code block")
                except:
                    pass
            
            # If no code block, try parsing the whole string
            if not response:
                try:
                    response = json.loads(flow_data)
                    logger.info("Parsed entire string as JSON")
                except:
                    # Maybe it's just the text with embedded JSON
                    # Try to find JSON structure in the text
                    json_start = flow_data.find('{')
                    if json_start >= 0:
                        try:
                            response = json.loads(flow_data[json_start:])
                            logger.info("Extracted JSON from text")
                        except:
                            pass
        else:
            response = flow_data
        
        # Check if we got a response
        if not response:
            return f"❌ Error: Could not extract JSON from response. Response was: {str(flow_data)[:500]}"
        
        # Detect format and extract flow data
        if "success" in response and "flow_data" in response:
            # Format 1: Sub-agent return format
            if not response.get("success"):
                return f"❌ Error: {response.get('error', 'Unknown error')}"
            flow_json = response.get("flow_data", {})
            flow_name = response.get("flow_name", "flow")
            filename = response.get("filename", f"{flow_name}.json")
        elif "version" in response and "flow" in response:
            # Format 2: Direct export format
            flow_json = response
            flow_name = response.get("flow", {}).get("flow_name", "flow")
            filename = f"{flow_name.lower().replace(' ', '_')}.json"
        else:
            # Try to detect if it's a flow structure without wrapper
            if "flow_definition" in response and "flow_name" in response:
                # Wrap in export format
                flow_json = {
                    "version": "1.0",
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "flow": response,
                    "metadata": {"required_applications": [], "warnings": []}
                }
                flow_name = response.get("flow_name", "flow")
                filename = f"{flow_name.lower().replace(' ', '_')}.json"
            else:
                return f"❌ Error: Unrecognized flow format. Expected success/flow_data or version/flow structure."
        
        # Save the flow using MCP tool (user determined from auth context)
        save_result = await _call_mcp_tool_impl("create_flow_design", json.dumps({
            "flow_name": flow_name,
            "flow_json": json.dumps(flow_json)
        }))
        
        # Parse the MCP response which has success/result structure
        mcp_response = json.loads(save_result)
        
        # Extract the actual result data from MCP response
        if mcp_response.get("success") and mcp_response.get("result"):
            save_data = mcp_response.get("result")
        else:
            save_data = {"success": False, "error": mcp_response.get("error", "Unknown error")}
        
        # Format the JSON nicely
        formatted_json = json.dumps(flow_json, indent=2, ensure_ascii=False)
        
        # Return formatted message with the JSON content
        if save_data.get("success"):
            output = f"""✅ **Flow JSON Generated and Saved Successfully!**

📁 **File Path:** `{save_data.get('file_path')}`
📄 **Filename:** `{save_data.get('filename')}`
📊 **Size:** {save_data.get('size', len(formatted_json)):,} bytes

## Your Flow JSON:

```json
{formatted_json}
```

**Flow has been saved to:** {save_data.get('user_directory')}/{save_data.get('filename')}

Flow design saved successfully.

---
🛑 **TASK COMPLETE** - Flow saved successfully. No further processing needed."""
        else:
            # If save failed, still show the JSON
            output = f"""⚠️ **Flow JSON Generated (Save Failed)**

📄 **Filename:** `{filename}`
📊 **Size:** {len(formatted_json):,} bytes
⚠️ **Note:** Could not save to file: {save_data.get('error', 'Unknown error')}

## Your Flow JSON:

```json
{formatted_json}
```

**To use this flow:**
1. Copy the JSON above
2. Save it as `{filename}`
3. Import it into IOFlow

---
🛑 **TASK COMPLETE** - JSON generated. No further processing needed."""
        
        return output
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from flow_assistant: {e}")
        return f"❌ Error: Invalid JSON format from flow_assistant - {str(e)}"
    except Exception as e:
        logger.error(f"Error displaying flow JSON: {e}")
        return f"❌ Error: {str(e)}"

# REMOVED: save_and_display_flow - Flow saving is now handled directly by flow_designer

@FunctionTool
async def search_web(query: str) -> str:
    """
    Search the web for current information about APIs, services, technical documentation, or any topic.
    This function helps discover API capabilities of various applications.
    
    Args:
        query: Search query for web search (e.g., "Gmail API documentation", "Stripe payment API")
    
    Returns:
        JSON string with search results and relevant information
    """
    logger.info(f"Searching web with query: {query}")
    
    # Fallback to calling Gemini API with search grounding via HTTP
    try:
        # Try multiple sources for API key
        api_key = (
            os.getenv("GOOGLE_API_KEY") or 
            os.getenv("GEMINI_API_KEY") or 
            os.getenv("GOOGLE_GENAI_API_KEY") or
            os.getenv("GOOGLE_GENERATIVEAI_API_KEY")
        )
        
        if not api_key:
            # Provide helpful instructions for setting up web search
            return json.dumps({
                "query": query,
                "error": "API key not configured",
                "message": "Web search requires a Google API key. Please set one of these environment variables: GOOGLE_API_KEY, GEMINI_API_KEY, or GOOGLE_GENAI_API_KEY",
                "instructions": [
                    "1. Get a Google API key from https://makersuite.google.com/app/apikey",
                    "2. Add to your .env file: GOOGLE_API_KEY=your-api-key-here",
                    "3. Restart the agent server"
                ]
            })
        
        # Use httpx to call Gemini API directly
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }
            
            # Construct the request with search grounding
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"""Search the web for: {query}
                        
                        Focus on:
                        - API documentation and specifications
                        - Technical details and capabilities
                        - Current information and updates
                        - Official documentation links
                        
                        Provide a comprehensive summary of the findings."""
                    }]
                }],
                "tools": [{
                    "googleSearch": {}  # Enable Google Search grounding
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.8,
                    "maxOutputTokens": 2048
                }
            }
            
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract the text content
                text_content = ""
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                text_content = part["text"]
                                break
                
                # Extract grounding metadata if available
                sources = []
                if "groundingMetadata" in data:
                    metadata = data["groundingMetadata"]
                    if "webSearchQueries" in metadata:
                        sources.append({"type": "search_queries", "data": metadata["webSearchQueries"]})
                    if "groundingAttributions" in metadata:
                        for attr in metadata["groundingAttributions"]:
                            if "sourceId" in attr:
                                sources.append({"url": attr["sourceId"]["groundingPassage"]["uri"] if "groundingPassage" in attr["sourceId"] else attr["sourceId"]})
                
                return json.dumps({
                    "query": query,
                    "results": text_content or "No results found",
                    "sources": sources,
                    "status": "success"
                })
            else:
                error_msg = response.text
                logger.error(f"Gemini API error: {response.status_code} - {error_msg}")
                return json.dumps({
                    "query": query,
                    "error": f"API error: {response.status_code}",
                    "message": "Could not complete web search. Please try again."
                })
                
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return json.dumps({
            "query": query,
            "error": str(e),
            "message": "Web search encountered an error. Please ensure API keys are configured and try again."
        })

# ============================================================================
# Flow Designer V2 Tools (Session-Based, Optimized)
# ============================================================================

@FunctionTool
async def create_flow_session(name: str, description: str = "", ttl_minutes: int = 30) -> str:
    """
    Create a new flow design session (V2 - optimized, session-based).

    This creates a session for incremental flow building with checkpointing and recovery.

    Args:
        name: Flow name
        description: Flow description (optional)
        ttl_minutes: Session TTL in minutes (default: 30)

    Returns:
        JSON string with session_id, status, and expiration info
    """
    logger.info(f"Creating flow session V2: {name}")
    return await _call_mcp_tool_impl("create_flow_session",
                                     json.dumps({"name": name, "description": description, "ttl_minutes": ttl_minutes}))

@FunctionTool
async def resume_flow_session(session_id: str) -> str:
    """
    Resume an existing flow design session (V2).

    Args:
        session_id: Session ID to resume

    Returns:
        JSON string with current session state including nodes, edges, and checkpoints
    """
    logger.info(f"Resuming flow session V2: {session_id}")
    return await _call_mcp_tool_impl("resume_flow_session", json.dumps({"session_id": session_id}))

@FunctionTool
async def add_trigger_node(session_id: str, trigger_type: str, config: str) -> str:
    """
    Add a trigger node to flow session (V2).

    Args:
        session_id: Session ID
        trigger_type: Type - "manual", "webhook", "schedule", or "application_event"
        config: JSON string with trigger configuration:
            For manual: {"variables": [{"name": "x", "dataType": "string"}]}
            For webhook: {"webhook_path": "/hook", "method": "POST"}
            For schedule: {"cron_expression": "0 0 * * *"}
            For event: {"app_id": "...", "event_id": "..."}

    Returns:
        JSON string with node_id and session info
    """
    logger.info(f"Adding trigger node V2: {trigger_type} to session {session_id}")
    config_dict = json.loads(config) if isinstance(config, str) else config
    return await _call_mcp_tool_impl("add_trigger_node",
                                     json.dumps({"session_id": session_id, "trigger_type": trigger_type, "config": config_dict}))

@FunctionTool
async def add_action_node(session_id: str, app_id: str, service_id: str, parameters: str,
                         app_name: str = "", service_name: str = "") -> str:
    """
    Add an action node to flow session (V2).

    Args:
        session_id: Session ID
        app_id: Application ID (UUID)
        service_id: Service ID (UUID)
        parameters: JSON string with service parameters (can include variable references like {{input.x}})
        app_name: Application name for display (optional)
        service_name: Service name for display (optional)

    Returns:
        JSON string with node_id and session info
    """
    logger.info(f"Adding action node V2: {service_name} to session {session_id}")
    params_dict = json.loads(parameters) if isinstance(parameters, str) else parameters
    return await _call_mcp_tool_impl("add_action_node",
                                     json.dumps({
                                         "session_id": session_id,
                                         "app_id": app_id,
                                         "service_id": service_id,
                                         "parameters": params_dict,
                                         "app_name": app_name,
                                         "service_name": service_name
                                     }))

@FunctionTool
async def connect_nodes(session_id: str, source_id: str, target_id: str) -> str:
    """
    Connect two nodes with an edge (V2).

    Args:
        session_id: Session ID
        source_id: Source node ID
        target_id: Target node ID

    Returns:
        JSON string with edge_id and confirmation
    """
    logger.info(f"Connecting nodes V2: {source_id} -> {target_id} in session {session_id}")
    return await _call_mcp_tool_impl("connect_nodes",
                                     json.dumps({"session_id": session_id, "source_id": source_id, "target_id": target_id}))

@FunctionTool
async def create_checkpoint(session_id: str, label: str = "") -> str:
    """
    Create a checkpoint for the session (V2).

    Checkpoints allow you to save progress and restore later if needed.

    Args:
        session_id: Session ID
        label: Optional checkpoint label/description

    Returns:
        JSON string with checkpoint_id
    """
    logger.info(f"Creating checkpoint V2 for session {session_id}: {label}")
    return await _call_mcp_tool_impl("create_checkpoint",
                                     json.dumps({"session_id": session_id, "label": label}))

@FunctionTool
async def restore_checkpoint(session_id: str, checkpoint_id: str) -> str:
    """
    Restore session from a checkpoint (V2).

    Args:
        session_id: Session ID
        checkpoint_id: Checkpoint ID to restore

    Returns:
        JSON string with restored session state
    """
    logger.info(f"Restoring checkpoint V2: {checkpoint_id} for session {session_id}")
    return await _call_mcp_tool_impl("restore_checkpoint",
                                     json.dumps({"session_id": session_id, "checkpoint_id": checkpoint_id}))

@FunctionTool
async def complete_flow_session(session_id: str) -> str:
    """
    Complete the session and generate final flow JSON (V2).

    This marks the session as completed and returns the complete flow definition.

    Args:
        session_id: Session ID

    Returns:
        JSON string with complete flow JSON in export format
    """
    logger.info(f"Completing flow session V2: {session_id}")
    return await _call_mcp_tool_impl("complete_flow_session", json.dumps({"session_id": session_id}))

@FunctionTool
async def get_lightweight_applications(category: str = "", search: str = "") -> str:
    """
    Get lightweight list of applications (V2 - cached, optimized).

    Returns minimal data with caching for better performance.

    Args:
        category: Optional filter by category
        search: Optional search by name

    Returns:
        JSON string with lightweight application list
    """
    logger.info(f"Getting lightweight applications V2: category={category}, search={search}")
    params = {}
    if category:
        params["category"] = category
    if search:
        params["search"] = search
    return await _call_mcp_tool_impl("get_lightweight_applications", json.dumps(params))

# Get model from environment - check specific override first, then general setting
model_name = os.getenv("IOFLOW_ANALYST_MODEL") or os.getenv("AGENT_MODEL", "gemini-2.5-pro")
logger.info(f"IOFlow Analyst using model: {model_name}")
logger.info(f"Model from env: IOFLOW_ANALYST_MODEL={os.getenv('IOFLOW_ANALYST_MODEL')}, AGENT_MODEL={os.getenv('AGENT_MODEL')}")

# No longer using AgentTool - flow_designer is added as a proper subagent

# Create the root agent with flow_designer as a subagent
root_agent = adk.Agent(
    name="ioflow_analyst",
    model=model_name,  # Model from environment
    description="""I am the IOFlow Analyst - a comprehensive analysis and information assistant for IOFlow. I can help you:

1. **Search IOFlow Resources:**
   - Applications, services, and flows within IOFlow
   - Seed applications available for installation
   - IOFlow documentation and guides

2. **Service Information & Documentation:**
   - Exact parameter schemas for any service
   - Parameter mapping patterns and examples
   - Transform node documentation and available modules
   - Variable references and scopes

3. **Technical Guides & Best Practices:**
   - Parameter mapping (static vs variable sources)
   - Variable scopes (input, node_outputs, global_vars, loop)
   - Transform environment restrictions and capabilities
   - Node types and their usage

4. **Web Search & Comparison:**
   - External API documentation
   - Compare multiple applications
   - Current technical information

5. **Application Discovery:**
   - Explore seed applications by category
   - Get detailed application information
   - Compare different services

**IMPORTANT:** For flow design tasks, I have two approaches:

**Option 1: Flow Designer Subagent (V1)** - Full delegation for complete flows:
- Creating complete flow JSON configurations
- Modifying and fixing flow issues
- Validating flow structures
- Use via: transfer_to_agent("flow_designer", request)

**Option 2: Flow Designer V2 Tools (Recommended)** - Session-based, incremental building:
- Optimized for token efficiency (99.7% less tokens)
- Session-based with checkpoints for recovery
- Build flows incrementally step-by-step
- Works with mid-tier models (Gemini Flash, GPT-3.5+)
- Use via: create_flow_session() → add nodes → connect → complete

**V2 is recommended for:**
- Large or complex flows
- When you need checkpoints
- Token optimization (lower costs)
- Incremental building with progress tracking

What would you like to know about IOFlow? For flow creation, I can use V2 tools or delegate to Flow Designer.""",
    instruction="""You are the IOFlow Analyst. You help users with IOFlow information and delegate flow creation to the Flow Designer subagent.

## CRITICAL ERROR HANDLING RULES:
When a user reports an error from flow execution:
1. **ANALYZE COMPREHENSIVELY FIRST:**
   - Read the ENTIRE error log carefully
   - Identify ALL issues present (there may be multiple)
   - List each specific problem found
   - DO NOT start fixing immediately

2. **SINGLE DELEGATION ONLY:**
   - After analyzing ALL errors, make ONE call to flow_designer
   - Include ALL fixes needed in a single comprehensive request
   - Example: "Fix the following issues in the flow: 1) Transform node script has incorrect syntax, 2) Action node missing serviceId, 3) Parameter mapping needs correction for X"
   - NEVER make multiple calls to flow_designer for the same error report

3. **STOP AFTER DELEGATION:**
   - Once flow_designer returns with the fixed flow, display it
   - DO NOT analyze the result and call flow_designer again
   - The task is COMPLETE after one fix attempt

## FOR FLOW CREATION/MODIFICATION:

### Option 1: Flow Designer V2 Tools (RECOMMENDED for most cases)
Use session-based incremental building with these tools:

**Workflow:**
1. `create_flow_session(name, description)` - Start a session
2. `add_trigger_node(session_id, trigger_type, config)` - Add trigger
3. `add_action_node(session_id, app_id, service_id, parameters)` - Add actions
4. `connect_nodes(session_id, source_id, target_id)` - Connect nodes
5. `create_checkpoint(session_id, label)` - Save progress (optional)
6. `complete_flow_session(session_id)` - Generate final JSON

**Benefits:**
- 99.7% less tokens (works with cheaper models)
- Checkpoint/restore for recovery
- Incremental progress tracking
- Session-based (can resume if interrupted)

**When to use V2:**
- Large flows (>3 nodes)
- Complex flows needing checkpoints
- When token optimization matters
- When using mid-tier models

### Option 2: Flow Designer Subagent (V1)
Use for simple flows or when you need full validation:

1. Use transfer_to_agent("flow_designer", <request>) to delegate
2. The Flow Designer will handle creation, validation, and saving
3. Display the result and STOP

**When to use V1:**
- Simple 1-2 node flows
- Need immediate complete result
- Complex validation requirements

## YOUR DIRECT TASKS:
- Search applications, services, flows
- Provide documentation and guides
- Compare applications and services
- Web search for API information

## SERVICE INFORMATION:
When calling get_service_information:
- Use the Application ID (UUID) from list_applications() as the app_key parameter
- Example: '351850ab-cf3c-438c-b276-e88567f3ad63'
- Answer IOFlow questions

## DELEGATE TO flow_designer FOR:
- Creating or modifying flows
- Fixing flow errors (WITH ALL ISSUES IN ONE REQUEST)
- Writing transform scripts
- Configuring parameters
- Any flow JSON work

## STRICT RULES:
- NEVER call flow_designer twice for the same request
- NEVER try to fix flow JSON yourself - always delegate
- When errors are reported, analyze ALL issues BEFORE delegating
- Include ALL necessary fixes in ONE delegation request
- STOP after flow_designer returns - do not iterate

When delegating to flow_designer, use transfer_to_agent with a COMPLETE description of what needs to be fixed or created.""",
    sub_agents=[flow_designer_agent],  # Add flow_designer as a proper subagent
    tools=[
        # Flow design is now delegated via transfer_to_agent to flow_designer

        # IOFlow application search and management
        list_applications,
        search_applications,
        get_application_details,
        search_services,
        get_application_services_list,
        search_flows,

        # IOFlow exploration and documentation
        get_ioflow_documentation,
        explore_seed_applications,
        get_seed_application_details,
        get_application_categories,
        search_ioflow_docs,
        compare_applications,

        # Service configuration and documentation only (flow design delegated to flow_designer)
        get_service_information,
        get_transform_node_guide,
        get_parameter_mapping_guide,
        get_variable_reference_guide,
        get_pdf_generation_guide,
        get_node_examples,

        # Flow design management
        create_flow_design,
        replace_flow_design,
        list_user_flow_designs,

        # Flow Designer V2 Tools (Session-Based, Optimized)
        create_flow_session,
        resume_flow_session,
        add_trigger_node,
        add_action_node,
        connect_nodes,
        create_checkpoint,
        restore_checkpoint,
        complete_flow_session,
        get_lightweight_applications,

        # Flow saving is now handled directly by flow_designer

        # Web search for external information
        search_web
    ]
)

# Also expose as 'agent' for compatibility
agent = root_agent

logger.info("IOFlow Analyst Agent created with Flow Designer subagent")