"""
Trigger Node Builder for Flow Designer V2

Handles creation and configuration of trigger nodes with
optimized data structures and validation.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Trigger type enumeration"""
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    APPLICATION_EVENT = "application_event"
    API_CALL = "api_call"
    FILE = "file"
    CHAT_INPUT = "chat_input"  # Chat-based trigger for conversational flows


@dataclass
class ManualVariable:
    """Manual trigger variable definition"""
    name: str
    dataType: str
    description: str = ""
    required: bool = True
    defaultValue: Any = ""
    uiControl: str = "text"
    validation: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class ScheduleConfig:
    """Schedule trigger configuration"""
    cron_expression: str
    timezone: str = "UTC"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


class TriggerBuilder:
    """
    Builder for creating trigger nodes with proper configuration
    and validation.
    """

    def __init__(self):
        """Initialize trigger builder."""
        self.node_counter = 0

    def create_manual_trigger(
        self,
        variables: List[Dict[str, Any]],
        position: Optional[Dict[str, int]] = None,
        execute_immediately: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create a manual trigger node.

        Args:
            variables: List of manual variable definitions
            position: Node position
            execute_immediately: Execute on save

        Returns:
            Tuple of (node_data, trigger_config)
        """
        # Convert to ManualVariable objects
        manual_vars = []
        for var in variables:
            if isinstance(var, dict):
                # Add ID if missing
                if "id" not in var:
                    var["id"] = var.get("name", f"var_{len(manual_vars)}")

                manual_var = ManualVariable(
                    name=var.get("name", f"input_{len(manual_vars)}"),
                    dataType=var.get("dataType", "string"),
                    description=var.get("description", ""),
                    required=var.get("required", True),
                    defaultValue=var.get("defaultValue", ""),
                    uiControl=var.get("uiControl", self._get_default_ui_control(var.get("dataType", "string"))),
                    validation=var.get("validation")
                )
                manual_vars.append(manual_var)

        # Create outputs mapping
        outputs = {var.name: f"{{{{input.{var.name}}}}}" for var in manual_vars}

        # Node data for UI
        node_data = {
            "id": "trigger_1",
            "type": "trigger",
            "position": position or {"x": 250, "y": 100},
            "data": {
                "label": "Manual Trigger",
                "triggerType": "manual",
                "type": "manual",
                "manualVariables": [v.to_dict() for v in manual_vars],
                "executeImmediately": execute_immediately,
                "outputs": outputs,
                "width": 200,
                "height": 100
            }
        }

        # Trigger config for backend
        trigger_config = {
            "type": "manual",
            "manual_variables": [v.to_dict() for v in manual_vars],
            "execute_immediately": execute_immediately
        }

        logger.info(f"Created manual trigger with {len(manual_vars)} variables")
        return node_data, trigger_config

    def create_webhook_trigger(
        self,
        webhook_path: str,
        method: str = "POST",
        auth_required: bool = False,
        position: Optional[Dict[str, int]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create a webhook trigger node.

        Args:
            webhook_path: Webhook endpoint path
            method: HTTP method
            auth_required: Require authentication
            position: Node position

        Returns:
            Tuple of (node_data, trigger_config)
        """
        # Ensure path starts with /
        if not webhook_path.startswith("/"):
            webhook_path = f"/{webhook_path}"

        node_data = {
            "id": "trigger_1",
            "type": "trigger",
            "position": position or {"x": 250, "y": 100},
            "data": {
                "label": "Webhook Trigger",
                "triggerType": "webhook",
                "type": "webhook",
                "webhookPath": webhook_path,
                "method": method,
                "authRequired": auth_required,
                "outputs": {
                    "body": "{{webhook.body}}",
                    "headers": "{{webhook.headers}}",
                    "query": "{{webhook.query}}"
                },
                "width": 200,
                "height": 100
            }
        }

        trigger_config = {
            "type": "webhook",
            "webhook_path": webhook_path,
            "method": method,
            "auth_required": auth_required
        }

        logger.info(f"Created webhook trigger for {method} {webhook_path}")
        return node_data, trigger_config

    def create_schedule_trigger(
        self,
        cron_expression: str,
        timezone: str = "UTC",
        position: Optional[Dict[str, int]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create a schedule trigger node.

        Args:
            cron_expression: Cron expression
            timezone: Timezone
            position: Node position

        Returns:
            Tuple of (node_data, trigger_config)
        """
        schedule_config = ScheduleConfig(
            cron_expression=cron_expression,
            timezone=timezone
        )

        node_data = {
            "id": "trigger_1",
            "type": "trigger",
            "position": position or {"x": 250, "y": 100},
            "data": {
                "label": "Schedule Trigger",
                "triggerType": "schedule",
                "type": "schedule",
                "cronExpression": cron_expression,
                "timezone": timezone,
                "schedule": schedule_config.to_dict(),
                "outputs": {
                    "execution_time": "{{schedule.execution_time}}",
                    "next_run": "{{schedule.next_run}}"
                },
                "width": 200,
                "height": 100
            }
        }

        trigger_config = {
            "type": "schedule",
            "schedule": schedule_config.to_dict()
        }

        logger.info(f"Created schedule trigger with cron: {cron_expression}")
        return node_data, trigger_config

    def create_application_event_trigger(
        self,
        app_id: str,
        event_id: str,
        app_name: str = "",
        event_name: str = "",
        position: Optional[Dict[str, int]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create an application event trigger node.

        Args:
            app_id: Application ID
            event_id: Event ID
            app_name: Application name (for display)
            event_name: Event name (for display)
            position: Node position

        Returns:
            Tuple of (node_data, trigger_config)
        """
        node_data = {
            "id": "trigger_1",
            "type": "trigger",
            "position": position or {"x": 250, "y": 100},
            "data": {
                "label": f"{app_name or 'App'} Event",
                "triggerType": "application_event",
                "type": "event",
                "appId": app_id,
                "eventId": event_id,
                "appName": app_name,
                "eventName": event_name,
                "outputs": {
                    "event_data": "{{event.data}}",
                    "event_type": "{{event.type}}",
                    "timestamp": "{{event.timestamp}}"
                },
                "width": 200,
                "height": 100
            }
        }

        trigger_config = {
            "type": "event",
            "app_id": app_id,
            "event_id": event_id,
            "event_name": event_name
        }

        logger.info(f"Created application event trigger for {app_name}:{event_name}")
        return node_data, trigger_config

    def create_chat_input_trigger(
        self,
        system_prompt: str = "",
        placeholder_text: str = "Type your message...",
        welcome_message: str = "",
        session_timeout_minutes: int = 1440,  # 24 hours default
        position: Optional[Dict[str, int]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create a chat input trigger node for conversational flows.

        This trigger type enables chat-like interaction with flows containing
        AI Agent nodes, maintaining conversation continuity across multiple
        flow invocations within a session.

        Args:
            system_prompt: Initial system context for the conversation
            placeholder_text: Placeholder text for the chat input field
            welcome_message: Welcome message displayed when chat opens
            session_timeout_minutes: Session timeout in minutes (default 24 hours)
            position: Node position

        Returns:
            Tuple of (node_data, trigger_config)
        """
        # Define the message variable (similar to manual trigger variables)
        # This makes input.message available to downstream nodes
        chat_variables = [
            {
                "id": "message",
                "name": "message",
                "dataType": "string",
                "description": "The user's chat message",
                "required": True,
                "defaultValue": "",
                "uiControl": "textarea"
            }
        ]

        node_data = {
            "id": "trigger_1",
            "type": "trigger",
            "position": position or {"x": 250, "y": 100},
            "data": {
                "label": "Chat Input",
                "triggerType": "chat_input",
                "type": "chat_input",
                "systemPrompt": system_prompt,
                "placeholderText": placeholder_text,
                "welcomeMessage": welcome_message,
                "sessionTimeoutMinutes": session_timeout_minutes,
                # Expose manualVariables for variable picker compatibility
                "manualVariables": chat_variables,
                "outputs": {
                    "message": "{{input.message}}",
                    "session_id": "{{input.session_id}}",
                    "is_first_message": "{{input.is_first_message}}"
                },
                "width": 200,
                "height": 100
            }
        }

        trigger_config = {
            "type": "chat_input",
            "system_prompt": system_prompt,
            "placeholder_text": placeholder_text,
            "welcome_message": welcome_message,
            "session_timeout_minutes": session_timeout_minutes,
            # Include manual_variables for backend processing
            "manual_variables": chat_variables
        }

        logger.info(f"Created chat input trigger with {session_timeout_minutes}min timeout")
        return node_data, trigger_config

    def validate_trigger_node(self, node_data: Dict[str, Any]) -> List[str]:
        """
        Validate a trigger node configuration.

        Args:
            node_data: Trigger node data

        Returns:
            List of validation errors
        """
        errors = []

        # Check basic structure
        if not node_data.get("id"):
            errors.append("Trigger node missing 'id' field")

        if node_data.get("type") != "trigger":
            errors.append(f"Invalid node type: {node_data.get('type')}, expected 'trigger'")

        if "data" not in node_data:
            errors.append("Trigger node missing 'data' field")
        else:
            data = node_data["data"]
            trigger_type = data.get("triggerType") or data.get("type")

            if not trigger_type:
                errors.append("Trigger node missing trigger type")
            else:
                # Type-specific validation
                if trigger_type == "manual":
                    errors.extend(self._validate_manual_trigger(data))
                elif trigger_type == "webhook":
                    errors.extend(self._validate_webhook_trigger(data))
                elif trigger_type == "schedule":
                    errors.extend(self._validate_schedule_trigger(data))
                elif trigger_type in ["application_event", "event"]:
                    errors.extend(self._validate_event_trigger(data))
                elif trigger_type == "chat_input":
                    errors.extend(self._validate_chat_input_trigger(data))

        return errors

    def optimize_trigger_data(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize trigger node data for minimal token usage.

        Args:
            node_data: Original trigger node data

        Returns:
            Optimized trigger node data
        """
        optimized = {
            "id": node_data.get("id"),
            "type": "trigger",
            "position": node_data.get("position", {"x": 250, "y": 100})
        }

        data = node_data.get("data", {})
        trigger_type = data.get("triggerType") or data.get("type")

        # Only include essential fields
        optimized_data = {
            "label": data.get("label", "Trigger"),
            "triggerType": trigger_type
        }

        # Type-specific optimization
        if trigger_type == "manual":
            # Compress manual variables
            if "manualVariables" in data:
                optimized_data["manualVariables"] = [
                    {
                        "name": v.get("name"),
                        "dataType": v.get("dataType", "string"),
                        "required": v.get("required", True)
                    }
                    for v in data["manualVariables"]
                ]

        elif trigger_type == "webhook":
            optimized_data["webhookPath"] = data.get("webhookPath")

        elif trigger_type == "schedule":
            if "schedule" in data:
                optimized_data["schedule"] = {
                    "cron_expression": data["schedule"].get("cron_expression")
                }

        elif trigger_type in ["application_event", "event"]:
            optimized_data["appId"] = data.get("appId")
            optimized_data["eventId"] = data.get("eventId")

        elif trigger_type == "chat_input":
            optimized_data["placeholderText"] = data.get("placeholderText", "Type your message...")
            if data.get("sessionTimeoutMinutes"):
                optimized_data["sessionTimeoutMinutes"] = data.get("sessionTimeoutMinutes")
            # Include manualVariables for variable picker
            if "manualVariables" in data:
                optimized_data["manualVariables"] = data["manualVariables"]

        optimized["data"] = optimized_data
        return optimized

    def _get_default_ui_control(self, data_type: str) -> str:
        """Get default UI control for data type."""
        ui_controls = {
            "string": "text",
            "number": "number",
            "boolean": "checkbox",
            "array": "textarea",
            "object": "textarea",
            "file": "file",
            "date": "date",
            "email": "email",
            "url": "url"
        }
        return ui_controls.get(data_type, "text")

    def _validate_manual_trigger(self, data: Dict[str, Any]) -> List[str]:
        """Validate manual trigger data."""
        errors = []

        if "manualVariables" not in data:
            errors.append("Manual trigger missing 'manualVariables' array")
        else:
            variables = data["manualVariables"]
            if not isinstance(variables, list):
                errors.append("manualVariables must be an array")
            else:
                var_names = set()
                for i, var in enumerate(variables):
                    if not isinstance(var, dict):
                        errors.append(f"Variable at index {i} must be an object")
                    else:
                        name = var.get("name")
                        if not name:
                            errors.append(f"Variable at index {i} missing 'name'")
                        elif name in var_names:
                            errors.append(f"Duplicate variable name: {name}")
                        else:
                            var_names.add(name)

                        if "dataType" not in var:
                            errors.append(f"Variable '{name}' missing 'dataType'")

        return errors

    def _validate_webhook_trigger(self, data: Dict[str, Any]) -> List[str]:
        """Validate webhook trigger data."""
        errors = []

        if "webhookPath" not in data:
            errors.append("Webhook trigger missing 'webhookPath'")
        else:
            path = data["webhookPath"]
            if not path.startswith("/"):
                errors.append(f"Webhook path should start with '/': {path}")

        return errors

    def _validate_schedule_trigger(self, data: Dict[str, Any]) -> List[str]:
        """Validate schedule trigger data."""
        errors = []

        if "schedule" not in data and "cronExpression" not in data:
            errors.append("Schedule trigger missing schedule configuration")

        return errors

    def _validate_event_trigger(self, data: Dict[str, Any]) -> List[str]:
        """Validate application event trigger data."""
        errors = []

        if "appId" not in data:
            errors.append("Application event trigger missing 'appId'")

        if "eventId" not in data and "eventName" not in data:
            errors.append("Application event trigger missing 'eventId' or 'eventName'")

        return errors

    def _validate_chat_input_trigger(self, data: Dict[str, Any]) -> List[str]:
        """Validate chat input trigger data."""
        errors = []

        # Session timeout validation (optional, but must be positive if provided)
        timeout = data.get("sessionTimeoutMinutes")
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                errors.append("Chat input trigger 'sessionTimeoutMinutes' must be a positive number")

        return errors


# Singleton instance
_trigger_builder: Optional[TriggerBuilder] = None

def get_trigger_builder() -> TriggerBuilder:
    """Get or create the global trigger builder instance."""
    global _trigger_builder
    if _trigger_builder is None:
        _trigger_builder = TriggerBuilder()
    return _trigger_builder