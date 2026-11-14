# IOFlow MCP Server Quick Start Guide

Get up and running with the IOFlow MCP Server in 5 minutes!

## Prerequisites

- IOFlow backend running on http://localhost:8000
- Valid IOFlow API key with appropriate permissions
- Python 3.8+ installed

## Step 1: Install Dependencies

```bash
cd backend
pip install mcp
```

## Step 2: Get Your API Key

1. Log into IOFlow admin panel
2. Navigate to Settings > API Keys
3. Create a new API key with INSTANCE_ADMIN role (for full access)
4. Copy the API key

## Step 3: Configure Environment

```bash
export IOFLOW_BASE_URL="http://localhost:8000"
export IOFLOW_API_KEY="your-api-key-here"
```

## Step 4: Run the MCP Server

```bash
python -m mcp_server.server
```

## Step 5: Connect Your LLM

### For Claude Desktop

1. Open Claude Desktop settings
2. Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ioflow-seed-manager": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/ioflow/backend",
      "env": {
        "IOFLOW_BASE_URL": "http://localhost:8000",
        "IOFLOW_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

3. Restart Claude Desktop

## Step 6: Test the Connection

In your LLM, try these commands:

1. **List all seed applications:**
   ```
   Use the explore_seed_applications tool to show me all available applications
   ```

2. **Get details about a specific app:**
   ```
   Use get_seed_application to show me details about the "slack" application
   ```

3. **Create a simple test application:**
   ```
   Create a new seed application called "test_api" with basic API integration
   ```

## Common Use Cases

### 1. Explore Existing Applications

```python
# Find all communication apps
await explore_seed_applications(category="Communication")

# Search for OAuth2 apps
await explore_seed_applications(auth_type="oauth2")

# Get full details of an app
await get_seed_application(app_key="github")
```

### 2. Create a New Integration

```python
# Step 1: Create the application
await create_seed_application(
    app_key="weather_service",
    app_name="Weather Service API",
    category="Integration",
    auth_type="api_key",
    description="Get weather data",
    base_url="https://api.weather.com"
)

# Step 2: Add a service
await add_service_to_application(
    app_key="weather_service",
    service_name="get_forecast",
    service_type="api_call",
    description="Get weather forecast",
    configuration={
        "method": "GET",
        "endpoint": "/forecast/{location}"
    }
)

# Step 3: Validate
await validate_application_schema(
    app_key="weather_service",
    strict_mode=True
)

# Step 4: Install
await install_application(
    app_key="weather_service"
)
```

### 3. Test Before Deployment

```python
# Test authentication
await test_authentication(
    app_key="weather_service",
    credentials={"api_key": "test-key"}
)

# Test a service endpoint
await test_service_endpoint(
    app_key="weather_service",
    service_name="get_forecast",
    test_params={"location": "NYC"}
)

# Generate full test report
await generate_test_report(
    app_key="weather_service",
    include_all_tests=True
)
```

## Troubleshooting

### "Authentication failed"
- Check your API key is correct
- Verify the key has required permissions
- Ensure IOFlow backend is running

### "Application not found"
- Use `explore_seed_applications()` to list available apps
- Check the app_key spelling
- Ensure the application exists in seed-applications directory

### "Permission denied"
- Installation requires INSTANCE_ADMIN role
- Creation/editing requires TENANT_ADMIN or higher
- Check your user role in IOFlow

### "Connection refused"
- Verify IOFlow backend is running
- Check IOFLOW_BASE_URL is correct
- Ensure no firewall blocking port 8000

## Next Steps

1. **Read the full documentation:** See README.md for comprehensive guide
2. **Explore templates:** Use resources like `seed-apps://templates/Integration`
3. **Join the community:** Share your seed applications with others
4. **Build complex integrations:** Combine multiple services and events

## Need Help?

- Check error messages - they include helpful hints
- Use `debug_failed_service` for detailed debugging
- Review the example_config.json for more examples
- Contact IOFlow support for additional assistance