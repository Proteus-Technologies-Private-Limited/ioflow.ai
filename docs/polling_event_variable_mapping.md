# Polling Event Variable Mapping

## Overview
Polling events now properly expose their output schema as variables in the flow designer, making them behave consistently with other application events (webhooks, API calls).

## The Problem
Previously, when a polling event was used as a trigger, subsequent nodes couldn't see the event's output variables, making it difficult to access fields like email ID, subject, sender, etc.

## The Solution
Polling events are now treated the same as API call events, with their output_schema being converted to eventVariables that are accessible throughout the flow.

## Technical Implementation

### Frontend Changes (FlowDesigner.js)

1. **Event Type Handling**: Added 'polling' to the event type check
```javascript
} else if (selectedEvent.event_type === 'api_call' || selectedEvent.event_type === 'polling') {
```

2. **Schema Processing**: Extract variables from output_schema
```javascript
if (selectedEvent.event_type === 'polling' && outputSchema.properties) {
  eventVariables = Object.entries(outputSchema.properties).map(([key, value]) => ({
    name: key,
    displayName: value.title || key.replace(/_/g, ' '),
    description: value.description || `${value.type} field from polling event`,
    type: value.type || 'string',
    required: outputSchema.required?.includes(key) || false
  }));
}
```

## Example: Gmail Polling Event

### Output Schema Definition
```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "description": "Gmail message ID"
    },
    "threadId": {
      "type": "string",
      "description": "Gmail thread ID"
    },
    "from": {
      "type": "string",
      "description": "Sender email address"
    },
    "subject": {
      "type": "string",
      "description": "Email subject"
    },
    "snippet": {
      "type": "string",
      "description": "Short preview of message text"
    },
    "hasAttachments": {
      "type": "boolean",
      "description": "Whether the email has attachments"
    }
  },
  "required": ["id", "threadId"]
}
```

### Available Variables in Flow
When this polling event is used as a trigger, the following variables become available:

| Variable | Type | Description |
|----------|------|-------------|
| `input.id` | string | Gmail message ID |
| `input.threadId` | string | Gmail thread ID |
| `input.from` | string | Sender email address |
| `input.to` | string | Recipient email address |
| `input.subject` | string | Email subject |
| `input.snippet` | string | Short preview of message |
| `input.date` | string | Date/time received |
| `input.labelIds` | array | Gmail label IDs |
| `input.hasAttachments` | boolean | Has attachments |

## Using Variables in Nodes

### Transform Node Example
```python
# Access polling event data
email_id = input.get('id')
sender = input.get('from')
subject = input.get('subject')
has_attachments = input.get('hasAttachments', False)

# Process the email
if 'urgent' in subject.lower():
    priority = 'high'
else:
    priority = 'normal'

# Output processed data
output['processed'] = {
    'message_id': email_id,
    'sender': sender,
    'subject': subject,
    'priority': priority,
    'needs_attachment_processing': has_attachments
}
```

### Condition Node Example
```javascript
// Check if email is from VIP sender
input.from && input.from.includes('@vip.company.com')

// Check if email has attachments
input.hasAttachments === true

// Check subject keywords
input.subject && input.subject.toLowerCase().includes('urgent')
```

### Action Node Parameter Mapping
When calling another service, you can map polling event data:
```json
{
  "notification_title": "{{input.subject}}",
  "notification_body": "New email from {{input.from}}",
  "message_preview": "{{input.snippet}}",
  "message_id": "{{input.id}}"
}
```

## Variable Availability

### In First Node After Trigger
- All fields from output_schema available as `input.*`
- Fields marked as required in schema shown with asterisk
- Descriptions from schema shown in autocomplete

### In Subsequent Nodes
- Original trigger data still available as `input.*`
- Previous node outputs available as `node_outputs.{node_id}.*`
- Global variables available as `global.*`

## Benefits

1. **Consistency**: Polling events work the same as other event types
2. **Discoverability**: Variables shown in autocomplete and variable picker
3. **Type Safety**: Variable types defined in schema
4. **Documentation**: Descriptions help users understand each field
5. **No Manual Configuration**: Variables automatically extracted from schema

## Testing

Run the test to verify variable mapping:
```bash
./venv/bin/python test-script/test_polling_event_variables.py
```

This will:
1. Load Gmail polling event
2. Extract output_schema
3. Show available variables
4. Demonstrate usage in transform nodes

## Migration

No migration needed - existing flows will automatically benefit from this enhancement when the frontend is updated.