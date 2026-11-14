# Polling Event UI Enhancements

## Overview
The polling event configuration UI has been enhanced to provide a user-friendly parameter form based on the selected service's schema, replacing the raw JSON editor with proper form fields.

## Key Improvements

### 1. Smart Parameter Form Rendering
- **Automatic UI Generation**: When a polling service is selected, the UI automatically renders form fields based on the service's parameter schema
- **Field Types**: Supports text inputs, numbers, booleans, arrays, and dropdowns based on schema definitions
- **Required Fields**: Clearly marks required parameters with asterisks
- **Descriptions**: Shows helpful descriptions for each parameter

### 2. Service Selection Enhancement
```
Before: Simple dropdown with service names
After:  Dropdown with service names + descriptions
        Filters to show only GET/List services suitable for polling
```

### 3. Fallback Support
- If a service lacks a parameter schema, the UI gracefully falls back to a JSON editor
- Users can still configure parameters manually when needed

### 4. Template Variable Support
The parameter form supports template variables for dynamic values:
- `{{state.last_id}}` - Last processed item ID
- `{{state.last_timestamp}}` - Last poll timestamp
- `{{flow.custom_field}}` - Custom flow parameters
- `{{variable || 'default'}}` - Default values

## Example: Gmail Polling Configuration

### Before (JSON Editor)
Users had to manually write JSON:
```json
{
  "userId": "me",
  "query": "is:unread",
  "maxResults": 50
}
```

### After (Form UI)
Users now see proper form fields:
- **userId**: Text input with default "me"
- **query**: Text input with placeholder "is:unread"
- **maxResults**: Number input (1-500)
- **labelIds**: Array field to add multiple labels
- **includeSpamTrash**: Checkbox for boolean value

## Technical Implementation

### Frontend Changes
1. **ApplicationDetails.js**: 
   - Imports ParameterForm component
   - Detects selected service's schema
   - Renders ParameterForm when schema available
   - Falls back to JSON textarea when no schema

2. **Field Name Fix**:
   - Changed `polling_interval` to `interval_seconds`
   - Maintains backward compatibility

### Code Structure
```javascript
// Detect service and schema
const selectedService = services.find(s => 
  s.service_name === formData.event_configuration?.polling_service
);
const parameterSchema = selectedService?.parameter_schema;

// Render appropriate UI
if (parameterSchema) {
  return <ParameterForm 
    inputSchema={parameterSchema}
    parameters={polling_parameters}
    onParametersChange={handleChange}
  />;
} else {
  return <textarea ... />; // Fallback
}
```

## Benefits

### For Users
- **Intuitive Configuration**: No need to write JSON manually
- **Validation**: Form validates input types automatically
- **Discovery**: Users can see all available parameters
- **Help Text**: Each field shows its purpose

### For Developers
- **Consistency**: Same parameter form used in flow designer
- **Maintainability**: Schema-driven UI updates automatically
- **Extensibility**: Easy to add new parameter types

## Testing

Run the test script to verify:
```bash
./venv/bin/python test-script/test_polling_ui_enhancement.py
```

Expected results:
- ✅ Service dropdown filters polling-suitable services
- ✅ Parameter form renders based on schema
- ✅ Fallback to JSON editor when needed
- ✅ Template variables supported
- ✅ interval_seconds properly handled

## Migration Guide

### For Existing Polling Events
No migration needed - the UI handles both old and new field names:
- Reads both `polling_interval` and `interval_seconds`
- Saves as `interval_seconds` going forward

### For New Implementations
Always use `interval_seconds` in seed applications:
```json
{
  "event_type": "polling",
  "event_configuration": {
    "interval_seconds": 300,  // Not polling_interval
    "polling_service": "Service Name",
    "polling_parameters": { ... }
  }
}
```

## Future Enhancements
- Add parameter validation rules from schema
- Support conditional parameters
- Add parameter presets/templates
- Visual parameter mapping builder