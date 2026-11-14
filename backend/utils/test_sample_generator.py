#!/usr/bin/env python3
"""
Test and demonstrate the sample data generator for application events
"""
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.sample_data_generator import generate_sample_from_schema, validate_and_generate_sample

def test_event_schemas():
    """Test various event schemas and generate sample data"""
    
    # Example event schemas
    event_schemas = [
        {
            "name": "Slack New Message Event",
            "schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "title": "Message Text", "minLength": 1, "maxLength": 1000},
                    "user": {"type": "string", "title": "User ID"},
                    "channel": {"type": "string", "title": "Channel ID"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "thread_ts": {"type": "string", "title": "Thread Timestamp"},
                    "attachments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "text": {"type": "string"},
                                "color": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["text", "user", "channel", "timestamp"]
            }
        },
        {
            "name": "GitHub Push Event",
            "schema": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "title": "Git Reference"},
                    "before": {"type": "string", "title": "Previous Commit SHA"},
                    "after": {"type": "string", "title": "New Commit SHA"},
                    "repository": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string", "title": "Repository Name"},
                            "full_name": {"type": "string", "title": "Full Name"},
                            "private": {"type": "boolean"},
                            "owner": {
                                "type": "object",
                                "properties": {
                                    "login": {"type": "string"},
                                    "id": {"type": "integer"},
                                    "type": {"type": "string", "enum": ["User", "Organization"]}
                                }
                            }
                        }
                    },
                    "pusher": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "title": "Pusher Name"},
                            "email": {"type": "string", "format": "email"}
                        }
                    },
                    "commits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "message": {"type": "string", "title": "Commit Message"},
                                "timestamp": {"type": "string", "format": "date-time"},
                                "author": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string", "format": "email"}
                                    }
                                }
                            }
                        },
                        "minItems": 1,
                        "maxItems": 5
                    }
                },
                "required": ["ref", "repository", "pusher", "commits"]
            }
        },
        {
            "name": "E-commerce Order Event",
            "schema": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "title": "Order ID"},
                    "customer": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string", "title": "Customer Name"},
                            "email": {"type": "string", "format": "email"},
                            "phone": {"type": "string", "title": "Phone Number"}
                        },
                        "required": ["id", "name", "email"]
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "product_name": {"type": "string"},
                                "quantity": {"type": "integer", "minimum": 1},
                                "price": {"type": "number", "minimum": 0},
                                "total": {"type": "number", "minimum": 0}
                            }
                        },
                        "minItems": 1
                    },
                    "total_amount": {"type": "number", "title": "Total Amount", "minimum": 0},
                    "currency": {"type": "string", "enum": ["USD", "EUR", "GBP", "CAD"]},
                    "status": {"type": "string", "enum": ["pending", "processing", "completed", "cancelled"]},
                    "created_at": {"type": "string", "format": "date-time"}
                },
                "required": ["order_id", "customer", "items", "total_amount", "currency", "status"]
            }
        },
        {
            "name": "IoT Sensor Data Event",
            "schema": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "title": "Device ID"},
                    "sensor_type": {"type": "string", "enum": ["temperature", "humidity", "pressure", "motion", "light"]},
                    "readings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "timestamp": {"type": "string", "format": "date-time"},
                                "value": {"type": "number"},
                                "unit": {"type": "string"}
                            }
                        }
                    },
                    "location": {
                        "type": "object",
                        "properties": {
                            "lat": {"type": "number", "minimum": -90, "maximum": 90},
                            "lng": {"type": "number", "minimum": -180, "maximum": 180},
                            "altitude": {"type": "number"}
                        }
                    },
                    "battery_level": {"type": "integer", "minimum": 0, "maximum": 100},
                    "signal_strength": {"type": "integer", "minimum": -100, "maximum": 0}
                },
                "required": ["device_id", "sensor_type", "readings"]
            }
        }
    ]
    
    print("=== Application Event Sample Data Generator ===\n")
    
    for event_def in event_schemas:
        print(f"\n{'='*60}")
        print(f"Event: {event_def['name']}")
        print(f"{'='*60}")
        
        # Generate sample data
        result = validate_and_generate_sample(event_def['schema'])
        
        if result['error']:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"\n📋 Schema:")
            print(json.dumps(event_def['schema'], indent=2))
            print(f"\n✅ Generated Sample Data:")
            print(json.dumps(result['sample'], indent=2))
            
            # Demonstrate context override
            if event_def['name'] == "Slack New Message Event":
                context = {
                    "channel": "#general",
                    "user": "U123456789"
                }
                context_result = validate_and_generate_sample(event_def['schema'], context)
                print(f"\n🔄 With Context Override (channel=#general, user=U123456789):")
                print(json.dumps(context_result['sample'], indent=2))

def test_service_input_schemas():
    """Test service input schemas for actions"""
    
    service_schemas = [
        {
            "name": "Send Email Service",
            "schema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string", "format": "email"},
                        "minItems": 1,
                        "title": "Recipients"
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string", "format": "email"},
                        "title": "CC Recipients"
                    },
                    "subject": {"type": "string", "minLength": 1, "maxLength": 200},
                    "body": {"type": "string", "title": "Email Body"},
                    "attachments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "filename": {"type": "string"},
                                "content": {"type": "string"},
                                "content_type": {"type": "string"}
                            }
                        }
                    },
                    "priority": {"type": "string", "enum": ["low", "normal", "high"], "default": "normal"}
                },
                "required": ["to", "subject", "body"]
            }
        },
        {
            "name": "Database Query Service",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "title": "SQL Query"},
                    "parameters": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    },
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 300, "default": 30},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 100}
                },
                "required": ["query"]
            }
        }
    ]
    
    print(f"\n\n{'='*60}")
    print("Service Input Schema Examples")
    print(f"{'='*60}")
    
    for service_def in service_schemas:
        print(f"\n📦 Service: {service_def['name']}")
        result = validate_and_generate_sample(service_def['schema'])
        
        if not result['error']:
            print(f"Input Sample:")
            print(json.dumps(result['sample'], indent=2))

if __name__ == "__main__":
    test_event_schemas()
    test_service_input_schemas()
    print("\n✨ Sample data generation complete!")