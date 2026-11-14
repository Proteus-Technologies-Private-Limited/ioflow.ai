---
description: Design a new IOFlow automation flow. Describe what the flow should do as arguments.
---

# Design IOFlow Flow

Design a new automation flow based on the user's requirements: "$ARGUMENTS"

Follow this workflow:

1. **MANDATORY FIRST STEP**: Call `get_flow_design_guideline()` to get flow JSON structure and rules
2. If the flow uses external applications, call `list_applications()` (with app_names if specific apps mentioned)
3. For each application in the flow:
   - For triggers: call `get_application_events_list(app_id)` and `get_event_information(app_id, event_id)`
   - For actions: call `get_application_services_list(app_id)` and `get_service_information(app_id, service_id)`
4. For complex nodes, call the appropriate guides:
   - Transform nodes → `get_transform_node_guide()`
   - Condition nodes → `get_condition_node_guide()`
   - Loop nodes → `get_loop_node_guide()`
   - Triggers → `get_trigger_node_guide(trigger_type)`
5. Create the flow JSON with correct UUIDs from the discovery calls
6. Call `validate_and_save_flow(flow_json)` - only ONE call per turn
7. Wait for result, fix errors if needed in next turn

Important:
- Use service_id (UUID) not service names
- All nodes and edges go inside flow.flow_definition
- One validate_and_save_flow call per turn maximum
