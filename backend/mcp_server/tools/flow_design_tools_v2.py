"""
Flow Design Editor Tools for MCP Server

Tools for editing and modifying existing flow designs.
Focused on updating, refining, and improving already created flows.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import logging
import httpx
import uuid
from pathlib import Path

# Import MCP classes
from mcp.types import TextContent

logger = logging.getLogger(__name__)

# Tool base class
class Tool:
    """Base class for flow design tools"""
    name = None  # Should be overridden in subclasses

    def __init__(self, auth_handler=None):
        # Use class-level name if defined, otherwise use class name
        if not hasattr(self.__class__, 'name') or self.__class__.name is None:
            self.name = self.__class__.__name__
        else:
            self.name = self.__class__.name
        self.auth_handler = auth_handler

    async def run(self, **kwargs):
        """Override in subclasses"""
        raise NotImplementedError


class CreateFlowSession(Tool):
    """
    Create a new flow design session for incremental building.

    This starts a session that allows adding nodes one at a time,
    creating checkpoints, and resuming from failures.
    """

    name = "create_flow_session"
    description = """Create a new flow design session for incremental building.

    Args:
        name (str): Flow name
        description (str, optional): Flow description
        ttl_minutes (int, optional): Session TTL in minutes (default: 30)

    Returns:
        Session information including session_id, status, and expiration
    """

    async def run(
        self,
        name: str,
        description: str = "",
        ttl_minutes: int = 30
    ) -> TextContent:
        """Create a flow design session (tracked in ADK conversation context)."""
        try:
            # Just generate a session ID for conversation tracking
            # No external storage needed - ADK maintains conversation context
            session_id = str(uuid.uuid4())

            result = f"""✅ Flow Session Created

**Session ID**: `{session_id}`
**Name**: {name}
**Description**: {description}

**Important**: Track this session_id in your conversation. All flow state is maintained in your ADK conversation context, not external storage.

Next steps:
1. Add trigger: `add_trigger_node`
2. Add actions: `add_action_node`
3. Complete flow: `complete_flow_session` (pass all nodes/edges you've tracked)

Start by adding a trigger node to begin building your flow.
"""

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return TextContent(
                type="text",
                text=f"Error creating session: {str(e)}"
            )


class ResumeFlowSession(Tool):
    """Resume an existing flow design session."""

    name = "resume_flow_session"
    description = """Resume an existing flow design session.

    Args:
        session_id (str): Session ID to resume

    Returns:
        Current session state with nodes, edges, and checkpoints
    """

    async def run(self, session_id: str) -> TextContent:
        """Resume a flow session."""
        try:
            from agent.flow_designer_v2.core.session_manager import get_session_manager

            session_mgr = get_session_manager()
            state = session_mgr.get_session_state(session_id)

            if not state:
                return TextContent(
                    type="text",
                    text=f"❌ Session not found: {session_id}"
                )

            result = f"""📋 Session State: {state['name']}

**Session ID**: `{session_id}`
**Status**: {state['status']}
**Created**: {state['created_at']}
**Updated**: {state['updated_at']}

**Current Progress**:
- Nodes: {state['nodes_count']}
- Edges: {state['edges_count']}
- Checkpoints: {state['checkpoints_count']}
- Has Trigger: {'✅' if state['has_trigger'] else '❌'}

**Structure**:
"""

            # Add node list
            for node in state['current_structure']['nodes']:
                result += f"  - {node['id']} ({node['type']})\n"

            # Add edge list
            if state['current_structure']['edges']:
                result += "\n**Connections**:\n"
                for edge in state['current_structure']['edges']:
                    result += f"  - {edge['source']} → {edge['target']}\n"

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error resuming session: {e}")
            return TextContent(
                type="text",
                text=f"Error resuming session: {str(e)}"
            )


class AddTriggerNode(Tool):
    """Add a trigger node to the session."""

    name = "add_trigger_node"
    description = """Add a trigger node to the flow session.

    Args:
        session_id (str): Session ID
        trigger_type (str): Type (manual, webhook, schedule, application_event)
        config (dict): Trigger configuration
            For manual: {"variables": [{"name": "x", "dataType": "string"}]}
            For webhook: {"webhook_path": "/hook", "method": "POST"}
            For schedule: {"cron_expression": "0 0 * * *"}
            For event: {"app_id": "...", "event_id": "..."}

    Returns:
        Node ID and updated session state
    """

    async def run(
        self,
        session_id: str,
        trigger_type: str,
        config: Dict[str, Any]
    ) -> TextContent:
        """Add trigger node (returns node data for agent to track in conversation)."""
        try:
            from agent.flow_designer_v2.builders.trigger_builder import get_trigger_builder

            trigger_builder = get_trigger_builder()

            # Build trigger node
            if trigger_type == "manual":
                node_data, trigger_config = trigger_builder.create_manual_trigger(
                    variables=config.get("variables", [])
                )
            elif trigger_type == "webhook":
                node_data, trigger_config = trigger_builder.create_webhook_trigger(
                    webhook_path=config.get("webhook_path", "/webhook"),
                    method=config.get("method", "POST")
                )
            elif trigger_type == "schedule":
                node_data, trigger_config = trigger_builder.create_schedule_trigger(
                    cron_expression=config["cron_expression"],
                    timezone=config.get("timezone", "UTC")
                )
            elif trigger_type == "application_event":
                node_data, trigger_config = trigger_builder.create_application_event_trigger(
                    app_id=config["app_id"],
                    event_id=config["event_id"],
                    app_name=config.get("app_name", ""),
                    event_name=config.get("event_name", "")
                )
            else:
                return TextContent(
                    type="text",
                    text=f"❌ Unknown trigger type: {trigger_type}"
                )

            # Return node data for agent to track in conversation (no external storage)
            node_id = node_data["id"]

            result = f"""✅ Trigger Node Created

**Node ID**: `{node_id}`
**Type**: {trigger_type}
**Session**: {session_id}

**Node Data** (track this):
```json
{json.dumps(node_data, indent=2)}
```

**Trigger Config** (track this):
```json
{json.dumps(trigger_config, indent=2)}
```

Next: Add action nodes or complete flow with `complete_flow_session`.
"""

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error adding trigger node: {e}")
            return TextContent(
                type="text",
                text=f"Error adding trigger node: {str(e)}"
            )


class AddActionNode(Tool):
    """Add an action node to the session."""

    name = "add_action_node"
    description = """Add an action node to the flow session.

    Args:
        session_id (str): Session ID
        app_id (str): Application ID
        service_id (str): Service ID
        parameters (dict): Service parameters with values or variable references
        app_name (str, optional): Application name for display
        service_name (str, optional): Service name for display
        node_id (str, optional): Custom node ID

    Returns:
        Node ID and updated session state
    """

    async def run(
        self,
        session_id: str,
        app_id: str,
        service_id: str,
        parameters: Dict[str, Any],
        app_name: str = "",
        service_name: str = "",
        node_id: Optional[str] = None
    ) -> TextContent:
        """Add action node (returns node data for agent to track in conversation)."""
        try:
            from agent.flow_designer_v2.builders.action_builder import get_action_builder

            action_builder = get_action_builder()

            # Build action node
            node_data = action_builder.create_action_node(
                app_id=app_id,
                service_id=service_id,
                parameters=parameters,
                app_name=app_name,
                service_name=service_name,
                node_id=node_id
            )

            # Return node data for agent to track in conversation (no external storage)
            result = f"""✅ Action Node Created

**Node ID**: `{node_id}`
**Service**: {service_name or service_id}
**Application**: {app_name or app_id}
**Session**: {session_id}

**Node Data** (track this):
```json
{json.dumps(node_data, indent=2)}
```

Next: Add more actions or complete flow with `complete_flow_session`.
"""

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error adding action node: {e}")
            return TextContent(
                type="text",
                text=f"Error adding action node: {str(e)}"
            )


class ConnectNodes(Tool):
    """Connect two nodes with an edge."""

    name = "connect_nodes"
    description = """Connect two nodes in the flow session.

    Args:
        session_id (str): Session ID
        source_id (str): Source node ID
        target_id (str): Target node ID
        source_handle (str, optional): Source handle name
        target_handle (str, optional): Target handle name

    Returns:
        Edge ID and confirmation
    """

    async def run(
        self,
        session_id: str,
        source_id: str,
        target_id: str,
        source_handle: Optional[str] = None,
        target_handle: Optional[str] = None
    ) -> TextContent:
        """Connect nodes with an edge."""
        try:
            from agent.flow_designer_v2.core.session_manager import get_session_manager

            session_mgr = get_session_manager()

            edge_id = session_mgr.add_edge(
                session_id=session_id,
                source=source_id,
                target=target_id,
                source_handle=source_handle,
                target_handle=target_handle
            )

            if not edge_id:
                return TextContent(
                    type="text",
                    text="❌ Failed to connect nodes. Check that both nodes exist."
                )

            result = f"""✅ Nodes Connected

**Edge ID**: `{edge_id}`
**Connection**: {source_id} → {target_id}
**Session**: {session_id}

The nodes are now connected in the flow.
"""

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error connecting nodes: {e}")
            return TextContent(
                type="text",
                text=f"Error connecting nodes: {str(e)}"
            )


class CreateCheckpoint(Tool):
    """Create a checkpoint for the session."""

    name = "create_checkpoint"
    description = """Create a checkpoint for the flow session.

    Checkpoints allow you to save the current state and restore
    it later if something goes wrong.

    Args:
        session_id (str): Session ID
        label (str, optional): Checkpoint label/description

    Returns:
        Checkpoint ID
    """

    async def run(
        self,
        session_id: str,
        label: str = ""
    ) -> TextContent:
        """Create a checkpoint."""
        try:
            from agent.flow_designer_v2.core.session_manager import get_session_manager

            session_mgr = get_session_manager()

            checkpoint_id = session_mgr.create_checkpoint(session_id, label)

            if not checkpoint_id:
                return TextContent(
                    type="text",
                    text="❌ Failed to create checkpoint. Session may not exist."
                )

            result = f"""💾 Checkpoint Created

**Checkpoint ID**: `{checkpoint_id}`
**Label**: {label or '(none)'}
**Session**: {session_id}

Use this checkpoint_id to restore this state if needed.
"""

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error creating checkpoint: {e}")
            return TextContent(
                type="text",
                text=f"Error creating checkpoint: {str(e)}"
            )


class RestoreCheckpoint(Tool):
    """Restore session from a checkpoint."""

    name = "restore_checkpoint"
    description = """Restore a flow session from a checkpoint.

    Args:
        session_id (str): Session ID
        checkpoint_id (str): Checkpoint ID to restore

    Returns:
        Restored session state
    """

    async def run(
        self,
        session_id: str,
        checkpoint_id: str
    ) -> TextContent:
        """Restore from checkpoint."""
        try:
            from agent.flow_designer_v2.core.session_manager import get_session_manager

            session_mgr = get_session_manager()

            success = session_mgr.restore_checkpoint(session_id, checkpoint_id)

            if not success:
                return TextContent(
                    type="text",
                    text="❌ Failed to restore checkpoint. It may not exist."
                )

            # Get restored state
            state = session_mgr.get_session_state(session_id)

            result = f"""✅ Checkpoint Restored

**Checkpoint ID**: {checkpoint_id}
**Session**: {session_id}

**Restored State**:
- Nodes: {state['nodes_count']}
- Edges: {state['edges_count']}
- Status: {state['status']}

The session has been restored to this checkpoint.
"""

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error restoring checkpoint: {e}")
            return TextContent(
                type="text",
                text=f"Error restoring checkpoint: {str(e)}"
            )


class CompleteFlowSession(Tool):
    """Complete the session and generate final flow JSON."""

    name = "complete_flow_session"
    description = """Complete the flow session and generate final flow JSON.

    This marks the session as completed and returns the complete
    flow definition ready for import/execution.

    Args:
        session_id (str): Session ID

    Returns:
        Complete flow JSON in export format
    """

    async def run(
        self,
        session_id: str,
        flow_name: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        trigger_config: Dict[str, Any]
    ) -> TextContent:
        """Complete flow using data tracked in ADK conversation."""
        try:
            # Build final flow JSON from conversation-tracked data
            flow_json = {
                "name": flow_name,
                "nodes": nodes,
                "edges": edges,
                "trigger": trigger_config,
                "synchronous": False,
                "created_at": datetime.utcnow().isoformat()
            }

            result = f"""✅ Flow Completed

**Flow Name**: {flow_name}
**Session**: {session_id}
**Nodes**: {len(nodes)}
**Edges**: {len(edges)}

**Complete Flow JSON**:
```json
{json.dumps(flow_json, indent=2)}
```

The flow is ready! You can now save it using `create_flow_design`.
"""

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error completing flow: {e}")
            return TextContent(
                type="text",
                text=f"Error completing flow: {str(e)}"
            )


class ValidateAndSaveFlow(Tool):
    """Validate and save flow design in a single operation."""

    name = "validate_and_save_flow"
    description = """Validate and save a flow design to IOFlow.

    This tool combines validation and saving into a single operation.
    It first validates the flow, and if valid, saves it to IOFlow.

    Args:
        flow_name (str): Name for the flow design
        flow_json (dict): Complete flow design in export format

    Returns:
        Result with validation status and save confirmation or errors
    """

    async def run(
        self,
        flow_name: str,
        flow_json: Dict[str, Any]
    ) -> TextContent:
        """Validate and save flow design."""
        try:
            import base64

            # Ensure flow is in export format
            if 'version' not in flow_json or 'flow' not in flow_json:
                # Wrap in export format if not already
                flow_json = {
                    "version": "1.0",
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "flow": flow_json,
                    "metadata": {
                        "source": "flow_design_editor",
                        "created_by": "mcp_tool"
                    }
                }

            # Ensure flow_name is set in the flow
            if 'flow' in flow_json:
                flow_json['flow']['flow_name'] = flow_name

            # First validate the flow
            logger.info(f"Validating flow: {flow_name}")

            # Import auth handler and make API call for validation
            if hasattr(self, 'auth_handler') and self.auth_handler:
                # Base64 encode the flow JSON for validation
                flow_json_str = json.dumps(flow_json)
                flow_json_base64 = base64.b64encode(flow_json_str.encode()).decode('ascii')

                # Call validation API
                validation_response = await self.auth_handler.make_authenticated_request(
                    "POST",
                    "/api/mcp/tools/execute",
                    json_data={
                        "tool": "validate_flow_design",
                        "parameters": {"flow_json": flow_json_base64}
                    }
                )

                if not validation_response.get("valid", False):
                    # Validation failed
                    errors = validation_response.get("errors", [])
                    warnings = validation_response.get("warnings", [])

                    error_msg = "❌ **Flow Validation Failed**\n\n"
                    if errors:
                        error_msg += "**Errors:**\n"
                        for error in errors:
                            error_msg += f"- {error}\n"
                    if warnings:
                        error_msg += "\n**Warnings:**\n"
                        for warning in warnings:
                            error_msg += f"- {warning}\n"

                    error_msg += "\nPlease fix the errors and try again."
                    return TextContent(type="text", text=error_msg)

                # Validation successful, now save the flow
                logger.info(f"Validation successful, saving flow: {flow_name}")

                # Call create_flow_design API to save
                save_response = await self.auth_handler.make_authenticated_request(
                    "POST",
                    "/api/mcp/tools/execute",
                    json_data={
                        "tool": "create_flow_design",
                        "parameters": {
                            "flow_name": flow_name,
                            "flow_json": flow_json_base64
                        }
                    }
                )

                if save_response.get("success"):
                    flow_id = save_response.get('flow_id')
                    edit_link = f"/flow-designer?flowId={flow_id}"

                    result = f"""✅ **Flow Validated and Saved Successfully!**

🔍 **Validation:** Passed
📋 **Flow Name:** {flow_name}
🔗 **Flow ID:** `{flow_id}`
📝 **[Edit Flow]({edit_link})**

Your flow has been validated and saved to IOFlow."""

                    # Add warnings if any
                    warnings = validation_response.get("warnings", [])
                    if warnings:
                        result += "\n\n⚠️ **Warnings:**\n"
                        for warning in warnings:
                            result += f"- {warning}\n"

                    return TextContent(type="text", text=result)
                else:
                    error = save_response.get("error", "Unknown error")
                    return TextContent(
                        type="text",
                        text=f"❌ Validation passed but save failed: {error}"
                    )
            else:
                # No auth handler, can't make API calls
                return TextContent(
                    type="text",
                    text="❌ Authentication required to validate and save flow"
                )

        except Exception as e:
            logger.error(f"Error in validate_and_save_flow: {e}")
            return TextContent(
                type="text",
                text=f"❌ Error validating/saving flow: {str(e)}"
            )


class GetLightweightApplications(Tool):
    """Get lightweight list of applications (cached)."""

    name = "get_lightweight_applications"
    description = """Get a lightweight list of applications with minimal data.

    This returns only essential information and uses caching for
    better performance and token efficiency.

    Args:
        category (str, optional): Filter by category
        search (str, optional): Search by name

    Returns:
        List of applications with id, name, services_count
    """

    async def run(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> TextContent:
        """Get lightweight applications list."""
        try:
            from agent.flow_designer_v2.core.cache_manager import get_cache_manager
            from db.database import get_db_context

            cache = get_cache_manager()

            # Try cache first
            cached = cache.get_applications_list()
            if cached:
                apps = cached
            else:
                # Fetch from database
                with get_db_context() as db:
                    from db.application_models import Application
                    from db.application_models import ApplicationService

                    query = db.query(Application)
                    if category:
                        query = query.filter(Application.category == category)
                    if search:
                        query = query.filter(Application.name.ilike(f"%{search}%"))

                    db_apps = query.all()

                    apps = []
                    for app in db_apps:
                        services_count = db.query(ApplicationService).filter(
                            ApplicationService.app_id == app.id
                        ).count()

                        apps.append({
                            "id": str(app.id),
                            "name": app.name,
                            "type": app.type,
                            "services_count": services_count
                        })

                    # Cache it
                    cache.set_applications_list(apps)

            # Format result
            result = "📱 **Applications** (lightweight)\n\n"
            for app in apps[:10]:  # Limit to 10
                result += f"- **{app['name']}** (ID: `{app['id']}`, Services: {app['services_count']})\n"

            if len(apps) > 10:
                result += f"\n...and {len(apps) - 10} more applications\n"

            result += f"\n**Total**: {len(apps)} applications"

            return TextContent(type="text", text=result)

        except Exception as e:
            logger.error(f"Error getting applications: {e}")
            return TextContent(
                type="text",
                text=f"Error getting applications: {str(e)}"
            )


# Export all V2 tools
FLOW_DESIGN_TOOLS_V2 = [
    CreateFlowSession,
    ResumeFlowSession,
    AddTriggerNode,
    AddActionNode,
    ConnectNodes,
    CreateCheckpoint,
    RestoreCheckpoint,
    CompleteFlowSession,
    ValidateAndSaveFlow,
    GetLightweightApplications
]

__all__ = ['FLOW_DESIGN_TOOLS_V2']