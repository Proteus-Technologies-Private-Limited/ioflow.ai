"""
Generate sample data based on JSON Schema definitions
"""
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
from faker import Faker
import uuid as uuid_module

fake = Faker()

def generate_sample_from_schema(schema: Dict[str, Any]) -> Any:
    """
    Generate sample data based on a JSON Schema
    
    Args:
        schema: JSON Schema definition
        
    Returns:
        Sample data matching the schema
    """
    if not schema:
        return {}
    
    schema_type = schema.get('type', 'object')
    
    if schema_type == 'object':
        return generate_object(schema)
    elif schema_type == 'array':
        return generate_array(schema)
    elif schema_type == 'string':
        return generate_string(schema)
    elif schema_type == 'number':
        return generate_number(schema)
    elif schema_type == 'integer':
        return generate_integer(schema)
    elif schema_type == 'boolean':
        return generate_boolean(schema)
    elif schema_type == 'null':
        return None
    else:
        return None

def generate_object(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Generate sample object based on schema"""
    result = {}
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    
    for prop_name, prop_schema in properties.items():
        # Always include required fields, include others 80% of the time
        if prop_name in required or random.random() > 0.2:
            result[prop_name] = generate_sample_from_schema(prop_schema)
    
    # Handle additionalProperties
    if schema.get('additionalProperties', False):
        # Add 0-2 additional properties
        for i in range(random.randint(0, 2)):
            key = f"additional_prop_{i}"
            if isinstance(schema['additionalProperties'], dict):
                result[key] = generate_sample_from_schema(schema['additionalProperties'])
            else:
                result[key] = fake.word()
    
    return result

def generate_array(schema: Dict[str, Any]) -> List[Any]:
    """Generate sample array based on schema"""
    items_schema = schema.get('items', {})
    min_items = schema.get('minItems', 0)
    max_items = schema.get('maxItems', 5)
    
    # Generate random number of items between min and max
    num_items = random.randint(min_items, min(max_items, 5))
    
    result = []
    for _ in range(num_items):
        result.append(generate_sample_from_schema(items_schema))
    
    return result

def generate_string(schema: Dict[str, Any]) -> str:
    """Generate sample string based on schema"""
    # Check for enum
    if 'enum' in schema:
        return random.choice(schema['enum'])
    
    # Check for pattern
    pattern = schema.get('pattern')
    format_type = schema.get('format')
    min_length = schema.get('minLength', 0)
    max_length = schema.get('maxLength', 50)
    
    # Handle specific formats
    if format_type == 'date-time':
        return fake.date_time().isoformat()
    elif format_type == 'date':
        return fake.date()
    elif format_type == 'time':
        return fake.time()
    elif format_type == 'email':
        return fake.email()
    elif format_type == 'uri' or format_type == 'url':
        return fake.url()
    elif format_type == 'uuid':
        return str(uuid_module.uuid4())
    elif format_type == 'ipv4':
        return fake.ipv4()
    elif format_type == 'ipv6':
        return fake.ipv6()
    elif format_type == 'hostname':
        return fake.domain_name()
    
    # Handle patterns (simplified)
    if pattern:
        # Common patterns
        if pattern == '^[0-9]{5}$':  # ZIP code
            return fake.zipcode()
        elif pattern == '^\\+?[1-9]\\d{1,14}$':  # Phone number
            return fake.phone_number()
        elif 'email' in pattern.lower():
            return fake.email()
        # For other patterns, generate random string
        else:
            length = random.randint(min_length, min(max_length, 20))
            return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    # Check for specific property names for better sample data
    prop_name = schema.get('title', '').lower()
    if 'name' in prop_name:
        if 'first' in prop_name:
            return fake.first_name()
        elif 'last' in prop_name:
            return fake.last_name()
        elif 'full' in prop_name or 'user' in prop_name:
            return fake.name()
        else:
            return fake.company()
    elif 'email' in prop_name:
        return fake.email()
    elif 'phone' in prop_name:
        return fake.phone_number()
    elif 'address' in prop_name:
        return fake.address()
    elif 'city' in prop_name:
        return fake.city()
    elif 'country' in prop_name:
        return fake.country()
    elif 'description' in prop_name or 'text' in prop_name or 'message' in prop_name:
        return fake.text(max_nb_chars=max_length)
    elif 'title' in prop_name:
        return fake.sentence(nb_words=6)
    elif 'url' in prop_name or 'link' in prop_name:
        return fake.url()
    elif 'id' in prop_name:
        return uuid_module.uuid4().hex[:8]
    
    # Default: generate random text
    length = random.randint(min_length, min(max_length, 20))
    return fake.text(max_nb_chars=length) if length > 10 else fake.word()

def generate_number(schema: Dict[str, Any]) -> float:
    """Generate sample number based on schema"""
    minimum = schema.get('minimum', 0)
    maximum = schema.get('maximum', 1000)
    multiple_of = schema.get('multipleOf')
    
    if multiple_of:
        # Generate number that's multiple of specified value
        min_mult = int(minimum / multiple_of)
        max_mult = int(maximum / multiple_of)
        return random.randint(min_mult, max_mult) * multiple_of
    
    # Check for specific property names
    prop_name = schema.get('title', '').lower()
    if 'price' in prop_name or 'amount' in prop_name or 'cost' in prop_name:
        return round(random.uniform(10, 1000), 2)
    elif 'percentage' in prop_name or 'percent' in prop_name:
        return round(random.uniform(0, 100), 2)
    elif 'rating' in prop_name:
        return round(random.uniform(1, 5), 1)
    
    return round(random.uniform(minimum, maximum), 2)

def generate_integer(schema: Dict[str, Any]) -> int:
    """Generate sample integer based on schema"""
    minimum = schema.get('minimum', 0)
    maximum = schema.get('maximum', 1000)
    multiple_of = schema.get('multipleOf')
    
    if multiple_of:
        # Generate integer that's multiple of specified value
        min_mult = int(minimum / multiple_of)
        max_mult = int(maximum / multiple_of)
        return random.randint(min_mult, max_mult) * multiple_of
    
    # Check for specific property names
    prop_name = schema.get('title', '').lower()
    if 'age' in prop_name:
        return random.randint(18, 80)
    elif 'count' in prop_name or 'quantity' in prop_name:
        return random.randint(1, 100)
    elif 'year' in prop_name:
        return random.randint(2000, 2024)
    
    return random.randint(minimum, maximum)

def generate_boolean(schema: Dict[str, Any]) -> bool:
    """Generate sample boolean"""
    return random.choice([True, False])

def validate_and_generate_sample(schema: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate schema and generate sample data with optional context
    
    Args:
        schema: JSON Schema definition
        context: Optional context for generating more relevant sample data
        
    Returns:
        Dictionary with sample data and any validation errors
    """
    try:
        # Basic schema validation
        if not isinstance(schema, dict):
            return {
                "error": "Schema must be a dictionary",
                "sample": None
            }
        
        # Generate sample data
        sample = generate_sample_from_schema(schema)
        
        # Apply context if provided
        if context and isinstance(sample, dict):
            # Override with context values where applicable
            for key, value in context.items():
                if key in sample:
                    sample[key] = value
        
        return {
            "sample": sample,
            "error": None
        }
        
    except Exception as e:
        return {
            "error": f"Failed to generate sample: {str(e)}",
            "sample": None
        }

# Example usage and test cases
if __name__ == "__main__":
    # Test with various schemas
    test_schemas = [
        {
            "name": "User Registration",
            "schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "minLength": 3, "maxLength": 20},
                    "email": {"type": "string", "format": "email"},
                    "age": {"type": "integer", "minimum": 18, "maximum": 100},
                    "is_active": {"type": "boolean"},
                    "registration_date": {"type": "string", "format": "date-time"}
                },
                "required": ["username", "email"]
            }
        },
        {
            "name": "Product List",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "price": {"type": "number", "minimum": 0},
                        "in_stock": {"type": "boolean"}
                    }
                },
                "minItems": 1,
                "maxItems": 3
            }
        }
    ]
    
    for test in test_schemas:
        print(f"\n{test['name']}:")
        print(f"Schema: {json.dumps(test['schema'], indent=2)}")
        result = validate_and_generate_sample(test['schema'])
        if result['error']:
            print(f"Error: {result['error']}")
        else:
            print(f"Sample: {json.dumps(result['sample'], indent=2)}")