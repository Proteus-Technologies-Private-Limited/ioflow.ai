# Manual Trigger & Debug Guide for IOFlow

## Overview
This guide explains how to use the new manual trigger feature with the chat-like interface and debug capabilities in IOFlow.

## Features

### 1. Manual Trigger from Flow Designer
- When editing a flow, you'll see a "Manual Trigger" button in the header
- Click this button to open the manual execution interface
- The button appears with a cursor/rays icon

### 2. Chat-like Variable Input Interface

The manual trigger modal provides a conversational interface where you can:

#### Input Variables
Type variables in the format: `variable_name=value`

**Examples:**
```
name=John Doe
email=john@example.com
age=30
is_active=true
config={"api_key": "abc123", "timeout": 30}
tags=["urgent", "customer", "bug"]
```

#### Supported Data Types:
- **Strings**: `name=John` or `name="John Doe"`
- **Numbers**: `count=42` or `price=19.99`
- **Booleans**: `active=true` or `enabled=false`
- **JSON Objects**: `data={"key": "value"}`
- **JSON Arrays**: `items=[1, 2, 3]`

#### Special Commands:
- Type `execute` or click the "Execute Flow" button to run the flow
- Type `clear` to reset all variables
- Type `help` to see the help message again

### 3. Debug Application

A new global "Debug" application is available with two actions:

#### Print Action
Logs variable values to the execution log.

**Configuration in Flow Designer:**
1. Add an Action node
2. Select "Debug" as the application
3. Select "Print Variables" as the service
4. Configure the action with:
   - `message`: A descriptive message
   - `variables`: Object containing variables to log
   - `level`: Log level (debug, info, warning, error)

**Example Node Configuration:**
```json
{
  "message": "User data received",
  "variables": {
    "name": "{{input.name}}",
    "email": "{{input.email}}",
    "timestamp": "{{input.timestamp}}"
  },
  "level": "info"
}
```

#### Wait Action
Pauses flow execution for a specified duration (0-300 seconds).

**Configuration:**
- `seconds`: Number of seconds to wait

## Usage Example

### Step 1: Create a Debug Flow

1. Go to Flows → New Flow
2. Name it "Test Debug Flow"
3. Keep the trigger as "Manual"
4. Add a Debug Print action:
   - Application: Debug
   - Service: Print Variables
   - Message: "Flow started with variables"
   - Variables: `{"all_vars": "{{input}}"}`
5. Add another action for your actual logic
6. Add a final Debug Print to show results
7. Save the flow

### Step 2: Execute with Variables

1. Click "Manual Trigger" in the flow designer
2. In the chat interface, enter:
   ```
   user_name=John Smith
   user_id=12345
   action=create_ticket
   priority=high
   ```
3. Type `execute` or click "Execute Flow"

### Step 3: View Debug Output

1. Go to the Executions page
2. Find your execution and click "Details"
3. In the Execution Logs section, you'll see:
   ```
   [timestamp] [debug_node_1] Flow started with variables
   [timestamp] [debug_node_1] {
     "all_vars": {
       "user_name": "John Smith",
       "user_id": 12345,
       "action": "create_ticket",
       "priority": "high"
     }
   }
   ```

## Best Practices

1. **Use Debug Print at Key Points**
   - At the start to log input variables
   - Before and after transformations
   - Before external API calls
   - To log error conditions

2. **Variable Naming**
   - Use descriptive names: `customer_email` not `email`
   - Use underscores for multi-word names
   - Avoid reserved words

3. **Testing Workflows**
   - Start with debug prints to verify data flow
   - Test with various input combinations
   - Use wait actions to simulate delays

4. **Production Considerations**
   - Remove or disable debug nodes in production flows
   - Use appropriate log levels
   - Be mindful of sensitive data in logs

## Troubleshooting

### Variables Not Passing Through
- Ensure variable names match exactly (case-sensitive)
- Check that variables are properly referenced with `{{input.variable_name}}`
- Use Debug Print to inspect actual values

### Execution Not Starting
- Verify the flow is saved
- Check that at least one node follows the trigger
- Ensure proper node connections

### Debug Output Not Visible
- Check the Executions page for the latest execution
- Click "Details" to see full logs
- Ensure Debug actions are properly configured

## Advanced Usage

### Conditional Debugging
Use a Condition node before Debug Print to log only when certain conditions are met:
```
Condition: input.priority === "high"
  → Debug Print: "High priority request received"
```

### Variable Transformation Debugging
Log variables before and after transformation:
```
Debug Print: "Original data"
→ Transform Node
→ Debug Print: "Transformed data"
```

This feature set provides powerful debugging capabilities for developing and testing flows in IOFlow!