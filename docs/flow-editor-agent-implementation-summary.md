# Flow Design Editor Agent - Implementation Summary

**Date:** 2025-10-06
**Status:** ✅ Complete

## Overview

Implemented a complete Flow Design Editor Agent with capabilities to edit existing flows, debug execution failures, and intelligently detect when redesign is needed. The implementation follows the same clean architecture as the Flow Designer Agent, using MCP tools throughout.

---

## Architecture

```
Flow Editor Agent (ADK)
  ↓ uses
MCPToolset (stdio)
  ↓ connects to
MCP Server (ioflow_mcp_server.py)
  ↓ exposes
Flow Editor Tools (flow_editor_tools.py)
  ↓ call via HTTP
MCP Bridge API (/api/mcp/tools/execute)
  ↓ routes to
MCP Bridge Service (mcp_bridge.py)
  ↓ calls via HTTP
Backend APIs (/api/v1/flows, /api/v1/executions)
  ↓ accesses
Database (SQLite/PostgreSQL)
```

**Key Principle:** All MCP tools use the MCP bridge → Backend API pattern (no direct database access).

---

## Files Created/Modified

### Created Files

1. **`/backend/mcp_server/tools/flow_editor_tools.py`** (NEW)
   - 9 MCP tool classes for flow editing
   - Follows same pattern as `flow_designer_tools.py`
   - Tools:
     - `ListUserFlowsTool`
     - `GetFlowByIdTool`
     - `GetFlowByNameTool`
     - `ReplaceNodeInFlowTool`
     - `AddNodeToFlowTool`
     - `RemoveNodeFromFlowTool`
     - `UpdateEdgeInFlowTool`
     - `GetExecutionLogsTool`
     - `GetExecutionDetailsTool`

### Modified Files

1. **`/backend/api/flows.py`**
   - Added 5 new API endpoints (lines 3734-4142):
     - `GET /api/v1/flows/by-name` - Get flow by name
     - `PUT /api/v1/flows/{flow_id}/nodes/{node_id}` - Replace node
     - `POST /api/v1/flows/{flow_id}/nodes` - Add node
     - `DELETE /api/v1/flows/{flow_id}/nodes/{node_id}` - Remove node
     - `PUT /api/v1/flows/{flow_id}/edges` - Update edge

2. **`/backend/api/mcp_bridge.py`**
   - Added 9 MCP bridge wrapper functions (lines 901-1120):
     - `list_user_flows(user_email)`
     - `get_flow_by_id(flow_id)`
     - `get_flow_by_name(flow_name, user_email)`
     - `replace_node_in_flow(flow_id, node_id, node_json)`
     - `add_node_to_flow(flow_id, node_json, position)`
     - `remove_node_from_flow(flow_id, node_id, reconnect)`
     - `update_edge_in_flow(flow_id, edge_json)`
     - `get_execution_logs(execution_id, include_data, limit)`
     - `get_execution_details(execution_id)`

3. **`/backend/mcp_server/ioflow_mcp_server.py`**
   - Added import for `FLOW_EDITOR_TOOLS` (line 46)
   - Initialize flow editor tools (lines 84-88)
   - Added registration call (line 100)
   - Added `_register_flow_editor_tools()` method (lines 1299-1306)
   - Added `_register_single_flow_editor_tool()` method (lines 1308-1381)

4. **`/backend/agent/flow_design_editor/agent.py`**
   - Complete refactor from HTTP-based to MCPToolset-based
   - Removed custom `_call_mcp_tool_impl` function
   - Removed all `@FunctionTool` decorated functions
   - Added MCPToolset initialization (lines 77-90)
   - Enhanced instructions with:
     - Bug fixing workflow
     - Execution log analysis
     - Redesign detection logic
     - Error fixing examples
     - Complete tool documentation

---

## Key Features Implemented

### 1. Flow Loading & Discovery
- Load flows by ID or name
- List all flows for a user
- Search and filter capabilities

### 2. Flow Editing Operations
- **Replace Node**: Update existing nodes with complete JSON
- **Add Node**: Insert new nodes with auto-connection
- **Remove Node**: Delete nodes with optional edge reconnection
- **Update Edges**: Modify connections between nodes

### 3. Debugging & Error Analysis
- **Get Execution Logs**: Fetch detailed logs with error messages
- **Get Execution Details**: Retrieve execution status and results
- **Log Analysis**: Identify failed nodes by step_id and error level
- **Error Mapping**: Map errors to specific nodes in flow

### 4. Intelligent Redesign Detection
- Analyzes scope of changes
- Detects when >50% of nodes need modification
- Identifies fundamental changes (trigger type, core logic)
- Generates detailed prompts for flow_designer agent
- Suggests creating new flow instead of editing

### 5. Consistent Architecture
- Uses MCPToolset (same as flow designer)
- All operations go through MCP bridge
- No direct database access from agent
- Follows established patterns

---

## API Endpoints

### Flow Retrieval

**GET `/api/v1/flows/by-name`**
```
Query: ?flow_name=Customer%20Onboarding
Returns: Complete flow JSON
```

### Node Operations

**PUT `/api/v1/flows/{flow_id}/nodes/{node_id}`**
```json
{
  "id": "action_1",
  "type": "action",
  "position": {"x": 100, "y": 200},
  "data": {
    "label": "Send Email",
    "appId": "uuid",
    "serviceId": "uuid",
    "parameters": {...}
  }
}
```

**POST `/api/v1/flows/{flow_id}/nodes`**
```json
{
  "node_data": {...complete node JSON...},
  "position": "after_last"
}
```

**DELETE `/api/v1/flows/{flow_id}/nodes/{node_id}`**
```
Query: ?reconnect=true
```

**PUT `/api/v1/flows/{flow_id}/edges`**
```json
{
  "source": "action_1",
  "target": "action_2",
  "sourceHandle": null,
  "targetHandle": null
}
```

---

## Usage Examples

### Example 1: Bug Fixing from Execution Log

```
User: "Execution abc-123 failed, please fix it"

Agent Workflow:
1. get_execution_logs("abc-123")
   → Finds: ERROR at node send_email_1: Missing parameter 'to_email'

2. get_execution_details("abc-123")
   → Gets flow_id: "flow-456"

3. get_flow_by_id("flow-456")
   → Loads current flow definition

4. Identifies problematic node in flow.nodes
   → Current: {"subject": "{{input.subject}}"}

5. Creates corrected node
   → Fixed: {
       "to_email": "{{input.recipient}}",
       "subject": "{{input.subject}}"
     }

6. replace_node_in_flow("flow-456", "send_email_1", corrected_node_json)

7. Reports: "✅ Fixed missing 'to_email' parameter in email node"
```

### Example 2: Feature Addition

```
User: "Add Slack notification to my Payment Flow after payment succeeds"

Agent Workflow:
1. get_flow_by_name("Payment Flow", "user@email.com")

2. list_applications(app_names="slack")
   → Find Slack app_id

3. get_application_services_list(slack_app_id)
   → Find "send_message" service

4. get_service_information(app_id, service_id)
   → Get parameter schema

5. Build slack notification node JSON

6. add_node_to_flow(
      flow_id,
      slack_node_json,
      position="after_payment_node"
   )

7. Reports: "✅ Added Slack notification after payment node"
```

### Example 3: Redesign Detection

```
User: "Change my webhook flow to use scheduled trigger and change all the logic"

Agent Analysis:
- Trigger type change: webhook → schedule (fundamental change)
- All nodes depend on webhook.body (data structure changes)
- >50% of logic needs modification

Agent Response:
"I recommend creating a new flow instead of editing because:
1. Changing trigger type from webhook to schedule requires different input handling
2. 5 out of 6 nodes depend on webhook.body which won't exist in scheduled trigger
3. This is essentially a different workflow

Here's the prompt for flow_designer agent:

'Create a scheduled flow named \"Data Sync Job\" that:
- Trigger: Schedule (daily at 9 AM)
- Step 1: Fetch records from Database
- Step 2: Process each record
- Step 3: Send to External API
- Step 4: Log results

Required applications:
- MySQL: For fetching records
- HTTP Service: For API calls

Key requirements:
- Run daily at 9 AM
- Process all pending records
- Error handling and logging'

Would you like me to help create this new flow?"
```

---

## Agent Instructions Summary

The Flow Editor Agent includes comprehensive instructions for:

1. **Flow Identification** - Load by ID, name, or list
2. **Requirement Analysis** - Bug fixing vs feature changes
3. **Redesign Detection** - When to suggest new flow
4. **Editing Operations** - Replace, add, remove, update
5. **Error Debugging** - Log analysis and node identification
6. **Tool Usage** - Complete documentation of all available tools
7. **Examples** - Real-world usage scenarios

---

## Testing Recommendations

### Manual Testing

1. **Test Flow Loading:**
   ```python
   # Test get_flow_by_name
   agent.run("Load my 'Customer Onboarding' flow")

   # Test list_user_flows
   agent.run("Show me all my flows")
   ```

2. **Test Bug Fixing:**
   ```python
   # Provide execution_id with known error
   agent.run("Debug execution abc-123")
   ```

3. **Test Node Replacement:**
   ```python
   # Test parameter fix
   agent.run("In my Email Flow, fix the 'to_email' parameter in node action_1")
   ```

4. **Test Redesign Detection:**
   ```python
   # Request fundamental change
   agent.run("Change my webhook flow to use scheduled trigger")
   ```

### Automated Testing

Create test script: `/test-script/test_flow_editor_agent.py`

```python
import asyncio
from backend.agent.flow_design_editor.agent import agent

async def test_flow_editor():
    # Test 1: Load flow
    result = await agent.run("List all flows for test@ioflow.com")
    assert "flows" in result

    # Test 2: Get specific flow
    result = await agent.run("Load flow with ID abc-123")
    assert "flow_id" in result

    # Test 3: Debug execution
    result = await agent.run("Debug execution xyz-789")
    assert "logs" in result or "execution" in result

asyncio.run(test_flow_editor())
```

---

## Performance Considerations

### MCP Architecture Benefits
1. **Reduced Latency**: Direct stdio connection to MCP server
2. **Connection Pooling**: Reuses HTTP connections in MCP bridge
3. **Caching**: Auth tokens cached in auth handler
4. **Error Recovery**: Automatic retries in MCP tools

### Optimization Opportunities
1. **Flow Caching**: Cache frequently accessed flows in MCP server
2. **Log Pagination**: Already implemented with limit parameter
3. **Partial Updates**: API supports replacing individual nodes
4. **Batch Operations**: Could add bulk node update endpoint

---

## Security Considerations

### Implemented Safeguards

1. **Authentication**: All MCP tools check API key via auth handler
2. **Authorization**: API endpoints verify user ownership of flows
3. **Permission Checks**:
   - Can only edit own flows
   - TENANT_ADMIN can edit tenant flows
   - INSTANCE_ADMIN can edit any flow
4. **Input Validation**: API validates node JSON structure
5. **Trigger Protection**: Cannot remove trigger node

### Best Practices

1. **API Key Management**: Never log full API keys
2. **Error Messages**: Don't expose internal IDs in errors
3. **Audit Logging**: All edits logged in database
4. **Rate Limiting**: Consider adding to API endpoints
5. **JSON Validation**: Validate node structure before saving

---

## Future Enhancements

### Potential Improvements

1. **Batch Editing**: Support multiple node updates in one call
2. **Diff View**: Show what changed before/after edit
3. **Version History**: Track flow edit history
4. **Undo/Redo**: Rollback to previous versions
5. **AI Suggestions**: Suggest fixes based on error patterns
6. **Test Mode**: Dry-run edits without saving
7. **Conflict Resolution**: Handle concurrent edits
8. **Template Library**: Common edit patterns

### Integration Opportunities

1. **CI/CD**: Automated flow updates via API
2. **Monitoring**: Alert on repeated execution failures
3. **Analytics**: Track most common edit operations
4. **Collaboration**: Multi-user editing with locks
5. **Migration Tools**: Bulk flow updates across environments

---

## Troubleshooting

### Common Issues

**Issue: "Flow not found"**
```
Solution: Verify flow_name exact match (case-sensitive)
Check user email is correct
Use list_user_flows to see available flows
```

**Issue: "Node not found in flow"**
```
Solution: Check node_id in flow_definition.nodes
Verify node hasn't been removed
Get fresh flow JSON before editing
```

**Issue: "Invalid node JSON"**
```
Solution: Ensure complete node structure
Include id, type, position, data fields
Check parameter schema matches service
```

**Issue: "Cannot remove trigger"**
```
Solution: Trigger removal not allowed
Suggest redesign if trigger needs to change
Can modify trigger parameters via API
```

---

## Conclusion

The Flow Design Editor Agent is now fully implemented with:

✅ Complete MCP tool architecture
✅ 5 new API endpoints for flow editing
✅ 9 MCP tools for agent operations
✅ Execution log analysis for debugging
✅ Intelligent redesign detection
✅ Comprehensive instructions and examples
✅ Consistent with Flow Designer Agent architecture

The implementation provides a robust, scalable foundation for editing existing flows while maintaining clean separation of concerns and following established architectural patterns.

---

## References

- Flow Designer Agent: `/backend/agent/flow_designer/agent.py`
- MCP Server: `/backend/mcp_server/ioflow_mcp_server.py`
- Flow API: `/backend/api/flows.py`
- Execution API: `/backend/api/executions.py`
- MCP Bridge: `/backend/api/mcp_bridge.py`
- Flow Design Guide: `/docs/flow-design-guide.md`
