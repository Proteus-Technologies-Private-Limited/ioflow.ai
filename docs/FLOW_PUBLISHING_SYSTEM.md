# Flow Publishing System

## Quick Start

The Flow Publishing System allows you to convert any flow into a reusable application that works exactly like seed applications, with automatic parameter mapping and transformation capabilities.

### Basic Usage

1. **Design your flow** using the IOFlow flow designer
2. **Publish the flow** as an application
3. **Use the published application** in other flows as a service

### Example

```bash
# 1. Preview what will be generated
curl -X GET "http://localhost:7001/api/v1/flow-publishing/preview?flow_id=my-flow-123&app_key=my_app"

# 2. Publish the flow
curl -X POST "http://localhost:7001/api/v1/flow-publishing/publish" \
  -H "Content-Type: application/json" \
  -d '{
    "flow_id": "my-flow-123",
    "app_key": "my_custom_app",
    "app_name": "My Custom Application",
    "description": "Auto-generated from my flow"
  }'

# 3. List published applications
curl -X GET "http://localhost:7001/api/v1/flow-publishing/applications"
```

## Key Features

- ✅ **Automatic Analysis**: Extracts flow structure and parameters
- ✅ **Seed Application Generation**: Creates standard IOFlow applications
- ✅ **Parameter Mapping**: Maps flow variables to service parameters
- ✅ **Execution Bridge**: Seamlessly executes flows as services
- ✅ **Version Management**: Tracks versions and handles updates
- ✅ **Dependency Tracking**: Manages application dependencies

## System Components

### Core Services

| Component | Purpose | Location |
|-----------|---------|----------|
| FlowAnalyzer | Extracts flow metadata | `backend/services/flow_analyzer.py` |
| ApplicationGenerator | Converts to seed apps | `backend/services/application_generator.py` |
| FlowPublisher | Orchestrates publishing | `backend/services/flow_publisher.py` |
| ParameterMapper | Handles parameter mapping | `backend/services/parameter_mapper.py` |
| FlowExecutionBridge | Bridges app calls to flows | `backend/services/flow_execution_bridge.py` |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/api/v1/flow-publishing/preview` | GET | Preview publishing result |
| `/api/v1/flow-publishing/publish` | POST | Publish flow as application |
| `/api/v1/flow-publishing/applications` | GET | List published applications |
| `/api/v1/flow-publishing/applications/{id}` | GET | Get application details |
| `/api/v1/flow-publishing/applications/{id}/update` | PUT | Update published application |

### Database Tables

| Table | Purpose |
|-------|---------|
| `published_applications` | Main published app records |
| `published_application_versions` | Version history |
| `parameter_mappings` | Parameter mapping configurations |
| `flow_application_dependencies` | Dependency tracking |
| `flow_execution_bridges` | Execution bridge records |

## Installation

The flow publishing system is integrated into IOFlow. To set it up:

1. **Run database migrations**:
   ```bash
   sqlite3 ioflow.db < backend/migrations/add_published_applications_tables.sql
   ```

2. **Restart the backend** to load the new API endpoints

3. **Test the system**:
   ```bash
   python3 test-script/test_flow_publishing_core.py
   ```

## Usage Examples

### Publishing a Simple Flow

```python
# Example flow that validates email addresses
flow_definition = {
    "flow_name": "Email Validator",
    "trigger_config": {
        "type": "manual",
        "manual_variables": [
            {
                "name": "email",
                "type": "string", 
                "required": True,
                "description": "Email address to validate"
            }
        ]
    },
    "flow_definition": {
        "nodes": [
            {
                "id": "trigger-1",
                "type": "trigger"
            },
            {
                "id": "transform-1", 
                "type": "transform",
                "data": {
                    "code": """
import re
email = input.get('email', '')
is_valid = bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))
output['is_valid'] = is_valid
output['normalized_email'] = email.lower() if is_valid else ''
"""
                }
            }
        ]
    }
}

# This becomes a reusable "Email Validator App" that can be called from other flows
```

### Using Published Applications

Once published, applications can be used in flows like any other service:

```javascript
// Action node in another flow
{
  "id": "validate-email",
  "type": "action", 
  "data": {
    "selectedApp": "email_validator_app",
    "selectedService": "execute_email_validator",
    "parameters": {
      "email": "{{input.customerEmail}}"
    }
  }
}
```

## Testing

Run the test suite to verify everything works:

```bash
# Test core components
python3 test-script/test_flow_publishing_core.py

# Test results are saved to:
# test-script/flow_publishing_test_results/
```

Expected output:
```
🚀 Flow Publishing Core Components Test
✓ Flow Analysis: 6 params, 20 complexity  
✓ Application Generation: 2 services, 0 events
✓ Parameter Mapping: Success
The flow publishing core system is working correctly! 🚀
```

## Configuration

### Environment Variables

```bash
# Enable flow publishing features
FLOW_PUBLISHING_ENABLED=true

# Default timeout for flow execution
FLOW_EXECUTION_TIMEOUT=30

# Maximum complexity score for publishable flows  
MAX_FLOW_COMPLEXITY=100
```

### Settings in `core/config.py`

```python
# Flow publishing settings
FLOW_PUBLISHING_ENABLED = True
MAX_PUBLISHED_APPS_PER_USER = 50
FLOW_EXECUTION_TIMEOUT_SECONDS = 30
AUTO_UPDATE_CHECK_INTERVAL = 3600  # 1 hour
```

## Architecture Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Flow Designer │    │   Flow Publisher │    │  Seed App Store │
│                 │───▶│                  │───▶│                 │
│  Design Flow    │    │  Analyze & Gen   │    │  Published Apps │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        │
                       ┌──────────────────┐             │
                       │ Parameter Mapper │             │
                       │                  │             │
                       │ Map Variables    │             │
                       └──────────────────┘             │
                                │                        │
                                ▼                        │
                       ┌──────────────────┐             │
                       │ Execution Bridge │◀────────────┘
                       │                  │
                       │ Execute Flow     │
                       └──────────────────┘
```

## Troubleshooting

### Common Issues

1. **"Flow not found" error**
   - Verify the flow exists and is accessible
   - Check flow permissions

2. **"Parameter mapping failed"**
   - Review parameter names and types
   - Check variable paths in transformations

3. **"Execution timeout"**
   - Increase timeout settings
   - Optimize flow performance

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('services.flow_publisher').setLevel(logging.DEBUG)
```

### Health Check

Verify system health:

```bash
curl http://localhost:7001/api/v1/flow-publishing/statistics
```

## Performance

### Benchmarks

- Flow analysis: ~100ms for typical flows
- Application generation: ~200ms 
- Parameter mapping: ~50ms
- Total publishing time: ~500ms for simple flows

### Optimization Tips

1. **Minimize flow complexity** - Keep flows focused and simple
2. **Optimize transformations** - Efficient Python code in transform nodes
3. **Use caching** - Leverage global variables for repeated data
4. **Async execution** - Use async mode for long-running flows

## Security

### Access Control

- Only authenticated users can publish flows
- Published applications inherit flow permissions
- Tenant isolation is maintained

### Data Privacy

- Flow analysis data is encrypted at rest
- Execution logs follow retention policies
- No sensitive data in parameter mappings

## Roadmap

### Version 1.1 (Current)
- ✅ Core publishing system
- ✅ Parameter mapping
- ✅ Execution bridge
- ✅ Version management

### Version 1.2 (Planned)
- 🔄 Visual parameter mapping UI
- 🔄 Advanced transformation types
- 🔄 Performance analytics
- 🔄 Application marketplace

### Version 1.3 (Future)
- 📋 Bulk operations
- 📋 Export/import functionality
- 📋 Webhook notifications
- 📋 Template gallery

## Contributing

To contribute to the flow publishing system:

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/flow-publishing-enhancement`
3. **Add tests**: Update `test-script/test_flow_publishing_core.py`
4. **Submit pull request**: Include test results and documentation

### Development Setup

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run tests
python3 test-script/test_flow_publishing_core.py

# Start development server
./start_backend.sh
```

## Support

For help with the flow publishing system:

- 📖 **Documentation**: `/docs/flow-to-application-publishing-guide.md`
- 🐛 **Issues**: GitHub issues with `flow-publishing` label
- 💬 **Discussions**: GitHub discussions for questions
- 📧 **Contact**: IOFlow development team

## License

This feature is part of IOFlow and follows the same license terms.

---

**Happy Flow Publishing! 🚀**