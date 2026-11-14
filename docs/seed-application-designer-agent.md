# Seed Application Designer Agent

## Overview

The **Seed Application Designer Agent** is an AI-powered assistant that helps users create, edit, install, configure, and debug IOFlow applications. It follows the exact architectural pattern of the Flow Designer Agent, using Google ADK with MCPToolset integration to access all IOFlow capabilities through the MCP API bridge.

## Architecture

### Component Structure

```
Seed Application Designer Agent
├── Agent Module (Google ADK)
│   ├── Model: gemini-2.5-pro (configurable)
│   ├── MCP Connection: stdio subprocess
│   └── Tools: 28 MCP tools via MCPToolset
│
├── MCP Server (subprocess)
│   ├── Communication: stdio
│   ├── Authentication: JWT or API key
│   └── Bridge: Thin wrapper to IOFlow API
│
└── IOFlow Backend
    ├── Applications API
    ├── Subscriptions API
    ├── Seed Applications API
    └── Testing/Validation Services
```

### Architecture Diagram

```
User Request
    ↓
Frontend → POST /api/flow-agents/execute
    ↓
FlowAgentExecutor
    ↓
[Loads seed_application_designer module]
    ↓
Google ADK Agent
    ↓
MCPToolset (stdio)
    ↓
MCP Server (subprocess)
    ↓
MCP Bridge API
    ↓
IOFlow Backend Services
    ↓
Database
```

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| Agent Implementation | `backend/agent/seed_application_designer/agent.py` | Main agent with Google ADK + MCPToolset |
| Agent Configuration | `backend/agent/seed_application_designer/agent_config.py` | Configuration documentation |
| Agent Registration | `backend/services/flow_agent_executor.py` | Registers agent for execution |
| Basic Tests | `test-script/test_seed_app_agent.py` | Basic functionality tests |
| Workflow Tests | `test-script/test_seed_app_agent_workflows.py` | Comprehensive workflow tests |

## Features

### 1. Conversational Workflow

The agent guides users through multi-step processes with:
- Clarifying questions when requirements are unclear
- Step-by-step guidance through complex tasks
- Validation before proceeding to next step
- Confirmation before making destructive changes

### 2. Four Main Workflows

#### Workflow 1: Create New Seed Application
- Understand user requirements (app name, auth type, services)
- Explore examples for reference
- Gather service details (endpoints, parameters, responses)
- Create complete application definition
- Validate schema structure
- Test authentication and services

#### Workflow 2: Edit Existing Seed Application
- Find target application
- Identify required changes
- **Auto-increment version number** (critical!)
- Make changes (metadata, auth, services, events)
- Validate updated schema
- Test modified services

#### Workflow 3: Install and Configure Application
- List available applications
- Check prerequisites and authentication requirements
- Install application (create subscription)
- Configure authentication credentials
- Test connection
- Verify installation

#### Workflow 4: Debug and Test Application
- Identify the issue
- Gather context (app definition, service configs)
- Run diagnostic tests (auth, services, schemas)
- Simulate execution
- Generate diagnostic report
- Provide actionable solutions

## Available MCP Tools

The agent has access to **28 MCP tools** across 4 categories:

### Exploration Tools (5 tools)
- `explore_seed_applications` - List all seed applications
- `get_seed_application` - Get specific application details
- `get_sample_application` - Find example applications by criteria
- `explain_application_schema` - Understand schema requirements
- `get_application_categories` - See available categories

### Management Tools (8 tools)
- `create_seed_application` - Create new seed application
- `edit_application_metadata` - Update app info
- `add_service_to_application` - Add new service
- `remove_service_from_application` - Remove service
- `add_event_to_application` - Add webhook event
- `update_auth_configuration` - Update authentication
- `delete_seed_application` - Delete application
- `duplicate_application` - Copy existing app

### Testing Tools (8 tools)
- `validate_application_schema` - Validate structure
- `test_service_endpoint` - Test API endpoint
- `test_authentication` - Test auth credentials
- `test_parameter_extraction` - Test parameter mapping
- `simulate_service_execution` - Dry run without API call
- `generate_test_report` - Create diagnostic report
- `debug_failed_service` - Debug service errors
- `test_event_subscription` - Test webhook subscriptions

### Deployment Tools (7 tools)
- `install_application` - Install app for tenant
- `uninstall_application` - Remove app
- `update_installed_application` - Upgrade version
- `list_installed_applications` - Show installed apps
- `verify_deployment` - Check installation status
- `rollback_application` - Revert to previous version
- `create_application_subscription` - Create connection

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `IOFLOW_API_KEY` | Authentication token (JWT or API key) | Required |
| `IOFLOW_BASE_URL` | IOFlow backend URL | `http://localhost:7001` |
| `SEED_APP_AGENT_MODEL` | Model to use for agent | `gemini-2.5-pro` |
| `AGENT_MODEL` | Fallback model configuration | `gemini-2.5-pro` |
| `PYTHONPATH` | Path to backend for MCP server | Auto-set |

### MCP Connection Details

- **Type**: stdio (subprocess)
- **Server**: `backend/mcp_server/ioflow_mcp_server.py`
- **Communication**: All tools accessed through MCP bridge
- **Isolation**: Fresh MCP server instance per execution
- **Authentication**: Passed via `IOFLOW_API_KEY` environment variable

## Usage

### API Endpoint

```
POST /api/flow-agents/execute
```

### Request Format

```json
{
  "agent_id": "seed_application_designer",
  "input": "User request in natural language",
  "api_key": "JWT_TOKEN_OR_API_KEY"
}
```

### Response Format

```json
{
  "success": true,
  "agent_id": "seed_application_designer",
  "response": "Agent's natural language response",
  "model": "gemini-2.5-pro",
  "timestamp": "2024-01-15T10:30:00"
}
```

### Example Requests

#### 1. List Available Applications
```json
{
  "agent_id": "seed_application_designer",
  "input": "What applications are available?",
  "api_key": "eyJhbGc..."
}
```

#### 2. Create New Application
```json
{
  "agent_id": "seed_application_designer",
  "input": "I want to create a new application for Stripe payments API",
  "api_key": "eyJhbGc..."
}
```

#### 3. Install Application
```json
{
  "agent_id": "seed_application_designer",
  "input": "Install the Gmail application for me",
  "api_key": "eyJhbGc..."
}
```

#### 4. Debug Application
```json
{
  "agent_id": "seed_application_designer",
  "input": "My Gmail send email service is failing. Can you help debug?",
  "api_key": "eyJhbGc..."
}
```

## Seed Application Schema

### Required Structure

```json
{
  "key": "unique_lowercase_key",
  "application": {
    "app_name": "Display Name",
    "app_type": "api_service",
    "category": "productivity",
    "version": "1.0.0",
    "authentication": {
      "type": "api_key",
      // ... auth config
    },
    "display_info": {
      "icon_url": "https://...",
      "description": "What this app does"
    }
  },
  "services": [
    {
      "service_name": "action_name",
      "display_name": "Human Readable Name",
      "description": "What this service does",
      "service_type": "api_call",
      "http_config": {
        "method": "POST",
        "endpoint": "/api/v1/resource"
      },
      "parameter_schema": {
        "type": "object",
        "properties": {...},
        "required": [...]
      },
      "response_config": {
        "success_check": {
          "type": "status_code",
          "success_status_codes": [200, 201]
        }
      }
    }
  ],
  "events": []
}
```

### Critical Schema Rules

1. **Top-level `key` field** - REQUIRED unique identifier
2. **`application` object** - REQUIRED metadata
3. **`services` array** - REQUIRED (can be empty)
4. **`events` array** - OPTIONAL
5. **Use `parameter_schema`** NOT `input_schema`
6. **Use `success_status_codes`** NOT `value` in response_config
7. **Always increment version** when updating

### Common Schema Mistakes

❌ **Wrong:**
```json
{
  "application": {...},
  "services": [{
    "input_schema": {...},
    "response_config": {
      "success_check": {
        "value": [200]
      }
    }
  }]
}
```

✅ **Correct:**
```json
{
  "key": "my_app",
  "application": {...},
  "services": [{
    "parameter_schema": {...},
    "response_config": {
      "success_check": {
        "success_status_codes": [200]
      }
    }
  }]
}
```

## Testing

### Run Basic Tests

```bash
cd /path/to/ioflow
./venv/bin/python test-script/test_seed_app_agent.py
```

Tests:
- ✅ Basic agent execution
- ✅ Exploration workflow
- ✅ Schema explanation
- ✅ Installed applications
- ✅ Application categories

### Run Workflow Tests

```bash
./venv/bin/python test-script/test_seed_app_agent_workflows.py
```

Tests:
- ✅ Workflow 1: Create new seed application
- ✅ Workflow 2: Edit existing seed application
- ✅ Workflow 3: Install and configure application
- ✅ Workflow 4: Debug and test application
- ✅ Conversational flow

## Agent Instructions Summary

The agent follows these core principles:

### Absolute Rules

1. **FATAL ERROR = ABORT** - Stop on any fatal error
2. **ALWAYS INCREMENT VERSION** when updating seed apps
3. **FOLLOW SCHEMA STRUCTURE** - Use correct field names
4. **CONVERSATIONAL WORKFLOW** - Guide users step by step

### Tool Usage Strategy

1. **Exploration phase** - Use exploration tools to gather context
2. **Planning phase** - Ask clarifying questions
3. **Execution phase** - Use management/deployment tools
4. **Validation phase** - Use testing tools
5. **Confirmation phase** - Wait for user approval

### Error Handling

- Read error messages carefully (they tell you what's wrong)
- Use debug tools to diagnose issues
- Check schema with `validate_application_schema()`
- Test incrementally after each fix
- Ask user if unsure

## Comparison with Flow Designer Agent

| Aspect | Flow Designer | Seed App Designer |
|--------|---------------|-------------------|
| **Purpose** | Create flows | Manage applications |
| **Tools** | 20+ flow design tools | 28 application management tools |
| **Model** | FLOW_DESIGNER_MODEL | SEED_APP_AGENT_MODEL |
| **Architecture** | Google ADK + MCPToolset | Google ADK + MCPToolset |
| **MCP Connection** | stdio subprocess | stdio subprocess |
| **Auth** | JWT or API key | JWT or API key |
| **Output** | Flow JSON | Application JSON |
| **Validation** | Flow validation | Schema validation |
| **Key Focus** | Node/edge configuration | Service/event configuration |

Both agents follow the **exact same architectural pattern**, just with different tool sets and domain focus.

## Troubleshooting

### Agent Not Loading

**Issue**: Agent doesn't load when called

**Solution**:
1. Check agent is registered in `flow_agent_executor.py` (line 157)
2. Verify module exists at `backend/agent/seed_application_designer/agent.py`
3. Check logs for import errors

### MCP Tools Not Available

**Issue**: Agent can't access MCP tools

**Solution**:
1. Verify MCP server exists at `backend/mcp_server/ioflow_mcp_server.py`
2. Check `IOFLOW_API_KEY` is set in environment
3. Verify MCP bridge is running on port 7001

### Authentication Errors

**Issue**: "Unauthorized" or "Invalid token" errors

**Solution**:
1. Ensure JWT token is passed in `api_key` parameter
2. Token should be valid and not expired
3. Check `IOFLOW_API_KEY` environment variable is set before module import

### Version Not Incrementing

**Issue**: Agent doesn't increment version when updating

**Solution**:
1. Agent instructions include version increment rule
2. Remind agent: "Remember to increment the version"
3. Check agent response mentions version change

## Best Practices

### For Users

1. **Be specific** - Describe what you want to create/edit clearly
2. **Provide examples** - Reference existing apps if possible
3. **Test incrementally** - Validate after each major change
4. **Version properly** - Always increment version on updates
5. **Use categories** - Check available categories before creating

### For Developers

1. **Follow MCP pattern** - All tools through MCP bridge, no business logic in bridge
2. **Maintain isolation** - Subprocess for each execution
3. **Pass auth properly** - Set environment before module import
4. **Cache wisely** - Clear cache when reloading with new API key
5. **Test thoroughly** - Use both basic and workflow tests

## Future Enhancements

Potential improvements:

- [ ] Add bulk application creation from OpenAPI specs
- [ ] Support application templates library
- [ ] Add visual application builder integration
- [ ] Implement collaborative editing workflow
- [ ] Add application versioning with diff view
- [ ] Support application marketplace integration
- [ ] Add automated testing suite generation

## Related Documentation

- [MCP Bridge Architecture](../backend/api/mcp_bridge.py)
- [Seed Application Template](../backend/seed-applications/SEED_APPLICATION_TEMPLATE.md)
- [Seed JSON Structure](../backend/docs/seed-application-json-structure.md)
- [Flow Designer Agent](../backend/agent/flow_designer/agent.py)
- [Application Models](../backend/db/application_models.py)

## Support

For issues or questions:
- Check agent logs in backend output
- Review test scripts for usage examples
- Examine existing seed applications in `backend/seed-applications/`
- Test with basic requests first, then complex workflows
