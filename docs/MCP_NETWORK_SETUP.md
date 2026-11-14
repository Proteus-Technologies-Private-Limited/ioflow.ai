# IOFlow Network-Accessible MCP Setup

This document describes the network-accessible MCP (Model Context Protocol) implementation for IOFlow, allowing Claude Desktop to access IOFlow functionality from remote machines.

## Architecture Overview

The solution consists of three main components:

1. **MCP Bridge API** (`/backend/api/mcp_bridge.py`)
   - FastAPI endpoints exposing MCP functionality over HTTP
   - Handles authentication via API keys
   - Translates between HTTP requests and MCP tool execution

2. **Remote MCP Client** (`/backend/mcp_server/remote_client.py`)
   - Runs on the client machine (where Claude Desktop is installed)
   - Connects to IOFlow server over HTTP
   - Exposes tools to Claude Desktop via stdio MCP protocol

3. **Claude Desktop Configuration**
   - Configures Claude Desktop to use the remote MCP client
   - Passes server URL and API key via environment variables

## Setup Instructions

### 1. Start IOFlow Backend

Ensure the IOFlow backend is running with the MCP bridge enabled:

```bash
cd backend
python main.py  # Runs on port 7001 by default
```

### 2. Configure Claude Desktop

1. Get an API key from IOFlow:
   - Log into IOFlow web interface
   - Navigate to Settings > API Keys
   - Create a new API key or use an existing one

2. Update Claude Desktop configuration:

**macOS:**
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

Add the following configuration:

```json
{
  "mcpServers": {
    "ioflow-remote": {
      "command": "/path/to/python",
      "args": ["/path/to/IOFlow/backend/mcp_server/remote_client.py"],
      "env": {
        "IOFLOW_SERVER_URL": "http://localhost:7001",
        "IOFLOW_API_KEY": "ioflow_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

For remote access, replace `localhost` with the server's IP address or hostname.

### 3. Restart Claude Desktop

After updating the configuration, completely quit and restart Claude Desktop.

## Available Tools

The MCP bridge exposes 28+ tools across different categories:

### Exploration Tools
- `explore_seed_applications` - Browse available integrations
- `get_seed_application` - Get details about specific apps
- `get_sample_application` - Get sample application templates
- `explain_application_schema` - Understand schema structure
- `get_application_categories` - List available categories

### Management Tools
- `create_seed_application` - Create new integrations
- `edit_application_metadata` - Modify app information
- `add_service_to_application` - Add new services
- `remove_service_from_application` - Remove services
- `add_event_to_application` - Add event triggers
- `update_auth_configuration` - Update authentication
- `delete_seed_application` - Delete applications
- `duplicate_application` - Clone existing apps

### Testing Tools
- `validate_application_schema` - Validate JSON structure
- `test_service_endpoint` - Test API endpoints
- `test_authentication` - Test auth configuration
- `test_parameter_extraction` - Test parameter mapping
- `simulate_service_execution` - Simulate service calls
- `generate_test_report` - Comprehensive testing
- `debug_failed_service` - Debug failures
- `test_event_subscription` - Test event handling

### Deployment Tools
- `install_application` - Deploy apps to IOFlow
- `uninstall_application` - Remove applications
- `update_installed_application` - Update deployed apps
- `list_installed_applications` - View deployed apps
- `verify_deployment` - Check deployment status
- `rollback_application` - Rollback changes
- `create_application_subscription` - Manage subscriptions

## Testing the Connection

Use the provided test script to verify the MCP bridge is working:

```bash
cd backend
python test_mcp_connection.py --api-key "your_api_key"
```

This will test:
- Connection to the server
- Authentication with API key
- Tool discovery
- Basic tool execution

## Troubleshooting

### "Connection refused" error
- Ensure IOFlow backend is running
- Check the server is listening on the correct port (7001)
- Verify firewall settings

### "Authentication failed" error
- Double-check the API key is correct
- Ensure the API key is active in IOFlow
- Verify the user has proper permissions

### "Extension not found" in Claude Desktop
- Check the MCP server name matches in config (`ioflow-remote`)
- Ensure Python path is correct in the configuration
- Verify the remote_client.py path is absolute
- Check Claude Desktop logs for detailed errors

### Tools not appearing in Claude
- Restart Claude Desktop after config changes
- Test the connection using test_mcp_connection.py
- Check if all required Python packages are installed

## Security Considerations

1. **API Key Security**
   - Store API keys securely
   - Use environment variables in production
   - Rotate keys regularly
   - Never commit keys to version control

2. **Network Security**
   - Use HTTPS in production environments
   - Consider VPN for remote access
   - Implement IP whitelisting if needed
   - Monitor API usage

3. **Access Control**
   - API keys inherit user permissions
   - Limit tool access based on user roles
   - Audit tool usage through IOFlow logs

## Implementation Details

### MCP Bridge API

The bridge exposes the following endpoints:

- `GET /api/mcp/info` - Server information and capabilities
- `GET /api/mcp/tools` - List available tools
- `POST /api/mcp/tools/execute` - Execute a tool
- `GET /api/mcp/resources` - List available resources
- `GET /api/mcp/resources/{uri}` - Get specific resource

### Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer ioflow_YOUR_API_KEY
```

### Tool Execution Format

```json
{
  "tool": "tool_name",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

### Response Format

```json
{
  "success": true,
  "result": {...},
  "error": null,
  "tool": "tool_name",
  "execution_time": 0.123
}
```