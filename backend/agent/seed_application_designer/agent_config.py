"""
Seed Application Designer Agent Configuration

This file documents the configuration for the Seed Application Designer agent.
The actual agent implementation uses MCPToolset which auto-discovers all tools.

Agent Metadata:
- Name: seed_application_designer
- Model: Configurable via SEED_APP_AGENT_MODEL or AGENT_MODEL env var (default: gemini-2.5-pro)
- Purpose: Create, edit, install, configure, and debug IOFlow applications

Tool Categories Used:
- Exploration Tools (5): explore_seed_applications, get_seed_application, etc.
- Management Tools (8): create_seed_application, edit_application_metadata, etc.
- Testing Tools (8): validate_application_schema, test_service_endpoint, etc.
- Deployment Tools (7): install_application, uninstall_application, etc.

Total Tools: 28 tools from MCP bridge

Environment Variables:
- IOFLOW_API_KEY: Authentication token (JWT or API key)
- IOFLOW_BASE_URL: IOFlow backend URL (default: http://localhost:7001)
- SEED_APP_AGENT_MODEL: Model to use (default: gemini-2.5-pro)
- AGENT_MODEL: Fallback model configuration
- PYTHONPATH: Set to backend directory for MCP server

MCP Connection:
- Type: stdio (subprocess)
- Server: backend/mcp_server/ioflow_mcp_server.py
- Communication: All tools accessed through MCP bridge
- Isolation: Fresh MCP server instance per agent execution

Supported Workflows:
1. Create new seed application from scratch
2. Edit existing seed application (increment version)
3. Install and configure application for tenant
4. Debug and test application issues

Key Features:
- Conversational workflow (guides users step-by-step)
- Comprehensive validation before saving
- Testing and debugging capabilities
- Version management (auto-increment on updates)
- Authentication configuration support
- Service and event management
"""

# Agent is created in agent.py using MCPToolset
# This file serves as documentation and reference
