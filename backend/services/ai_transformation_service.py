"""
AI Transformation Service
Handles AI-powered code generation for transform nodes
"""

import json
import logging
from typing import Dict, Any, Optional, List
import httpx
import asyncio
from datetime import datetime
from openai import AsyncOpenAI

from utils.crypto_utils import decrypt_data
from db.user_settings_models import UserSettingsHelper
from core.config import settings

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import UserSettings
else:
    from db.models import UserSettings

logger = logging.getLogger(__name__)


class AITransformationService:
    """Service for generating transform code using various AI providers"""
    
    def __init__(self, user_id: str, db):
        """Initialize with user's AI configuration from user_settings table"""
        self.user_id = user_id
        self.db = db
        
        # Get AI configuration from user_settings
        ai_config = UserSettingsHelper.get_ai_config(db, user_id)
        
        self.provider = ai_config.get('provider')
        self.model_name = ai_config.get('model_name')
        self.api_endpoint = ai_config.get('api_endpoint')
        
        # Decrypt API key
        self.api_key = None
        if ai_config.get('api_key_hash'):
            try:
                self.api_key = decrypt_data(ai_config['api_key_hash'])
            except Exception as e:
                logger.error(f"Failed to decrypt API key: {str(e)}")
        
        # Get model configuration - optimized for concise code generation
        model_config = ai_config.get('model_config', {})
        self.temperature = model_config.get('temperature', 0.3)  # Lower for more focused output
        self.max_tokens = model_config.get('max_tokens', 1500)   # Reduced for concise code
        self.top_p = model_config.get('top_p', 0.8)             # More focused responses
        
        # Extra settings
        self.extra_settings = ai_config.get('extra_settings', {})
    
    def _build_system_prompt(self, input_schema: Dict, available_variables: Dict, flow_context: Dict, next_node_info: Dict = None, custom_system_prompt: str = None) -> str:
        """Build comprehensive system prompt with context"""
        
        # If a custom system prompt is provided, use it instead
        if custom_system_prompt:
            return custom_system_prompt
        
        # Extract context information
        flow_name = flow_context.get('flow_name', 'Unknown Flow')
        node_name = flow_context.get('node_name', 'Transform Node')
        node_description = flow_context.get('description', '')
        next_node_info = next_node_info or {}
        
        # Format available variables for prompt
        global_vars = available_variables.get('global', {})
        node_outputs = available_variables.get('node_outputs', {})
        
        # Build next node context information
        next_node_context = ""
        if next_node_info and next_node_info.get('node_type'):
            next_node_context = f"""

TARGET NODE CONTEXT:
- Next node type: {next_node_info.get('node_type', 'Unknown')}
- Next node name: {next_node_info.get('node_name', 'Unnamed')}
- Purpose: The transformation output will be used by this {next_node_info.get('node_type', 'node')}"""
            
            # Add expected parameters if available
            if next_node_info.get('expected_parameters'):
                expected_params = next_node_info['expected_parameters']
                if isinstance(expected_params, dict) and expected_params:
                    next_node_context += """
- Expected input parameters:"""
                    for param_name, param_info in expected_params.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'any')
                            param_desc = param_info.get('description', 'No description')
                            param_required = param_info.get('required', True)
                            required_text = " (required)" if param_required else " (optional)"
                            next_node_context += f"""
  • {param_name}: {param_type}{required_text} - {param_desc}"""
                        elif isinstance(param_info, str):
                            # Handle simple string descriptions like "string - RFC822 formatted email"
                            next_node_context += f"""
  • {param_name}: {param_info}"""
                        else:
                            next_node_context += f"""
  • {param_name}: {str(param_info)}"""
                elif isinstance(expected_params, list) and expected_params:
                    next_node_context += f"""
- Expected input parameters: {', '.join(expected_params)}"""
            
            # Add service/app information if available
            if next_node_info.get('service_name') or next_node_info.get('app_name'):
                service_info = next_node_info.get('service_name') or next_node_info.get('app_name')
                next_node_context += f"""
- Target service/application: {service_info}"""
            
            next_node_context += """
- IMPORTANT: Structure your output to match what the next node expects!"""

        # Build the comprehensive system prompt
        system_prompt = f"""You are an expert Python developer creating CONCISE data transformations for IOFlow automation platform.

CONTEXT:
- Flow name: {flow_name}
- Current node: {node_name}
- Purpose: {node_description}{next_node_context}

CRITICAL: Generate MINIMAL, DIRECT code that works immediately in IOFlow transform nodes.

EXECUTION ENVIRONMENT:
You are working in IOFlow's RestrictedPython environment with specific capabilities and limitations.

IMPORTANT: RestrictedPython supports comprehensive data processing with these standard Python modules:

TIME & DATE PROCESSING:
- import datetime (date/time operations, timedelta calculations)
- import time (time operations, timestamps)
- import calendar (calendar functions, weekdays, month info)

DATA PROCESSING & PARSING:
- import json (JSON parsing and serialization)
- import re (regular expressions for pattern matching)
- import urllib.parse (URL parsing, encoding, query parameters)
- import csv (CSV file processing with io module)
- import html (HTML entity encoding/decoding)
- import io (in-memory file operations for CSV/text processing)

TEXT & STRING PROCESSING:
- import string (string constants and utilities)
- import textwrap (text formatting and wrapping)

SECURITY & HASHING:
- import hashlib (secure hashing: MD5, SHA256, etc.)
- import base64 (base64 encoding/decoding)
- import binascii (binary data encoding/decoding)
- import uuid (generating unique identifiers)

ADVANCED DATA STRUCTURES:
- import collections (Counter, OrderedDict, defaultdict)
- import itertools (combinations, permutations, groupby)
- import functools (partial, reduce functions)
- import operator (operator functions for functional programming)

MATHEMATICAL & STATISTICAL:
- import math (mathematical functions: sqrt, log, sin, cos, etc.)
- import statistics (mean, median, stdev, mode)
- import decimal (precise decimal arithmetic)
- import fractions (fraction handling)
- import random (random numbers with seed control)

ADVANCED PROCESSING:
- import difflib (string similarity comparison)
- import unicodedata (unicode normalization)
- import email.utils (address validation and parsing utilities)
- import heapq (priority queue operations)
- import bisect (binary search utilities)

All modules work exactly like in regular Python. Use them for comprehensive data transformations.

AVAILABLE VARIABLES:
- input: Contains data from trigger/input: {json.dumps(input_schema, indent=2)}
- local: Dictionary for temporary variables (initialize before use)
- global: Flow-wide variables: {json.dumps(global_vars, indent=2)}
- node_outputs: Outputs from previous nodes: {json.dumps(node_outputs, indent=2)}
- output: Dictionary where you must store the final result

FLOW CONTEXT:
- Previous nodes: Data sources available to this transform
- Next nodes: Where this transform's output will be used

AVAILABLE FUNCTIONS:
String Operations:
- string['upper'](text) - Convert to uppercase
- string['lower'](text) - Convert to lowercase  
- string['capitalize'](text) - Capitalize first letter
- string['title'](text) - Title case
- string['strip'](text) - Remove whitespace
- string['split'](text, separator) - Split string
- string['join'](separator, items) - Join list of strings
- string['replace'](text, old, new) - Replace substring
- string['startswith'](text, prefix) - Check prefix
- string['endswith'](text, suffix) - Check suffix
- string['find'](text, substring) - Find substring index

Math Operations:
- math['add'](a, b) - Addition
- math['subtract'](a, b) - Subtraction
- math['multiply'](a, b) - Multiplication
- math['divide'](a, b) - Division (returns None if b=0)
- math['power'](a, b) - Exponentiation
- math['sqrt'](x) - Square root

Other Functions:
- len(collection) - Get length
- min(collection) - Get minimum value
- max(collection) - Get maximum value
- sum(collection) - Sum values
- sorted(collection) - Sort collection
- isinstance(obj, type) - Type checking
- set_global(name, value) - Set a global variable

FILE UPLOAD HANDLING:
When processing file uploads from manual triggers, files are structured as:
{{
  "name": "filename.ext",      # Original filename
  "type": "mime/type",         # MIME type (e.g., "text/plain", "image/jpeg")
  "size": 12345,              # File size in bytes
  "data": "base64EncodedData", # File content already base64-encoded (NO PREFIX)
  "lastModified": 1234567890   # Timestamp
}}

CRITICAL FILE PROCESSING RULES:
1. Access file content using file_obj.get('data') - NOT file_obj.get('content')
2. The 'data' field is ALREADY base64-encoded - do NOT re-encode it
3. Use file_obj.get('name') for filename and file_obj.get('type') for MIME type
4. Always check if file exists: if file_attach and isinstance(file_attach, dict) and 'data' in file_attach
5. For multiple files, iterate through the list and process each file object

GENERIC FILE ATTACHMENT EXAMPLE:
```python
# Single file processing
if file_attach and isinstance(file_attach, dict) and 'data' in file_attach:
    file_name = file_attach.get('name', 'attachment.txt')
    file_type = file_attach.get('type', 'application/octet-stream')
    file_size = file_attach.get('size', 0)
    file_data = file_attach.get('data')  # Already base64-encoded
    
    # Process the file data as needed
    output['file_info'] = {{
        'filename': file_name,
        'mimetype': file_type,
        'size_bytes': file_size,
        'content': file_data  # Use directly - already base64
    }}

# Multiple files processing
if isinstance(file_attach, list):
    output['files'] = []
    for file_obj in file_attach:
        if isinstance(file_obj, dict) and 'data' in file_obj:
            output['files'].append({{
                'filename': file_obj.get('name', 'file.txt'),
                'mimetype': file_obj.get('type', 'application/octet-stream'),
                'size_bytes': file_obj.get('size', 0),
                'content': file_obj.get('data')  # Already base64
            }})
```

DATA FORMATTING HELPERS:
- Text processing: Use string module for text manipulation and formatting
- Data encoding: Use base64 module for encoding/decoding (import base64; base64.b64encode(data).decode())
- JSON handling: Use json module for parsing and serializing data structures
- Date/time formatting: Use datetime module for timestamp and date operations
- URL handling: Use urllib.parse for URL encoding, decoding, and parsing

CRITICAL REQUIREMENTS:
1. Generate CONCISE code - NO verbose comments, NO helper functions, NO extensive explanations
2. Code must work immediately in transform node - NO production-style error handling
3. Use ONLY the modules listed above - they work exactly like regular Python
4. CANNOT import: requests, os, sys, subprocess, socket, threading, etc.
5. Always use .get() for dictionary access to avoid KeyErrors
6. Store final result in 'output' dictionary
7. Keep code under 50 lines when possible
8. NO try/except blocks unless absolutely necessary
9. NO function definitions - write inline code only

CODE STYLE:
- Simple variable names
- Minimal comments only when necessary
- Direct, inline operations
- No helper functions or classes

CODING BEST PRACTICES:
- Use list.extend() or list.append() instead of += for list operations to avoid _inplacevar_ errors
- Declare all variables explicitly before use
- For base64 encoding use: base64.urlsafe_b64encode(data.encode('utf-8')).decode().rstrip('=')
- For MIME multipart: use uuid.uuid4().hex for boundaries and standard Content-Type headers
- Validate input fields exist before processing: use input.get('field', '') or default values

RESPONSE FORMAT:
Provide a brief summary followed by the Python code in this exact format:

SUMMARY: [1-2 sentence explanation of what the code does and any issues it addresses]

```python
[Your Python code here]
```

The summary should explain what the transformation does and mention any specific issues or requirements addressed.
"""
        
        return system_prompt
    
    def _build_user_prompt_with_context(self, natural_language_prompt: str,
                                      input_schema: Dict, available_variables: Dict,
                                      conversation_history: List[Dict], next_node_info: Dict = None) -> str:
        """Build user prompt with conversation context"""
        
        prompt_parts = []
        
        # Add conversation context if available
        if conversation_history:
            prompt_parts.append("CONVERSATION HISTORY:")
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                if msg.get('message_type') == 'user_prompt':
                    prompt_parts.append(f"User: {msg.get('content', '')}")
                elif msg.get('message_type') == 'ai_response':
                    prompt_parts.append(f"Assistant: {msg.get('explanation', '')}")
                    if msg.get('generated_code'):
                        prompt_parts.append(f"Generated code:\n```python\n{msg.get('generated_code')}\n```")
            prompt_parts.append("")
        
        # Add current request
        prompt_parts.append("CURRENT REQUEST:")
        prompt_parts.append(natural_language_prompt)
        prompt_parts.append("")
        
        # Add context information
        prompt_parts.append("CONTEXT:")
        prompt_parts.append(f"- Input data structure: {json.dumps(input_schema, indent=2)}")
        prompt_parts.append(f"- Available global variables: {json.dumps(available_variables.get('global', {}), indent=2)}")
        
        # Enhanced previous nodes information
        node_outputs = available_variables.get('node_outputs', {})
        if node_outputs:
            prompt_parts.append(f"- Previous nodes available: {list(node_outputs.keys())} ({len(node_outputs)} nodes)")
            # Show a sample of what's available in the first node
            first_node_id = list(node_outputs.keys())[0]
            first_node_data = node_outputs[first_node_id]
            if isinstance(first_node_data, dict):
                sample_keys = list(first_node_data.keys())[:3]
                prompt_parts.append(f"- Example data from {first_node_id}: {sample_keys}")
        else:
            prompt_parts.append("- Previous nodes: None (this transform only has access to input data)")
            prompt_parts.append("- Note: To access outputs from other nodes, connect them before this transform")
        
        # Add next node information if available
        next_node_info = next_node_info or {}
        if next_node_info and next_node_info.get('nextNodes') and len(next_node_info['nextNodes']) > 0:
            next_nodes = next_node_info['nextNodes']
            node_descriptions = []
            for node in next_nodes:
                node_desc = f"{node.get('label', 'Unnamed')} ({node.get('type', 'Unknown')})"
                if node.get('serviceName'):
                    node_desc += f" - {node['serviceName']}"
                node_descriptions.append(node_desc)
            prompt_parts.append(f"- Next nodes (where output will be used): {', '.join(node_descriptions)}")
            prompt_parts.append("- IMPORTANT: Structure your output to match what the next nodes expect!")
        else:
            prompt_parts.append("- Next nodes: None (this transform output won't be used by other nodes)")
        
        # Legacy compatibility for old next_node_info format
        if next_node_info and next_node_info.get('node_type'):
            prompt_parts.append(f"- Legacy next node: {next_node_info.get('node_name', 'Unnamed')} ({next_node_info.get('node_type', 'Unknown')})")
            if next_node_info.get('expected_parameters'):
                expected_params = next_node_info['expected_parameters']
                if isinstance(expected_params, dict) and expected_params:
                    prompt_parts.append("- Next node parameter requirements:")
                    for param_name, param_info in expected_params.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'any')
                            param_desc = param_info.get('description', 'No description')
                            param_required = param_info.get('required', True)
                            required_text = " (required)" if param_required else " (optional)"
                            prompt_parts.append(f"  • {param_name}: {param_type}{required_text} - {param_desc}")
                        elif isinstance(param_info, str):
                            prompt_parts.append(f"  • {param_name}: {param_info}")
                        else:
                            prompt_parts.append(f"  • {param_name}: {str(param_info)}")
                elif isinstance(expected_params, list) and expected_params:
                    prompt_parts.append(f"- Next node expects: {', '.join(expected_params)}")
            if next_node_info.get('service_name') or next_node_info.get('app_name'):
                service_info = next_node_info.get('service_name') or next_node_info.get('app_name')
                prompt_parts.append(f"- Target service: {service_info}")
        
        prompt_parts.append("")
        
        # Add instructions
        prompt_parts.append("IMPORTANT: Provide a brief summary and the Python code in the specified format.")
        prompt_parts.append("Requirements:")
        prompt_parts.append("- Brief summary explaining what the code does and issues addressed")
        prompt_parts.append("- Concise, direct code (under 50 lines)")
        prompt_parts.append("- No helper functions or extensive comments")
        prompt_parts.append("- Code ready for immediate use in transform node")
        prompt_parts.append("")
        prompt_parts.append("Focus on the essential transformation logic only.")
        prompt_parts.append("")
        prompt_parts.append("Follow these coding best practices:")
        prompt_parts.append("- Use list.extend() or list.append() instead of += for list operations to avoid _inplacevar_ errors")
        prompt_parts.append("- Declare all variables explicitly before use")
        prompt_parts.append("- For base64 encoding use: base64.urlsafe_b64encode(data.encode('utf-8')).decode().rstrip('=')")
        prompt_parts.append("- For MIME multipart: use uuid.uuid4().hex for boundaries and standard Content-Type headers")
        prompt_parts.append("- Validate input fields exist before processing: use input.get('field', '') or default values")
        prompt_parts.append("")
        prompt_parts.append("IMPORTANT: If processing file uploads, remember:")
        prompt_parts.append("- Files have structure: {{name, type, size, data, lastModified}}")
        prompt_parts.append("- Access content with file_obj.get('data') - already base64-encoded")
        prompt_parts.append("- DO NOT re-encode the 'data' field - use it directly")
        prompt_parts.append("- Use file_obj.get('name') and file_obj.get('type') for metadata")
        
        if conversation_history:
            prompt_parts.append("Consider the conversation history and build upon or refine previous solutions as appropriate.")
        
        return "\n".join(prompt_parts)
    
    def _build_followup_prompt(self, followup_prompt: str, conversation_history: List[Dict],
                             input_schema: Dict, available_variables: Dict, next_node_info: Dict = None) -> str:
        """Build followup prompt with full conversation context"""
        
        prompt_parts = []
        
        prompt_parts.append("FULL CONVERSATION HISTORY:")
        for i, msg in enumerate(conversation_history):
            if msg.get('message_type') == 'user_prompt':
                prompt_parts.append(f"User Request #{i//2 + 1}: {msg.get('content', '')}")
            elif msg.get('message_type') == 'ai_response':
                prompt_parts.append(f"Assistant Response #{i//2 + 1}:")
                prompt_parts.append(f"Explanation: {msg.get('explanation', '')}")
                if msg.get('generated_code'):
                    prompt_parts.append(f"Code:\n```python\n{msg.get('generated_code')}\n```")
                if msg.get('warnings'):
                    prompt_parts.append(f"Warnings: {', '.join(msg.get('warnings', []))}")
                prompt_parts.append("")
        
        prompt_parts.append("FOLLOW-UP REQUEST:")
        prompt_parts.append(followup_prompt)
        prompt_parts.append("")
        
        prompt_parts.append("CONTEXT:")
        prompt_parts.append(f"- Input data structure: {json.dumps(input_schema, indent=2)}")
        prompt_parts.append(f"- Available global variables: {json.dumps(available_variables.get('global', {}), indent=2)}")
        
        # Enhanced previous nodes information for followup
        node_outputs = available_variables.get('node_outputs', {})
        if node_outputs:
            prompt_parts.append(f"- Previous nodes available: {list(node_outputs.keys())} ({len(node_outputs)} nodes)")
            # Show a sample of what's available in the first node
            first_node_id = list(node_outputs.keys())[0]
            first_node_data = node_outputs[first_node_id]
            if isinstance(first_node_data, dict):
                sample_keys = list(first_node_data.keys())[:3]
                prompt_parts.append(f"- Example data from {first_node_id}: {sample_keys}")
        else:
            prompt_parts.append("- Previous nodes: None (this transform only has access to input data)")
            prompt_parts.append("- Note: To access outputs from other nodes, connect them before this transform")
        
        # Add next node information if available for followup
        next_node_info = next_node_info or {}
        if next_node_info and next_node_info.get('nextNodes') and len(next_node_info['nextNodes']) > 0:
            next_nodes = next_node_info['nextNodes']
            node_descriptions = []
            for node in next_nodes:
                node_desc = f"{node.get('label', 'Unnamed')} ({node.get('type', 'Unknown')})"
                if node.get('serviceName'):
                    node_desc += f" - {node['serviceName']}"
                node_descriptions.append(node_desc)
            prompt_parts.append(f"- Next nodes (where output will be used): {', '.join(node_descriptions)}")
        else:
            prompt_parts.append("- Next nodes: None (this transform output won't be used by other nodes)")
        
        # Legacy compatibility for old next_node_info format
        if next_node_info and next_node_info.get('node_type'):
            prompt_parts.append(f"- Legacy next node: {next_node_info.get('node_name', 'Unnamed')} ({next_node_info.get('node_type', 'Unknown')})")
            if next_node_info.get('expected_parameters'):
                expected_params = next_node_info['expected_parameters']
                if isinstance(expected_params, dict) and expected_params:
                    prompt_parts.append("- Next node parameter requirements:")
                    for param_name, param_info in expected_params.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'any')
                            param_desc = param_info.get('description', 'No description')
                            param_required = param_info.get('required', True)
                            required_text = " (required)" if param_required else " (optional)"
                            prompt_parts.append(f"  • {param_name}: {param_type}{required_text} - {param_desc}")
                        elif isinstance(param_info, str):
                            prompt_parts.append(f"  • {param_name}: {param_info}")
                        else:
                            prompt_parts.append(f"  • {param_name}: {str(param_info)}")
                elif isinstance(expected_params, list) and expected_params:
                    prompt_parts.append(f"- Next node expects: {', '.join(expected_params)}")
            if next_node_info.get('service_name') or next_node_info.get('app_name'):
                service_info = next_node_info.get('service_name') or next_node_info.get('app_name')
                prompt_parts.append(f"- Target service: {service_info}")
        
        prompt_parts.append("")
        
        prompt_parts.append("INSTRUCTIONS:")
        prompt_parts.append("Based on the conversation history and this follow-up request:")
        prompt_parts.append("1. Modify, refine, or completely rewrite the code as needed")
        prompt_parts.append("2. Address the specific concerns mentioned in the follow-up")
        prompt_parts.append("3. Maintain IOFlow's RestrictedPython requirements")
        prompt_parts.append("")
        prompt_parts.append("CRITICAL: Provide a brief summary and the revised Python code in the specified format.")
        prompt_parts.append("- Brief summary explaining changes made and issues addressed")
        prompt_parts.append("- Keep code concise (under 50 lines)")
        prompt_parts.append("- No helper functions or verbose comments")
        prompt_parts.append("- Code ready for immediate use")
        prompt_parts.append("")
        prompt_parts.append("Follow these coding best practices:")
        prompt_parts.append("- Use list.extend() or list.append() instead of += for list operations to avoid _inplacevar_ errors")
        prompt_parts.append("- Declare all variables explicitly before use")
        prompt_parts.append("- For base64 encoding use: base64.urlsafe_b64encode(data.encode('utf-8')).decode().rstrip('=')")
        prompt_parts.append("- For MIME multipart: use uuid.uuid4().hex for boundaries and standard Content-Type headers")
        prompt_parts.append("- Validate input fields exist before processing: use input.get('field', '') or default values")
        prompt_parts.append("")
        prompt_parts.append("IMPORTANT: If processing file uploads, remember:")
        prompt_parts.append("- Files have structure: {{name, type, size, data, lastModified}}")
        prompt_parts.append("- Access content with file_obj.get('data') - already base64-encoded")
        prompt_parts.append("- DO NOT re-encode the 'data' field - use it directly")
        prompt_parts.append("- Use file_obj.get('name') and file_obj.get('type') for metadata")
        
        return "\n".join(prompt_parts)
    
    async def generate_transform_code(self, 
                                    natural_language_prompt: str,
                                    input_schema: Dict[str, Any] = None,
                                    available_variables: Dict[str, Any] = None,
                                    flow_context: Dict[str, Any] = None,
                                    conversation_history: List[Dict] = None,
                                    next_node_info: Dict[str, Any] = None,
                                    custom_system_prompt: str = None) -> Dict[str, Any]:
        """Generate transform code from natural language prompt with conversation context"""
        
        if not self.api_key:
            raise ValueError("API key not configured")
        
        # Set defaults
        input_schema = input_schema or {}
        available_variables = available_variables or {}
        flow_context = flow_context or {}
        conversation_history = conversation_history or []
        next_node_info = next_node_info or {}
        
        # Build system prompt
        system_prompt = self._build_system_prompt(input_schema, available_variables, flow_context, next_node_info, custom_system_prompt)
        
        # Build user prompt with conversation context
        user_prompt = self._build_user_prompt_with_context(
            natural_language_prompt, 
            input_schema, 
            available_variables, 
            conversation_history,
            next_node_info
        )
        
        # Call appropriate AI provider
        if self.provider == 'openai':
            return await self._call_openai(system_prompt, user_prompt)
        elif self.provider == 'claude':
            return await self._call_claude(system_prompt, user_prompt)
        elif self.provider == 'azure_openai':
            return await self._call_azure_openai(system_prompt, user_prompt)
        elif self.provider == 'gemini':
            return await self._call_gemini(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")
    
    async def generate_followup_transform_code(self,
                                             followup_prompt: str,
                                             conversation_history: List[Dict],
                                             input_schema: Dict[str, Any] = None,
                                             available_variables: Dict[str, Any] = None,
                                             flow_context: Dict[str, Any] = None,
                                             next_node_info: Dict[str, Any] = None,
                                             custom_system_prompt: str = None) -> Dict[str, Any]:
        """Generate transform code based on a followup prompt with full conversation context"""
        
        if not self.api_key:
            raise ValueError("API key not configured")
        
        # Set defaults
        input_schema = input_schema or {}
        available_variables = available_variables or {}
        flow_context = flow_context or {}
        next_node_info = next_node_info or {}
        
        # Build system prompt
        system_prompt = self._build_system_prompt(input_schema, available_variables, flow_context, next_node_info, custom_system_prompt)
        
        # Build followup prompt with full conversation context
        user_prompt = self._build_followup_prompt(
            followup_prompt,
            conversation_history,
            input_schema,
            available_variables,
            next_node_info
        )
        
        # Call appropriate AI provider
        if self.provider == 'openai':
            return await self._call_openai(system_prompt, user_prompt)
        elif self.provider == 'claude':
            return await self._call_claude(system_prompt, user_prompt)
        elif self.provider == 'azure_openai':
            return await self._call_azure_openai(system_prompt, user_prompt)
        elif self.provider == 'gemini':
            return await self._call_gemini(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to configured AI service"""
        
        if not self.api_key:
            return {"success": False, "message": "API key not configured"}
        
        try:
            # Simple test prompt
            test_prompt = "Generate a simple Python function that returns 'Hello World'"
            
            result = await self.generate_transform_code(
                natural_language_prompt=test_prompt,
                input_schema={},
                available_variables={},
                flow_context={"flow_name": "Connection Test"}
            )
            
            return {
                "success": True,
                "message": f"Successfully connected to {self.provider} ({self.model_name})",
                "model_info": {
                    "provider": self.provider,
                    "model": self.model_name,
                    "endpoint": self.api_endpoint
                }
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }
    
    async def test_connection_with_settings(self, provider: str, model_name: str, api_key: str, 
                                          api_endpoint: str = None, temperature: float = 0.7, 
                                          max_tokens: int = 4000, top_p: float = 1.0) -> Dict[str, Any]:
        """Test connection with temporary settings (not saved to database)"""
        
        if not api_key:
            return {"success": False, "message": "API key is required"}
        
        # Store original settings
        original_provider = self.provider
        original_model_name = self.model_name
        original_api_key = self.api_key
        original_api_endpoint = self.api_endpoint
        original_temperature = self.temperature
        original_max_tokens = self.max_tokens
        original_top_p = self.top_p
        
        try:
            # Temporarily set test settings
            self.provider = provider
            self.model_name = model_name or "gpt-5-mini"  # Default to latest GPT-5 model (August 2025)
            self.api_key = api_key
            self.api_endpoint = api_endpoint
            self.temperature = temperature
            self.max_tokens = max_tokens
            self.top_p = top_p
            
            # Simple test prompt
            test_prompt = "Generate a simple Python function that returns 'Hello World'"
            
            result = await self.generate_transform_code(
                natural_language_prompt=test_prompt,
                input_schema={},
                available_variables={},
                flow_context={"flow_name": "Connection Test"}
            )
            
            return {
                "success": True,
                "message": f"Successfully connected to {self.provider} ({self.model_name})",
                "model_info": {
                    "provider": self.provider,
                    "model": self.model_name,
                    "endpoint": self.api_endpoint
                }
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }
        
        finally:
            # Restore original settings
            self.provider = original_provider
            self.model_name = original_model_name
            self.api_key = original_api_key
            self.api_endpoint = original_api_endpoint
            self.temperature = original_temperature
            self.max_tokens = original_max_tokens
            self.top_p = original_top_p
    
    def _should_use_max_completion_tokens(self, model_name: str) -> bool:
        """Check if model requires max_completion_tokens instead of max_tokens"""
        # GPT-5 series and o-series models require max_completion_tokens
        gpt5_models = ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5-chat']
        o_series_models = ['o3', 'o3-mini', 'o4-mini', 'o1', 'o1-mini', 'o1-preview']
        
        return any(model_name.startswith(prefix) for prefix in gpt5_models + o_series_models)
    
    def _supports_custom_temperature(self, model_name: str) -> bool:
        """Check if model supports custom temperature values"""
        # GPT-5 series and o-series models only support temperature=1.0 (default)
        gpt5_models = ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5-chat']
        o_series_models = ['o3', 'o3-mini', 'o4-mini', 'o1', 'o1-mini', 'o1-preview']
        
        return not any(model_name.startswith(prefix) for prefix in gpt5_models + o_series_models)
    
    def _supports_top_p(self, model_name: str) -> bool:
        """Check if model supports top_p parameter"""
        # O-series models don't support top_p parameter
        o_series_models = ['o3', 'o3-mini', 'o4-mini', 'o1', 'o1-mini', 'o1-preview']
        
        return not any(model_name.startswith(prefix) for prefix in o_series_models)
    
    async def _call_openai(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call OpenAI API using official client with correct token parameters"""
        
        client = AsyncOpenAI(api_key=self.api_key)
        
        try:
            # Build base parameters
            params = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            
            # Add temperature only for models that support custom values
            if self._supports_custom_temperature(self.model_name):
                params["temperature"] = self.temperature
            # GPT-5 and O-series models use default temperature=1.0
            
            # Add top_p only for models that support it
            if self._supports_top_p(self.model_name):
                params["top_p"] = self.top_p
            # O-series models don't support top_p parameter
            
            # Use correct token parameter based on model type
            if self._should_use_max_completion_tokens(self.model_name):
                params["max_completion_tokens"] = self.max_tokens
            else:
                params["max_tokens"] = self.max_tokens
            
            response = await client.chat.completions.create(**params)
            
            content = response.choices[0].message.content
            return self._parse_ai_response(content)
            
        finally:
            await client.close()
    
    async def _call_claude(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call Anthropic Claude API"""
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            content = result['content'][0]['text']
            
            return self._parse_ai_response(content)
    
    async def _call_azure_openai(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call Azure OpenAI API"""
        
        if not self.api_endpoint:
            raise ValueError("API endpoint required for Azure OpenAI")
        
        url = f"{self.api_endpoint}/openai/deployments/{self.model_name}/chat/completions?api-version=2023-12-01-preview"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            return self._parse_ai_response(content)
    
    async def _call_gemini(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call Google Gemini API"""
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        
        # Combine system and user prompts for Gemini
        combined_prompt = f"{system_prompt}\\n\\nUser Request:\\n{user_prompt}"
        
        payload = {
            "contents": [{
                "parts": [{"text": combined_prompt}]
            }],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "topP": self.top_p
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            content = result['candidates'][0]['content']['parts'][0]['text']
            
            return self._parse_ai_response(content)
    
    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse AI response to extract summary and code"""
        
        # Extract summary
        summary = "Transform code generated"
        lines = content.split('\n')
        
        # Look for SUMMARY: line
        for line in lines:
            if line.strip().startswith('SUMMARY:'):
                summary = line.replace('SUMMARY:', '').strip()
                break
        
        # Extract Python code blocks
        code_blocks = []
        in_code_block = False
        current_code = []
        
        for line in lines:
            if line.strip().startswith('```python') or line.strip().startswith('```Python'):
                in_code_block = True
                current_code = []
            elif line.strip().startswith('```') and in_code_block:
                in_code_block = False
                if current_code:
                    code_blocks.append('\n'.join(current_code))
            elif in_code_block:
                current_code.append(line)
        
        # Use the first code block, or treat content after SUMMARY as code if no blocks found
        if code_blocks:
            generated_code = code_blocks[0]
        else:
            # If no code blocks, extract content after SUMMARY line
            content_lines = content.split('\n')
            code_start_idx = 0
            
            for i, line in enumerate(content_lines):
                if line.strip().startswith('SUMMARY:'):
                    code_start_idx = i + 1
                    break
            
            # Skip empty lines after summary
            while code_start_idx < len(content_lines) and not content_lines[code_start_idx].strip():
                code_start_idx += 1
            
            if code_start_idx < len(content_lines):
                generated_code = '\n'.join(content_lines[code_start_idx:]).strip()
            else:
                generated_code = content.strip()
        
        return {
            "code": generated_code,
            "explanation": summary,
            "test_cases": [],  # No test cases for concise responses
            "warnings": ["Code is optimized for immediate use in transform nodes"]
        }
    
    def get_default_system_prompt(self, input_schema: Dict = None, available_variables: Dict = None, 
                                flow_context: Dict = None, next_node_info: Dict = None) -> str:
        """Get the default system prompt for viewing/editing"""
        input_schema = input_schema or {}
        available_variables = available_variables or {}
        flow_context = flow_context or {}
        next_node_info = next_node_info or {}
        
        return self._build_system_prompt(input_schema, available_variables, flow_context, next_node_info)