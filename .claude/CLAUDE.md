# IOFlow Backend - Important Information for Claude

## Seed Applications

Seed applications are maintained in JSON files located in `/backend/seed-applications/`. These files define pre-configured applications and their services that can be loaded into the system.

### CRITICAL: Seed Application Structure

**Every seed application MUST follow this exact structure:**

```json
{
  "key": "unique_key",
  "application": {
    // Application configuration
  },
  "events": [],
  "services": []
}
```

### Key Points:
1. **Location**: All seed application JSON files are in `/backend/seed-applications/`
2. **Loading**: Seed applications are loaded by calling the appropriate API endpoint
3. **Required Structure**: 
   - **MUST have `key`** field at top level (unique identifier)
   - **MUST have `application`** object containing app metadata
   - **MUST have `services`** array with service definitions
   - **MAY have `events`** array with webhook event definitions
4. **Documentation**: See `/backend/seed-applications/SEED_APPLICATION_TEMPLATE.md` for the complete template
5. **Structure Guide**: See `/backend/docs/seed-application-json-structure.md` for detailed JSON structure documentation
6. **IMPORTANT**: Use `parameter_schema` NOT `input_schema` for defining service arguments

### Response Configuration

When configuring API services that need to treat certain HTTP error codes as successful responses, use the `response_config` structure:

```json
"response_config": {
  "success_check": {
    "type": "status_code",
    "success_status_codes": [200, 400, 404]  // Use 'success_status_codes', not 'value'
  },
  "error_extraction": {
    "error_field": "error.code",
    "message_field": "error.message"
  }
}
```

**Important**: The field name is `success_status_codes`, not `value`. This allows services to treat specific HTTP status codes (like 400) as successful responses instead of errors.

### Example: Atlas Core Application

The Atlas Core application (`/backend/seed-applications/atlascore.json`) demonstrates how to configure services that need custom success status codes. For example, the PAN Verification service treats both 200 and 400 as successful responses because a 400 response with "PAN is invalid" is a valid business response, not an error.

## Service Configuration Updates

When updating service configurations through the UI:
1. The `response_config` field must be properly serialized/deserialized
2. The ServiceUpdate model includes the `response_config` field
3. The backend properly handles this field in the update endpoint

## Running and Testing

After modifying seed application JSON files:
1. The changes need to be reloaded by calling the seed API endpoint
2. Existing services may need to be updated or recreated to pick up the new configuration
3. Test flows to ensure the custom status codes are being respected
- when an enhanced version of file created do not create new file, always make changes in existing file. Keep backup of the file in a backup-files folder with the current path structure of the file.
- all migration scripts should be created in migrations folder in project root