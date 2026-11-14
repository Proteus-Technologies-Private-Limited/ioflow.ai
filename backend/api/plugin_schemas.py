"""
Plugin Schemas API - Serves UI schemas registered by plugins.

Provides endpoints for the frontend to discover what configuration UI
to render for each auth type, service type, and node type.
Also provides a flow validation endpoint to detect broken plugin references.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import json
import logging

from plugins.registry import PluginRegistry
from db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/plugins", tags=["Plugin Schemas"])


@router.get("/ui-schemas")
async def list_ui_schemas(component_type: Optional[str] = None) -> Dict[str, Any]:
    """Get all registered UI schemas, optionally filtered by component type.

    Args:
        component_type: Filter by 'service_type', 'auth_type', or 'node_type'
    """
    if component_type:
        schemas = PluginRegistry.get_ui_schemas(component_type)
        return {"component_type": component_type, "schemas": schemas}

    # Return all schemas grouped by component type
    all_schemas = PluginRegistry.get_ui_schemas()

    # Also collect ui_schemas from auth handlers that haven't been explicitly registered
    auth_schemas = {}
    for auth_type in PluginRegistry.list_auth_handlers():
        handler = PluginRegistry.get_auth_handler(auth_type)
        if handler and hasattr(handler, 'ui_schema') and handler.ui_schema:
            auth_schemas[auth_type] = handler.ui_schema

    if auth_schemas:
        all_schemas.setdefault("auth_type", {}).update(auth_schemas)

    return {"schemas": all_schemas}


@router.get("/ui-schemas/{component_type}")
async def get_schemas_by_type(component_type: str) -> Dict[str, Any]:
    """Get all UI schemas for a specific component type.

    Args:
        component_type: One of 'service_type', 'auth_type', 'node_type'
    """
    if component_type == "auth_type":
        # Collect from auth handlers
        schemas = {}
        for auth_type in PluginRegistry.list_auth_handlers():
            handler = PluginRegistry.get_auth_handler(auth_type)
            if handler and hasattr(handler, 'ui_schema') and handler.ui_schema:
                schemas[auth_type] = handler.ui_schema
        # Also include any explicitly registered ones
        schemas.update(PluginRegistry.get_ui_schemas("auth_type"))
        return {"component_type": component_type, "schemas": schemas}

    schemas = PluginRegistry.get_ui_schemas(component_type)
    return {"component_type": component_type, "schemas": schemas}


@router.get("/ui-schemas/{component_type}/{key}")
async def get_schema(component_type: str, key: str) -> Dict[str, Any]:
    """Get a specific UI schema.

    Args:
        component_type: One of 'service_type', 'auth_type', 'node_type'
        key: The specific type key (e.g., 'api_call', 'oauth2')
    """
    # Check auth handlers first for auth_type
    if component_type == "auth_type":
        handler = PluginRegistry.get_auth_handler(key)
        if handler and hasattr(handler, 'ui_schema') and handler.ui_schema:
            return {"component_type": component_type, "key": key, "schema": handler.ui_schema}

    schema = PluginRegistry.get_ui_schema(component_type, key)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"No UI schema found for {component_type}/{key}")

    return {"component_type": component_type, "key": key, "schema": schema}


@router.get("/summary")
async def plugin_summary() -> Dict[str, Any]:
    """Get a summary of all registered plugins."""
    return {
        "summary": PluginRegistry.summary(),
        "service_executors": PluginRegistry.list_service_executors(),
        "node_handlers": PluginRegistry.list_node_handlers(),
        "auth_handlers": PluginRegistry.list_auth_handlers(),
        "webhook_verifiers": PluginRegistry.list_webhook_verifiers(),
    }


@router.post("/validate-flows")
async def validate_flows(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Scan all flows for references to unregistered service types, node types, or auth types.

    Returns a list of broken references with flow IDs so they can be fixed.
    """
    from db.models import Flow

    registered_service_types = set(PluginRegistry.list_service_executors())
    registered_node_types = set(PluginRegistry.list_node_handlers())
    registered_auth_types = set(PluginRegistry.list_auth_handlers())

    broken_refs = []

    flows = db.query(Flow).filter(Flow.status != 'deleted').all()

    for flow in flows:
        flow_def = flow.flow_definition
        if not flow_def:
            continue

        if isinstance(flow_def, str):
            try:
                flow_def = json.loads(flow_def)
            except json.JSONDecodeError:
                broken_refs.append({
                    "flow_id": flow.flow_id,
                    "flow_name": flow.flow_name,
                    "issue": "Invalid flow_definition JSON"
                })
                continue

        nodes = flow_def.get('nodes', [])
        for node in nodes:
            node_type = node.get('type', '')
            node_data = node.get('data', {})
            node_id = node.get('id', '')

            # Check node type
            if node_type and node_type not in registered_node_types:
                broken_refs.append({
                    "flow_id": flow.flow_id,
                    "flow_name": flow.flow_name,
                    "node_id": node_id,
                    "issue": f"Unregistered node type: {node_type}"
                })

            # For action nodes, check service type
            if node_type == 'action':
                service_type = node_data.get('serviceType') or node_data.get('service_type', '')
                if service_type and service_type not in registered_service_types:
                    broken_refs.append({
                        "flow_id": flow.flow_id,
                        "flow_name": flow.flow_name,
                        "node_id": node_id,
                        "issue": f"Unregistered service type: {service_type}"
                    })

    return {
        "total_flows_scanned": len(flows),
        "broken_references": broken_refs,
        "broken_count": len(broken_refs)
    }
