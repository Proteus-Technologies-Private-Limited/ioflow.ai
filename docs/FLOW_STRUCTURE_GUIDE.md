# IOFlow - Correct Flow Structure Guide

## Critical Discovery: Dual Configuration Required

For manual trigger flows to work properly in IOFlow, you need **TWO** configurations:

### 1. `trigger_config` at Flow Level
This defines the flow's input parameters at the flow level:
```json
"trigger_config": {
  "type": "manual",
  "manual_variables": [  // ← CRITICAL: Define inputs here
    {
      "name": "question",
      "dataType": "string",
      "description": "The question to ask",
      "required": true,
      "defaultValue": ""
    }
  ],
  "execute_immediately": true
}
```

### 2. `manualVariables` in Trigger Node
The trigger node ALSO needs the same configuration:
```json
{
  "id": "trigger",
  "type": "trigger",
  "data": {
    "type": "manual",
    "manualVariables": [  // ← ALSO needed here for UI
      {
        "name": "question",
        "dataType": "string",
        "description": "The question to ask",
        "required": true,
        "defaultValue": ""
      }
    ],
    "outputs": {
      "question": "{{input.question}}"
    }
  }
}
```

## Why Both Are Needed

1. **`trigger_config.manual_variables`**: Used by the backend execution engine to:
   - Accept input parameters when flow is executed
   - Validate input data
   - Pass parameters to the flow

2. **Node `data.manualVariables`**: Used by the frontend UI to:
   - Display input fields in the flow designer
   - Show parameter configuration
   - Render the node properly

## Complete Working Example

```json
{
  "version": "1.0.0",
  "flow": {
    "flow_name": "Example Flow",
    "trigger_config": {
      "type": "manual",
      "manual_variables": [  // ← Backend needs this
        {
          "name": "input_param",
          "dataType": "string",
          "description": "Input parameter",
          "required": true
        }
      ]
    },
    "flow_definition": {
      "nodes": [
        {
          "id": "trigger",
          "type": "trigger",
          "data": {
            "type": "manual",
            "manualVariables": [  // ← Frontend needs this
              {
                "name": "input_param",
                "dataType": "string",
                "description": "Input parameter",
                "required": true
              }
            ],
            "outputs": {
              "input_param": "{{input.input_param}}"
            }
          }
        }
      ]
    }
  }
}
```

## Common Import Issues

### Issue 1: Empty manualVariables Array
**Symptom**: Flow imports but trigger node shows `manualVariables: []`

**Cause**: Only `trigger_config` was set, not node `manualVariables`

**Fix**: Ensure BOTH locations have the manual variables defined

### Issue 2: Flow Accepts No Input
**Symptom**: Flow executes but ignores input parameters

**Cause**: Missing `trigger_config.manual_variables`

**Fix**: Add manual_variables to the trigger_config at flow level

### Issue 3: Missing Edges Handles
**Symptom**: Nodes appear disconnected in UI

**Fix**: Every edge needs:
```json
{
  "sourceHandle": "output",
  "targetHandle": "input"
}
```

## Validation Checklist

Before importing a flow, verify:

- [ ] `trigger_config.manual_variables` is defined (for backend)
- [ ] Trigger node `data.manualVariables` is defined (for UI)
- [ ] Both arrays contain the same variables
- [ ] `outputs` field maps inputs: `"var": "{{input.var}}"`
- [ ] All edges have `sourceHandle` and `targetHandle`
- [ ] Action nodes have both `appId` and `appName`
- [ ] Action nodes have both `serviceId` and `serviceName`

## File Backup Strategy

When modifying flows:
1. Create backup: `backup-files/flow-design-src/[original_name]_[timestamp].json`
2. Modify the original file in place
3. Never create duplicate enhanced versions in the same directory