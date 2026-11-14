#!/usr/bin/env python3
"""
Test script to verify JSON parsing with single quotes
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.execution_engine import ExecutionEngine

def test_json_parsing():
    """Test the _process_string_templates method with Google Sheets array data"""
    
    # Create an instance of ExecutionEngine
    engine = ExecutionEngine('public')
    
    # Test case 1: JSON-like string with single quotes
    test_value1 = "[['123','{{input.name}}', '9822211123']]"
    # Try different context structures
    context = {
        'data': {'input': {'name': 'Jane Doe'}},
        'variables': {},
        'node_outputs': {},
        'execution_id': 'test-execution-id'
    }
    
    print("Test Case 1: JSON-like string with single quotes")
    print(f"Input: {test_value1}")
    print(f"Context: {context}")
    
    result1 = engine._process_string_templates(test_value1, context)
    print(f"Result: {result1}")
    print(f"Result type: {type(result1)}")
    print()
    
    # Test case 2: Already valid JSON with double quotes
    test_value2 = '[["456","{{input.name}}", "9822211123"]]'
    
    print("Test Case 2: Valid JSON with double quotes")
    print(f"Input: {test_value2}")
    print(f"Context: {context}")
    
    result2 = engine._process_string_templates(test_value2, context)
    print(f"Result: {result2}")
    print(f"Result type: {type(result2)}")
    print()
    
    # Test case 3: Non-JSON string template
    test_value3 = "Hello {{input.name}}, welcome!"
    
    print("Test Case 3: Regular string template")
    print(f"Input: {test_value3}")
    print(f"Context: {context}")
    
    result3 = engine._process_string_templates(test_value3, context)
    print(f"Result: {result3}")
    print(f"Result type: {type(result3)}")
    print()
    
    # Test case 4: Complex nested JSON-like structure
    test_value4 = "{'data': [['id', '{{input.name}}', {'type': 'user'}]]}"
    
    print("Test Case 4: Complex nested structure")
    print(f"Input: {test_value4}")
    print(f"Context: {context}")
    
    try:
        result4 = engine._process_string_templates(test_value4, context)
        print(f"Result: {result4}")
        print(f"Result type: {type(result4)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_json_parsing()