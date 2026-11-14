# IOFlow Flow Design Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Flow Concepts](#flow-concepts)
3. [Node Types](#node-types)
4. [Variables and Data Flow](#variables-and-data-flow)
5. [Loop Nodes](#loop-nodes)
6. [Conditions and Logic](#conditions-and-logic)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

## Introduction

IOFlow is a visual workflow automation platform that allows you to create complex integrations and automations by connecting nodes in a flow. This guide covers everything you need to know about designing effective flows.

## Flow Concepts

### What is a Flow?

A flow is a visual representation of an automated workflow consisting of:
- **Nodes**: Individual steps that perform specific actions
- **Edges**: Connections between nodes that define the execution path
- **Variables**: Data that flows between nodes

### Flow Types

1. **Synchronous Flows**: Execute and return a response immediately
   - Must include a Response node
   - Suitable for webhooks and APIs that need immediate responses
   
2. **Asynchronous Flows**: Execute in the background
   - No Response node needed
   - Suitable for long-running processes and scheduled tasks

## Node Types

### 1. Trigger Node
The starting point of every flow.

**Available Trigger Types:**
- **Manual Trigger**: User-initiated execution with custom input variables
- **Schedule Trigger**: Time-based execution (cron, interval, daily, weekly, monthly)
- **Webhook Trigger**: HTTP request triggered execution
- **Event Trigger**: Application event triggered execution (e.g., new email, file upload)

**Key Features:**
- Each trigger type has specific configuration requirements
- Manual and event triggers support complex nested data structures
- Schedule triggers support multiple scheduling patterns
- Webhook triggers can include authentication

**For comprehensive configuration documentation including:**
- Detailed configuration schemas for each trigger type
- Manual trigger variable definitions with nested structures
- Schedule trigger cron expressions and patterns
- Webhook authentication and path configuration
- Event trigger setup and payload schemas
- Configuration examples and best practices

**See:** Use the `get_trigger_node_guide()` MCP tool or API endpoint `GET /api/v1/flow-design/trigger-guide`

You can get specific trigger type configuration:
- `get_trigger_node_guide(trigger_type="manual")` - Manual trigger configuration
- `get_trigger_node_guide(trigger_type="schedule")` - Schedule trigger with cron syntax
- `get_trigger_node_guide(trigger_type="webhook")` - Webhook trigger setup
- `get_trigger_node_guide(trigger_type="event")` - Event trigger configuration

### 2. Action Node
Executes services from connected applications.

**Key Features:**
- Calls APIs from integrated applications
- Supports parameter mapping
- Returns response data for use in subsequent nodes

**Variable Access:**
```
{{input.customerEmail}}        // Access trigger variables
{{node_outputs.123.data}}      // Access previous node outputs
{{global.apiKey}}              // Access global variables
```

### 3. Condition Node
Implements conditional logic in your flow.

**Quick Examples:**
```javascript
input.age >= 18
input.status == "active" && input.plan != "free"
input.items.length > 0
```

**Flow Control:**
- **True Branch**: Executes when condition is met
- **False Branch**: Executes when condition is not met

**For comprehensive documentation including:**
- Expression syntax and operators
- String and array operations
- Complex condition patterns
- Troubleshooting tips

**See:** Condition node guide (API endpoint: `GET /api/v1/flow-design/condition-guide`)

### 4. Transform Node
Manipulates data using Python scripts.

**Key Features:**
- RestrictedPython environment with 5-second timeout
- MUST set 'output' variable with results
- Access trigger variables via 'input' dictionary
- Access node outputs via 'node_outputs' dictionary with node ID

**CRITICAL**: To access data from previous nodes, use `node_outputs['node_id']`, NOT `input`!

**Quick Example:**
```python
# Get data from trigger and previous nodes
user_email = input.get('user_email')
api_data = node_outputs['fetch_api']['data']

# Process and set output
output['result'] = process_data(api_data)
output['user'] = user_email
```

**For comprehensive documentation including:**
- Available modules and libraries
- Variable access patterns
- File handling examples
- Debugging with print statements
- Complex data transformations

**See:** `/docs/transform-guide-escaping-fixes.md` or call the `get_transform_node_guide()` MCP tool

### 5. Loop Node
Iterates over data or repeats actions.

**Loop Types:**
- **For Each**: Iterate over array items (`loopType: "forEach"`)
- **While**: Continue while condition is true (`loopType: "while"`)
- **For**: Numeric range iteration (`loopType: "for"`)

**Loop Variables Available in Body:**
- `{{loop.item}}` - Current item (forEach)
- `{{loop.index}}` - 0-based index
- `{{loop.count}}` - 1-based count
- `{{loop.first}}` / `{{loop.last}}` - Boolean flags

**Loop Connections:**
- **Body Output** (right upper): First node in loop
- **Loop Back Input** (right lower): End of iteration
- **Continue Output** (bottom): After loop completes

**For comprehensive documentation including:**
- Detailed loop type configurations
- Loop variable usage in transforms
- Common loop patterns
- Early exit strategies

**See:** `/docs/loop-variables-in-transform.md`

### 6. Response Node
Defines the response for synchronous flows.

**Configuration:**
```javascript
// Response data
variable: "{{node_outputs.transform_1}}"
statusCode: 200
headers: {
  "Content-Type": "application/json",
  "X-Process-Time": "{{flow.execution_time}}"
}
```

## Variables and Data Flow

### CRITICAL: Understanding Variable Scopes

**The most important concept**: The `input` namespace ALWAYS contains trigger variables only, NOT data from previous nodes!

### Variable Types

1. **Input Variables** (`input.*`)
   - **ONLY contains data from the trigger** (manual inputs, webhook payload, event data)
   - **NOT data from previous nodes** - this is a common misconception!
   - Read-only and accessible throughout the entire flow
   - Example: `{{input.customerEmail}}` (from manual trigger input)

2. **Node Outputs** (`node_outputs.*`)
   - Results from specific nodes that have already executed
   - **Must specify the node ID** to access: `{{node_outputs.nodeId.property}}`
   - This is how you access data from previous nodes (not through `input`!)
   - Example: `{{node_outputs.fetch_user_api.data.userId}}`

3. **Loop Variables** (`loop.*`)
   - **Only available inside loop body nodes**
   - Iteration-specific data
   - Example: `{{loop.item}}`, `{{loop.index}}`

4. **Global Variables** (`global.*`)
   - Shared across all nodes in the flow
   - Must be set by Transform nodes using `set_global()`
   - Persist within flow execution
   - Example: `{{global.authToken}}`

5. **Flow Variables** (`flow.*`)
   - Metadata about flow execution
   - Examples:
     - `{{flow.execution_id}}`
     - `{{flow.start_time}}`
     - `{{flow.current_node}}`

### Variable Resolution

Variables use double curly braces for resolution:
```
{{variablePath}}                    // Simple variable
{{node_outputs.api_123.data.user.id}}   // Nested path with node ID
{{input.items[0].name}}             // Array access (from trigger)
```

**Accessing Nested Structures:**
```javascript
// Array of objects
{{input.contacts[0].name}}

// Nested objects
{{input.company_data.departments[0].name}}

// In Transform nodes (Python)
contacts = input.get('contacts', [])

// In loop context
{{loop.item.name}}
```

### Variable Access by Context

Different contexts require different syntax:

**1. In Parameter Mapping (Action Nodes):**
```json
{
  "parameterMapping": {
    "email": {
      "source": "variable",
      "value": "input.user_email"  // No curly braces!
    },
    "data": {
      "source": "variable", 
      "value": "node_outputs.transform_1.processed_data"  // Specify node ID
    }
  }
}
```

**2. In Transform Nodes (Python):**
```python
# No curly braces, use dict/object access
email = input.get('user_email')  # Trigger variable
api_result = node_outputs['fetch_api']['data']  # Previous node output
loop_item = loop.get('item')  # Loop variable (if in loop)
global_var = global.get('api_key')  # Global variable
```

**3. In Condition Nodes:**
```javascript
// No curly braces, use dot notation
input.status == "active"
node_outputs.validate_api.is_valid == true
loop.index < 10
```

**4. In Response Nodes:**
```json
{
  "variable": "{{node_outputs.final_transform}}",  // With curly braces
  "statusCode": 200
}
```

### Data Transformation

Transform nodes can modify data structure:
```python
# Get from trigger and previous nodes
user_email = input.get('user_email')
api_data = node_outputs['fetch_api']['response']

# Process and output
output['summary'] = {
    'count': len(api_data.get('items', [])),
    'user': user_email
}
```

**See transform guide for detailed examples:** `/docs/transform-guide-escaping-fixes.md`

## Loop Nodes

### Best Practices
- Initialize variables before loop
- Update loop conditions inside loop body
- Collect results in array for aggregation

### Common Patterns
1. **Process Array**: `Trigger → Loop (forEach) → Action → Loop Back → Continue`
2. **Retry Logic**: `Loop (while) → Action → Condition → Loop Back or Continue`
3. **Pagination**: `Loop (while hasMore) → Fetch Page → Process → Loop Back`

**See loop guide for detailed patterns:** `/docs/loop-variables-in-transform.md`

## Conditions and Logic

### Quick Reference
**Operators:** `==`, `!=`, `>`, `<`, `>=`, `<=`, `&&`, `||`, `!`

**Examples:**
```javascript
input.email.includes('@gmail.com')
input.status == "active" && input.total > 100
input.items.length > 0
```

### Common Patterns
- **Multi-Branch**: Chain conditions for multiple paths
- **Validation**: Check conditions before processing
- **Error Handling**: Route to different actions based on status

**See condition guide for comprehensive syntax:** API endpoint `GET /api/v1/flow-design/condition-guide`

## Best Practices

### 1. Error Handling
- Use condition nodes to check for errors
- Provide meaningful error responses
- Log errors for debugging

### 2. Performance
- Minimize API calls in loops
- Use batch operations when available
- Cache results in global variables

### 3. Maintainability
- Use descriptive node labels
- Document complex transforms
- Group related logic

### 4. Security
- Never hardcode credentials
- Use application authentication
- Validate input data

### 5. Testing
- Test with edge cases
- Verify loop termination
- Check error scenarios

## Flow Examples

### Simple Patterns
1. **API Chain**: `Trigger → API Call → Transform → Response`
2. **Conditional**: `Trigger → Condition → True: Action A | False: Action B`
3. **Loop Processing**: `Trigger → Loop → Action → Loop Back → Response`

### Complex Patterns
1. **Order Processing**: Webhook trigger → Validate → Loop items → Reserve stock → Email
2. **Data Sync**: Schedule trigger → Fetch → Loop batches → Check/Create/Update → Report
3. **Approval Flow**: Form trigger → Loop approvers → Wait for approval → Process/Reject

**Note:** See specific node guides for detailed implementation patterns

## Troubleshooting

### Common Issues

1. **Infinite Loops**
   - Always update loop condition variables
   - Add safety counters
   - Use max iteration limits

2. **Variable Not Found**
   - Check variable paths
   - Verify node execution order
   - Look for typos in variable names

3. **No Output from Node**
   - Check node logs
   - Verify authentication
   - Test with simulation mode

4. **Flow Not Executing**
   - Verify trigger configuration
   - Check flow status (active/inactive)
   - Review execution logs

### Debug Tips
1. Use Transform nodes with `print()` statements
2. Add temporary Response nodes to inspect data
3. Check execution logs for flow path
4. Start with simple test data

**For detailed debugging:** See transform guide `/docs/transform-guide-escaping-fixes.md`

## Conclusion

IOFlow provides a powerful visual interface for creating complex workflows. By understanding node types, variable scoping, and flow patterns, you can build robust automations that handle real-world scenarios effectively.

Remember to:
- Start simple and iterate
- Test thoroughly
- Document your flows
- Follow best practices
- Leverage the visual nature of flows for clarity

For more information, refer to the API documentation and application-specific guides.