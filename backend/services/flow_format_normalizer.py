"""
Flow Format Normalizer - Handles different flow JSON formats and normalizes them
"""
from typing import Dict, Any, Optional, Tuple, List
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FlowFormatNormalizer:
    """
    Normalizes different flow JSON formats into the standard import format.
    Handles:
    - Direct format (nodes + edges at root)
    - Hybrid format (flow metadata but no wrapper)
    - Export format (standard import format)
    - Incomplete formats with missing metadata
    """

    @staticmethod
    def detect_format(json_data: Dict[str, Any]) -> str:
        """
        Detect the format of the JSON data.
        Returns: 'export', 'direct', 'hybrid', 'flow_create', or 'unknown'
        """
        # Check for export format. The discriminator is the `flow` envelope,
        # NOT `version`: version is metadata, and requiring it meant a payload
        # of {"flow": {...}} fell through to "unknown", whose best-effort
        # branch scrapes the nodes and REGENERATES the name/description/
        # trigger — silently discarding whatever the caller asked for. Any API
        # client that omitted the optional version field lost its flow name.
        if "flow" in json_data and isinstance(json_data.get("flow"), dict):
            inner = json_data["flow"]
            if any(k in inner for k in
                   ("flow_definition", "flow_name", "trigger_config", "nodes")):
                return "export"

        # Check for FlowCreate format (has flow_name + flow_definition)
        if "flow_name" in json_data and "flow_definition" in json_data:
            return "flow_create"

        # Check for direct format (nodes + edges at root, no other metadata)
        if "nodes" in json_data and "edges" in json_data:
            # If it has additional flow metadata, it's hybrid
            if any(key in json_data for key in ["flow_name", "description", "trigger_config"]):
                return "hybrid"
            return "direct"

        return "unknown"

    @staticmethod
    def extract_trigger_from_nodes(nodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Extract trigger configuration from nodes list.
        """
        trigger_nodes = [n for n in nodes if n.get('type') == 'trigger']
        if not trigger_nodes:
            return None

        trigger_node = trigger_nodes[0]
        trigger_data = trigger_node.get('data', {})

        # Build trigger config from node data
        trigger_config = {
            "type": trigger_data.get('trigger_type', 'manual'),
            "app_id": trigger_data.get('app_id') or trigger_data.get('appId'),
            "service_id": trigger_data.get('service_id') or trigger_data.get('serviceId'),
        }

        # Add schedule if it's a scheduled trigger
        if trigger_config['type'] == 'scheduled' and 'schedule' in trigger_data:
            trigger_config['schedule'] = trigger_data['schedule']

        # Add event info if it's an event trigger
        if trigger_config['type'] == 'event':
            if 'event_name' in trigger_data:
                trigger_config['event_name'] = trigger_data['event_name']
            if 'webhook_path' in trigger_data:
                trigger_config['webhook_path'] = trigger_data['webhook_path']

        # Clean up None values
        return {k: v for k, v in trigger_config.items() if v is not None}

    @staticmethod
    def normalize_node_fields(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize node field names (app_id -> appId, service_id -> serviceId, etc.)
        """
        normalized_nodes = []

        for node in nodes:
            normalized_node = node.copy()

            if 'data' in normalized_node:
                data = normalized_node['data'].copy()

                # Normalize field names
                field_mappings = {
                    'app_id': 'appId',
                    'service_id': 'serviceId',
                    'app_name': 'appName',
                    'service_name': 'serviceName',
                    'trigger_type': 'triggerType',
                    'event_name': 'eventName',
                    'webhook_path': 'webhookPath',
                    'loop_type': 'loopType',
                    'response_type': 'responseType'
                }

                for old_name, new_name in field_mappings.items():
                    if old_name in data and new_name not in data:
                        data[new_name] = data.pop(old_name)

                normalized_node['data'] = data

            normalized_nodes.append(normalized_node)

        return normalized_nodes

    @staticmethod
    def extract_required_applications(nodes: List[Dict[str, Any]]) -> List[str]:
        """
        Extract list of required applications from nodes.
        """
        required_apps = set()

        for node in nodes:
            data = node.get('data', {})

            # Check for app references
            app_ref = data.get('appId') or data.get('app_id') or data.get('seed_key')
            if app_ref:
                required_apps.add(app_ref)

        return list(required_apps)

    @staticmethod
    def generate_flow_name(nodes: List[Dict[str, Any]]) -> str:
        """
        Generate a descriptive flow name from nodes.
        """
        # Try to get name from trigger node
        trigger_nodes = [n for n in nodes if n.get('type') == 'trigger']
        if trigger_nodes:
            trigger_label = trigger_nodes[0].get('data', {}).get('label', '')
            if trigger_label:
                return f"Flow - {trigger_label}"

        # Try to get name from first action node
        action_nodes = [n for n in nodes if n.get('type') == 'action']
        if action_nodes:
            action_label = action_nodes[0].get('data', {}).get('label', '')
            if action_label:
                return f"Flow - {action_label}"

        # Default name with timestamp
        return f"Imported Flow - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    def normalize_to_import_format(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize any supported format to the standard import format.
        Returns the normalized import data.
        """
        format_type = self.detect_format(json_data)
        logger.info(f"Detected format: {format_type}")

        # If it's already in export format, validate and return
        if format_type == "export":
            # Ensure nodes have normalized field names
            if 'flow' in json_data and 'flow_definition' in json_data['flow']:
                flow_def = json_data['flow']['flow_definition']
                if 'nodes' in flow_def:
                    flow_def['nodes'] = self.normalize_node_fields(flow_def['nodes'])
            # `version` is optional on the way in (see detect_format) but the
            # downstream import path treats it as required, so supply it rather
            # than making every caller carry boilerplate.
            json_data.setdefault("version", "1.0")
            return json_data

        # Handle direct format (nodes + edges at root)
        if format_type == "direct":
            nodes = self.normalize_node_fields(json_data.get('nodes', []))
            edges = json_data.get('edges', [])

            # Extract trigger config from nodes
            trigger_config = self.extract_trigger_from_nodes(nodes) or {"type": "manual"}

            # Extract required applications
            required_apps = self.extract_required_applications(nodes)

            # Generate flow name
            flow_name = self.generate_flow_name(nodes)

            return {
                "version": "1.0",
                "export_timestamp": datetime.now().isoformat(),
                "flow": {
                    "flow_name": flow_name,
                    "description": "Auto-imported flow",
                    "category": "imported",
                    "flow_scope": "user",
                    "trigger_config": trigger_config,
                    "flow_definition": {
                        "nodes": nodes,
                        "edges": edges
                    },
                    "is_synchronous": False,
                    "sync_timeout": 30
                },
                "metadata": {
                    "required_applications": required_apps,
                    "auto_normalized": True,
                    "original_format": format_type
                }
            }

        # Handle FlowCreate format
        if format_type == "flow_create":
            nodes = json_data.get('flow_definition', {}).get('nodes', [])
            normalized_nodes = self.normalize_node_fields(nodes)

            flow_data = json_data.copy()
            flow_data['flow_definition']['nodes'] = normalized_nodes

            # Extract required applications
            required_apps = self.extract_required_applications(normalized_nodes)

            return {
                "version": "1.0",
                "export_timestamp": datetime.now().isoformat(),
                "flow": flow_data,
                "metadata": {
                    "required_applications": required_apps,
                    "auto_normalized": True,
                    "original_format": format_type
                }
            }

        # Handle hybrid format
        if format_type == "hybrid":
            nodes = self.normalize_node_fields(json_data.get('nodes', []))
            edges = json_data.get('edges', [])

            # Extract or generate trigger config
            trigger_config = json_data.get('trigger_config')
            if not trigger_config:
                trigger_config = self.extract_trigger_from_nodes(nodes) or {"type": "manual"}

            # Extract required applications
            required_apps = self.extract_required_applications(nodes)

            # Use existing metadata or generate
            flow_name = json_data.get('flow_name', self.generate_flow_name(nodes))
            description = json_data.get('description', 'Auto-imported flow')
            category = json_data.get('category', 'imported')

            return {
                "version": "1.0",
                "export_timestamp": json_data.get('export_timestamp', datetime.now().isoformat()),
                "flow": {
                    "flow_name": flow_name,
                    "description": description,
                    "category": category,
                    "flow_scope": json_data.get('flow_scope', 'user'),
                    "trigger_config": trigger_config,
                    "flow_definition": {
                        "nodes": nodes,
                        "edges": edges
                    },
                    "is_synchronous": json_data.get('is_synchronous', False),
                    "sync_timeout": json_data.get('sync_timeout', 30)
                },
                "metadata": {
                    "required_applications": required_apps,
                    "auto_normalized": True,
                    "original_format": format_type
                }
            }

        # Unknown format - try to extract what we can
        logger.warning(f"Unknown format, attempting best-effort normalization")

        # Look for nodes and edges anywhere in the structure
        nodes = []
        edges = []

        def find_nodes_edges(obj, depth=0):
            if depth > 3:  # Prevent deep recursion
                return
            if isinstance(obj, dict):
                if 'nodes' in obj and isinstance(obj['nodes'], list):
                    nodes.extend(obj['nodes'])
                if 'edges' in obj and isinstance(obj['edges'], list):
                    edges.extend(obj['edges'])
                for value in obj.values():
                    find_nodes_edges(value, depth + 1)

        find_nodes_edges(json_data)

        if nodes:
            normalized_nodes = self.normalize_node_fields(nodes)
            required_apps = self.extract_required_applications(normalized_nodes)

            # Honour whatever the caller DID state before inventing anything.
            # Generating over a supplied name is the worst outcome here: the
            # flow saves, reports success, and quietly carries a name nobody
            # chose — so the caller cannot find it again by name, and the next
            # save makes a second one.
            stated = json_data.get("flow") if isinstance(json_data.get("flow"), dict) else {}
            if not isinstance(stated, dict):
                stated = {}
            flow_name = (stated.get("flow_name") or json_data.get("flow_name")
                         or self.generate_flow_name(normalized_nodes))
            trigger_config = (stated.get("trigger_config")
                              or json_data.get("trigger_config")
                              or self.extract_trigger_from_nodes(normalized_nodes)
                              or {"type": "manual"})

            return {
                "version": "1.0",
                "export_timestamp": datetime.now().isoformat(),
                "flow": {
                    "flow_name": flow_name,
                    "description": (stated.get("description")
                                    or json_data.get("description")
                                    or "Auto-imported flow (unknown format)"),
                    "category": (stated.get("category")
                                 or json_data.get("category") or "imported"),
                    "flow_scope": "user",
                    "trigger_config": trigger_config,
                    "flow_definition": {
                        "nodes": normalized_nodes,
                        "edges": edges
                    },
                    "is_synchronous": False,
                    "sync_timeout": 30
                },
                "metadata": {
                    "required_applications": required_apps,
                    "auto_normalized": True,
                    "original_format": "unknown",
                    "warning": "Flow was imported from an unknown format and may require manual adjustments"
                }
            }

        # Cannot normalize - return as is
        raise ValueError(f"Cannot normalize flow data: no valid nodes found in format type '{format_type}'")