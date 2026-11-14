# IOFlow Trigger Configuration Guide for AI Agents

## 🚨 CRITICAL: Dual Configuration Required

When creating flows with manual triggers in IOFlow, you MUST configure the trigger in **TWO places**:

### 1. Flow-Level Configuration (`trigger_config`)
```json
{
  "flow": {
    "trigger_config": {
      "type": "manual",
      "manual_variables": [  // ← REQUIRED HERE for backend
        {
          "name": "input_param",
          "dataType": "string",
          "description": "Description",
          "required": true,
          "defaultValue": ""
        }
      ]
    }
  }
}
```

### 2. Node-Level Configuration (trigger node `data`)
```json
{
  "nodes": [{
    "id": "trigger",
    "type": "trigger",
    "data": {
      "type": "manual",
      "manualVariables": [  // ← ALSO REQUIRED HERE for UI
        {
          "name": "input_param",
          "dataType": "string",
          "description": "Description",
          "required": true,
          "defaultValue": ""
        }
      ]
    }
  }]
}
```

## Why Both Are Required

| Configuration | Location | Purpose | What Happens If Missing |
|--------------|----------|---------|------------------------|
| `trigger_config.manual_variables` | Flow level | Backend execution engine | Flow won't accept input parameters |
| `data.manualVariables` | Trigger node | UI rendering | Input fields won't show in UI |

## Complete Working Template

```json
{
  "version": "1.0.0",
  "flow": {
    "flow_name": "AI Agent Generated Flow",
    "description": "Flow with proper trigger configuration",
    "trigger_config": {
      "type": "manual",
      "manual_variables": [
        {
          "name": "question",
          "dataType": "string",
          "description": "User's question",
          "required": true,
          "defaultValue": ""
        },
        {
          "name": "context",
          "dataType": "object",
          "description": "Additional context",
          "required": false,
          "defaultValue": {}
        }
      ],
      "execute_immediately": true
    },
    "flow_definition": {
      "nodes": [
        {
          "id": "trigger",
          "type": "trigger",
          "position": {"x": 100, "y": 100},
          "data": {
            "label": "Manual Trigger",
            "type": "manual",
            "triggerType": "manual",
            "manualVariables": [
              {
                "name": "question",
                "dataType": "string",
                "description": "User's question",
                "required": true,
                "defaultValue": ""
              },
              {
                "name": "context",
                "dataType": "object",
                "description": "Additional context",
                "required": false,
                "defaultValue": {}
              }
            ],
            "executeImmediately": true
          }
        },
        {
          "id": "action_1",
          "type": "action",
          "position": {"x": 300, "y": 100},
          "data": {
            "label": "Process Data",
            "appId": "app-uuid",
            "serviceId": "service-uuid",
            "appName": "Application Name",
            "serviceName": "service_name",
            "inputs": {
              "input_text": "{{trigger.question}}",
              "context": "{{trigger.context}}"
            }
          }
        }
      ],
      "edges": [
        {
          "id": "edge1",
          "source": "trigger",
          "target": "action_1",
          "sourceHandle": "output",
          "targetHandle": "input"
        }
      ]
    }
  }
}
```

## Validation Checklist for AI Agents

Before submitting a flow, verify:

- [ ] `flow.trigger_config.manual_variables` contains all input parameters
- [ ] `trigger_node.data.manualVariables` contains the SAME parameters
- [ ] All edges have `sourceHandle` and `targetHandle` 
- [ ] Action nodes have both IDs and names (`appId`+`appName`, `serviceId`+`serviceName`)
- [ ] Variable references use correct syntax: `{{node_id.field}}`

## Common Patterns

### Single Input
```json
"manual_variables": [{
  "name": "input",
  "dataType": "string",
  "required": true
}]
```

### Multiple Inputs
```json
"manual_variables": [
  {"name": "text", "dataType": "string", "required": true},
  {"name": "options", "dataType": "object", "required": false},
  {"name": "count", "dataType": "number", "required": false, "defaultValue": 1}
]
```

### File Input
```json
"manual_variables": [{
  "name": "file",
  "dataType": "file",
  "description": "File to process",
  "required": true,
  "accept": ".pdf,.txt,.doc"
}]
```

## MCP Tools Available

When using IOFlow MCP services:

1. **get_flow_node_template("trigger")** - Returns a trigger template (note: template needs manual_variables populated)
2. **validate_flow_definition()** - Validates flow structure including trigger configuration
3. **flow_design_guidelines** - Get comprehensive flow design documentation

## Remember

⚠️ **ALWAYS** configure manual triggers in both places or the flow will not work properly!

- Backend needs `trigger_config.manual_variables` for flow execution
- Frontend needs `data.manualVariables` for UI rendering
- Both must be synchronized with the same parameters
- Input variables are automatically accessible via `{{trigger.variableName}}` or `{{input.variableName}}` in subsequent nodes