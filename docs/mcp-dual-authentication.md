# MCP Dual Authentication Implementation

## Overview

This document describes the dual authentication mechanism implemented for the IOFlow MCP (Model Control Protocol) server. The system now distinguishes between:

1. **External Agent Authentication** - Using API keys (e.g., Claude Desktop)
2. **Frontend Session Authentication** - Using JWT session tokens from IOFlow frontend

## Problem Statement

Previously, when users created flow designs through the IOFlow frontend using MCP tools, the `created_by` field would show "mcp_service" instead of the actual user ID. This made it impossible to track which user created which flow design.

## Solution Architecture

### 1. Enhanced Authentication Handler

Created `EnhancedMCPAuthHandler` (`backend/mcp_server/auth/enhanced_mcp_auth.py`) that:
- Supports both API key and session token authentication
- Detects authentication type automatically
- Properly extracts user context from both auth methods
- Includes authentication type tracking (`api_key` vs `session`)

### 2. MCP Bridge Updates

Updated MCP Bridge (`backend/api/mcp_bridge.py`) to:
- Detect authentication type from request headers
- Use enhanced auth handler for dual authentication
- Pass proper user context to MCP tools
- Include `X-User-Id` and `X-Auth-Type` headers for frontend requests

### 3. Flow Design Tools Updates

Modified flow design tools (`backend/mcp_server/tools/flow_design_tools.py`) to:
- Accept auth handler in constructor
- Extract user ID from auth handler when creating flows
- Use actual user ID instead of hardcoded "mcp_service"
- Log authentication context for debugging

### 4. MCP Server Updates

Updated main MCP server (`backend/mcp_server/ioflow_mcp_server.py`) to:
- Use enhanced auth handler instead of basic one
- Support initialization with API key for standalone mode
- Pass auth context through to all tools

## Authentication Flow

### Frontend User Flow
```
1. User logs in via frontend → Gets JWT session token
2. Frontend calls MCP tool → Includes JWT in Authorization header
3. MCP Bridge detects JWT (not starting with "ioflow_")
4. Authenticates as session user
5. Extracts user ID from session
6. Creates flow with actual user ID as created_by
```

### External Agent Flow
```
1. Agent configured with API key (starts with "ioflow_")
2. Agent calls MCP tool → Includes API key in Authorization header
3. MCP Bridge detects API key prefix
4. Authenticates with API key
5. Extracts user ID from API key owner
6. Creates flow with API key owner's user ID
```

## Key Components

### Enhanced Auth Handler Methods

```python
async def authenticate(
    api_key: Optional[str] = None,
    session_token: Optional[str] = None,
    request_headers: Optional[Dict[str, str]] = None
) -> bool
```
- Authenticates using either API key or session token
- Priority: session token > API key > environment variable

```python
def get_user_context() -> Dict[str, Any]
```
- Returns complete user context including auth type
- Used for logging and tracking

```python
def is_frontend_user() -> bool
def is_external_agent() -> bool
```
- Helper methods to check authentication source

### Headers for API Calls

When making API calls from MCP tools:
- **X-User-Id**: Contains actual user ID for frontend users
- **X-Auth-Type**: Either "session" or "api_key"

## Testing

Two test scripts verify the implementation:

1. **test_mcp_dual_auth.py** - Comprehensive test of both auth flows
2. **test_mcp_auth_simple.py** - Simple verification of auth context

### Running Tests
```bash
./venv/bin/python test-script/test_mcp_auth_simple.py
```

## Benefits

1. **Proper User Tracking**: Flows created via frontend now show correct user ID
2. **Audit Trail**: Can track who created/modified flows
3. **Permission Enforcement**: Can apply user-specific permissions
4. **Multi-tenancy Support**: Tenant ID properly tracked
5. **Backward Compatibility**: External agents continue to work with API keys

## Configuration

### Environment Variables
- `IOFLOW_API_KEY`: Used for external agent authentication
- `IOFLOW_BASE_URL`: Base URL for API calls (default: http://localhost:7001)

### Frontend Integration
No changes required for frontend - it continues to use JWT tokens as before.

### External Agent Setup
External agents (like Claude Desktop) should be configured with an API key that starts with "ioflow_" prefix.

## Security Considerations

1. API keys should be kept secure and rotated regularly
2. JWT tokens have expiration and should be refreshed
3. User context validation happens on every request
4. Permissions are checked based on user role

## Future Enhancements

1. Add rate limiting per authentication type
2. Implement API key scoping for limited permissions
3. Add authentication metrics and monitoring
4. Support for service accounts with specific permissions