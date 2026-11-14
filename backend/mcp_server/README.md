# IOFlow MCP Server for Seed Application Management

The IOFlow MCP Server provides a comprehensive Model Context Protocol (MCP) interface for managing seed applications. It enables external LLM applications to discover, create, edit, test, and deploy seed applications autonomously.

## 📚 IMPORTANT: Seed Application Creation Guide

**Before creating seed applications via MCP, please read the [Comprehensive Seed Application Guide](docs/SEED_APPLICATION_GUIDE.md)**. This guide covers:
- ✅ Correct parameter mapping configuration
- ✅ URL pattern parameters vs body parameters  
- ✅ Required fields for each service
- ✅ Common mistakes and how to avoid them
- ✅ Troubleshooting parameter issues

## Overview

This MCP server exposes three main categories of services:

1. **Exploration Services** - Discover and explore existing seed applications
2. **Application Management Services** - Create, edit, and manage seed applications
3. **Application Testing Services** - Validate, test, and debug seed applications

### Access Methods

The MCP server can be accessed in two ways:

1. **Local Access** - Direct connection from Claude Desktop on the same machine
2. **Remote Access** - Network access from Claude Desktop on remote machines via the MCP Bridge API

## Installation

### Requirements

- Python 3.8+
- IOFlow backend running
- MCP Python package (`pip install mcp`)

### Setup

1. Install the MCP package:
```bash
cd backend
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export IOFLOW_BASE_URL="http://localhost:7001"
export IOFLOW_API_KEY="your-api-key-here"
```

3. Run the MCP server:
```bash
python -m mcp_server.server
```

## Configuration

### Local Access (Same Machine)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ioflow-seed-manager": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/ioflow/backend",
      "env": {
        "IOFLOW_BASE_URL": "http://localhost:7001",
        "IOFLOW_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Remote Access (Network)

For accessing IOFlow from a remote machine, use the remote MCP client:

```json
{
  "mcpServers": {
    "ioflow-remote": {
      "command": "python",
      "args": ["/path/to/remote_client.py"],
      "env": {
        "IOFLOW_SERVER_URL": "http://YOUR_SERVER_IP:7001",
        "IOFLOW_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

See [REMOTE_MCP_SETUP.md](/docs/REMOTE_MCP_SETUP.md) for detailed remote setup instructions.

### For Other LLM Applications

Connect to the MCP server using:
- Server name: `ioflow-seed-manager`
- Transport: stdio
- Authentication: Via IOFLOW_API_KEY environment variable

## Available Tools

### Documentation Services

#### `ioflow_get_service_docs`
Get comprehensive documentation for creating IOFlow application services.

**Parameters:**
- `service_type` (optional): Specific service type to get detailed docs for
  - Options: `api_call`, `webhook`, `database_query`, `email_send`, `llm_api_call`, `mcp_call`

**Returns:** Service documentation with configuration details, schemas, and examples

#### `ioflow_get_event_docs`
Get comprehensive documentation for creating IOFlow application events.

**Parameters:**
- `event_type` (optional): Specific event type to get detailed docs for
  - Options: `webhook`, `schedule`, `polling`, `api_call`, `manual`, `email`, `form`

**Returns:** Event documentation with configuration details, schemas, and examples

#### `ioflow_get_app_guide`
Get complete guide for creating IOFlow applications.

**Returns:** Comprehensive guide including:
- Application structure
- Service creation guidelines
- Event creation guidelines
- Best practices
- Complete examples

#### `ioflow_search_docs`
Search IOFlow documentation for specific terms or concepts.

**Parameters:**
- `query` (required): Search query string

**Returns:** Relevant documentation sections matching the query

### Exploration Services

#### `get_documentation`
Get comprehensive documentation for creating seed applications.

**Parameters:**
- `doc_type`: Type of documentation to retrieve:
  - `"comprehensive"`: Full seed application guide (default)
  - `"quick_reference"`: Parameter mapping quick reference
  - `"troubleshooting"`: Troubleshooting common issues
  - `"examples"`: Example applications and patterns
- `format`: Documentation format (currently only "markdown")

**Example:**
```python
# Get the quick reference for parameter mapping
docs = await get_documentation(doc_type="quick_reference")
print(docs["content"])

# Get troubleshooting guide
troubleshooting = await get_documentation(doc_type="troubleshooting")
```

#### `explore_seed_applications`
List all available seed applications with optional filters.

**Parameters:**
- `category` (optional): Filter by category (Communication, Productivity, etc.)
- `auth_type` (optional): Filter by auth type (oauth2, api_key, basic, etc.)
- `search_term` (optional): Search in name or description

**Example:**
```python
result = await explore_seed_applications(
    category="Communication",
    auth_type="oauth2"
)
```

#### `get_seed_application`
Get detailed information about a specific seed application.

**Parameters:**
- `app_key`: The unique key of the seed application

**Example:**
```python
details = await get_seed_application(app_key="slack")
```

#### `get_sample_application`
Get a complete sample seed application JSON for reference.

**Parameters:**
- `category`: Category of sample to retrieve
- `auth_type` (optional): Preferred authentication type
- `has_webhooks`: Whether sample should include webhook events
- `service_count` (optional): Minimum number of services

**Example:**
```python
sample = await get_sample_application(
    category="Integration",
    auth_type="api_key",
    has_webhooks=True
)
```

### Application Management Services

#### `create_seed_application`
Create a new seed application with basic configuration.

**Parameters:**
- `app_key`: Unique identifier (lowercase, underscore separated)
- `app_name`: Human-readable name
- `app_type`: Type of application (database, email, api, file_system, memory, flow)
- `app_scope`: Scope of application (global, tenant, or user)
- `category`: Application category
- `auth_type`: Authentication method
- `description`: Application description
- `base_url`: Base API URL
- `version`: Semantic version

**Example:**
```python
new_app = await create_seed_application(
    app_key="my_api",
    app_name="My API Integration",
    category="Integration",
    auth_type="api_key",
    description="Integration with My API service",
    base_url="https://api.myservice.com"
)
```

#### `add_service_to_application`
Add a new service to a seed application.

**Parameters:**
- `app_key`: Application to add service to
- `service_name`: Unique service name
- `service_type`: Type of service (api_call, webhook, etc.)
- `description`: Service description
- `configuration`: Service-specific configuration (must include method and endpoint)
- `endpoint_url`: **REQUIRED** - The full endpoint URL (use {{param}} for URL parameters)
- `request_config`: **REQUIRED** - Must include parameter_method and headers_template
- `parameters`: **REQUIRED** - List of parameter definitions with mapping field
- `parameter_schema`: **REQUIRED** - JSON schema for parameter validation
- `sample_input` (optional): Example input data
- `sample_output` (optional): Example output data

**Example:**
```python
service = await add_service_to_application(
    app_key="my_api",
    service_name="get_user",
    service_type="api_call",
    description="Get user information",
    configuration={
        "method": "GET",
        "endpoint": "/users/{{user_id}}"
    },
    endpoint_url="/users/{{user_id}}",  # Required!
    request_config={
        "parameter_method": "url_pattern",  # Required!
        "headers_template": {
            "Authorization": "Bearer {{auth.api_key}}"
        }
    },
    parameters=[{
        "name": "user_id",
        "type": "string",
        "required": True,
        "description": "User ID",
        "mapping": "user_id"  # Required!
    }],
    parameter_schema={  # Required!
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "User identifier"
            }
        },
        "required": ["user_id"]
    }
)
```

### Application Testing Services

#### `validate_application_schema`
Validate seed application JSON structure against schema.

**Parameters:**
- `app_key`: Application key to validate
- `strict_mode`: If True, enforce all best practices

**Example:**
```python
validation = await validate_application_schema(
    app_key="my_api",
    strict_mode=True
)
```

#### `test_service_endpoint`
Test a specific service endpoint with mock data.

**Parameters:**
- `app_key`: Application key
- `service_name`: Name of service to test
- `test_params` (optional): Test parameters
- `mock_auth` (optional): Mock authentication credentials
- `timeout`: Request timeout in seconds

**Example:**
```python
test_result = await test_service_endpoint(
    app_key="my_api",
    service_name="get_user",
    test_params={"user_id": "123"},
    mock_auth={"api_key": "test-key"}
)
```

#### `generate_test_report`
Generate a comprehensive test report for an application.

**Parameters:**
- `app_key`: Application to test
- `include_all_tests`: Run all tests if True

**Example:**
```python
report = await generate_test_report(
    app_key="my_api",
    include_all_tests=True
)
```

### Deployment Tools

#### `install_application`
Install a seed application to IOFlow.

**Parameters:**
- `app_key`: Application key to install
- `pre_validate`: Run validation before installation
- `force_reinstall`: Force reinstall if already installed

**Example:**
```python
installation = await install_application(
    app_key="my_api",
    pre_validate=True
)
```

#### `verify_deployment`
Verify that an application is properly deployed.

**Parameters:**
- `app_key`: Application key to verify
- `run_tests`: Run basic tests on services

**Example:**
```python
verification = await verify_deployment(
    app_key="my_api",
    run_tests=True
)
```

## Webhook Configuration Guide

### Understanding Webhook Events vs Webhook Services

IOFlow distinguishes between webhook **events** (triggers) and webhook **services** (actions):

#### Webhook Events (Triggers)
- Define incoming webhooks that trigger flows
- Use standardized URL format: `/webhooks/{app_id}/{event_name}`
- Can specify custom endpoint via `api_endpoint` field
- Configuration stored in `event_configuration` (for headers, auth, etc.)
- **DO NOT** use `webhook_url` or `webhook_path` in event configuration

Example webhook event:
```json
{
  "event_name": "message_received",
  "event_type": "webhook",
  "description": "Triggered when a message is received",
  "api_endpoint": "/custom/webhook",  // Optional custom endpoint
  "event_configuration": {
    "webhook_method": "POST",
    "headers": {
      "X-Signature": "{{signature}}"
    }
  }
}
```

#### Webhook Services (Actions)
- Define outgoing webhooks to external systems
- Use `webhook_url` or `endpoint_template` in service configuration
- Configuration includes URL, method, headers, etc.

Example webhook service:
```json
{
  "service_name": "send_webhook",
  "service_type": "webhook",
  "configuration": {
    "webhook_url": "https://api.example.com/webhook",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    }
  }
}
```

### Key Differences
- **Events**: Receive webhooks → Use `api_endpoint` field
- **Services**: Send webhooks → Use `webhook_url` in configuration

## Available Resources

The MCP server provides read-only access to various resources:

### `seed-apps://catalog`
Get the complete seed applications catalog.

### `seed-apps://catalog/{app_key}`
Get detailed information for a specific seed application.

### `seed-apps://schema`
Get the JSON schema for seed applications.

### `seed-apps://templates/{category}`
Get a template for creating applications in a specific category.

### `seed-apps://docs`
Get documentation for creating seed applications.

## Authentication

The MCP server uses IOFlow API keys for authentication. You must provide a valid API key via:

1. Environment variable: `IOFLOW_API_KEY`
2. Or configure it in your MCP client

### Required Permissions

Different operations require different permission levels:

- **View/Explore**: Any authenticated user
- **Create/Edit**: `TENANT_ADMIN` or higher
- **Install/Deploy**: `INSTANCE_ADMIN` only

## Example Workflow

Here's a typical workflow for creating and deploying a new seed application:

```python
# 0. Get the documentation first
docs = await get_documentation(doc_type="quick_reference")
print(docs["content"])  # Review parameter mapping requirements

# 1. Explore existing applications for reference
apps = await explore_seed_applications(category="Integration")

# 2. Get a sample template
template = await get_sample_application(
    category="Integration",
    auth_type="api_key"
)

# 3. Create new application
new_app = await create_seed_application(
    app_key="weather_api",
    app_name="Weather API",
    category="Integration",
    auth_type="api_key",
    description="Get weather information",
    base_url="https://api.weather.com"
)

# 4. Add a service
await add_service_to_application(
    app_key="weather_api",
    service_name="get_current_weather",
    service_type="api_call",
    description="Get current weather for a location",
    configuration={
        "method": "GET",
        "endpoint": "/weather/current"
    },
    parameters=[{
        "name": "location",
        "type": "string",
        "required": True,
        "description": "City name or coordinates"
    }]
)

# 5. Validate the application
validation = await validate_application_schema(
    app_key="weather_api",
    strict_mode=True
)

# 6. Test the service
test = await test_service_endpoint(
    app_key="weather_api",
    service_name="get_current_weather",
    test_params={"location": "New York"},
    mock_auth={"api_key": "test-key"}
)

# 7. Install the application
await install_application(
    app_key="weather_api",
    pre_validate=True
)

# 8. Verify deployment
await verify_deployment(
    app_key="weather_api",
    run_tests=True
)
```

## Error Handling

The MCP server provides detailed error information:

```python
{
    "error": "Permission denied",
    "required_permission": "install_applications",
    "required_role": "INSTANCE_ADMIN"
}
```

Use the `debug_failed_service` tool for detailed debugging:

```python
debug_info = await debug_failed_service(test_id="test_123")
```

## Best Practices

1. **Always validate before deployment** - Use `validate_application_schema` before installing
2. **Test services thoroughly** - Use `test_service_endpoint` with various test cases
3. **Provide comprehensive metadata** - Include descriptions, sample data, and documentation
4. **Use semantic versioning** - Follow x.y.z format for versions
5. **Handle errors gracefully** - Check response status and provide fallbacks

## Troubleshooting

### Authentication Issues
- Verify your API key is correct
- Check that the user has required permissions
- Ensure IOFlow backend is running

### Connection Issues
- Verify `IOFLOW_BASE_URL` is correct
- Check network connectivity
- Ensure MCP server is running

### Validation Errors
- Use `explain_application_schema` for field explanations
- Check required fields are present
- Validate JSON syntax

## Support

For issues or questions:
1. Check the IOFlow documentation
2. Review error messages and debugging info
3. Contact the IOFlow support team

## License

This MCP server is part of the IOFlow project and follows the same license terms.