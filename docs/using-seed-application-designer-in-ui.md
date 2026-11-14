# Using Seed Application Designer in IOFlow Assistant

## Quick Start Guide

The **Seed Application Designer** agent is now available in the IOFlow Assistant interface! No frontend changes were needed - it was automatically discovered.

## How to Access

### Option 1: Via Assistant Panel (Left Sidebar)
1. Open IOFlow application
2. Click on the **Assistant** icon in the left sidebar
3. Click the agent dropdown menu at the top
4. Select **"Seed Application Designer"** from the list
5. Start chatting!

### Option 2: Via IOFlow Assistant Page
1. Navigate to the **IOFlow Assistant** page
2. Click the agent selector dropdown
3. Choose **"Seed Application Designer"**
4. Begin your conversation

## What Can It Do?

The agent helps you with:

### 1. Create New Seed Applications
**Example prompts:**
- "I want to create a new application for Stripe payments API"
- "Help me create a seed application for my custom REST API"
- "Guide me through creating a new application"

### 2. Edit Existing Applications
**Example prompts:**
- "Show me all available seed applications"
- "Update the Gmail application version"
- "Add a new service to the Slack application"

### 3. Install and Configure Applications
**Example prompts:**
- "What applications can I install?"
- "Install the Gmail application for me"
- "How do I configure authentication for Salesforce?"

### 4. Debug and Test Applications
**Example prompts:**
- "My Gmail send email service is failing. Can you help?"
- "Test the authentication for my custom application"
- "Validate the schema for application X"
- "Why is my service returning an error?"

## Features

✅ **Conversational Workflow** - Guides you step-by-step
✅ **Auto-version Management** - Increments versions on updates
✅ **Schema Validation** - Validates before saving
✅ **Testing Tools** - Tests auth, services, and schemas
✅ **28 MCP Tools** - Full access to all application management capabilities

## Prerequisites

Make sure you have:
1. **AI Settings configured** (Go to Settings → AI Configuration)
2. **API Key** for your preferred AI provider (Google, OpenAI, Anthropic, etc.)
3. Appropriate permissions to manage applications

## Tips for Best Results

### Be Specific
Instead of: *"Create an app"*
Try: *"Create a seed application for Mailchimp's Email API with OAuth2 authentication"*

### Provide Context
Instead of: *"It's broken"*
Try: *"The 'send_email' service in Gmail is returning a 401 error when I try to execute it"*

### Use Natural Language
The agent understands conversational requests:
- "Can you explain what fields are required in a seed application?"
- "I'm not sure how to configure OAuth2 for my app"
- "Show me an example of a well-structured application"

## Example Workflow: Creating a New Application

```
You: I want to create a new application for Twilio SMS API

Agent: I'll help you create a Twilio SMS application. Let me gather some information...

      What authentication does Twilio use?
      - API Key
      - OAuth2
      - Basic Auth

You: API Key

Agent: Got it! What services do you want to expose?

You: I want to send SMS messages and check account balance

Agent: Perfect! For the send SMS service:
      - What's the HTTP method? (GET/POST/etc)
      - What's the endpoint URL?
      - What parameters are needed?

[... conversation continues ...]

Agent: I've created your Twilio application! Here's what I did:
      ✅ Created application definition (v1.0.0)
      ✅ Added 2 services: send_sms, get_balance
      ✅ Configured API key authentication
      ✅ Validated schema structure

      Would you like me to test the authentication?
```

## Troubleshooting

### Agent Not Showing Up?
- Refresh the agents list (click the menu → Refresh Agents)
- Reload the page
- Check that backend is running

### "Please configure your API key" Error?
- Go to Settings → AI Configuration
- Add your AI provider API key
- Save settings
- Try again

### Agent Gives Generic Responses?
- Make sure you selected "Seed Application Designer" (not another agent)
- Check that the agent has access to MCP tools
- Verify backend logs for any errors

## Technical Details

### Agent Type
- **Type**: Python module agent
- **Model**: gemini-2.5-pro (configurable via `SEED_APP_AGENT_MODEL`)
- **Tools**: 28 MCP tools via MCPToolset
- **Architecture**: Google ADK + MCP Bridge

### Location
- **Agent**: `backend/agent/seed_application_designer/agent.py`
- **Auto-discovered**: Yes (no configuration needed)
- **Endpoint**: `/api/assistant/execute`

### Available MCP Tools
The agent can use:
- **5 Exploration tools** - List, get, search applications
- **8 Management tools** - Create, edit, update applications
- **8 Testing tools** - Validate, test, debug
- **7 Deployment tools** - Install, uninstall, manage subscriptions

## Advanced Usage

### Version Management
The agent automatically increments version numbers when updating applications:
- Patch (1.0.0 → 1.0.1): Bug fixes
- Minor (1.0.0 → 1.1.0): New features
- Major (1.0.0 → 2.0.0): Breaking changes

### Schema Validation
The agent enforces correct schema structure:
- Uses `parameter_schema` (not `input_schema`)
- Uses `success_status_codes` (not `value`)
- Requires top-level `key` field
- Validates all required fields

### Multi-turn Conversations
The agent maintains context across messages:
```
You: Show me all seed applications
Agent: [Lists applications]

You: Tell me more about the Gmail one
Agent: [Shows Gmail details - remembers context]

You: Can you add a new service to it?
Agent: [Proposes changes to Gmail app]
```

## Related Documentation

- [Seed Application Designer Agent](./seed-application-designer-agent.md) - Full technical documentation
- [Seed Application Template](../backend/seed-applications/SEED_APPLICATION_TEMPLATE.md) - Schema reference
- [MCP Bridge Architecture](../backend/api/mcp_bridge.py) - Tool system details

## Support

If you encounter issues:
1. Check backend logs for detailed error messages
2. Review the [troubleshooting guide](#troubleshooting)
3. Test with simpler requests first
4. Verify your AI settings configuration

---

**🎉 Happy building with the Seed Application Designer!**
