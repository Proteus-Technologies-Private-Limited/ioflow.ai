# MCP Flow Management Tools

## Overview

The IOFlow MCP server now provides comprehensive tools for creating, updating, and managing flows programmatically. These tools enable external applications and LLM agents to design and deploy flows without direct UI interaction.

## Available Tools

### Flow Design Assistant Tools

These tools help MCP clients create well-formed flows that work correctly with both the backend execution engine and frontend UI.

#### 1. `get_flow_node_template`

Get a properly structured template for any node type with all required fields.

**Parameters:**
- `node_type` (string, required): Type of node (trigger, action, transform, condition, loop, response)
- `example_data` (object, optional): Data to merge with the template

**Example:**
```python
template = await get_flow_node_template(
    node_type="action",
    example_data={
        "data": {
            "appId": "gmail",
            "serviceId": "send_message"
        }
    }
)
```

#### 2. `validate_and_fix_flow`

Automatically fix common issues in flow definitions to ensure UI compatibility.

**Parameters:**
- `flow_definition` (object, required): The flow to validate and fix

**Returns:**
- `fixed_flow`: The corrected flow definition
- `issues_fixed`: List of issues that were corrected
- `is_valid`: Whether the original flow was valid

**Common fixes:**
- Adds missing `label` fields to all nodes
- Adds `serviceDisplayName` to action nodes
- Ensures proper edge configurations
- Adds missing positions

**Example:**
```python
result = await validate_and_fix_flow(flow_definition=my_flow)
if not result['is_valid']:
    print(f"Fixed {len(result['issues_fixed'])} issues")
    my_flow = result['fixed_flow']
```

#### 3. `get_common_flow_patterns`

Get examples of common flow patterns with proper structure.

**Returns:** Dictionary of flow patterns including:
- `webhook_to_action`: Webhook trigger calling external service
- `conditional_processing`: Different paths based on conditions
- `loop_processing`: Process array of items in a loop

#### 4. `get_flow_edge_template`

Get properly structured edge template for connecting nodes.

**Parameters:**
- `source_id` (string, required): Source node ID
- `target_id` (string, required): Target node ID
- `source_handle` (string, optional): Source handle name (default: "output")
- `target_handle` (string, optional): Target handle name (default: "input")

### Flow Management Tools

#### 1. `create_or_update_flow`

Create a new flow or update an existing flow with a complete flow definition.

**Parameters:**
- `flow_name` (string, required): Name of the flow
- `flow_definition` (dict, required): Complete flow definition with nodes and edges
- `description` (string, optional): Description of the flow
- `flow_id` (string, optional): ID of existing flow (required for updates)
- `is_update` (boolean, optional): If True, update existing flow; if False, create new
- `activate` (boolean, optional): If True, activate the flow after creation/update
- `is_synchronous` (boolean, optional): If True, flow will run synchronously
- `sync_timeout` (integer, optional): Timeout in seconds for synchronous flows (default: 30)

**Example Usage:**
```python
# Create a new flow
result = await create_or_update_flow(
    flow_name="Data Processing Flow",
    flow_definition={
        "nodes": [...],
        "edges": [...]
    },
    description="Automated data processing workflow",
    activate=True
)

# Update an existing flow
result = await create_or_update_flow(
    flow_name="Data Processing Flow v2",
    flow_definition={...},
    flow_id="existing-flow-id",
    is_update=True,
    activate=True
)
```

### 2. `list_flows`

List all flows or search for specific flows by criteria.

**Parameters:**
- `search_name` (string, optional): Partial flow name to search for
- `status` (string, optional): Filter by status (active, inactive, draft)
- `trigger_type` (string, optional): Filter by trigger type (manual, schedule, webhook, etc.)
- `limit` (integer, optional): Maximum number of flows to return (default: 20)

**Example Usage:**
```python
# List all active flows
result = await list_flows(status="active")

# Search for flows by name
result = await list_flows(search_name="google", limit=10)

# Find scheduled flows
result = await list_flows(trigger_type="schedule")
```

### 3. `delete_flow`

Permanently delete a flow from the system.

**Parameters:**
- `flow_id` (string, optional): ID of the flow to delete
- `flow_name` (string, optional): Name of the flow to delete (if ID not provided)
- `confirm` (boolean, required): Must be True to confirm deletion

**Example Usage:**
```python
# Delete by ID
result = await delete_flow(
    flow_id="flow-id-to-delete",
    confirm=True
)

# Delete by name
result = await delete_flow(
    flow_name="Obsolete Flow",
    confirm=True
)
```

## Flow Definition Structure

A flow definition must contain two main components:

### Nodes
Array of node objects, each containing:
- `id`: Unique identifier for the node
- `type`: Node type (trigger, action, transform, condition, loop, response, etc.)
- `position`: {x, y} coordinates for visual representation
- `data`: Node-specific configuration

### Edges
Array of edge objects connecting nodes:
- `id`: Unique identifier for the edge
- `source`: Source node ID
- `target`: Target node ID
- `sourceHandle`: Optional handle identifier on source node
- `targetHandle`: Optional handle identifier on target node

## Example Flow Definitions

### Simple Manual Trigger Flow
```json
{
  "nodes": [
    {
      "id": "1",
      "type": "trigger",
      "position": {"x": 100, "y": 100},
      "data": {
        "label": "Manual Trigger",
        "triggerType": "manual",
        "manualVariables": [
          {"name": "input_data", "type": "string"}
        ]
      }
    },
    {
      "id": "2",
      "type": "transform",
      "position": {"x": 300, "y": 100},
      "data": {
        "label": "Process Data",
        "script": "output['result'] = input.input_data.upper()"
      }
    },
    {
      "id": "3",
      "type": "response",
      "position": {"x": 500, "y": 100},
      "data": {
        "label": "Return Result",
        "variable": "{{local.result}}"
      }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "1",
      "target": "2",
      "sourceHandle": "a",
      "targetHandle": "a"
    },
    {
      "id": "e2",
      "source": "2",
      "target": "3",
      "sourceHandle": "b",
      "targetHandle": "a"
    }
  ]
}
```

### Application Event Trigger Flow
```json
{
  "nodes": [
    {
      "id": "1",
      "type": "trigger",
      "position": {"x": 100, "y": 100},
      "data": {
        "label": "Google Sheets Trigger",
        "triggerType": "application_event",
        "appId": "google-sheets-app-id",
        "eventName": "row_added"
      }
    },
    {
      "id": "2",
      "type": "action",
      "position": {"x": 300, "y": 100},
      "data": {
        "label": "Process New Row",
        "appId": "processing-app-id",
        "serviceId": "process-service-id",
        "parameters": {
          "data": "{{input.row_data}}"
        }
      }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "1",
      "target": "2"
    }
  ]
}
```

## Integration with MCP Clients

To use these tools from an MCP client:

1. Connect to the IOFlow MCP server
2. Discover available tools using the MCP protocol
3. Call tools with appropriate parameters
4. Handle responses and errors

### Example MCP Client Usage (Python)
```python
from mcp import Client

# Connect to IOFlow MCP server
client = Client("ioflow-mcp://localhost:8080")

# Create a flow
response = await client.call_tool(
    "create_or_update_flow",
    {
        "flow_name": "My Automated Flow",
        "flow_definition": {...},
        "activate": True
    }
)

# List flows
flows = await client.call_tool(
    "list_flows",
    {"status": "active"}
)
```

## Best Practices

1. **Validate Flow Definitions**: Ensure all required nodes (especially trigger) are present
2. **Use Descriptive Names**: Choose clear, descriptive flow names for easy identification
3. **Test Before Activation**: Create flows as inactive first, test, then activate
4. **Handle Errors Gracefully**: Implement proper error handling in transform scripts
5. **Document Flows**: Always provide descriptions for complex flows
6. **Version Control**: When updating flows, consider creating new versions instead of overwriting

## Error Handling

The tools provide detailed error messages for common issues:
- Missing or invalid flow definition structure
- Duplicate flow names
- Missing trigger nodes
- Invalid node types or configurations
- Database connection issues

## UI Compatibility Requirements

For flows to display correctly in the IOFlow UI, certain fields are required:

### Action Nodes
- `label`: Display name for the node (required)
- `appName`: Application display name (required if appId is present)
- `serviceDisplayName` or `serviceName`: Service display name (required if serviceId is present)

### All Nodes
- `label`: Display name for the node
- `position`: {x, y} coordinates for visual placement

### Edges
- `sourceHandle`: Handle on source node (e.g., "output", "true", "false", "loop-body")
- `targetHandle`: Handle on target node (e.g., "input", "loop-back")
- `markerEnd`: Arrow marker configuration

**Tip:** Use the `validate_and_fix_flow` tool to automatically add missing required fields.

## Security Considerations

- Flow creation/update requires appropriate permissions
- Sensitive data in flow definitions should be handled carefully
- Use environment variables or secure storage for credentials
- Audit flow changes for compliance

## Support

For issues or questions about the MCP flow management tools:
1. Check the error messages returned by the tools
2. Verify flow definition structure
3. Ensure proper authentication and permissions
4. Contact IOFlow support with detailed error information