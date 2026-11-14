"""
JSON utility functions for handling database field serialization/deserialization.
Works with both PostgreSQL (JSONB) and SQLite (TEXT).
"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def ensure_dict(value: Any, field_name: str = "field") -> Dict[str, Any]:
    """
    Ensure a value is a dictionary. Handles:
    - None -> {}
    - dict -> dict (returned as-is)
    - str -> parsed JSON dict (for SQLite TEXT columns or double-serialized data)

    This function is database-agnostic and works with both:
    - PostgreSQL JSONB columns (returns dict natively)
    - SQLite TEXT columns (stored as JSON strings)
    - Double-serialized JSON (string stored in JSONB)

    Args:
        value: The value to ensure is a dict
        field_name: Name of the field for logging purposes

    Returns:
        Dictionary (empty dict if conversion fails)
    """
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        if not value.strip():
            return {}
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                logger.debug(f"Parsed {field_name} from JSON string to dict")
                return parsed
            else:
                logger.warning(f"{field_name} JSON parsed to {type(parsed).__name__}, not dict")
                return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {field_name} JSON string: {e}")
            return {}

    logger.warning(f"{field_name} is {type(value).__name__}, returning empty dict")
    return {}


def ensure_list(value: Any, field_name: str = "field") -> list:
    """
    Ensure a value is a list. Handles:
    - None -> []
    - list -> list (returned as-is)
    - str -> parsed JSON list (for SQLite TEXT columns or double-serialized data)

    Args:
        value: The value to ensure is a list
        field_name: Name of the field for logging purposes

    Returns:
        List (empty list if conversion fails)
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        if not value.strip():
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                logger.debug(f"Parsed {field_name} from JSON string to list")
                return parsed
            else:
                logger.warning(f"{field_name} JSON parsed to {type(parsed).__name__}, not list")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {field_name} JSON string: {e}")
            return []

    logger.warning(f"{field_name} is {type(value).__name__}, returning empty list")
    return []


def safe_json_field(value: Any, default: Any = None, field_name: str = "field") -> Any:
    """
    Safely parse a JSON field that could be:
    - Already parsed (dict/list) from PostgreSQL JSONB
    - JSON string from SQLite TEXT
    - Double-serialized JSON string

    Args:
        value: The value to parse
        default: Default value to return if parsing fails (default: None)
        field_name: Name of the field for logging purposes

    Returns:
        Parsed value or default
    """
    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        if not value.strip():
            return default
        try:
            parsed = json.loads(value)
            logger.debug(f"Parsed {field_name} from JSON string")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {field_name} JSON string: {e}")
            return default

    return value  # Return as-is for other types
