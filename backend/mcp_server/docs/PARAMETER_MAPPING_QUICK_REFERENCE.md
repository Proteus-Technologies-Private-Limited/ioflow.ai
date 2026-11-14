# Parameter Mapping Quick Reference for MCP Clients

## 🚨 CRITICAL: New Standardized Format ONLY

The old format with `configuration` field and `parameters` as JSON string is **DEPRECATED** and will be **REJECTED**.

When creating services via MCP, use ONLY the new standardized format:

```json
{
    "service_name": "unique_service_name",
    "display_name": "User Friendly Name", 
    "description": "Service description",
    "service_type": "api_call",
    
    # Endpoint URL with {{parameter}} placeholders
    "endpoint_url": "{{base_url}}/path/{{parameter}}",
    "http_method": "GET",
    
    # Request configuration
    "request_config": {
        "parameter_method": "url_pattern",  # or "body" or "query"
        "headers_template": {
            "Authorization": "Bearer {{auth.api_key}}"
        }
    },
    
    # Parameter Schema (JSON Schema format)
    "parameter_schema": {
        "type": "object",
        "properties": {
            "parameter_name": {
                "type": "string",
                "description": "Parameter description",
                "pattern": "^[A-Z0-9]+$"
            }
        },
        "required": ["parameter_name"]
    },
    
    # Output Schema
    "output_schema": {
        "type": "object",
        "properties": {
            "result": {"type": "string"}
        }
    },
    
    "timeout_seconds": 30,
    "is_async": false
}
```

## Parameter Methods Explained

### 1. URL Pattern (`parameter_method: "url_pattern"`)
For parameters that go in the URL path:
```
endpoint_url: "/verify/pan/{{pan_number}}"
request_config: {
    "parameter_method": "url_pattern"
}
```

### 2. Body Parameters (`parameter_method: "body"`)
For parameters in request body:
```
endpoint_url: "/api/send"
request_config: {
    "parameter_method": "body",
    "body_template": {
        "To": "{{recipient}}",     # API expects "To"
        "Body": "{{message}}"       # API expects "Body"
    }
}
parameters: [{
    "name": "recipient",           # IOFlow uses "recipient"
    "mapping": "To"                # Maps to "To" in body_template
}, {
    "name": "message",             # IOFlow uses "message"
    "mapping": "Body"              # Maps to "Body" in body_template
}]
```

### 3. Query Parameters (`parameter_method: "query"`)
For parameters in query string:
```
endpoint_url: "/api/search"
request_config: {
    "parameter_method": "query",
    "query_params": {
        "q": "{{search_term}}",
        "limit": "{{max_results}}"
    }
}
```

## Common Errors and Solutions

### ❌ Error: "Parameter mapping is not there"
```python
# WRONG - Missing mapping field
parameters=[{
    "name": "pan_number",
    "type": "string",
    "required": True
}]

# CORRECT - Includes mapping
parameters=[{
    "name": "pan_number",
    "type": "string", 
    "required": True,
    "mapping": "pan_number"  # ← THIS IS REQUIRED
}]
```

### ❌ Error: "Service receives parameter in URL, even URL is not mapped"
```python
# WRONG - Missing parameter_method
request_config={
    "headers_template": {...}
}

# CORRECT - Includes parameter_method
request_config={
    "parameter_method": "url_pattern",  # ← THIS IS REQUIRED
    "headers_template": {...}
}
```

### ❌ Error: "Parameters not being passed to API"
```python
# WRONG - Missing endpoint_url
configuration={
    "method": "GET",
    "endpoint": "/verify/{{id}}"
}

# CORRECT - Includes endpoint_url
configuration={
    "method": "GET",
    "endpoint": "/verify/{{id}}"
},
endpoint_url="/verify/{{id}}"  # ← THIS IS REQUIRED
```

## Complete Working Example

Here's a complete example of creating a PAN verification service:

```python
await add_service_to_application(
    app_key="vayana_api",
    service_name="verify_pan",
    service_type="api_call",
    description="Verify PAN card details",
    
    # Configuration
    configuration={
        "method": "GET",
        "endpoint": "/verify/pan/{{pan_number}}"
    },
    
    # Endpoint URL (Required)
    endpoint_url="/verify/pan/{{pan_number}}",
    
    # Request Configuration (Required)
    request_config={
        "parameter_method": "url_pattern",
        "headers_template": {
            "Authorization": "Bearer {{auth.api_key}}",
            "Content-Type": "application/json"
        }
    },
    
    # Parameters with Mapping (Required)
    parameters=[{
        "name": "pan_number",
        "type": "string",
        "required": True,
        "description": "10-character PAN to verify",
        "pattern": "^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
        "mapping": "pan_number"
    }],
    
    # Parameter Schema (Required)
    parameter_schema={
        "type": "object",
        "properties": {
            "pan_number": {
                "type": "string",
                "pattern": "^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
                "description": "PAN to verify"
            }
        },
        "required": ["pan_number"]
    },
    
    # Sample Data (Optional but recommended)
    sample_input={"pan_number": "ABCDE1234F"},
    sample_output={
        "status": "success",
        "data": {
            "name": "John Doe",
            "pan": "ABCDE1234F",
            "status": "Active"
        }
    }
)
```

## Checklist Before Creating a Service

- [ ] `configuration` includes method and endpoint
- [ ] `endpoint_url` is provided separately
- [ ] `request_config` includes `parameter_method`
- [ ] `request_config` includes `headers_template` if auth is needed
- [ ] Each parameter has a `mapping` field
- [ ] `parameter_schema` matches the parameters list
- [ ] URL parameters use `{{parameter_name}}` format
- [ ] Body parameters have `body_template` in request_config
- [ ] Query parameters have `query_params` in request_config

## Need More Help?

See the full [Seed Application Guide](SEED_APPLICATION_GUIDE.md) for comprehensive documentation.