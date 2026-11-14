# IOFlow - Complete Flow Structure Reference

## ✅ Correct Node Types and Structure

### 1. Trigger Node
```json
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
        "description": "Input question",
        "required": true,
        "defaultValue": ""
      }
    ],
    "outputs": {
      "question": "{{input.question}}"
    },
    "executeImmediately": true
  }
}
```

### 2. Action Node
```json
{
  "id": "action_id",
  "type": "action",
  "position": {"x": 300, "y": 100},
  "data": {
    "label": "Service Name",
    "config": {},
    "appId": "uuid",
    "serviceId": "uuid",
    "appName": "Application Name",
    "serviceName": "service_name",
    "serviceDisplayName": "Display Name",
    "appIcon": "/path/to/icon.png",
    "appType": "api",
    "appCategory": "Category",
    "useParameterMapping": true,
    "parameterMapping": {
      "param1": "{{trigger.output1}}",
      "param2": "value"
    },
    "parameters": {
      "param1": "{{trigger.output1}}",
      "param2": "value"
    }
  }
}
```

**IMPORTANT for Action Nodes:**
- Must have BOTH `parameterMapping` AND `parameters`
- Set `useParameterMapping: true`
- Include empty `config: {}`
- Must have both IDs and names (appId + appName, serviceId + serviceName)

### 3. Response Node (NOT "output")
```json
{
  "id": "response",
  "type": "response",  // ← NOT "output"
  "position": {"x": 500, "y": 100},
  "data": {
    "label": "Return Result",
    "responseType": "success",
    "statusCode": 200,
    "responseBody": {
      "field1": "{{node.output}}",
      "field2": "value"
    },
    "response": {
      "field1": "{{node.output}}",
      "field2": "value"
    }
  }
}
```

**IMPORTANT for Response Nodes:**
- Type must be `"response"` NOT `"output"`
- Include both `responseBody` AND `response` fields
- Set `responseType: "success"` and `statusCode: 200`

### 4. Edges
```json
{
  "id": "edge_id",
  "source": "source_node_id",
  "target": "target_node_id",
  "sourceHandle": "output",
  "targetHandle": "input",
  "type": "smoothstep"
}
```

**IMPORTANT for Edges:**
- MUST have `sourceHandle` and `targetHandle`
- Use node IDs that actually exist in the nodes array
- Common handles: "output" and "input"

## Complete Working Example

```json
{
  "version": "1.0.0",
  "flow": {
    "flow_name": "Complete Example Flow",
    "description": "Properly structured flow",
    "trigger_config": {
      "type": "manual",
      "manual_variables": [
        {
          "name": "input_text",
          "dataType": "string",
          "description": "Input text",
          "required": true,
          "defaultValue": ""
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
            "label": "Start",
            "type": "manual",
            "triggerType": "manual",
            "manualVariables": [
              {
                "name": "input_text",
                "dataType": "string",
                "description": "Input text",
                "required": true,
                "defaultValue": ""
              }
            ],
            "outputs": {
              "input_text": "{{input.input_text}}"
            },
            "executeImmediately": true
          }
        },
        {
          "id": "action_1",
          "type": "action",
          "position": {"x": 300, "y": 100},
          "data": {
            "label": "Process",
            "config": {},
            "appId": "app-uuid",
            "serviceId": "service-uuid",
            "appName": "App Name",
            "serviceName": "service_name",
            "serviceDisplayName": "Service Display Name",
            "useParameterMapping": true,
            "parameterMapping": {
              "input": "{{trigger.input_text}}"
            },
            "parameters": {
              "input": "{{trigger.input_text}}"
            }
          }
        },
        {
          "id": "response",
          "type": "response",
          "position": {"x": 500, "y": 100},
          "data": {
            "label": "Return",
            "responseType": "success",
            "statusCode": 200,
            "responseBody": {
              "result": "{{action_1.output}}"
            },
            "response": {
              "result": "{{action_1.output}}"
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
          "targetHandle": "input",
          "type": "smoothstep"
        },
        {
          "id": "edge2",
          "source": "action_1",
          "target": "response",
          "sourceHandle": "output",
          "targetHandle": "input",
          "type": "smoothstep"
        }
      ]
    }
  },
  "metadata": {
    "required_applications": ["app_key"],
    "tags": ["example"],
    "version": "1.0.0"
  }
}
```

## Common Issues and Solutions

### Issue: Nodes appear disconnected in UI
**Solution:** Ensure edges have `sourceHandle` and `targetHandle` fields

### Issue: Response node doesn't render
**Solution:** Use type `"response"` not `"output"`

### Issue: Action node parameters not working
**Solution:** Include BOTH `parameterMapping` and `parameters` fields, set `useParameterMapping: true`

### Issue: Trigger doesn't accept inputs
**Solution:** Define `manual_variables` in BOTH `trigger_config` and node `data.manualVariables`

### Issue: Variables not accessible between nodes
**Solution:** 
- Trigger outputs: `{{trigger.variable_name}}`
- Action outputs: `{{action_id.field_path}}`
- Use proper JSONPath for nested: `{{action_id.result[0].value}}`

## Validation Checklist

Before importing a flow:

- [ ] All nodes have unique IDs
- [ ] Node type is correct (`trigger`, `action`, `response` - NOT `output`)
- [ ] Trigger has `manualVariables` in both places
- [ ] Trigger has `outputs` mapping inputs
- [ ] Action nodes have:
  - [ ] Both `parameterMapping` AND `parameters`
  - [ ] `useParameterMapping: true`
  - [ ] `config: {}`
  - [ ] Both IDs and names (appId, appName, serviceId, serviceName)
- [ ] Response node has:
  - [ ] Type `"response"` not `"output"`
  - [ ] Both `responseBody` and `response`
  - [ ] `responseType` and `statusCode`
- [ ] All edges have:
  - [ ] Valid source and target IDs
  - [ ] `sourceHandle` and `targetHandle`
- [ ] Variable references use correct syntax `{{node_id.path}}`

## For MCP/AI Agents

When generating flows:
1. Always use this structure exactly
2. Include all required fields even if empty
3. Use `"response"` type, never `"output"`
4. Set both `parameterMapping` and `parameters` in actions
5. Configure triggers in both `trigger_config` and node data