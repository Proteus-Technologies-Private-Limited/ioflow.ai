# Polling Parameter Mapping Guide

## Overview
The generic polling system supports sophisticated parameter mapping to handle various API requirements. Parameters can be configured at three levels with increasing precedence.

## Three-Layer Parameter System

### Layer 1: Event Default Parameters (Seed Application)
Defined in the seed application's event configuration. These are the baseline parameters.

```json
{
  "event_configuration": {
    "polling_service": "List Messages",
    "polling_parameters": {
      "userId": "me",
      "query": "is:unread",
      "maxResults": 50
    }
  }
}
```

### Layer 2: Flow-Specific Overrides
Configured in the flow's trigger configuration. These override event defaults.

```json
{
  "trigger_config": {
    "type": "application_event",
    "polling_overrides": {
      "query": "from:vip@company.com",
      "maxResults": 10
    }
  }
}
```

### Layer 3: Dynamic Runtime Parameters
Automatically added by the system based on state and context.

## Template Variables

Parameters support template variables using `{{variable}}` syntax:

### Available Variables

1. **State Variables** - From previous polling state
   - `{{state.last_id}}` - Last processed item ID
   - `{{state.last_timestamp}}` - Last poll timestamp
   - `{{state.custom_field}}` - Any custom state field

2. **Flow Variables** - From flow configuration
   - `{{flow.id}}` - Flow ID
   - `{{flow.name}}` - Flow name
   - `{{flow.custom_param}}` - Custom flow parameters

3. **System Variables** - Automatic values
   - `{{last_poll}}` - ISO timestamp of last poll

### Template Features

#### Optional Chaining
Use `?` for safe navigation:
```json
{
  "folder": "{{user?.preferences?.email_folder}}"
}
```

#### Default Values
Use `||` for fallback values:
```json
{
  "query": "{{state.custom_query || 'is:unread'}}",
  "folder": "{{flow.folder || 'INBOX'}}"
}
```

## Practical Examples

### Example 1: Gmail with Department Filtering

```json
{
  "flow_name": "Finance Email Monitor",
  "trigger_config": {
    "type": "application_event",
    "polling_overrides": {
      "query": "from:*@finance.company.com OR label:finance",
      "maxResults": 25,
      "labelIds": ["FINANCE", "IMPORTANT"]
    }
  }
}
```

### Example 2: GitHub Issues with Pagination

```json
{
  "event_configuration": {
    "polling_service": "List Issues",
    "polling_parameters": {
      "state": "open",
      "per_page": 30,
      "page": "{{state.next_page || 1}}",
      "since": "{{state.last_check}}"
    },
    "parameter_mapping": {
      "state_fields": {
        "page": "next_page",
        "since": "last_timestamp"
      }
    }
  }
}
```

### Example 3: Slack Messages with Channel Override

```json
{
  "trigger_config": {
    "polling_overrides": {
      "channel": "#alerts",
      "oldest": "{{state.last_message_ts}}",
      "limit": 100
    }
  }
}
```

### Example 4: Database Query with Dynamic Filters

```json
{
  "polling_parameters": {
    "query": "SELECT * FROM orders WHERE created_at > :since_date",
    "params": {
      "since_date": "{{state.last_poll_timestamp || '2024-01-01'}}"
    }
  }
}
```

### Example 5: Weather API with Location

```json
{
  "polling_overrides": {
    "location": "{{flow.city || 'New York'}}",
    "units": "{{flow.units || 'metric'}}",
    "include": ["current", "alerts"]
  }
}
```

## Advanced Parameter Mapping

### Using parameter_mapping Configuration

Define how parameters should be mapped from state:

```json
{
  "event_configuration": {
    "parameter_mapping": {
      "state_fields": {
        "since_id": "last_tweet_id",
        "max_id": "oldest_tweet_id"
      },
      "computed_fields": {
        "timestamp": "current_timestamp",
        "flow_ref": "flow_id"
      }
    }
  }
}
```

## API-Specific Examples

### Twitter/X Timeline
```json
{
  "polling_overrides": {
    "count": 50,
    "since_id": "{{state.last_tweet_id}}",
    "exclude_replies": true,
    "include_rts": false
  }
}
```

### Stripe Payments
```json
{
  "polling_overrides": {
    "limit": 100,
    "starting_after": "{{state.last_payment_id}}",
    "status": "succeeded",
    "created": {
      "gte": "{{state.last_poll_timestamp}}"
    }
  }
}
```

### Shopify Orders
```json
{
  "polling_overrides": {
    "status": "any",
    "created_at_min": "{{state.last_check}}",
    "limit": 250,
    "fields": "id,email,total_price,created_at"
  }
}
```

### RSS Feed
```json
{
  "polling_overrides": {
    "url": "{{flow.feed_url}}",
    "since": "{{state.last_guid}}",
    "max_items": 20
  }
}
```

## Best Practices

1. **Use Specific Queries**: Override with specific filters to reduce data transfer
2. **Set Appropriate Limits**: Override `maxResults`/`limit` based on expected volume
3. **Leverage State**: Use state variables to avoid reprocessing
4. **Provide Defaults**: Always use `||` operator for critical parameters
5. **Test Overrides**: Use the `/api/v1/polling/test` endpoint to validate

## Debugging

To see final resolved parameters, check the logs:
```
DEBUG: Final polling parameters: {
  "userId": "me",
  "query": "from:vip@company.com",
  "maxResults": 10,
  "since": "2024-01-15T10:30:00Z",
  "after_id": "msg_12345"
}
```

## Migration from Static Parameters

If you have existing flows with static parameters, migrate them to use overrides:

**Before:**
```json
{
  "event_configuration": {
    "polling_parameters": {
      "query": "label:important"
    }
  }
}
```

**After:**
```json
{
  "trigger_config": {
    "polling_overrides": {
      "query": "label:important AND is:unread"
    }
  }
}
```

This allows different flows to use the same event with different parameters!