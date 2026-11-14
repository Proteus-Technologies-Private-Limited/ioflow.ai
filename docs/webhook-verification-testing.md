# Testing Webhook Verification in IOFlow

This guide covers how to test the webhook verification implementation for various providers.

## Overview

IOFlow now supports multiple webhook verification methods:

1. **HMAC Signature Verification** - Used by Slack, GitHub, Stripe, etc.
2. **URL Challenge Verification** - Used by Slack for initial setup
3. **Token Verification** - Simple API key/token verification
4. **No Verification** - For development/testing

## Testing Slack Integration

### Prerequisites

1. Create a Slack application in your Slack workspace
2. Set up OAuth2 credentials in IOFlow
3. Subscribe to the Slack application in IOFlow
4. Add webhook signing secret to your subscription

### Step 1: Set Up Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Create a new app or select existing one
3. Go to "Basic Information" → "App Credentials"
4. Copy the "Signing Secret"

### Step 2: Configure IOFlow Subscription

1. Login to IOFlow
2. Go to Applications → Slack
3. Click "Connect" and add your OAuth2 credentials:
   - Client ID: Your Slack app's Client ID
   - Client Secret: Your Slack app's Client Secret
   - Signing Secret: Your Slack app's Signing Secret

### Step 3: Test Webhook Verification

#### Using the Test Script

```bash
cd backend
python test_webhook_verification.py
```

#### Manual Testing with cURL

1. **Test URL Challenge**:
```bash
curl -X POST http://localhost:8000/webhook/slack/channel.message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_SUBSCRIPTION_API_KEY" \
  -d '{
    "token": "test_token",
    "challenge": "test_challenge_123",
    "type": "url_verification"
  }'
```

Expected response:
```json
{"challenge": "test_challenge_123"}
```

2. **Test HMAC Verification**:

First, generate a valid signature:
```python
import hmac
import hashlib
import time
import json

signing_secret = "YOUR_SIGNING_SECRET"
timestamp = str(int(time.time()))
payload = {"event": {"type": "message", "text": "Hello"}}
body = json.dumps(payload, separators=(',', ':'))

sig_basestring = f"v0:{timestamp}:{body}"
signature = 'v0=' + hmac.new(
    signing_secret.encode(),
    sig_basestring.encode(),
    hashlib.sha256
).hexdigest()

print(f"Timestamp: {timestamp}")
print(f"Signature: {signature}")
```

Then send the request:
```bash
curl -X POST http://localhost:8000/webhook/slack/channel.message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_SUBSCRIPTION_API_KEY" \
  -H "X-Slack-Signature: YOUR_SIGNATURE" \
  -H "X-Slack-Request-Timestamp: YOUR_TIMESTAMP" \
  -d '{"event":{"type":"message","text":"Hello"}}'
```

### Step 4: Configure Slack Event Subscriptions

1. In your Slack app settings, go to "Event Subscriptions"
2. Enable events
3. Set Request URL to: `https://your-domain.com/webhook/slack/channel.message`
4. Add bot event subscriptions:
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `message.mpim`

### Step 5: Test Real Events

1. Add your Slack bot to a channel
2. Send a message in the channel
3. Check IOFlow logs for webhook processing

## Testing GitHub Integration

### GitHub Webhook Setup

1. Go to your repository settings → Webhooks
2. Add webhook URL: `https://your-domain.com/webhook/github/push`
3. Content type: `application/json`
4. Secret: Generate a secure secret and save it
5. Add the same secret to your IOFlow GitHub subscription

### Test with GitHub CLI

```bash
# Generate signature
PAYLOAD='{"ref":"refs/heads/main","commits":[]}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "YOUR_SECRET" | sed 's/^.* //')

# Send request
curl -X POST http://localhost:8000/webhook/github/push \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_SUBSCRIPTION_API_KEY" \
  -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

## Verification Methods by Provider

| Provider | Method | Signature Header | Algorithm | Format |
|----------|--------|------------------|-----------|---------|
| Slack | HMAC | X-Slack-Signature | SHA256 | v0={hash} |
| GitHub | HMAC | X-Hub-Signature-256 | SHA256 | sha256={hash} |
| Stripe | HMAC | Stripe-Signature | SHA256 | t={ts},v1={hash} |
| Shopify | HMAC | X-Shopify-Hmac-Sha256 | SHA256 | base64({hash}) |
| Twilio | HMAC | X-Twilio-Signature | SHA1 | {hash} |
| SendGrid | HMAC | X-Twilio-Email-Event-Webhook-Signature | SHA256 | {hash} |

## Common Issues and Solutions

### 1. Signature Verification Fails

**Symptoms**: 401 Unauthorized with "Invalid webhook signature"

**Causes**:
- Wrong signing secret
- Body encoding issues
- Timestamp too old (> 5 minutes)

**Solution**:
- Verify signing secret matches provider's secret
- Ensure body is raw bytes, not parsed JSON
- Check server time synchronization

### 2. URL Challenge Fails

**Symptoms**: Slack shows "Your URL didn't respond with the challenge value"

**Causes**:
- Webhook verification not enabled
- Wrong response format

**Solution**:
- Ensure `url_verification_enabled: true` in webhook config
- Return only `{"challenge": "value"}` for challenge requests

### 3. Missing Headers

**Symptoms**: 401 with "Missing required headers"

**Causes**:
- Provider not sending expected headers
- Proxy stripping headers

**Solution**:
- Check webhook config for correct header names
- Ensure reverse proxy forwards all headers

## Security Best Practices

1. **Always use HTTPS** for webhook endpoints
2. **Rotate signing secrets** periodically
3. **Log verification failures** for security monitoring
4. **Implement rate limiting** to prevent abuse
5. **Validate timestamp** to prevent replay attacks
6. **Store secrets encrypted** in the database

## Debugging Tips

1. **Enable debug logging**:
```python
# In webhook_handler.py
logger.debug(f"Headers: {dict(request.headers)}")
logger.debug(f"Body: {body[:100]}...")  # First 100 chars
```

2. **Test with ngrok** for local development:
```bash
ngrok http 8000
# Use the HTTPS URL for webhook configuration
```

3. **Verify signature manually**:
```python
# Use the test script functions to verify signatures
python -c "from test_webhook_verification import *; test_slack_webhook_verification()"
```

## Next Steps

1. Monitor webhook success/failure rates
2. Set up alerts for verification failures
3. Implement webhook retry logic
4. Add webhook event logging
5. Create provider-specific documentation