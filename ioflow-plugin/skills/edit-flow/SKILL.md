---
description: Edit an existing IOFlow flow. Provide the flow name or ID and what changes to make.
---

# Edit IOFlow Flow

Edit an existing flow based on the user's request: "$ARGUMENTS"

Follow this workflow:

1. Identify the flow:
   - If a flow name is provided, call `get_flow_by_name(flow_name)`
   - If a flow ID is provided, call `get_flow_by_id(flow_id)`
   - If neither is clear, ask the user for the flow name or ID

2. Analyze what needs to change and gather required information:
   - For service changes → call `list_applications()`, `get_application_services_list()`, `get_service_information()`
   - For trigger changes → call `get_application_events_list()`, `get_event_information()`
   - For adding complex nodes → call the appropriate guide (transform, condition, loop)

3. If debugging an execution failure:
   - Call `get_execution_details(execution_id)` and `get_execution_logs(execution_id)`
   - Identify which node failed and why

4. Make edits using:
   - `replace_node_in_flow()` - for fixing/updating nodes (pass COMPLETE node JSON)
   - `add_node_to_flow()` - for adding new nodes
   - `remove_node_from_flow()` - for removing nodes
   - `update_edge_in_flow()` - for changing connections

5. If >50% of the flow needs changing, suggest creating a new flow with the flow-designer agent instead.
