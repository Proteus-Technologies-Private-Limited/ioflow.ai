# IOFlow Analyst Agent - Delegation Changes

## Overview
The IOFlow Analyst agent has been updated to strictly delegate ALL flow design related tasks to the Flow Design Assistant sub-agent, ensuring proper separation of concerns.

## Changes Made

### 1. Updated Delegation Instructions
- Added explicit CRITICAL DELEGATION RULES section
- Listed 15 specific scenarios that must be delegated
- Added trigger words/phrases that indicate flow-related tasks
- Emphasized that even small flow modifications must be delegated

### 2. Removed Flow Design Tools
The following tools were removed from the analyst agent to prevent direct flow manipulation:
- `get_flow_design_structure()` - Removed completely
- `validate_flow_design()` - Removed completely

These capabilities are now exclusively handled by the flow_assistant sub-agent.

### 3. Kept Documentation Tools
The analyst retains these tools for providing information only:
- `get_service_information()` - For service schemas
- `get_transform_node_guide()` - For documentation
- `get_parameter_mapping_guide()` - For examples
- `get_variable_reference_guide()` - For reference
- `get_pdf_generation_guide()` - For documentation
- `get_node_examples()` - For examples

### 4. Updated Agent Description
- Clarified that flow design tasks will be delegated
- Made it explicit in the user-facing description
- Added warning about delegation in the description

## Delegation Rules

### Tasks That MUST Be Delegated to flow_assistant:
1. Creating any flow (simple or complex)
2. Modifying existing flows
3. Fixing flow errors or issues
4. Validating flow JSON
5. Configuring action nodes in flows
6. Writing transform node scripts
7. Setting up loops, conditions, response nodes
8. Flow JSON structure or generation
9. Troubleshooting flow execution
10. Optimizing flows
11. Adding nodes to flows
12. Changing parameter mappings
13. Debugging flow variables
14. Converting descriptions to flow JSON
15. Configuring flow triggers/events

### Tasks the Analyst Handles Directly:
- Searching for applications, services, flows
- Providing documentation and guides
- Explaining concepts and best practices
- Comparing applications and services
- Web searching for external API info
- Answering questions about IOFlow features
- Providing service schemas and information

## Trigger Words for Delegation
If any of these appear in a flow context, the analyst delegates immediately:
- "create flow", "build flow", "make flow", "design flow"
- "modify flow", "update flow", "change flow", "edit flow", "fix flow"
- "add node", "configure node", "setup node", "connect nodes"
- "transform script", "transform node", "data transformation"
- "parameter mapping", "map parameters", "configure parameters"
- "flow JSON", "flow configuration", "flow structure"
- "validate flow", "check flow", "debug flow", "test flow"
- "action node", "loop node", "condition node", "response node"
- "trigger", "event", "webhook trigger", "schedule trigger"
- "flow error", "flow issue", "flow problem"

## Testing
A test script has been created at `/test-script/test_analyst_delegation.py` that defines test cases for:
- Flow creation requests (should delegate)
- Flow modification requests (should delegate)
- Information requests (should not delegate)
- Documentation requests (should not delegate)

## Running the Analyst
Use the script: `./run_ioflow_analyst.sh`
- Runs on port 8002
- Includes flow_assistant as a sub-agent
- Properly configured for delegation

## Important Notes
1. The analyst now acts as a pure information and analysis agent
2. ALL flow design work is delegated to flow_assistant
3. This ensures consistency in flow creation and modification
4. The analyst can still provide documentation about flow components
5. When in doubt, the analyst will delegate to flow_assistant