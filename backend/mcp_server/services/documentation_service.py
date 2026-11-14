"""
MCP Documentation Service - Provides detailed documentation for creating application services and events
"""

from typing import Dict, Any, List
import json
from datetime import datetime

class DocumentationService:
    """Service to provide documentation for application services and events"""
    
    def __init__(self):
        self.service_types = {
            "api_call": {
                "name": "API Call Service",
                "description": "Call external REST APIs with customizable request configuration",
                "required_config": ["method", "endpoint_template"],
                "optional_config": ["headers_template", "query_params", "body_template", "auth_type"]
            },
            "webhook": {
                "name": "Webhook Service",
                "description": "Send webhooks to external endpoints",
                "required_config": ["url", "method"],
                "optional_config": ["headers", "retry_config", "timeout"]
            },
            "database_query": {
                "name": "Database Query Service",
                "description": "Execute database queries (SELECT, INSERT, UPDATE, DELETE)",
                "required_config": ["operation_type"],
                "optional_config": ["result_format", "max_rows", "timeout_seconds", "fetch_size", "transaction_mode"]
            },
            "email_send": {
                "name": "Email Send Service",
                "description": "Send emails via SMTP or email service providers",
                "required_config": ["provider", "from_email"],
                "optional_config": ["smtp_config", "template_id", "api_key"]
            },
            "llm_api_call": {
                "name": "LLM API Call Service",
                "description": "Call Large Language Model APIs",
                "required_config": ["provider", "model"],
                "optional_config": ["temperature", "max_tokens", "system_prompt"]
            },
            "mcp_call": {
                "name": "MCP Call Service",
                "description": "Call Model Context Protocol servers",
                "required_config": ["server_name", "tool_name"],
                "optional_config": ["server_params", "tool_params"]
            }
        }
        
        self.event_types = {
            "webhook": {
                "name": "Webhook Event",
                "description": "Triggered by incoming HTTP requests",
                "required_config": [],
                "optional_config": ["http_method", "headers", "validation"],
                "notes": [
                    "Webhook URLs are automatically generated: /webhooks/{app_id}/{event_name}",
                    "For custom endpoints, use the 'api_endpoint' field at the event level",
                    "Do NOT include 'webhook_url' in event_configuration"
                ]
            },
            "schedule": {
                "name": "Schedule Event",
                "description": "Triggered on a schedule (cron or interval)",
                "required_config": ["schedule_expression"],
                "optional_config": ["timezone", "start_date", "end_date"]
            },
            "polling": {
                "name": "Polling Event", 
                "description": "Poll external sources for changes",
                "required_config": ["service_name", "interval_seconds"],
                "optional_config": ["comparison_field", "comparison_type", "initial_poll_limit"]
            },
            "api_call": {
                "name": "API Call Event",
                "description": "Triggered via IOFlow API",
                "required_config": [],
                "optional_config": ["api_endpoint", "sync_mode", "http_method"]
            },
            "manual": {
                "name": "Manual Event",
                "description": "Manually triggered by users",
                "required_config": [],
                "optional_config": ["description"]
            },
            "email": {
                "name": "Email Event",
                "description": "Triggered by incoming emails",
                "required_config": ["email_address"],
                "optional_config": ["subject_filter", "sender_filter"]
            },
            "form": {
                "name": "Form Event",
                "description": "Triggered by form submissions",
                "required_config": ["form_id"],
                "optional_config": ["form_fields", "validation_rules"]
            }
        }
    
    def get_service_documentation(self, service_type: str = None) -> Dict[str, Any]:
        """Get documentation for application services"""
        
        if service_type:
            if service_type not in self.service_types:
                return {
                    "error": f"Unknown service type: {service_type}",
                    "available_types": list(self.service_types.keys())
                }
            
            service_info = self.service_types[service_type]
            return {
                "service_type": service_type,
                "name": service_info["name"],
                "description": service_info["description"],
                "configuration": {
                    "required": service_info["required_config"],
                    "optional": service_info["optional_config"]
                },
                "schema": self._get_service_schema(service_type),
                "examples": self._get_service_examples(service_type)
            }
        
        # Return overview of all service types
        return {
            "overview": "Application services define the actions that can be performed in flows",
            "service_types": {
                stype: {
                    "name": info["name"],
                    "description": info["description"]
                }
                for stype, info in self.service_types.items()
            },
            "usage": "Use get_service_documentation with a specific service_type for detailed information"
        }
    
    def get_event_documentation(self, event_type: str = None) -> Dict[str, Any]:
        """Get documentation for application events"""
        
        if event_type:
            if event_type not in self.event_types:
                return {
                    "error": f"Unknown event type: {event_type}",
                    "available_types": list(self.event_types.keys())
                }
            
            event_info = self.event_types[event_type]
            result = {
                "event_type": event_type,
                "name": event_info["name"],
                "description": event_info["description"],
                "configuration": {
                    "required": event_info["required_config"],
                    "optional": event_info["optional_config"]
                },
                "schema": self._get_event_schema(event_type),
                "examples": self._get_event_examples(event_type)
            }
            
            # Add notes if available
            if "notes" in event_info:
                result["notes"] = event_info["notes"]
            
            return result
        
        # Return overview of all event types
        return {
            "overview": "Application events define triggers that can start flows",
            "event_types": {
                etype: {
                    "name": info["name"],
                    "description": info["description"]
                }
                for etype, info in self.event_types.items()
            },
            "usage": "Use get_event_documentation with a specific event_type for detailed information"
        }
    
    def get_complete_guide(self) -> Dict[str, Any]:
        """Get complete guide for creating applications with services and events"""
        
        return {
            "title": "IOFlow Application Development Guide",
            "version": "1.0",
            "overview": {
                "description": "This guide explains how to create IOFlow applications with services and events",
                "key_concepts": {
                    "application": "A collection of services and events that integrate with external systems",
                    "service": "An action that can be performed (API call, database query, etc.)",
                    "event": "A trigger that can start a flow (webhook, schedule, etc.)",
                    "flow": "A workflow that connects events to services"
                }
            },
            "application_structure": {
                "required_fields": {
                    "key": "Unique identifier for the application",
                    "application": {
                        "app_name": "Display name",
                        "app_type": "database, email, api, file_system, memory, or flow",
                        "app_scope": "global, tenant, or user",
                        "description": "What the application does",
                        "auth_type": "none, api_key, oauth2, basic, custom"
                    },
                    "services": "Array of service definitions",
                    "events": "Array of event definitions"
                },
                "optional_fields": {
                    "metadata": "Author, version, tags, etc.",
                    "version": "Application version",
                    "icon_url": "Application icon URL",
                    "base_url": "Base URL for API services"
                }
            },
            "service_creation": {
                "overview": "Services define actions your application can perform",
                "common_fields": {
                    "service_name": "Unique identifier within the application",
                    "display_name": "Human-readable name",
                    "description": "What the service does",
                    "service_type": "Type of service (api_call, webhook, etc.)",
                    "service_config": "Type-specific configuration",
                    "parameter_schema": "JSON Schema for input parameters",
                    "output_schema": "JSON Schema for output"
                },
                "types": self._get_service_creation_guide()
            },
            "event_creation": {
                "overview": "Events define triggers that can start flows",
                "common_fields": {
                    "event_name": "Unique identifier within the application",
                    "display_name": "Human-readable name",
                    "description": "When this event triggers",
                    "event_type": "Type of event (webhook, schedule, etc.)",
                    "event_configuration": "Type-specific configuration",
                    "output_schema": "JSON Schema for event payload"
                },
                "types": self._get_event_creation_guide()
            },
            "best_practices": {
                "naming": [
                    "Use snake_case for service_name and event_name",
                    "Use descriptive names that indicate the action/trigger",
                    "Keep names consistent within your application"
                ],
                "schemas": [
                    "Always define parameter_schema for services that accept input",
                    "Always define output_schema for predictable outputs",
                    "Use JSON Schema draft-07 format",
                    "Include descriptions in schema properties"
                ],
                "error_handling": [
                    "Services should return consistent error formats",
                    "Include error codes and messages",
                    "Document possible error scenarios"
                ],
                "security": [
                    "Never hardcode credentials",
                    "Use IOFlow's credential management",
                    "Validate all inputs",
                    "Implement rate limiting where appropriate"
                ]
            },
            "examples": {
                "minimal_application": self._get_minimal_app_example(),
                "full_application": self._get_full_app_example()
            }
        }
    
    def _get_service_schema(self, service_type: str) -> Dict[str, Any]:
        """Get JSON schema for a service type"""
        
        schemas = {
            "api_call": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "service_type": {"type": "string", "const": "api_call"},
                    "endpoint_template": {"type": "string"},
                    "request_config": {
                        "type": "object",
                        "properties": {
                            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                            "headers_template": {"type": "object"},
                            "query_params": {"type": "object"},
                            "body_template": {"type": "object"}
                        },
                        "required": ["method"]
                    },
                    "parameter_schema": {"type": "object"},
                    "output_schema": {"type": "object"}
                },
                "required": ["service_name", "service_type", "endpoint_template", "request_config"]
            },
            "webhook": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "service_type": {"type": "string", "const": "webhook"},
                    "service_config": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "format": "uri"},
                            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                            "headers": {"type": "object"},
                            "retry_config": {
                                "type": "object",
                                "properties": {
                                    "max_retries": {"type": "integer"},
                                    "retry_delay": {"type": "integer"}
                                }
                            }
                        },
                        "required": ["url", "method"]
                    }
                },
                "required": ["service_name", "service_type", "service_config"]
            },
            "database_query": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "service_type": {"type": "string", "const": "database_query"},
                    "service_config": {
                        "type": "object",
                        "properties": {
                            "operation_type": {"type": "string", "enum": ["query", "execute", "batch"], "description": "Type of database operation"},
                            "result_format": {"type": "string", "enum": ["json_array", "json_object"], "description": "Format for query results"},
                            "max_rows": {"type": "integer", "minimum": 1, "default": 10000, "description": "Maximum rows to return"},
                            "timeout_seconds": {"type": "integer", "minimum": 1, "default": 30, "description": "Query timeout in seconds"},
                            "fetch_size": {"type": "integer", "minimum": 1, "default": 1000, "description": "Batch fetch size"},
                            "transaction_mode": {"type": "string", "enum": ["auto", "manual"], "description": "Transaction handling mode"}
                        },
                        "required": ["operation_type"]
                    },
                    "parameter_schema": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "SQL query with :param_name placeholders for parameters"
                            }
                        },
                        "required": ["sql"],
                        "additionalProperties": true,
                        "description": "The sql parameter contains the query, all other properties are bind parameters"
                    }
                },
                "required": ["service_name", "service_type", "service_config"]
            }
        }
        
        return schemas.get(service_type, {})
    
    def _get_event_schema(self, event_type: str) -> Dict[str, Any]:
        """Get JSON schema for an event type"""
        
        schemas = {
            "webhook": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "event_type": {"type": "string", "const": "webhook"},
                    "event_configuration": {
                        "type": "object",
                        "properties": {
                            "webhook_url": {"type": "string"},
                            "http_method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                            "headers": {"type": "object"},
                            "validation": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "secret": {"type": "string"}
                                }
                            }
                        }
                    },
                    "output_schema": {"type": "object"}
                },
                "required": ["event_name", "event_type"]
            },
            "schedule": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "event_type": {"type": "string", "const": "schedule"},
                    "event_configuration": {
                        "type": "object",
                        "properties": {
                            "schedule_expression": {"type": "string"},
                            "timezone": {"type": "string"},
                            "enabled": {"type": "boolean"}
                        },
                        "required": ["schedule_expression"]
                    }
                },
                "required": ["event_name", "event_type", "event_configuration"]
            },
            "polling": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "event_type": {"type": "string", "const": "polling"},
                    "event_configuration": {
                        "type": "object",
                        "properties": {
                            "service_name": {"type": "string"},
                            "interval_seconds": {"type": "integer", "minimum": 60},
                            "comparison_field": {"type": "string"},
                            "comparison_type": {"type": "string", "enum": ["new_items", "changed_items", "custom"]}
                        },
                        "required": ["service_name", "interval_seconds"]
                    },
                    "output_schema": {"type": "object"}
                },
                "required": ["event_name", "event_type", "event_configuration"]
            }
        }
        
        return schemas.get(event_type, {})
    
    def _get_service_examples(self, service_type: str) -> List[Dict[str, Any]]:
        """Get example configurations for a service type"""
        
        examples = {
            "api_call": [
                {
                    "name": "GET request example",
                    "config": {
                        "service_name": "get_user",
                        "display_name": "Get User Details",
                        "description": "Fetch user information by ID",
                        "service_type": "api_call",
                        "endpoint_template": "/users/{{user_id}}",
                        "request_config": {
                            "method": "GET",
                            "headers_template": {
                                "Accept": "application/json"
                            }
                        },
                        "parameter_schema": {
                            "type": "object",
                            "properties": {
                                "user_id": {
                                    "type": "string",
                                    "description": "User ID to fetch"
                                }
                            },
                            "required": ["user_id"]
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "email": {"type": "string"}
                            }
                        }
                    }
                },
                {
                    "name": "POST request example",
                    "config": {
                        "service_name": "create_record",
                        "display_name": "Create Record",
                        "description": "Create a new record",
                        "service_type": "api_call",
                        "endpoint_template": "/records",
                        "request_config": {
                            "method": "POST",
                            "headers_template": {
                                "Content-Type": "application/json"
                            },
                            "body_template": {
                                "name": "{{name}}",
                                "type": "{{record_type}}",
                                "data": "{{data}}"
                            }
                        },
                        "parameter_schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "record_type": {"type": "string"},
                                "data": {"type": "object"}
                            },
                            "required": ["name", "record_type"]
                        }
                    }
                }
            ],
            "webhook": [
                {
                    "name": "Simple webhook",
                    "config": {
                        "service_name": "send_notification",
                        "display_name": "Send Notification",
                        "description": "Send webhook notification",
                        "service_type": "webhook",
                        "service_config": {
                            "url": "https://hooks.example.com/webhook",
                            "method": "POST",
                            "headers": {
                                "X-Webhook-Token": "{{webhook_token}}"
                            },
                            "retry_config": {
                                "max_retries": 3,
                                "retry_delay": 1000
                            }
                        },
                        "parameter_schema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                                "severity": {"type": "string", "enum": ["info", "warning", "error"]}
                            },
                            "required": ["message"]
                        }
                    }
                }
            ],
            "database_query": [
                {
                    "name": "SELECT query",
                    "config": {
                        "service_name": "execute_query",
                        "display_name": "Execute Query",
                        "description": "Execute a SELECT query and return results",
                        "service_type": "database_query",
                        "service_config": {
                            "operation_type": "query",
                            "result_format": "json_array",
                            "max_rows": 1000,
                            "timeout_seconds": 30
                        },
                        "parameter_schema": {
                            "type": "object",
                            "properties": {
                                "sql": {
                                    "type": "string",
                                    "description": "SQL query with named parameters"
                                },
                                "status": {"type": "string"},
                                "date": {"type": "string", "format": "date"}
                            },
                            "required": ["sql"],
                            "additionalProperties": true
                        },
                        "sample_input": {
                            "sql": "SELECT * FROM records WHERE status = :status AND created_at > :date",
                            "status": "active",
                            "date": "2024-01-01"
                        }
                    }
                },
                {
                    "name": "INSERT/UPDATE/DELETE command",
                    "config": {
                        "service_name": "execute_command",
                        "display_name": "Execute Command",
                        "description": "Execute INSERT, UPDATE, or DELETE commands",
                        "service_type": "database_query",
                        "service_config": {
                            "operation_type": "execute",
                            "transaction_mode": "auto",
                            "timeout_seconds": 30
                        },
                        "parameter_schema": {
                            "type": "object",
                            "properties": {
                                "sql": {
                                    "type": "string",
                                    "description": "SQL command with named parameters"
                                }
                            },
                            "required": ["sql"],
                            "additionalProperties": true
                        },
                        "sample_input": {
                            "sql": "INSERT INTO users (name, email, status) VALUES (:name, :email, :status)",
                            "name": "John Doe",
                            "email": "john@example.com",
                            "status": "active"
                        }
                    }
                }
            ]
        }
        
        return examples.get(service_type, [])
    
    def _get_event_examples(self, event_type: str) -> List[Dict[str, Any]]:
        """Get example configurations for an event type"""
        
        examples = {
            "webhook": [
                {
                    "name": "Basic webhook",
                    "config": {
                        "event_name": "order_received",
                        "display_name": "Order Received",
                        "description": "Triggered when a new order is received",
                        "event_type": "webhook",
                        "event_configuration": {
                            "http_method": "POST"
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "order_id": {"type": "string"},
                                "customer_id": {"type": "string"},
                                "items": {"type": "array"},
                                "total": {"type": "number"}
                            }
                        }
                    },
                    "note": "Webhook URL will be: /webhooks/{app_id}/order_received"
                },
                {
                    "name": "Webhook with validation",
                    "config": {
                        "event_name": "github_push",
                        "display_name": "GitHub Push",
                        "description": "Triggered by GitHub push events",
                        "event_type": "webhook",
                        "event_configuration": {
                            "http_method": "POST",
                            "headers": {
                                "X-GitHub-Event": "push"
                            },
                            "validation": {
                                "type": "hmac_signature",
                                "signature_header": "X-Hub-Signature-256",
                                "secret": "{{github_webhook_secret}}"
                            }
                        }
                    }
                },
                {
                    "name": "Webhook with custom endpoint",
                    "config": {
                        "event_name": "stripe_webhook",
                        "display_name": "Stripe Webhook",
                        "description": "Triggered by Stripe payment events",
                        "event_type": "webhook",
                        "api_endpoint": "/api/stripe/webhook",
                        "event_configuration": {
                            "http_method": "POST",
                            "validation": {
                                "type": "stripe_signature",
                                "signature_header": "Stripe-Signature",
                                "secret": "{{stripe_webhook_secret}}"
                            }
                        }
                    },
                    "note": "Custom endpoint: /api/stripe/webhook (instead of default /webhooks/{app_id}/stripe_webhook)"
                }
            ],
            "schedule": [
                {
                    "name": "Daily schedule",
                    "config": {
                        "event_name": "daily_report",
                        "display_name": "Daily Report",
                        "description": "Generate daily report at 9 AM",
                        "event_type": "schedule",
                        "event_configuration": {
                            "schedule_expression": "0 9 * * *",
                            "timezone": "America/New_York",
                            "enabled": True
                        }
                    }
                },
                {
                    "name": "Interval schedule",
                    "config": {
                        "event_name": "health_check",
                        "display_name": "Health Check",
                        "description": "Run health check every 5 minutes",
                        "event_type": "schedule",
                        "event_configuration": {
                            "schedule_expression": "*/5 * * * *",
                            "enabled": True
                        }
                    }
                }
            ],
            "polling": [
                {
                    "name": "Poll for new items",
                    "config": {
                        "event_name": "new_messages",
                        "display_name": "New Messages",
                        "description": "Check for new messages every minute",
                        "event_type": "polling",
                        "event_configuration": {
                            "service_name": "list_messages",
                            "interval_seconds": 60,
                            "comparison_field": "id",
                            "comparison_type": "new_items",
                            "initial_poll_limit": 10
                        }
                    }
                }
            ]
        }
        
        return examples.get(event_type, [])
    
    def _get_service_creation_guide(self) -> Dict[str, Any]:
        """Get detailed guide for creating each service type"""
        
        return {
            "api_call": {
                "description": "For calling REST APIs",
                "when_to_use": "When you need to interact with external REST APIs",
                "configuration": {
                    "endpoint_template": "URL path with {{variables}}",
                    "request_config": {
                        "method": "HTTP method",
                        "headers_template": "Headers with {{variables}}",
                        "query_params": "Query parameters",
                        "body_template": "Request body with {{variables}}"
                    }
                },
                "tips": [
                    "Use {{variable}} syntax for dynamic values",
                    "Base URL is set at application level",
                    "Authentication is handled by auth_config"
                ]
            },
            "webhook": {
                "description": "For sending webhooks",
                "when_to_use": "When you need to notify external systems",
                "configuration": {
                    "url": "Full webhook URL",
                    "method": "HTTP method",
                    "headers": "Static headers",
                    "retry_config": "Retry configuration"
                },
                "tips": [
                    "URL can include {{variables}}",
                    "Automatic retries on failure",
                    "Payload is the input parameters"
                ]
            },
            "database_query": {
                "description": "For database operations",
                "when_to_use": "When you need to query or modify database",
                "configuration": {
                    "query_template": "SQL query with :parameters",
                    "database_type": "postgresql, mysql, sqlite, mongodb",
                    "operation_type": "select, insert, update, delete"
                },
                "tips": [
                    "Use :param syntax for parameters",
                    "Connection details in credentials",
                    "Supports transactions"
                ]
            }
        }
    
    def _get_event_creation_guide(self) -> Dict[str, Any]:
        """Get detailed guide for creating each event type"""
        
        return {
            "webhook": {
                "description": "Triggered by HTTP requests",
                "when_to_use": "When external systems need to trigger flows",
                "configuration": {
                    "webhook_url": "Optional custom path",
                    "http_method": "Expected HTTP method",
                    "validation": "Security validation"
                },
                "tips": [
                    "Automatic URL generation if not specified",
                    "Supports various validation methods",
                    "Payload becomes flow input"
                ]
            },
            "schedule": {
                "description": "Triggered on schedule",
                "when_to_use": "For recurring tasks",
                "configuration": {
                    "schedule_expression": "Cron expression",
                    "timezone": "Timezone for schedule",
                    "enabled": "Enable/disable flag"
                },
                "tips": [
                    "Standard cron syntax",
                    "Minimum interval is 1 minute",
                    "Empty payload by default"
                ]
            },
            "polling": {
                "description": "Poll for changes",
                "when_to_use": "When you need to check for updates",
                "configuration": {
                    "service_name": "Service to call",
                    "interval_seconds": "Polling interval",
                    "comparison_field": "Field to track changes"
                },
                "tips": [
                    "Automatically tracks state",
                    "Only triggers on changes",
                    "Service must return array"
                ]
            }
        }
    
    def _get_minimal_app_example(self) -> Dict[str, Any]:
        """Get minimal application example"""
        
        return {
            "key": "hello_world",
            "application": {
                "app_name": "Hello World",
                "app_type": "global",
                "description": "Minimal IOFlow application",
                "auth_type": "none"
            },
            "services": [
                {
                    "service_name": "say_hello",
                    "display_name": "Say Hello",
                    "description": "Returns a greeting",
                    "service_type": "webhook",
                    "service_config": {
                        "url": "https://example.com/hello",
                        "method": "POST"
                    },
                    "parameter_schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        }
                    }
                }
            ],
            "events": [
                {
                    "event_name": "manual_trigger",
                    "display_name": "Manual Trigger",
                    "description": "Manually trigger the flow",
                    "event_type": "manual"
                }
            ]
        }
    
    def _get_full_app_example(self) -> Dict[str, Any]:
        """Get full application example"""
        
        return {
            "key": "crm_integration",
            "application": {
                "app_name": "CRM Integration",
                "app_type": "tenant",
                "description": "Full-featured CRM integration",
                "category": "Business",
                "auth_type": "oauth2",
                "auth_config": {
                    "authorization_url": "https://crm.example.com/oauth/authorize",
                    "token_url": "https://crm.example.com/oauth/token",
                    "scopes": ["read", "write"]
                },
                "base_url": "https://api.crm.example.com/v2",
                "version": "1.0.0",
                "icon_url": "https://example.com/crm-icon.png"
            },
            "services": [
                {
                    "service_name": "get_contact",
                    "display_name": "Get Contact",
                    "description": "Retrieve contact details",
                    "service_type": "api_call",
                    "endpoint_template": "/contacts/{{contact_id}}",
                    "request_config": {
                        "method": "GET",
                        "headers_template": {
                            "Accept": "application/json"
                        }
                    },
                    "parameter_schema": {
                        "type": "object",
                        "properties": {
                            "contact_id": {
                                "type": "string",
                                "description": "Contact ID"
                            }
                        },
                        "required": ["contact_id"]
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "phone": {"type": "string"}
                        }
                    }
                },
                {
                    "service_name": "create_contact",
                    "display_name": "Create Contact",
                    "description": "Create a new contact",
                    "service_type": "api_call",
                    "endpoint_template": "/contacts",
                    "request_config": {
                        "method": "POST",
                        "headers_template": {
                            "Content-Type": "application/json"
                        },
                        "body_template": {
                            "name": "{{name}}",
                            "email": "{{email}}",
                            "phone": "{{phone}}",
                            "company": "{{company}}"
                        }
                    },
                    "parameter_schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string", "format": "email"},
                            "phone": {"type": "string"},
                            "company": {"type": "string"}
                        },
                        "required": ["name", "email"]
                    }
                }
            ],
            "events": [
                {
                    "event_name": "contact_created",
                    "display_name": "Contact Created",
                    "description": "Triggered when a new contact is created",
                    "event_type": "webhook",
                    "event_configuration": {
                        "http_method": "POST",
                        "validation": {
                            "type": "api_key",
                            "header": "X-CRM-Token"
                        }
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "created_at": {"type": "string", "format": "date-time"}
                        }
                    }
                },
                {
                    "event_name": "daily_sync",
                    "display_name": "Daily Sync",
                    "description": "Sync contacts daily at midnight",
                    "event_type": "schedule",
                    "event_configuration": {
                        "schedule_expression": "0 0 * * *",
                        "timezone": "UTC"
                    }
                }
            ],
            "metadata": {
                "author": "IOFlow Team",
                "documentation_url": "https://docs.example.com/crm",
                "support_email": "support@example.com",
                "tags": ["crm", "contacts", "business"]
            }
        }
    
    def search_documentation(self, query: str) -> Dict[str, Any]:
        """Search documentation for specific terms"""
        
        query_lower = query.lower()
        query_words = query_lower.split()
        results = []
        
        # Enhanced search in service types
        for stype, info in self.service_types.items():
            score = 0
            matches = []
            
            # Check for matches in type name
            if query_lower in stype.lower():
                score += 3
                matches.append(f"service type name: {stype}")
            
            # Check for matches in description
            if query_lower in info["description"].lower():
                score += 2
                matches.append("description")
            
            # Check for word matches
            for word in query_words:
                if word in stype.lower():
                    score += 1
                    matches.append(f"word '{word}' in type")
                if word in info["description"].lower():
                    score += 1
                    matches.append(f"word '{word}' in description")
                    
            # Check required/optional fields
            all_fields = info.get("required_config", []) + info.get("optional_config", [])
            for field in all_fields:
                if any(word in field.lower() for word in query_words):
                    score += 1
                    matches.append(f"field: {field}")
            
            if score > 0:
                results.append({
                    "type": "service_type",
                    "name": stype,
                    "description": info["description"],
                    "score": score,
                    "matches": matches,
                    "details": f"Use get_service_documentation('{stype}') for details",
                    "fields": all_fields
                })
        
        # Enhanced search in event types
        for etype, info in self.event_types.items():
            score = 0
            matches = []
            
            if query_lower in etype.lower():
                score += 3
                matches.append(f"event type name: {etype}")
                
            if query_lower in info["description"].lower():
                score += 2
                matches.append("description")
                
            for word in query_words:
                if word in etype.lower():
                    score += 1
                    matches.append(f"word '{word}' in type")
                if word in info["description"].lower():
                    score += 1
                    matches.append(f"word '{word}' in description")
                    
            # Check in notes
            for note in info.get("notes", []):
                if any(word in note.lower() for word in query_words):
                    score += 1
                    matches.append(f"note: {note[:50]}...")
            
            if score > 0:
                results.append({
                    "type": "event_type",
                    "name": etype,
                    "description": info["description"],
                    "score": score,
                    "matches": matches,
                    "details": f"Use get_event_documentation('{etype}') for details"
                })
        
        # Search in extended documentation concepts
        documentation_concepts = {
            "transform": {
                "description": "Transform nodes modify or process data using Python scripts",
                "related": ["script", "node", "data", "python", "processing", "transformation"],
                "examples": ["data transformation", "transform node", "python script"]
            },
            "node": {
                "description": "Nodes are the building blocks of flows - trigger, action, transform, condition, loop, response",
                "related": ["flow", "trigger", "action", "transform", "condition", "loop", "response"],
                "examples": ["node types", "flow nodes", "node configuration"]
            },
            "script": {
                "description": "Python scripts used in transform nodes for data processing",
                "related": ["python", "transform", "code", "data", "node"],
                "examples": ["transform script", "python code", "script node"]
            },
            "flow": {
                "description": "Flows are automated workflows that connect applications and process data",
                "related": ["workflow", "automation", "nodes", "edges"],
                "examples": ["create flow", "flow design", "flow execution"]
            },
            "trigger": {
                "description": "Triggers initiate flow execution - manual, webhook, schedule, application event",
                "related": ["start", "initiate", "webhook", "schedule", "event"],
                "examples": ["trigger types", "flow trigger", "webhook trigger"]
            },
            "action": {
                "description": "Action nodes perform operations using connected applications and services",
                "related": ["service", "application", "api", "operation"],
                "examples": ["action node", "api action", "service call"]
            },
            "condition": {
                "description": "Condition nodes create branching logic based on expressions",
                "related": ["if", "branch", "logic", "expression"],
                "examples": ["conditional logic", "if-else", "branching"]
            },
            "loop": {
                "description": "Loop nodes iterate over collections or repeat based on conditions",
                "related": ["iterate", "foreach", "while", "repeat"],
                "examples": ["loop node", "forEach loop", "iteration"]
            },
            "parameter": {
                "description": "Parameters pass data between nodes and configure services",
                "related": ["input", "output", "variable", "data", "mapping"],
                "examples": ["parameter mapping", "input parameters", "service parameters"]
            },
            "variable": {
                "description": "Variables store and reference data throughout flow execution",
                "related": ["data", "reference", "value", "parameter"],
                "examples": ["flow variables", "variable reference", "{{variable}}"]
            },
            "authentication": {
                "description": "Authentication methods for connecting to external services",
                "related": ["auth", "oauth", "api_key", "bearer", "basic"],
                "examples": ["oauth2", "api key", "bearer token"]
            },
            "webhook": {
                "description": "HTTP endpoints for receiving data or triggering flows",
                "related": ["http", "endpoint", "url", "trigger", "event"],
                "examples": ["webhook url", "webhook trigger", "incoming webhook"]
            },
            "schedule": {
                "description": "Time-based triggers using cron expressions",
                "related": ["cron", "time", "periodic", "recurring"],
                "examples": ["cron schedule", "daily run", "scheduled trigger"]
            },
            "data": {
                "description": "Data flows through nodes and can be transformed, filtered, or mapped",
                "related": ["transform", "process", "flow", "variable", "transformation"],
                "examples": ["data transformation", "data flow", "process data"]
            },
            "transformation": {
                "description": "Data transformation using transform nodes with Python scripts",
                "related": ["transform", "script", "modify", "process", "python", "node", "data"],
                "examples": ["data transformation", "transform script", "modify data"]
            }
        }
        
        # Search in documentation concepts
        for concept, info in documentation_concepts.items():
            score = 0
            matches = []
            
            # Direct match
            if query_lower in concept.lower():
                score += 3
                matches.append(f"concept: {concept}")
            
            # Description match
            if query_lower in info["description"].lower():
                score += 2
                matches.append("in description")
            
            # Word matches
            for word in query_words:
                if word in concept.lower():
                    score += 2
                    matches.append(f"word '{word}' in concept")
                if word in info["description"].lower():
                    score += 1
                    matches.append(f"word '{word}' in description")
                
                # Check related terms
                for related in info.get("related", []):
                    if word == related.lower():
                        score += 2
                        matches.append(f"related term: {related}")
                    elif word in related.lower():
                        score += 1
                        matches.append(f"partial match: {related}")
                
                # Check examples
                for example in info.get("examples", []):
                    if word in example.lower():
                        score += 1
                        matches.append(f"example: {example}")
            
            # Check full query in examples
            for example in info.get("examples", []):
                if query_lower in example.lower():
                    score += 3
                    matches.append(f"full match in example: {example}")
            
            if score > 0:
                results.append({
                    "type": "concept",
                    "name": concept,
                    "description": info["description"],
                    "score": score,
                    "matches": matches,
                    "related_terms": info.get("related", []),
                    "examples": info.get("examples", [])
                })
        
        # Sort results by score
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Limit to top 10 results
        results = results[:10]
        
        return {
            "query": query,
            "results": results,
            "count": len(results),
            "suggestion": "Try get_complete_guide() for comprehensive documentation" if not results else None
        }