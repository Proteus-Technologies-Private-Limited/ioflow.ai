"""
Patch for service executors to handle custom parameters from subscription_config
"""
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


def _ensure_dict(value: Any, field_name: str = "field") -> Dict[str, Any]:
    """Ensure value is a dict, handling JSON strings for both SQLite and PostgreSQL."""
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
                return parsed
        except json.JSONDecodeError:
            pass
        return {}
    return {}


def merge_custom_params_with_credentials(
    auth_credentials: Dict[str, Any],
    subscription_config: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Merge custom parameters from subscription_config with auth_credentials.
    Custom params are stored separately to avoid being masked in API responses.
    """
    logger.info(f"=== CUSTOM PARAMS DEBUG ===")
    logger.info(f"Subscription config type: {type(subscription_config)}")
    logger.info(f"Subscription config: {subscription_config}")

    if not subscription_config:
        logger.info("No subscription_config provided")
        return auth_credentials

    # Ensure subscription_config is a dict (handles both PostgreSQL JSONB and SQLite TEXT/double-serialized)
    subscription_config = _ensure_dict(subscription_config, "subscription_config")

    custom_params = subscription_config.get('custom_params', {})
    logger.info(f"Custom params found: {custom_params}")
    
    if not custom_params:
        logger.info("No custom_params in subscription_config")
        return auth_credentials
    
    # Create a copy to avoid modifying the original
    merged_credentials = auth_credentials.copy()
    
    # Merge custom headers
    if 'header' in custom_params and custom_params['header']:
        if 'headers' not in merged_credentials:
            merged_credentials['headers'] = {}
        merged_credentials['headers'].update(custom_params['header'])
        logger.info(f"Added custom headers: {custom_params['header']}")
        logger.info(f"Merged headers now: {merged_credentials['headers']}")
    
    # Merge custom query params
    if 'query' in custom_params and custom_params['query']:
        if 'query_params' not in merged_credentials:
            merged_credentials['query_params'] = {}
        merged_credentials['query_params'].update(custom_params['query'])
        logger.info(f"Added custom query params: {custom_params['query']}")
    
    # Merge custom body params
    if 'body' in custom_params and custom_params['body']:
        if 'body_params' not in merged_credentials:
            merged_credentials['body_params'] = {}
        merged_credentials['body_params'].update(custom_params['body'])
        logger.info(f"Added custom body params: {custom_params['body']}")
    
    logger.info(f"Final merged credentials keys: {list(merged_credentials.keys())}")
    return merged_credentials