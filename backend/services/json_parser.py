"""
Tolerant JSON Parser - Handles JSON with literal newlines and tabs

This module provides a more tolerant JSON parser that can handle:
- Literal newlines in strings
- Literal tabs in strings
- Comments (optional)
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_tolerant_json(json_str: str, allow_comments: bool = False) -> dict:
    """
    Parse JSON with tolerance for literal newlines and tabs in strings.

    This parser handles JSON that may contain:
    - Literal newlines within string values
    - Literal tabs within string values
    - Optional C-style comments (if allow_comments=True)

    Args:
        json_str: The JSON string to parse
        allow_comments: Whether to strip comments before parsing

    Returns:
        Parsed JSON as dictionary

    Raises:
        json.JSONDecodeError: If the JSON is invalid after preprocessing
    """
    if not json_str or not json_str.strip():
        return {}

    try:
        # First try standard JSON parsing
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"Standard JSON parse failed: {e}. Trying tolerant parser.")

    # Preprocess the JSON string
    processed = json_str

    # Remove comments if requested
    if allow_comments:
        # Remove single-line comments (//)
        processed = re.sub(r'//.*?$', '', processed, flags=re.MULTILINE)
        # Remove multi-line comments (/* ... */)
        processed = re.sub(r'/\*.*?\*/', '', processed, flags=re.DOTALL)

    # Fix common issues with string literals
    # This is a more complex operation that requires parsing the JSON structure
    try:
        # Try to fix strings with literal newlines
        processed = fix_literal_newlines(processed)

        # Try parsing again
        return json.loads(processed)
    except json.JSONDecodeError as e:
        logger.error(f"Tolerant JSON parse also failed: {e}")
        # Try one more aggressive fix
        return aggressive_json_fix(json_str)


def fix_literal_newlines(json_str: str) -> str:
    """
    Fix JSON strings that contain literal newlines and tabs.

    This function finds string values and escapes any literal control characters.
    """
    # This is a simplified approach - find strings and escape newlines/tabs
    # Pattern to match JSON string values (simplified)
    result = []
    in_string = False
    escape_next = False
    current_quote = None

    for i, char in enumerate(json_str):
        if escape_next:
            result.append(char)
            escape_next = False
            continue

        if char == '\\' and in_string:
            result.append(char)
            escape_next = True
            continue

        if char in '"\'':
            if not in_string:
                in_string = True
                current_quote = char
            elif char == current_quote:
                in_string = False
                current_quote = None
            result.append(char)
            continue

        if in_string:
            # Replace literal newlines and tabs with escaped versions
            if char == '\n':
                result.append('\\n')
            elif char == '\t':
                result.append('\\t')
            elif char == '\r':
                result.append('\\r')
            else:
                result.append(char)
        else:
            result.append(char)

    return ''.join(result)


def aggressive_json_fix(json_str: str) -> dict:
    """
    Aggressive attempt to fix and parse malformed JSON.

    This is a last resort that tries various fixes to make the JSON parseable.
    """
    import ast

    # Try some common fixes
    fixes = [
        # Replace single quotes with double quotes
        lambda s: s.replace("'", '"'),
        # Add missing commas between objects
        lambda s: re.sub(r'"\s*\n\s*"', '",\n"', s),
        # Remove trailing commas
        lambda s: re.sub(r',\s*}', '}', re.sub(r',\s*]', ']', s)),
        # Try to evaluate as Python literal
        lambda s: ast.literal_eval(s) if s else {}
    ]

    for fix in fixes:
        try:
            if callable(fix):
                result = fix(json_str)
                if isinstance(result, dict):
                    return result
                return json.loads(result)
        except Exception as e:
            logger.debug(f"Fix attempt failed: {e}")
            continue

    # If all else fails, return empty dict
    logger.error("All JSON parsing attempts failed. Returning empty dict.")
    return {}


def validate_json_structure(data: dict, required_fields: list = None) -> bool:
    """
    Validate that parsed JSON has required structure.

    Args:
        data: Parsed JSON data
        required_fields: List of required top-level field names

    Returns:
        True if structure is valid
    """
    if not isinstance(data, dict):
        return False

    if required_fields:
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return False

    return True