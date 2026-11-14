# Weaviate GraphQL Integration - Complete Solution

## Problem Summary
1. **Content-Type Issue**: Fixed - now sends `application/json`
2. **Query Format Issue**: Weaviate expects `{"query": "...GraphQL..."}` but IOFlow was sending raw parameters

## Complete Solution Implemented

### 1. Service Executor Fix (service_executors.py)
- Added support for `request_config.headers` 
- Handles `parameter_method: "body"` and `"none"` to respect Content-Type
- Now correctly sends JSON with `Content-Type: application/json`

### 2. Service Configuration Update
Updated `vector_search` service to accept GraphQL query strings:
```json
{
  "parameter_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "GraphQL query string"
      }
    },
    "required": ["query"]
  },
  "parameter_method": "body"
}
```

### 3. Flow with Query Builder
Created "Weaviate GraphQL Search" flow with:
- **Trigger Node**: Accepts search text and limit
- **Transform Node**: Builds properly formatted GraphQL query
- **Action Node**: Sends query to Weaviate
- **Response Node**: Returns results

## How the Transform Node Works
```python
# Builds the GraphQL query string
graphql_query = '''
{
  Get {
    IOFlowData(
      nearText: {
        concepts: ["%s"]
        certainty: 0.7
      }
      limit: %d
    ) {
      source
      type
      title
      content
      priority
      tags
      _additional {
        id
        certainty
        distance
      }
    }
  }
}
''' % (search_text, limit)

output = {"query": graphql_query}
```

## Testing Results
✅ Flow executes successfully
✅ Sends proper `Content-Type: application/json`
✅ Query is properly formatted for Weaviate GraphQL
✅ Returns search results from Weaviate

## Files Modified
1. `/backend/services/service_executors.py` - Fixed header handling
2. Database: `application_services` table - Updated vector_search service
3. Created flow: "Weaviate GraphQL Search" - Properly constructs queries

## Usage
1. Open IOFlow UI
2. Navigate to "Weaviate GraphQL Search" flow
3. Enter search text and limit
4. Execute to search Weaviate vector database

The integration now works correctly with Weaviate's GraphQL endpoint!