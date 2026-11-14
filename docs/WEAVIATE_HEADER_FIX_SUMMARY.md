# Weaviate Content-Type Header Fix Summary

## Problem
The IOFlow execution engine was sending `application/x-www-form-urlencoded` as the Content-Type header for Weaviate GraphQL requests, even though the seed application correctly specified `application/json` in the service configuration.

## Root Cause
The issue was in `/backend/services/service_executors.py`:

1. **Missing Headers Support**: The code only processed `headers_template` but not direct `headers` from `request_config`
2. **Incorrect Logic**: The logic for determining when to send JSON didn't properly check the Content-Type header from the service configuration
3. **Header Override**: Even when headers were set, the code would override them with form-urlencoded

## Solution Implemented

### 1. Added Direct Headers Support (Line 621)
```python
# First, add direct headers from request_config if present
if request_config.get('headers') and not is_internal_flow_call:
    logger.info(f"Adding direct headers from request_config: {mask_sensitive_data(request_config['headers'])}")
    headers.update(request_config['headers'])
```

### 2. Improved JSON Detection Logic (Lines 788-805)
```python
# Added support for 'graphql' and 'body' parameter methods
if parameter_method in ['json_payload', 'hybrid', 'graphql']:
    send_as_json = True
elif parameter_method == 'body':
    # For 'body' parameter method, check Content-Type header
    send_as_json = headers.get('Content-Type') == 'application/json'
# ... 
else:
    # Check headers first, then response_type
    send_as_json = (
        headers.get('Content-Type') == 'application/json' or
        config.get('response_type') == 'json'
    )
```

### 3. Fixed Header Override Issue (Lines 991-995)
```python
# Only set Content-Type for form-encoded data if not already set
# This respects headers from request_config
if 'Content-Type' not in headers:
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
```

## Files Modified
- `/backend/services/service_executors.py` - Fixed header handling logic
- Backup created at: `backup-files/backend/services/service_executors.py.[timestamp]`

## Testing
1. **Service Configuration Verified**: 
   - Weaviate service correctly has `Content-Type: application/json` in request_config.headers
   
2. **Flow Execution Tested**:
   - Weaviate flows now execute successfully
   - GraphQL queries are sent with correct Content-Type header

3. **Test Scripts Created**:
   - `test-script/test_weaviate_header_fix.py` - Comprehensive test
   - `test-script/test_simple_weaviate.py` - Simple execution test
   - `test-script/check_weaviate_logs.py` - Log verification

## Impact
This fix ensures that:
- All services that specify headers in `request_config` will have them respected
- GraphQL services (like Weaviate) will properly send JSON content
- The execution engine no longer incorrectly overrides Content-Type headers
- Better support for various parameter methods including 'graphql' and 'body'

## Verification
Run the following to verify the fix:
```bash
# Check service configuration
python3 test-script/check_weaviate_logs.py

# Test flow execution
source venv/bin/activate
python3 test-script/test_simple_weaviate.py
```

The flow should execute successfully with the correct Content-Type header.