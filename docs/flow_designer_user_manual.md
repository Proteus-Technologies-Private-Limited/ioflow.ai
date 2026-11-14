# IOFlow Designer User Manual

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Flow Designer Interface](#flow-designer-interface)
4. [Node Types](#node-types)
5. [Creating Your First Flow](#creating-your-first-flow)
6. [Working with Nodes](#working-with-nodes)
7. [Connecting Nodes](#connecting-nodes)
8. [Configuring Nodes](#configuring-nodes)
9. [Variables and Data Flow](#variables-and-data-flow)
10. [Testing and Debugging](#testing-and-debugging)
11. [Synchronous vs Asynchronous Flows](#synchronous-vs-asynchronous-flows)
12. [Best Practices](#best-practices)
13. [Troubleshooting](#troubleshooting)

## Introduction

IOFlow Designer is a visual workflow automation tool that allows you to create integrations between different applications and services without writing code. You can design flows by dragging and dropping nodes, connecting them together, and configuring their behavior.

### Key Concepts

- **Flow**: A series of connected nodes that define an automated workflow
- **Node**: A single step in your workflow (trigger, action, condition, etc.)
- **Edge**: A connection between two nodes that defines the flow of data
- **Trigger**: The starting point of a flow that initiates execution
- **Action**: A node that performs an operation (API call, data processing, etc.)

## Getting Started

### Accessing the Flow Designer

1. Log into IOFlow
2. Navigate to the "Flows" section
3. Click "Create New Flow" or select an existing flow to edit

### Flow Designer Layout

The Flow Designer consists of several key areas:

```
┌─────────────────────────────────────────────────────────┐
│  Header (Flow Name, Description, Save, Test)           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Canvas Area                    │  Properties Panel    │
│  (Drop nodes here)              │  (Configure nodes)   │
│                                 │                      │
│  ┌─────┐    ┌─────┐           │                      │
│  │Trigger├──►│Action│          │                      │
│  └─────┘    └─────┘           │                      │
│                                 │                      │
├─────────────────────────────────┴──────────────────────┤
│  Controls (Zoom, Mini-map, Background)                 │
└─────────────────────────────────────────────────────────┘
```

## Flow Designer Interface

### 1. Header Section
- **Flow Name**: Click to edit the flow name
- **Description**: Add a description for your flow
- **Synchronous Checkbox**: Enable for flows that return responses
- **Save Button**: Save your flow changes
- **Test Button**: Execute the flow with test data

### 2. Canvas Area
- **Drag and drop** nodes from the node panel
- **Pan** by clicking and dragging the background
- **Zoom** using mouse wheel or zoom controls
- **Select** nodes by clicking on them
- **Multi-select** by holding Shift and clicking

### 3. Node Panel
Click "Add Node" to see available node types:
- Action
- Condition
- Transform
- Response (only for synchronous flows)

### 4. Properties Panel
Opens when you select a node to configure:
- Node label
- Node-specific settings
- Delete button (trash icon)

### 5. Controls
- **Zoom In/Out**: Adjust canvas zoom level
- **Fit View**: Auto-zoom to show all nodes
- **Mini Map**: Overview of your entire flow
- **Background**: Toggle grid pattern

## Node Types

### 1. Trigger Node
**Purpose**: Starting point of every flow

**Types**:
- **Manual**: Triggered by user action or API call
- **Webhook**: Triggered by external webhook
- **Schedule**: Triggered on a schedule (cron)
- **Event**: Triggered by application events
- **API Call**: Triggered by direct API calls

**Configuration**:
```
Manual Trigger:
- Define input variables with types
- Set descriptions for each variable

Webhook Trigger:
- Get unique webhook URL after saving

Schedule Trigger:
- Set cron expression (e.g., "0 9 * * *" for 9 AM daily)

Event Trigger:
- Select application
- Choose specific event
```

### 2. Action Node
**Purpose**: Perform operations like API calls, sending emails, etc.

**Configuration**:
1. Select Application
2. Choose Service/Operation
3. Map parameters from previous nodes
4. Configure authentication (if needed)

**Example**:
```
Application: Slack
Service: Send Message
Parameters:
  - channel: {{input.channel}}
  - message: {{node_outputs.transform_1.formatted_message}}
```

### 3. Condition Node
**Purpose**: Branch flow based on conditions

**Features**:
- Compare values
- Multiple conditions (AND/OR)
- Different paths for true/false

**Configuration**:
```
IF input.order_total > 100
THEN → Premium Processing
ELSE → Standard Processing
```

### 4. Transform Node
**Purpose**: Manipulate and transform data

**Features**:
- Write Python-like scripts
- Access to previous node outputs
- String and math operations
- Loops and conditionals

**Example Script**:
```python
# Calculate order summary
local['items'] = input.get('items', [])
local['total'] = 0

for item in local['items']:
    local['total'] = math['add'](local['total'], item['price'])

result['item_count'] = len(local['items'])
result['total_amount'] = local['total']
result['average_price'] = math['divide'](local['total'], len(local['items']))
```

### 5. Response Node (Synchronous Flows Only)
**Purpose**: Return data from a synchronous flow

**Configuration**:
- Select variable to return
- Set HTTP status code
- Add response headers

## Creating Your First Flow

### Step 1: Create a New Flow

1. Click "Create New Flow"
2. Enter a flow name (e.g., "Process Order")
3. Add a description
4. Choose flow type:
   - **Asynchronous**: Fire-and-forget workflows
   - **Synchronous**: Return a response (API-like)

### Step 2: Add a Trigger

1. Every flow starts with a trigger node (automatically added)
2. Click the trigger node to configure
3. Select trigger type:
   - For testing, use "Manual" trigger
   - Define input variables

### Step 3: Add Action Nodes

1. Click "Add Node" button
2. Select "Action"
3. Click the new node to configure:
   - Choose an application
   - Select a service
   - Map parameters

### Step 4: Connect Nodes

1. Hover over a node to see connection points
2. Drag from the output handle to the input handle of the next node
3. Connections show data flow direction

### Step 5: Test Your Flow

1. Click "Save" to save your flow
2. Click "Test" to open the test dialog
3. Enter test data for your trigger variables
4. Click "Execute" to run the flow
5. View execution results in the Executions page

## Working with Nodes

### Adding Nodes

1. Click "Add Node" button
2. Choose node type from the panel
3. Node appears on canvas at a random position
4. Drag to desired location

### Selecting Nodes

- **Single Click**: Select one node
- **Shift + Click**: Add to selection
- **Click Background**: Deselect all

### Moving Nodes

- Click and drag selected nodes
- Use arrow keys for precise movement
- Maintain connections while moving

### Deleting Nodes

1. Select the node
2. Click trash icon in properties panel
3. Or press Delete/Backspace key
4. Connections are automatically removed

### Copying Nodes

Currently not supported - must recreate nodes manually

## Connecting Nodes

### Creating Connections

1. Hover over source node
2. Click and drag from output handle (bottom)
3. Drop on target node's input handle (top)
4. Connection line shows data flow

### Connection Rules

- Trigger nodes can only have outputs
- Action nodes have both inputs and outputs
- Condition nodes have multiple outputs (true/false)
- Response nodes only have inputs
- No circular connections allowed

### Removing Connections

1. Click on a connection line to select it
2. Press Delete/Backspace key

## Configuring Nodes

### Action Node Configuration

1. **Application Selection**
   ```
   Application: [Dropdown - Slack, Email, Database, etc.]
   ```

2. **Service Selection**
   ```
   Service: [Dropdown - Send Message, Create Record, etc.]
   ```

3. **Parameter Mapping**
   - Static values: Enter directly
   - Dynamic values: Use variable syntax `{{variable_path}}`
   - Examples:
     ```
     Channel: #general (static)
     Message: {{input.message}} (dynamic)
     User: {{node_outputs.fetch_user.email}} (from previous node)
     ```

### Transform Node Configuration

1. **Script Templates**
   - Basic: Simple transformations
   - Loop: Process arrays/lists
   - String Ops: Text manipulation
   - Aggregate: Calculate statistics

2. **Available Objects**
   ```python
   input          # Data from previous node
   local          # Local variables (dictionary)
   global_vars    # Global flow variables
   node_outputs   # All node outputs
   result         # Your output (dictionary)
   string         # String functions
   math           # Math functions
   set_global()   # Set global variable
   ```

3. **Example Scripts**
   ```python
   # Format currency
   result['formatted_price'] = f"${input.get('price', 0):.2f}"
   
   # Process list
   local['emails'] = []
   for user in input.get('users', []):
       local['emails'].append(user.get('email'))
   result['email_list'] = local['emails']
   ```

### Condition Node Configuration

1. **Simple Conditions**
   ```
   Field: {{input.age}}
   Operator: Greater than
   Value: 18
   ```

2. **Complex Conditions**
   ```
   ({{input.status}} == "active" AND {{input.credits}} > 0)
   OR
   {{input.subscription}} == "premium"
   ```

### Response Node Configuration

1. **Variable Selection**
   - Choose from dropdown or enter path
   - Static string: `"Hello World"`
   - Variable: `node_outputs.transform_1.result`

2. **HTTP Configuration**
   ```
   Status Code: 200
   Headers:
     Content-Type: application/json
     X-Flow-ID: {{flow.execution_id}}
   ```

## Variables and Data Flow

### Variable Syntax

Use double curly braces for variables:
```
{{variable_path}}
```

### Variable Paths

1. **Input Variables**
   ```
   {{input.username}}
   {{input.order.id}}
   {{input.items[0].name}}
   ```

2. **Node Outputs**
   ```
   {{node_outputs.action_1.data}}
   {{node_outputs.fetch_user.user.email}}
   {{node_outputs.transform_1.total}}
   ```

3. **Global Variables**
   ```
   {{global_vars.user_count}}
   {{global_vars.settings.api_key}}
   ```

4. **Flow Metadata**
   ```
   {{flow.execution_id}}
   {{flow.start_time}}
   {{flow.current_node}}
   ```

### Variable Scope

- **Input**: Available throughout the flow
- **Node Outputs**: Available in subsequent nodes
- **Local** (Transform only): Scoped to current transform
- **Global**: Persistent across all nodes

## Testing and Debugging

### Test Mode

1. **Manual Trigger Testing**
   - Click "Test" button
   - Fill in test data for variables
   - Execute and monitor progress

2. **Viewing Results**
   - Go to Executions page
   - Click on execution to see details
   - View node-by-node execution trace

### Execution Trace

Shows for each node:
- Input data
- Output data
- Execution time
- Error messages (if any)

### Common Issues

1. **"Variable not found"**
   - Check variable path spelling
   - Ensure previous node outputs data
   - Verify node execution order

2. **"Connection refused"**
   - Check application credentials
   - Verify API endpoint is correct
   - Check network connectivity

3. **"Transform error"**
   - Review script syntax
   - Check for division by zero
   - Verify data types match operations

## Synchronous vs Asynchronous Flows

### Asynchronous Flows

- **Use When**: 
  - Processing doesn't need immediate response
  - Long-running operations
  - Bulk processing

- **Characteristics**:
  - Fire-and-forget execution
  - No response node available
  - Can run indefinitely

- **Example Use Cases**:
  - Send notification emails
  - Process uploaded files
  - Sync data between systems

### Synchronous Flows

- **Use When**:
  - Need immediate response
  - Building API endpoints
  - Request-response patterns

- **Characteristics**:
  - Must complete within timeout (30s default)
  - Response node required
  - Returns data to caller

- **Example Use Cases**:
  - Data validation endpoints
  - Real-time calculations
  - API proxies/transformations

### Enabling Synchronous Mode

1. Check "Synchronous" in flow header
2. Response node becomes available
3. Add Response node at flow end
4. Configure return data

## Best Practices

### 1. Flow Design

- **Keep flows focused**: One flow = one purpose
- **Use meaningful names**: Both for flows and nodes
- **Add descriptions**: Document complex logic
- **Modular design**: Break complex flows into smaller ones

### 2. Error Handling

- **Validate inputs**: Check data exists before using
- **Handle edge cases**: Empty arrays, null values
- **Use default values**: `input.get('key', default)`
- **Test thoroughly**: Use various test scenarios

### 3. Performance

- **Minimize API calls**: Batch when possible
- **Efficient transforms**: Avoid nested loops
- **Parallel execution**: Use parallel branches
- **Cache when appropriate**: Use global variables

### 4. Security

- **Never hardcode secrets**: Use application credentials
- **Validate external input**: Don't trust webhook data
- **Limit access**: Use appropriate permissions
- **Audit flows**: Review who can edit/execute

### 5. Maintenance

- **Version control**: Save flow versions
- **Document changes**: Use flow description
- **Test after changes**: Ensure nothing breaks
- **Monitor executions**: Check for failures

## Troubleshooting

### Flow Won't Save

**Symptoms**: Save button doesn't work or shows error

**Solutions**:
1. Check for validation errors (red nodes)
2. Ensure all required fields are filled
3. Verify at least one trigger exists
4. Check browser console for errors

### Nodes Won't Connect

**Symptoms**: Can't draw connections between nodes

**Solutions**:
1. Ensure nodes are compatible
2. Check for existing connections
3. Verify no circular dependencies
4. Try deleting and recreating connection

### Execution Fails

**Symptoms**: Flow starts but fails at specific node

**Solutions**:
1. Check execution logs for error details
2. Verify node configuration
3. Test with simpler data
4. Check application credentials

### Slow Performance

**Symptoms**: Flow designer is laggy or slow

**Solutions**:
1. Reduce number of nodes if possible
2. Clear browser cache
3. Use Chrome/Firefox (latest)
4. Close other browser tabs

### Data Not Passing Between Nodes

**Symptoms**: Next node receives empty/wrong data

**Solutions**:
1. Check variable paths are correct
2. Verify previous node outputs data
3. Use execution trace to debug
4. Test nodes individually

## Keyboard Shortcuts

- **Delete/Backspace**: Delete selected nodes/edges
- **Ctrl/Cmd + S**: Save flow
- **Ctrl/Cmd + Z**: Undo (limited support)
- **Escape**: Deselect all
- **Arrow Keys**: Move selected nodes

## Advanced Features

### 1. Conditional Branching

Create complex decision trees:
```
Trigger → Condition → Action A (if true)
                   ↘ Action B (if false)
```

### 2. Parallel Execution

Process multiple paths simultaneously:
```
Trigger → Split → Action A ↘
                → Action B → Merge → Continue
                → Action C ↗
```

### 3. Error Recovery

Handle failures gracefully:
```
Action → On Error → Error Handler → Notification
```

### 4. Dynamic Routing

Route based on data:
```
Transform → Condition (route) → Queue A
                              → Queue B
                              → Queue C
```

## Getting Help

1. **Documentation**: Check this manual and API docs
2. **Examples**: Browse sample flows
3. **Support**: Contact support team
4. **Community**: Join IOFlow community forum

## Conclusion

The IOFlow Designer provides a powerful yet intuitive way to create automated workflows. Start simple with basic flows, then gradually explore advanced features as you become comfortable with the interface.

Remember: Every expert was once a beginner. Happy flow building!