# Seed Applications Script

The `seed_applications.py` script has been updated to preserve existing application configurations by default.

## Changes Made

1. **Interactive Mode** (default): When running the script without arguments, it will:
   - Check for existing global applications
   - Ask if you want to preserve them
   - Only add missing applications if you choose to preserve

2. **Command Line Options**:
   ```bash
   # Preserve existing applications (non-interactive)
   python seed_applications.py --preserve
   
   # Replace all applications (non-interactive)
   python seed_applications.py --replace
   
   # Specify custom database path
   python seed_applications.py --db-path /path/to/database.db
   ```

3. **Preservation Logic**:
   - When preserving, the script will:
     - Skip existing applications
     - Skip existing events for those applications
     - Skip existing services for those applications
   - Only new applications/events/services will be added

## Viewing Error Handling in the UI

IOFlow now includes a comprehensive UI for viewing service error handling configurations:

1. **Service Detail Modal**: Click the info icon (ℹ️) next to any service in the Application Details page
2. **Error Handling Tab**: View detailed error configurations including:
   - Response configuration with success/error field mappings
   - Common error codes and their descriptions
   - Retry configuration with backoff strategies
   - Success and error response schemas
3. **Interactive Display**: Expandable sections for easy navigation
4. **Raw Configuration View**: See the complete service configuration in JSON format

### How to Access:
1. Navigate to Applications page
2. Click on any application (e.g., Slack)
3. Go to the "Services" tab
4. Click the green info icon (ℹ️) next to any service
5. Select the "Error Handling" tab in the modal

## Slack Application Configuration

The seed script includes the following Slack configuration:

### OAuth Settings:
- Authorization URL: `https://slack.com/oauth/v2/authorize`
- Token URL: `https://slack.com/api/oauth.v2.access`
- Scopes: `channels:read`, `channels:write.invites`, `channels:write.topic`, `chat:write`, `users:read`

### Webhook Configuration:
- Verification method: HMAC
- Signature header: `X-Slack-Signature`
- Algorithm: SHA256
- Timestamp header: `X-Slack-Request-Timestamp`

### Events:
1. **new_message**: Triggers when a new message is posted to a channel
2. **new_channel**: Triggers when a new channel is created

### Services:
1. **send_message**: Send a message to a Slack channel
   - Parameters stored in `service_config` field:
     - **channel** (required): Channel ID or name (e.g., #general or C1234567890)
     - **text** (required): The message content (up to 40,000 characters)
     - **thread_ts** (optional): Thread timestamp for replying in a thread
   - Parameter method: `json_payload`
   - **Error Handling**: Comprehensive error schema with common Slack API errors
   - **Retry Configuration**: Automatic retry for rate limiting with exponential backoff
   - **Success Response**: Returns message timestamp and channel info

2. **get_channel_info**: Get information about a Slack channel
   - Parameters:
     - **channel** (required): Channel ID (e.g., C1234567890)
   - Parameter method: `query_params`
   - Returns channel details including name, privacy settings, topic, and purpose

3. **list_channels**: List all channels in a Slack workspace
   - Parameters:
     - **types** (optional): Channel types filter (default: public_channel)
     - **limit** (optional): Maximum channels to return (1-1000, default: 100)
   - Parameter method: `query_params`
   - Returns array of channels with basic information

### Error Handling Features:
- **Common Error Codes**: Predefined error messages for typical Slack API errors
- **Error Schema**: Structured error response parsing
- **Retry Logic**: Automatic retry for rate-limited requests
- **Response Validation**: Checks `ok` field for success/failure

## Usage Examples

```bash
# Run interactively (will ask about preserving)
python backend/seed_applications.py

# Always preserve existing applications
python backend/seed_applications.py --preserve

# Always replace existing applications
python backend/seed_applications.py --replace
```

This ensures that any manual parameter definitions you've added to the Slack application won't be overwritten when running the seed script.