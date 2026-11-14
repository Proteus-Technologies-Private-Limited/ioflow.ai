# API Key Authentication

IOFlow now supports API key authentication in addition to JWT tokens. This allows programmatic access to IOFlow services, including the MCP server.

## Overview

API keys provide a secure way to authenticate applications and scripts without requiring login credentials. They are particularly useful for:
- CI/CD pipelines
- Automated scripts
- Third-party integrations
- MCP server access

## Creating API Keys

### Via UI

1. Login to IOFlow
2. Navigate to Settings → API Keys
3. Click "Create API Key"
4. Fill in:
   - Name: A descriptive name for the key
   - Description: What the key will be used for
   - Scopes: Permissions (read, write, delete)
   - Expiration: Optional expiration time (max 365 days)
5. Click "Create"
6. **Important**: Copy the API key immediately - it won't be shown again!

### Via API

```bash
# First, get a JWT token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your@email.com&password=yourpassword"

# Then create an API key
curl -X POST http://localhost:8000/api/v1/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My API Key",
    "description": "For automation scripts",
    "scopes": ["read", "write"],
    "expires_in_days": 30
  }'
```

## Using API Keys

Include the API key in the Authorization header:

```bash
curl -H "Authorization: Bearer ioflow_YOUR_API_KEY" \
  http://localhost:8000/api/v1/auth/me
```

### In Python

```python
import requests

headers = {
    "Authorization": "Bearer ioflow_YOUR_API_KEY"
}

response = requests.get(
    "http://localhost:8000/api/v1/applications",
    headers=headers
)
```

### In MCP Server

Set the environment variable:
```bash
export IOFLOW_API_KEY="ioflow_YOUR_API_KEY"
```

## API Key Format

- All API keys start with `ioflow_` prefix
- Keys are 44 characters long (including prefix)
- Keys are case-sensitive

## Security Best Practices

1. **Never commit API keys to version control**
2. **Use environment variables** to store keys
3. **Rotate keys regularly** 
4. **Use minimal scopes** - only grant permissions needed
5. **Set expiration dates** when possible
6. **Monitor usage** - check the usage count and last used timestamp

## Managing API Keys

### List Your Keys
```bash
curl -H "Authorization: Bearer YOUR_API_KEY_OR_TOKEN" \
  http://localhost:8000/api/v1/api-keys
```

### Deactivate a Key
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY_OR_TOKEN" \
  http://localhost:8000/api/v1/api-keys/{key_id}/deactivate
```

### Delete a Key
```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_API_KEY_OR_TOKEN" \
  http://localhost:8000/api/v1/api-keys/{key_id}
```

## Scopes

Available scopes:
- `read` - Read-only access to resources
- `write` - Create and update resources
- `delete` - Delete resources

## Troubleshooting

### Invalid API Key Error
- Check that the key starts with `ioflow_`
- Verify the key hasn't expired
- Ensure the key is active (not deactivated)
- Confirm you're using the full key, not just the prefix

### Permission Denied
- Verify the API key has the required scopes
- Check if your user account is active

### Key Not Working
- API keys are hashed in the database - you can't retrieve them
- If lost, create a new key and delete the old one
- Check the `last_used_at` field to see if it's being used