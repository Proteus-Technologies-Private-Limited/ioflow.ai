"""
JSON Schema Validator for Seed Applications

Provides comprehensive schema validation for seed application JSON files.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from jsonschema import validate, ValidationError, Draft7Validator

logger = logging.getLogger(__name__)

class SchemaValidator:
    """Validates seed application JSON against defined schemas"""
    
    def __init__(self):
        self.application_schema = self._get_application_schema()
        self.service_schema = self._get_service_schema_definition()  # Use the correct schema
        self.event_schema = self._get_event_schema()
        self.parameter_schema = self._get_parameter_schema()
        # Create validators for reuse
        self.app_validator = Draft7Validator(self.application_schema)
        self.service_validator = Draft7Validator(self.service_schema)
        self.event_validator = Draft7Validator(self.event_schema)
    
    def validate_seed_application(self, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate complete seed application structure.
        
        Args:
            app_data: Seed application JSON data
            
        Returns:
            Validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "schema_version": "1.0"
        }
        
        # Validate against main schema and collect ALL errors
        schema_errors = list(self.app_validator.iter_errors(app_data))
        
        # Add all schema validation errors
        for error in schema_errors:
            results["valid"] = False
            error_msg = self._format_validation_error(error)
            results["errors"].append({
                "path": list(error.path),
                "message": error_msg,
                "schema_path": list(error.schema_path)
            })
        
        # Always validate individual services and events to collect all errors
        # The main schema validation handles the array structure, but we need
        # to validate each item individually
        self._validate_all_services(app_data, results)
        self._validate_all_events(app_data, results)
        
        # Run additional validations even if there are schema errors
        # This helps users fix everything in one go
        self._validate_unique_names(app_data, results)
        self._validate_auth_config(app_data, results)
        self._validate_service_configurations(app_data, results)
        self._validate_event_configurations(app_data, results)
        self._validate_parameter_schemas(app_data, results)
        self._validate_json_string_fields(app_data, results)
        
        return results
    
    def _validate_all_services(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate all services individually to collect all errors"""
        services = app_data.get("services", [])
        for i, service in enumerate(services):
            service_errors = list(self.service_validator.iter_errors(service))
            for error in service_errors:
                results["valid"] = False
                error_msg = self._format_validation_error(error)
                # Prepend service index to path
                full_path = ["services", i] + list(error.path)
                results["errors"].append({
                    "path": full_path,
                    "message": error_msg,
                    "schema_path": list(error.schema_path)
                })
    
    def _validate_all_events(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate all events individually to collect all errors"""
        events = app_data.get("events", [])
        for i, event in enumerate(events):
            event_errors = list(self.event_validator.iter_errors(event))
            for error in event_errors:
                results["valid"] = False
                error_msg = self._format_validation_error(error)
                # Prepend event index to path
                full_path = ["events", i] + list(error.path)
                results["errors"].append({
                    "path": full_path,
                    "message": error_msg,
                    "schema_path": list(error.schema_path)
                })
    
    def _get_application_schema(self) -> Dict[str, Any]:
        """Get the main application schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["key", "application"],
            "properties": {
                "key": {
                    "type": "string",
                    "pattern": "^[a-z0-9_]+$",
                    "description": "Unique application identifier"
                },
                "application": {
                    "type": "object",
                    "required": ["app_name", "app_type", "category", "auth_type", "version"],
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "minLength": 1
                        },
                        "app_type": {
                            "type": "string",
                            "enum": ["database", "email", "api", "file_system", "memory", "flow", "ai_agent", "ssh", "mqtt"]
                        },
                        "app_scope": {
                            "type": "string",
                            "enum": ["global", "tenant", "user"]
                        },
                        "description": {
                            "type": "string"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["AI/ML", "Communication", "Productivity", "Analytics", "Database", "Integration", "Development", "API Platform", "Email", "Messaging", "Automation", "Data Extraction", "Other"]
                        },
                        "auth_type": {
                            "type": "string",
                            "enum": ["none", "api_key", "oauth2", "basic", "token_exchange", "custom"]
                        },
                        "auth_config": {
                            "type": "object"
                        },
                        "version": {
                            "type": "string",
                            "pattern": "^\\d+\\.\\d+\\.\\d+$"
                        },
                        "base_url": {
                            "type": "string",
                            "format": "uri"
                        },
                        "icon_url": {
                            "type": "string",
                            "format": "uri"
                        }
                    }
                },
                "services": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/service"}
                },
                "events": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/event"}
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "author": {"type": "string"},
                        "documentation_url": {"type": "string", "format": "uri"},
                        "support_email": {"type": "string", "format": "email"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            },
            "definitions": {
                "service": self._get_service_schema_definition(),
                "event": self._get_event_schema_definition(),
                "parameter": self._get_parameter_schema_definition()
            }
        }
    
    def _get_service_schema_definition(self) -> Dict[str, Any]:
        """Get service schema definition - supports correct structure"""
        return {
            "type": "object",
            "required": ["service_name", "description", "service_type"],
            "properties": {
                "service_name": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_\\s]+$"
                },
                "display_name": {
                    "type": "string"
                },
                "description": {
                    "type": "string",
                    "minLength": 1
                },
                "service_type": {
                    "type": "string",
                    "enum": ["api_call", "webhook", "email_send", "database_query", "llm_api_call", "mcp_call", "smtp_send", "pop3_receive", "imap_receive", "file_operation", "ai_agent_execute", "graphql", "ssh_command"]
                },
                "endpoint_template": {
                    "type": "string",
                    "description": "Endpoint URL template with {{parameter}} placeholders"
                },
                "request_config": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
                        },
                        "parameter_method": {"type": "string"},
                        "headers_template": {"type": "object"},
                        "body_template": {"type": ["object", "string"]},
                        "query_params_template": {"type": "object"}
                    }
                },
                "parameter_schema": {"type": "object"},
                "response_config": {"type": "object"},
                "service_config": {
                    "type": "object",
                    "description": "Additional service-specific configuration for non-api_call services"
                },
                "output_schema": {
                    "type": "object"
                },
                "is_async": {
                    "type": "boolean"
                },
                "timeout_seconds": {
                    "type": "integer"
                },
                "is_active": {
                    "type": "boolean"
                },
                "sync_mode": {
                    "type": "string",
                    "enum": ["synchronous", "asynchronous", "streaming"]
                },
                "sample_input": {
                    "type": ["object", "string"]
                },
                "sample_output": {
                    "type": ["object", "string"]
                }
            },
            "additionalProperties": False,
            "not": {
                "anyOf": [
                    {"required": ["configuration"]},
                    {"required": ["parameters"]},
                    {"required": ["name"]},
                    {"required": ["http_method"]},
                    {"required": ["headers_template"]},
                    {"required": ["body_template"]}
                ]
            }
        }
    
    def _get_event_schema_definition(self) -> Dict[str, Any]:
        """Get event schema definition"""
        return {
            "type": "object",
            "required": ["event_name", "description", "event_type", "event_configuration"],
            "properties": {
                "event_name": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_\\s]+$",
                    "minLength": 1,
                    "maxLength": 100
                },
                "description": {
                    "type": "string",
                    "minLength": 1
                },
                "event_type": {
                    "type": "string",
                    "enum": ["webhook", "schedule", "polling", "manual", "email", "form", "api_call", "mqtt"]
                },
                "event_configuration": {
                    "type": "object"
                },
                "display_name": {
                    "type": "string"
                },
                "sample_payload": {
                    "oneOf": [
                        {"type": "object"},
                        {"type": "string"}
                    ]
                },
                "output_schema": {
                    "type": "object"
                },
                "extraction_configuration": {
                    "type": "object"
                }
            },
            "allOf": [
                {
                    "if": {
                        "properties": {"event_type": {"const": "webhook"}}
                    },
                    "then": {
                        "properties": {
                            "event_configuration": {
                                "type": "object",
                                "properties": {
                                    "webhook_method": {
                                        "type": "string",
                                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
                                    },
                                    "headers": {
                                        "type": "object"
                                    },
                                    "authentication": {
                                        "type": "object"
                                    }
                                }
                            }
                        }
                    }
                },
                {
                    "if": {
                        "properties": {"event_type": {"const": "schedule"}}
                    },
                    "then": {
                        "properties": {
                            "event_configuration": {
                                "type": "object",
                                "required": ["schedule"],
                                "properties": {
                                    "schedule": {
                                        "type": "string",
                                        "pattern": "^(\\*|[0-9,\\-\\/]+)\\s+(\\*|[0-9,\\-\\/]+)\\s+(\\*|[0-9,\\-\\/]+)\\s+(\\*|[0-9,\\-\\/]+)\\s+(\\*|[0-9,\\-\\/]+)$"
                                    },
                                    "timezone": {
                                        "type": "string"
                                    },
                                    "description": {
                                        "type": "string"
                                    }
                                }
                            }
                        }
                    }
                },
                {
                    "if": {
                        "properties": {"event_type": {"const": "polling"}}
                    },
                    "then": {
                        "properties": {
                            "event_configuration": {
                                "type": "object",
                                "required": ["interval_seconds"],
                                "properties": {
                                    "interval_seconds": {
                                        "type": "integer",
                                        "minimum": 60
                                    },
                                    "service_name": {
                                        "type": "string"
                                    },
                                    "comparison_field": {
                                        "type": "string"
                                    },
                                    "comparison_type": {
                                        "type": "string",
                                        "enum": ["new_items", "updated_items", "all_items"]
                                    },
                                    "store_state": {
                                        "type": "boolean"
                                    },
                                    "initial_poll_limit": {
                                        "type": "integer"
                                    },
                                    "service_params": {
                                        "type": "object"
                                    }
                                }
                            }
                        }
                    }
                }
            ]
        }
    
    def _get_parameter_schema_definition(self) -> Dict[str, Any]:
        """Get parameter schema definition"""
        return {
            "type": "object",
            "required": ["name", "type"],
            "properties": {
                "name": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_]+$"
                },
                "type": {
                    "type": "string",
                    "enum": ["string", "number", "boolean", "object", "array"]
                },
                "required": {
                    "type": "boolean"
                },
                "description": {
                    "type": "string"
                },
                "default": {},
                "enum": {
                    "type": "array"
                },
                "pattern": {
                    "type": "string"
                },
                "minimum": {
                    "type": "number"
                },
                "maximum": {
                    "type": "number"
                },
                "minLength": {
                    "type": "integer"
                },
                "maxLength": {
                    "type": "integer"
                },
                "items": {
                    "type": "object"
                },
                "properties": {
                    "type": "object"
                }
            }
        }
    
    def _get_service_schema(self) -> Dict[str, Any]:
        """Get detailed service validation schema - This is deprecated, use _get_service_schema_definition"""
        # This method is kept for backward compatibility but should not be used
        # The actual validation is done by _get_service_schema_definition
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "deprecated": True,
            "description": "This schema is deprecated. Services must use the new format with service_config."
        }
    
    def _get_event_schema(self) -> Dict[str, Any]:
        """Get detailed event validation schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["event_name", "description", "event_type", "event_configuration"],
            "properties": {
                "event_name": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_\\s]+$",
                    "minLength": 1,
                    "maxLength": 100
                },
                "description": {
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 200
                },
                "event_type": {
                    "type": "string",
                    "enum": ["webhook", "schedule", "polling", "manual", "email", "form", "api_call", "mqtt"]
                },
                "event_configuration": {
                    "type": "object"
                },
                "display_name": {
                    "type": "string"
                },
                "sample_payload": {
                    "oneOf": [
                        {"type": "object"},
                        {"type": "string"}
                    ]
                },
                "output_schema": {
                    "type": "object"
                }
            }
        }
    
    def _get_parameter_schema(self) -> Dict[str, Any]:
        """Get parameter validation schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["name", "type"],
            "properties": {
                "name": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_]+$"
                },
                "type": {
                    "type": "string",
                    "enum": ["string", "number", "boolean", "object", "array"]
                },
                "required": {
                    "type": "boolean",
                    "default": False
                },
                "description": {
                    "type": "string"
                },
                "default": {},
                "enum": {
                    "type": "array",
                    "minItems": 1
                },
                "pattern": {
                    "type": "string"
                }
            },
            "allOf": [
                {
                    "if": {
                        "properties": {"type": {"const": "string"}}
                    },
                    "then": {
                        "properties": {
                            "minLength": {"type": "integer", "minimum": 0},
                            "maxLength": {"type": "integer", "minimum": 0},
                            "pattern": {"type": "string"}
                        }
                    }
                },
                {
                    "if": {
                        "properties": {"type": {"const": "number"}}
                    },
                    "then": {
                        "properties": {
                            "minimum": {"type": "number"},
                            "maximum": {"type": "number"},
                            "exclusiveMinimum": {"type": "number"},
                            "exclusiveMaximum": {"type": "number"}
                        }
                    }
                },
                {
                    "if": {
                        "properties": {"type": {"const": "array"}}
                    },
                    "then": {
                        "properties": {
                            "items": {"type": "object"},
                            "minItems": {"type": "integer", "minimum": 0},
                            "maxItems": {"type": "integer", "minimum": 0}
                        }
                    }
                },
                {
                    "if": {
                        "properties": {"type": {"const": "object"}}
                    },
                    "then": {
                        "properties": {
                            "properties": {"type": "object"},
                            "required": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            ]
        }
    
    def _validate_unique_names(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate that service and event names are unique"""
        # Check service names - handle both service_name (new) and name (old)
        service_names = []
        for s in app_data.get("services", []):
            name = s.get("service_name") or s.get("name")
            if name:
                service_names.append(name)
        
        duplicates = [name for name in service_names if service_names.count(name) > 1]
        if duplicates:
            results["errors"].append({
                "path": ["services"],
                "message": f"Duplicate service names found: {set(duplicates)}"
            })
            results["valid"] = False
        
        # Check event names
        event_names = []
        for e in app_data.get("events", []):
            name = e.get("event_name")
            if name:
                event_names.append(name)
        duplicates = [name for name in event_names if event_names.count(name) > 1]
        if duplicates:
            results["errors"].append({
                "path": ["events"],
                "message": f"Duplicate event names found: {set(duplicates)}"
            })
            results["valid"] = False
    
    def _validate_auth_config(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate authentication configuration"""
        app_info = app_data.get("application", {})
        auth_type = app_info.get("auth_type")
        auth_config = app_info.get("auth_config", {})

        if auth_type == "oauth2":
            # OAuth2 MUST have authorization_url and token_url - these are ERRORS not warnings
            required_fields = ["authorization_url", "token_url"]
            for field in required_fields:
                if field not in auth_config:
                    results["errors"].append({
                        "path": ["application", "auth_config"],
                        "message": f"OAuth2 configuration MUST include '{field}'. This is required for OAuth2 authentication.",
                        "schema_path": ["application", "auth_config", field]
                    })
                    results["valid"] = False

        elif auth_type == "api_key":
            # Skip header_name/query_param check for ai_agent app types or internal apps
            # These use API keys differently (passed to SDK, not via HTTP headers)
            app_type = app_info.get("app_type")
            base_url = app_info.get("base_url", "")
            is_internal_app = app_type == "ai_agent" or base_url.startswith("internal://")

            if not is_internal_app and not auth_config.get("header_name") and not auth_config.get("query_param"):
                results["warnings"].append({
                    "path": ["application", "auth_config"],
                    "message": "API key configuration should specify header_name or query_param"
                })
    
    def _validate_service_configurations(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate service-specific configurations and reject old format"""
        for i, service in enumerate(app_data.get("services", [])):
            service_name = service.get("service_name", service.get("name", f"Service {i}"))
            service_type = service.get("service_type")
            
            # REJECT OLD FORMAT - Check for deprecated fields
            if "configuration" in service:
                results["errors"].append({
                    "path": ["services", i],
                    "message": f"Service '{service_name}' uses deprecated 'configuration' field. Must use 'service_config' with nested configuration."
                })
                results["valid"] = False
                continue  # Skip further validation for this service
            
            if "parameters" in service:
                results["errors"].append({
                    "path": ["services", i],
                    "message": f"Service '{service_name}' uses deprecated 'parameters' field. Use 'parameter_schema' inside 'service_config'."
                })
                results["valid"] = False
            
            if "name" in service and "service_name" not in service:
                results["errors"].append({
                    "path": ["services", i],
                    "message": f"Service uses deprecated 'name' field. Must use 'service_name' instead."
                })
                results["valid"] = False
            
            # Check for top-level deprecated fields
            if "http_method" in service:
                results["errors"].append({
                    "path": ["services", i],
                    "message": f"Service '{service_name}' has 'http_method' at top level. Must be inside 'service_config.request_config.method'."
                })
                results["valid"] = False
            
            if "endpoint_url" in service:
                results["warnings"].append({
                    "path": ["services", i],
                    "message": f"Service '{service_name}' uses deprecated 'endpoint_url'. Please use 'endpoint_template' instead."
                })
            
            if "headers_template" in service:
                results["errors"].append({
                    "path": ["services", i],
                    "message": f"Service '{service_name}' has 'headers_template' at top level. Must be inside 'service_config.request_config.headers_template'."
                })
                results["valid"] = False
            
            if "body_template" in service:
                results["errors"].append({
                    "path": ["services", i],
                    "message": f"Service '{service_name}' has 'body_template' at top level. Must be inside 'service_config.request_config.body_template'."
                })
                results["valid"] = False
            
            # request_config at top level is correct for api_call services
            # No error needed here
            
            # Validate format based on service type
            if service_type == "api_call":
                # For api_call, endpoint_template should be at service level
                if not service.get("endpoint_template") and not service.get("endpoint_url"):
                    # Check if it's in the old location
                    service_config = service.get("service_config", {})
                    if service_config.get("endpoint_template") or service_config.get("endpoint_url"):
                        results["errors"].append({
                            "path": ["services", i],
                            "message": f"API call service '{service_name}' has endpoint_template/endpoint_url inside service_config. Move it to service level."
                        })
                        results["valid"] = False
                    else:
                        results["errors"].append({
                            "path": ["services", i],
                            "message": f"API call service '{service_name}' must specify endpoint_template at service level"
                        })
                        results["valid"] = False
                
                # Check for request_config at service level (correct location)
                request_config = service.get("request_config", {})
                if not request_config:
                    # Check if it's in the old location
                    service_config = service.get("service_config", {})
                    if service_config.get("request_config"):
                        results["errors"].append({
                            "path": ["services", i],
                            "message": f"API call service '{service_name}' has request_config inside service_config. Move it to service level."
                        })
                        results["valid"] = False
                    else:
                        results["warnings"].append({
                            "path": ["services", i],
                            "message": f"API call service '{service_name}' should have request_config at service level"
                        })
                
                if request_config and not request_config.get("method"):
                    results["errors"].append({
                        "path": ["services", i, "request_config"],
                        "message": f"API call service '{service_name}' must specify method inside request_config"
                    })
                    results["valid"] = False
            
            elif service_type == "database_query":
                service_config = service.get("service_config", {})
                if not service_config.get("operation_type"):
                    results["warnings"].append({
                        "path": ["services", i, "service_config"],
                        "message": f"Database query service '{service_name}' should specify operation_type",
                        "valid_values": ["select", "insert", "update", "delete", "execute"],
                        "example": {"operation_type": "select"}
                    })
            
            elif service_type == "webhook":
                # For webhooks, check both locations
                if not service.get("endpoint_template") and not service.get("webhook_url"):
                    service_config = service.get("service_config", {})
                    if not service_config.get("endpoint_template") and not service_config.get("webhook_url"):
                        results["errors"].append({
                            "path": ["services", i],
                            "message": f"Webhook service '{service_name}' must specify endpoint_template or webhook_url"
                        })
                        results["valid"] = False
    
    def _validate_event_configurations(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate event-specific configurations based on event_type"""
        for i, event in enumerate(app_data.get("events", [])):
            event_type = event.get("event_type")
            # Get event configuration
            config = event.get("event_configuration", {})
            
            if event_type == "webhook":
                # Webhook events may have additional webhook configuration
                # but don't require specific fields
                pass
            
            elif event_type == "schedule":
                schedule = config.get("schedule")
                if not schedule:
                    results["errors"].append({
                        "path": ["events", i, "event_configuration"],
                        "message": "Schedule event must specify schedule"
                    })
                    results["valid"] = False
                elif not self._validate_cron_expression(schedule):
                    results["errors"].append({
                        "path": ["events", i, "event_configuration", "schedule"],
                        "message": f"Invalid cron expression: {schedule}"
                    })
                    results["valid"] = False
            
            elif event_type == "polling":
                interval = config.get("interval_seconds")
                if not interval:
                    results["errors"].append({
                        "path": ["events", i, "event_configuration"],
                        "message": "Polling event must specify interval_seconds"
                    })
                    results["valid"] = False
                elif not isinstance(interval, int) or interval < 60:
                    results["warnings"].append({
                        "path": ["events", i, "event_configuration"],
                        "message": f"Polling interval {interval} is too short. Should be at least 60 seconds",
                        "valid_range": "60 to 86400 (1 minute to 24 hours)",
                        "recommended": "300 (5 minutes) or higher for API rate limits"
                    })
    
    def _validate_json_string_fields(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate JSON string fields can be parsed"""
        # Check services
        for i, service in enumerate(app_data.get("services", [])):
            # Check sample_input
            if "sample_input" in service and isinstance(service["sample_input"], str):
                try:
                    json.loads(service["sample_input"])
                except json.JSONDecodeError as e:
                    results["warnings"].append({
                        "path": ["services", i, "sample_input"],
                        "message": f"Invalid JSON string: {str(e)}"
                    })
            
            # Check sample_output
            if "sample_output" in service and isinstance(service["sample_output"], str):
                try:
                    json.loads(service["sample_output"])
                except json.JSONDecodeError as e:
                    results["warnings"].append({
                        "path": ["services", i, "sample_output"],
                        "message": f"Invalid JSON string: {str(e)}"
                    })
        
        # Check events
        for i, event in enumerate(app_data.get("events", [])):
            if "sample_payload" in event and isinstance(event["sample_payload"], str):
                try:
                    json.loads(event["sample_payload"])
                except json.JSONDecodeError as e:
                    results["warnings"].append({
                        "path": ["events", i, "sample_payload"],
                        "message": f"Invalid JSON string: {str(e)}"
                    })
    
    def _validate_parameter_schemas(self, app_data: Dict[str, Any], results: Dict[str, Any]):
        """Validate parameter schemas in services"""
        for i, service in enumerate(app_data.get("services", [])):
            service_config = service.get("service_config", {})
            param_schema = service_config.get("parameter_schema", {})
            
            if param_schema and param_schema.get("type") == "object":
                properties = param_schema.get("properties", {})
                
                for param_name, param_def in properties.items():
                    param_type = param_def.get("type")
                    
                    # Check default value type matches declared type
                    if "default" in param_def:
                        if not self._validate_value_type(param_def["default"], param_type):
                            results["warnings"].append({
                                "path": ["services", i, "service_config", "parameter_schema", "properties", param_name, "default"],
                                "message": f"Default value type doesn't match declared type '{param_type}'"
                            })
                    
                    # Check enum values match type
                    if "enum" in param_def:
                        for k, enum_val in enumerate(param_def["enum"]):
                            if not self._validate_value_type(enum_val, param_type):
                                results["warnings"].append({
                                    "path": ["services", i, "service_config", "parameter_schema", "properties", param_name, "enum", k],
                                    "message": f"Enum value '{enum_val}' doesn't match declared type '{param_type}'"
                                })
            
            # Check if service has parameter_schema at top level (allowed for all service types)
            if "parameter_schema" in service:
                # Validate the top-level parameter_schema
                top_level_schema = service.get("parameter_schema", {})
                if top_level_schema and top_level_schema.get("type") == "object":
                    properties = top_level_schema.get("properties", {})
                    
                    for param_name, param_def in properties.items():
                        param_type = param_def.get("type")
                        
                        # Check default value type matches declared type
                        if "default" in param_def:
                            if not self._validate_value_type(param_def["default"], param_type):
                                results["warnings"].append({
                                    "path": ["services", i, "parameter_schema", "properties", param_name, "default"],
                                    "message": f"Default value type doesn't match declared type '{param_type}'"
                                })
                        
                        # Check enum values match type
                        if "enum" in param_def:
                            for k, enum_val in enumerate(param_def["enum"]):
                                if not self._validate_value_type(enum_val, param_type):
                                    results["warnings"].append({
                                        "path": ["services", i, "parameter_schema", "properties", param_name, "enum", k],
                                        "message": f"Enum value '{enum_val}' doesn't match declared type '{param_type}'"
                                    })
    
    def _validate_cron_expression(self, cron: str) -> bool:
        """Basic cron expression validation"""
        parts = cron.split()
        if len(parts) != 5:
            return False
        
        # Basic validation - could be enhanced
        for part in parts:
            if part != "*" and not part.replace(",", "").replace("-", "").replace("/", "").isdigit():
                return False
        
        return True
    
    def _validate_value_type(self, value: Any, expected_type: str) -> bool:
        """Validate that a value matches expected type"""
        type_validators = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict)
        }
        
        validator = type_validators.get(expected_type)
        return validator(value) if validator else True
    
    def _format_validation_error(self, error: ValidationError) -> str:
        """Format validation error with helpful context including valid values"""
        message = error.message
        
        # Handle enum validation errors
        if "is not one of" in message or "is not valid under any of the given schemas" in message:
            if hasattr(error, 'validator_value') and isinstance(error.validator_value, list):
                valid_values = error.validator_value
                invalid_value = error.instance
                field_name = error.path[-1] if error.path else "field"
                return f"'{invalid_value}' is not a valid {field_name}. Valid values are: {', '.join(map(str, valid_values))}"
        
        # Handle pattern validation errors  
        elif "does not match" in message and "pattern" in message:
            if hasattr(error, 'validator_value'):
                pattern = error.validator_value
                invalid_value = error.instance
                field_name = error.path[-1] if error.path else "field"
                
                # Provide helpful pattern descriptions
                pattern_descriptions = {
                    "^[a-z0-9_]+$": "lowercase letters, numbers, and underscores only",
                    "^[a-zA-Z0-9_]+$": "letters, numbers, and underscores only", 
                    "^\\d+\\.\\d+\\.\\d+$": "semantic version format (e.g., 1.0.0)"
                }
                
                desc = pattern_descriptions.get(pattern, f"pattern {pattern}")
                return f"'{invalid_value}' is not a valid {field_name}. Must match {desc}"
        
        # Handle type validation errors
        elif "is not of type" in message:
            expected_type = message.split("is not of type")[1].strip().strip("'")
            invalid_value = error.instance
            field_name = error.path[-1] if error.path else "field"
            
            type_examples = {
                "string": '"example text"',
                "number": "123 or 123.45",
                "boolean": "true or false",
                "array": '["item1", "item2"]',
                "object": '{"key": "value"}'
            }
            
            example = type_examples.get(expected_type, expected_type)
            return f"{field_name} must be a {expected_type}. Example: {example}. Got: {type(invalid_value).__name__}"
        
        # Handle required field errors
        elif "is a required property" in message:
            field_name = message.split("'")[1] if "'" in message else "field"
            return f"Missing required field: '{field_name}'"
        
        # Default to original message if no special handling
        return message