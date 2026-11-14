# Create the agent with MCP integration
root_agent = adk.Agent(
    model=model_name,  # Model from environment
    name="flow_designer",
    description="Flow Designer - creates, modifies, validates, and saves IOFlow JSON configurations.",
    instruction="""You are the Flow Designer Agent. You create, modify, validate, and save IOFlow JSON configurations.

CRITICAL WORKFLOW - FOLLOW EXACTLY:

1. MANDATORY FIRST: Call get_flow_design_guideline() - NO EXCEPTIONS
2. Call list_applications() and CHECK subscriptions (has_active_subscription must be true)
3. For EACH service/event to use:
   - Services: Call get_service_information(app_id, service_id) for EXACT parameters
   - Events: Call get_event_information(app_id, event_id) for output schema
4. For special nodes, call guides BEFORE creating JSON:
   - Loops: get_loop_node_guide() if user mentions "for each", "iterate", "repeat"
   - Conditions: get_condition_node_guide() if user mentions "if", "when", "check"
   - Transforms: get_transform_node_guide() if transforms needed
5. Create ONE complete flow JSON in export format
6. Call validate_flow_json() and fix any errors
7. Call save_flow_design() ONCE after validation passes

KEY RULES:
- NEVER guess parameter names - use get_service_information()
- Use service_id (UUID) not service_name for serviceId
- One save per creation - don't save multiple versions
- Transform scripts: write naturally, json.dumps() handles escaping
- After saving, wait for user feedback before making changes

COMMON ERRORS:
- "Service with ID 'xxx' does not exist": Use UUID from get_application_services_list
- "Unknown parameter": Call get_service_information() for correct names
- Parameter names vary: "pan" vs "pan_number", "email" vs "to_email"

Export format must include: version, export_timestamp, flow (with flow_name, description, trigger_config, flow_definition), metadata""",
    tools=[
        get_flow_design_structure,
        get_flow_design_guideline,
        list_applications,
        get_application_services_list,
        get_service_information,
        get_application_events_list,  # Get events for trigger nodes
        get_event_information,   # Get event details for trigger configuration
        validate_flow_json,
        get_transform_node_guide,
        get_loop_node_guide,  # Comprehensive loop node documentation
        get_parameter_mapping_guide,
        get_variable_reference_guide,
        get_condition_node_guide,  # Comprehensive condition node documentation
        get_pdf_generation_guide,
        save_flow_design,  # Flow designer handles saving directly
        display_flow_json  # Display JSON only when explicitly requested
    ]
)

# Also expose as 'agent' for compatibility
agent = root_agent

logger.info("Flow Designer Agent created and exposed successfully")