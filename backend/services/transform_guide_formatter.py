"""
Transform Guide Formatter - Formats transform node guide as markdown for better LLM comprehension
"""

def format_transform_guide_as_markdown(guide_data: dict) -> dict:
    """
    Enhance the transform guide with better structure for external functions.
    Preserves all original content while emphasizing external functions approach.
    """

    # If guide_data already has content, merge it with our enhancements
    # Otherwise, provide a complete guide

    enhanced_guide = {
        "overview": "Transform nodes execute Python scripts in RestrictedPython environment",

        "CRITICAL_REQUIREMENT": {
            "title": "⚠️ MANDATORY: You MUST Use External Functions for ALL Transform Nodes",
            "rule": "NEVER write inline scripts with multiple lines of code",
            "correct_approach": "ALWAYS create an external function and call it from the script field",
            "why": "Inline multiline scripts cause JSON validation errors",
            "enforcement": "Any transform node with inline multiline code WILL fail validation"
        },

        "MANDATORY_PATTERN": {
            "title": "THIS IS THE ONLY ACCEPTABLE PATTERN FOR TRANSFORM NODES",
            "script_field": "MUST be a single line that calls your function(s)",
            "example_script": "output = your_function_name(input)",
            "functions_field": "Contains the actual Python code as external functions",
            "NEVER_DO": [
                "NEVER write multiple lines directly in the script field",
                "NEVER put actual logic in the script field",
                "NEVER use inline variable assignments except for output"
            ],
            "ALWAYS_DO": [
                "ALWAYS create a function with ALL your logic",
                "ALWAYS call that function from the script field",
                "ALWAYS set output = your_function_result"
            ]
        },

        "external_functions_approach": {
            "when_to_use": "ALWAYS - NO EXCEPTIONS",
            "benefits": [
                "Completely avoids JSON escaping issues",
                "Natural Python code with real newlines and quotes",
                "Cleaner, more readable code organization",
                "Reusable functions across multiple nodes",
                "No risk of validation errors from multiline strings"
            ],

            "how_it_works": {
                "step_1": {
                    "action": "Define your transform node with minimal script",
                    "example_node": {
                        "type": "transform",
                        "data": {
                            "label": "Process Data",
                            "script": "output = process_data(input)",
                            "functions_used": ["process_data"]
                        }
                    },
                    "note": "The script just calls the function"
                },

                "step_2": {
                    "action": "Write your function as plain Python text",
                    "instruction": "Write it EXACTLY as you would in a .py file",
                    "CRITICAL": "DO NOT manually escape the Python code for JSON!",
                    "formatting_note": "Functions are plain Python text with natural quotes and newlines",
                    "example_description": "A function with natural Python formatting",
                    "DO_NOT": [
                        "Do NOT escape quotes as \\\" or \\'",
                        "Do NOT escape newlines as \\n",
                        "Do NOT try to manually create JSON strings"
                    ],
                    "DO": [
                        "Write Python code naturally with real newlines",
                        "Use triple quotes for docstrings: \"\"\"docstring\"\"\"",
                        "Use single or double quotes naturally: 'string' or \"string\"",
                        "Let the system handle JSON serialization automatically"
                    ]
                },

                "step_3": {
                    "action": "Pass the Python code block directly as the functions parameter",
                    "CRITICAL_FORMAT": {
                        "description": "The functions parameter is a plain Python code string:",
                        "format": "Send pure Python code module with function definitions",
                        "structure": "Multiple functions in a single Python code block",
                        "no_wrapper": "DO NOT wrap in dictionary or JSON - just Python code",
                        "example_format": [
                            "def function1(input):",
                            "    # Implementation",
                            "    return result",
                            "",
                            "def function2(input):",
                            "    # Another function",
                            "    return output"
                        ],
                        "how_to_pass": "Pass the entire Python code string as 'functions' parameter"
                    },
                    "structure": {
                        "flow_definition": "<your flow JSON>",
                        "functions": "<Plain Python code string with function definitions>"
                    },
                    "example_call": "validate_flow_json(flow_json, functions=python_code_string)",
                    "IMPORTANT": "Send Python code as-is - no dict wrapper, no repr(), no JSON"
                }
            }
        },

        "concrete_example": {
            "description": "CORRECT way to create transform nodes - ALWAYS use this pattern",

            "WRONG_WAY": {
                "label": "❌ NEVER DO THIS - Inline multiline script",
                "transform_node": {
                    "script": "pdf = create_pdf(input.get('contacts', []))\nsubject = 'Your Contacts'\nbody = 'Please find attached...'\noutput = {'raw': raw}",
                    "problem": "This WILL FAIL validation due to multiline inline code"
                }
            },

            "CORRECT_WAY": {
                "label": "✅ ALWAYS DO THIS - External function with single-line call",
                "transform_node": {
                    "id": "transform_1",
                    "type": "transform",
                    "data": {
                        "label": "Process and Send Email",
                        "script": "output = process_contacts_to_email(input)",
                        "functions_used": ["process_contacts_to_email"]
                    }
                }
            },

            "functions_parameter_format": {
                "CRITICAL": "Must be plain Python code string, NOT dict or JSON!",
                "correct_format": "Pure Python module with function definitions",
                "example": "def func1(input):\n    return output\n\ndef func2(input):\n    return result",
                "why": "Plain Python code avoids ALL escaping and parsing issues"
            },

            "functions_parameter": """def clean_data(data):
    '''Remove private fields and clean strings'''
    if not isinstance(data, dict):
        return data

    cleaned = {}
    for key, value in data.items():
        # Skip private fields
        if key.startswith('_'):
            continue

        # Clean string values
        if isinstance(value, str):
            cleaned[key] = value.strip().lower()
        else:
            cleaned[key] = value

    return cleaned

def validate_data(data):
    '''Validate required fields'''
    required = ['email', 'name']

    for field in required:
        if field not in data:
            raise ValueError(f'Missing required field: {field}')

    # Validate email format
    if '@' not in data.get('email', ''):
        raise ValueError('Invalid email format')

    return data""",

            "api_call_structure": {
                "endpoint": "POST /api/v1/flow-design/validate",
                "body": {
                    "flow_definition": "<the transform node above>",
                    "functions": "<the functions dict above>"
                }
            }
        },


        "multiline_strings_guide": {
            "title": "📝 Important: Multiline Strings in Python Functions",
            "description": "When writing multiline strings in external functions, use proper Python syntax",
            "correct_approach": {
                "method": "Use triple quotes for multiline strings",
                "example": '''body = """Hello,
This is a multiline string.
It can span multiple lines.
"""''',
                "alternative": '''body = \'\'\'Hello,
This is also valid using single quotes.
\'\'\''''
            },
            "incorrect_approaches": {
                "avoid_these": [
                    {
                        "wrong": '''body = ("Hello,
This will cause a syntax error")''',
                        "issue": "Parentheses don't make strings multiline"
                    },
                    {
                        "wrong": '''body = "Hello,
This is split across lines"''',
                        "issue": "Regular quotes can't span lines without escape"
                    }
                ]
            },
            "best_practice": "Always use triple quotes (\"\"\" or ''') for multiline strings in your functions"
        },

        "available_modules": [
            "base64", "json", "datetime", "re", "urllib.parse",
            "math", "random", "collections", "itertools", "hashlib",
            "io", "csv", "pandas (as pd)", "openpyxl", "docx",
            "pypdf", "pptx", "reportlab"
        ],

        "context_variables": {
            "input": "Trigger variables only (NOT from other nodes)",
            "node_outputs": "Dictionary of outputs from previous nodes by node ID",
            "loop": "Loop context (item, index) when inside a loop",
            "global_vars": "Flow-level variables accessible across nodes",
            "output": "REQUIRED - must be set with the node's output"
        },

        "variable_access_explained": {
            "node_outputs": {
                "description": "Access outputs from nodes that have already executed",
                "how_it_works": "Each node's output is stored in node_outputs dictionary with the node's ID as the key",
                "examples": [
                    "# Get output from a previous API call node",
                    "api_data = node_outputs['api_call_1']['data']",
                    "# Safely access with defaults",
                    "status = node_outputs.get('action_1', {}).get('status', 'unknown')",
                    "# Access transform node output (same as any other node)",
                    "previous_result = node_outputs['transform_1']['processed_data']"
                ],
                "important": "Transform nodes output to node_outputs just like any other node type"
            },
            "output": {
                "description": "YOU MUST SET THIS - it's how your node passes data to the next nodes",
                "how_it_works": "Whatever you assign to 'output' becomes available in node_outputs for subsequent nodes",
                "examples": [
                    "# Simple output",
                    "output = {'status': 'success', 'data': processed_data}",
                    "# Output that next nodes can access",
                    "output = {",
                    "    'user': {'id': 123, 'name': 'John'},",
                    "    'processed': True",
                    "}",
                    "# Next node accesses this as: node_outputs['your_node_id']['user']"
                ],
                "critical": "If you don't set output, your node won't pass any data forward!"
            },
            "input": {
                "description": "Contains ONLY trigger variables, NOT outputs from other nodes",
                "examples": [
                    "# Access trigger variables",
                    "user_email = input.get('user_email')",
                    "uploaded_file = input.get('file_data', {})"
                ],
                "common_mistake": "Don't try to access other node outputs through 'input' - use 'node_outputs' instead"
            }
        },

        "restrictions": {
            "max_execution_time": "5 seconds",
            "max_output_size": "50MB",
            "forbidden": ["file I/O", "exec", "eval", "compile", "imports of os/sys/subprocess", "network operations"]
        },

        "key_takeaway": "For complex logic or reusable code, use external functions - pass them as plain Python code blocks!",

        "practical_data_flow_example": {
            "description": "How data flows through multiple nodes",
            "scenario": "API call → Transform → Another Transform",

            "node_1_api": {
                "id": "fetch_user_data",
                "type": "action",
                "output_example": {
                    "user": {"id": 123, "name": "john doe", "email": "john@example.com"},
                    "status": 200
                }
            },

            "node_2_transform": {
                "id": "process_user",
                "type": "transform",
                "script": """# Get API response from previous node
api_result = node_outputs['fetch_user_data']
user_data = api_result.get('user', {})

# Process the data
processed = {
    'id': user_data.get('id'),
    'display_name': user_data.get('name', '').title(),
    'email': user_data.get('email', '').lower(),
    'processed_at': str(datetime.now())
}

# IMPORTANT: Set output for next node to use
output = {
    'processed_user': processed,
    'original_status': api_result.get('status')
}""",
                "output_available_as": "node_outputs['process_user']"
            },

            "node_3_transform": {
                "id": "create_report",
                "type": "transform",
                "script": """# Get output from previous transform node
processed_data = node_outputs['process_user']['processed_user']

# Create report
report = f\"User Report for {processed_data['display_name']}\"

# Set final output
output = {'report': report, 'user_id': processed_data['id']}""",
                "key_point": "Each node accesses previous outputs via node_outputs[node_id]"
            }
        }
    }

    # If the original guide has content, merge it
    if guide_data:
        # Preserve all original fields that aren't being enhanced
        for key, value in guide_data.items():
            if key not in enhanced_guide:
                enhanced_guide[key] = value

        # Specifically ensure we keep the detailed available_modules if present
        if 'available_modules' in guide_data and isinstance(guide_data['available_modules'], dict):
            # Convert dict format to our list format but preserve the descriptions
            enhanced_guide['available_modules_detailed'] = guide_data['available_modules']

    return enhanced_guide