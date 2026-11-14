"""
Related Flows Service

Service for managing pre-requisite and follow-up flow relationships between micro SaaS applications.
Includes CRUD operations, parameter auto-mapping logic, and relationship management.
"""

import json
import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.config import settings
from db.db_compat import parse_json_field

# Import unified models (work with both PostgreSQL and SQLite)
from db.models import User, Tenant, Flow
from db.application_models import FrontendFlowApplication, MicroSaasRelatedFlow

logger = logging.getLogger(__name__)


class RelatedFlowsError(Exception):
    """Custom exception for related flows errors"""
    pass


class RelatedFlowsService:
    """Service for managing pre-requisite and follow-up flow relationships"""

    def get_related_flows(
        self,
        db: Session,
        frontend_app_id: str,
        user_id: str,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Get all related flows (prerequisites and follow-ups) for a micro SaaS app.

        Args:
            db: Database session
            frontend_app_id: ID of the main frontend app
            user_id: User ID for authorization
            include_inactive: Whether to include inactive relationships

        Returns:
            Dictionary with prerequisites and followups lists
        """
        # Verify the user has access to this app
        main_app = self._verify_app_access(db, frontend_app_id, user_id)
        if not main_app:
            raise RelatedFlowsError("App not found or access denied")

        # Build query
        query = db.query(MicroSaasRelatedFlow).filter(
            MicroSaasRelatedFlow.frontend_app_id == frontend_app_id
        )

        if not include_inactive:
            query = query.filter(MicroSaasRelatedFlow.is_active == True)

        # Get all relationships
        relationships = query.order_by(
            MicroSaasRelatedFlow.relationship_type,
            MicroSaasRelatedFlow.execution_order
        ).all()

        prerequisites = []
        followups = []

        for rel in relationships:
            # Get related app details
            related_app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == rel.related_frontend_app_id
            ).first()

            if not related_app:
                continue

            # Get flow input/output schema
            input_schema, output_schema = self._get_flow_schemas(db, related_app.flow_id)

            rel_data = {
                "relationship_id": str(rel.relationship_id),
                "frontend_app_id": str(rel.frontend_app_id),
                "related_frontend_app_id": str(rel.related_frontend_app_id),
                "relationship_type": rel.relationship_type,
                "is_mandatory": bool(rel.is_mandatory),
                "execution_order": rel.execution_order,
                "display_name": rel.display_name,
                "documentation": rel.documentation,
                "parameter_mappings": parse_json_field(rel.parameter_mappings),
                "auto_map_enabled": bool(rel.auto_map_enabled),
                "is_active": bool(rel.is_active),
                "created_at": rel.created_at.isoformat() if rel.created_at else None,
                "updated_at": rel.updated_at.isoformat() if rel.updated_at else None,
                "related_app_name": related_app.frontend_app_name,
                "related_app_description": related_app.description,
                "related_app_public_url_slug": related_app.public_url_slug,
                "related_app_icon_url": related_app.icon_url,
                "related_app_input_schema": input_schema,
                "related_app_output_schema": output_schema
            }

            if rel.relationship_type == "prerequisite":
                prerequisites.append(rel_data)
            else:
                followups.append(rel_data)

        return {
            "prerequisites": prerequisites,
            "followups": followups,
            "total_prerequisites": len(prerequisites),
            "total_followups": len(followups)
        }

    def add_related_flow(
        self,
        db: Session,
        frontend_app_id: str,
        user_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a new related flow relationship.

        Args:
            db: Database session
            frontend_app_id: ID of the main frontend app
            user_id: User ID for authorization
            config: Configuration for the relationship

        Returns:
            Created relationship data
        """
        # Verify access to main app
        main_app = self._verify_app_access(db, frontend_app_id, user_id)
        if not main_app:
            raise RelatedFlowsError("App not found or access denied")

        related_frontend_app_id = config.get("related_frontend_app_id")
        relationship_type = config.get("relationship_type")

        # Verify related app exists
        related_app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == related_frontend_app_id
        ).first()

        if not related_app:
            raise RelatedFlowsError("Related app not found")

        # Prevent self-reference
        if frontend_app_id == related_frontend_app_id:
            raise RelatedFlowsError("Cannot create relationship with self")

        # Check for duplicate
        existing = db.query(MicroSaasRelatedFlow).filter(
            and_(
                MicroSaasRelatedFlow.frontend_app_id == frontend_app_id,
                MicroSaasRelatedFlow.related_frontend_app_id == related_frontend_app_id,
                MicroSaasRelatedFlow.relationship_type == relationship_type
            )
        ).first()

        if existing:
            raise RelatedFlowsError(f"Relationship already exists")

        # Check for circular reference (A -> B as prerequisite, B -> A as prerequisite)
        if relationship_type == "prerequisite":
            circular = db.query(MicroSaasRelatedFlow).filter(
                and_(
                    MicroSaasRelatedFlow.frontend_app_id == related_frontend_app_id,
                    MicroSaasRelatedFlow.related_frontend_app_id == frontend_app_id,
                    MicroSaasRelatedFlow.relationship_type == "prerequisite"
                )
            ).first()

            if circular:
                raise RelatedFlowsError("Circular prerequisite relationship not allowed")

        # Get the next execution order
        max_order = db.query(func.max(MicroSaasRelatedFlow.execution_order)).filter(
            and_(
                MicroSaasRelatedFlow.frontend_app_id == frontend_app_id,
                MicroSaasRelatedFlow.relationship_type == relationship_type
            )
        ).scalar()

        execution_order = config.get("execution_order", (max_order or 0) + 1)

        # Prepare parameter mappings
        parameter_mappings = config.get("parameter_mappings")
        if parameter_mappings and isinstance(parameter_mappings, dict):
            parameter_mappings = json.dumps(parameter_mappings)

        # Create relationship
        new_rel = MicroSaasRelatedFlow(
            relationship_id=str(uuid.uuid4()),
            frontend_app_id=frontend_app_id,
            related_frontend_app_id=related_frontend_app_id,
            relationship_type=relationship_type,
            is_mandatory=config.get("is_mandatory", False),
            execution_order=execution_order,
            display_name=config.get("display_name"),
            documentation=config.get("documentation"),
            parameter_mappings=parameter_mappings,
            auto_map_enabled=config.get("auto_map_enabled", True),
            is_active=True
        )

        db.add(new_rel)
        db.commit()
        db.refresh(new_rel)

        # Get input/output schema for related app
        input_schema, output_schema = self._get_flow_schemas(db, related_app.flow_id)

        return {
            "relationship_id": str(new_rel.relationship_id),
            "frontend_app_id": str(new_rel.frontend_app_id),
            "related_frontend_app_id": str(new_rel.related_frontend_app_id),
            "relationship_type": new_rel.relationship_type,
            "is_mandatory": bool(new_rel.is_mandatory),
            "execution_order": new_rel.execution_order,
            "display_name": new_rel.display_name,
            "documentation": new_rel.documentation,
            "parameter_mappings": parse_json_field(new_rel.parameter_mappings),
            "auto_map_enabled": bool(new_rel.auto_map_enabled),
            "is_active": bool(new_rel.is_active),
            "created_at": new_rel.created_at.isoformat() if new_rel.created_at else None,
            "updated_at": new_rel.updated_at.isoformat() if new_rel.updated_at else None,
            "related_app_name": related_app.frontend_app_name,
            "related_app_description": related_app.description,
            "related_app_public_url_slug": related_app.public_url_slug,
            "related_app_icon_url": related_app.icon_url,
            "related_app_input_schema": input_schema,
            "related_app_output_schema": output_schema
        }

    def update_related_flow(
        self,
        db: Session,
        relationship_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing related flow relationship.

        Args:
            db: Database session
            relationship_id: ID of the relationship to update
            user_id: User ID for authorization
            updates: Fields to update

        Returns:
            Updated relationship data
        """
        # Get relationship
        rel = db.query(MicroSaasRelatedFlow).filter(
            MicroSaasRelatedFlow.relationship_id == relationship_id
        ).first()

        if not rel:
            raise RelatedFlowsError("Relationship not found")

        # Verify access to main app
        main_app = self._verify_app_access(db, str(rel.frontend_app_id), user_id)
        if not main_app:
            raise RelatedFlowsError("Access denied")

        # Update allowed fields
        if "is_mandatory" in updates and updates["is_mandatory"] is not None:
            rel.is_mandatory = updates["is_mandatory"]

        if "execution_order" in updates and updates["execution_order"] is not None:
            rel.execution_order = updates["execution_order"]

        if "display_name" in updates:
            rel.display_name = updates["display_name"]

        if "documentation" in updates:
            rel.documentation = updates["documentation"]

        if "parameter_mappings" in updates:
            pm = updates["parameter_mappings"]
            rel.parameter_mappings = json.dumps(pm) if pm and isinstance(pm, dict) else pm

        if "auto_map_enabled" in updates and updates["auto_map_enabled"] is not None:
            rel.auto_map_enabled = updates["auto_map_enabled"]

        if "is_active" in updates and updates["is_active"] is not None:
            rel.is_active = updates["is_active"]

        db.commit()
        db.refresh(rel)

        # Get related app details
        related_app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == rel.related_frontend_app_id
        ).first()

        input_schema, output_schema = self._get_flow_schemas(db, related_app.flow_id) if related_app else (None, None)

        return {
            "relationship_id": str(rel.relationship_id),
            "frontend_app_id": str(rel.frontend_app_id),
            "related_frontend_app_id": str(rel.related_frontend_app_id),
            "relationship_type": rel.relationship_type,
            "is_mandatory": bool(rel.is_mandatory),
            "execution_order": rel.execution_order,
            "display_name": rel.display_name,
            "documentation": rel.documentation,
            "parameter_mappings": parse_json_field(rel.parameter_mappings),
            "auto_map_enabled": bool(rel.auto_map_enabled),
            "is_active": bool(rel.is_active),
            "created_at": rel.created_at.isoformat() if rel.created_at else None,
            "updated_at": rel.updated_at.isoformat() if rel.updated_at else None,
            "related_app_name": related_app.frontend_app_name if related_app else None,
            "related_app_description": related_app.description if related_app else None,
            "related_app_public_url_slug": related_app.public_url_slug if related_app else None,
            "related_app_icon_url": related_app.icon_url if related_app else None,
            "related_app_input_schema": input_schema,
            "related_app_output_schema": output_schema
        }

    def remove_related_flow(
        self,
        db: Session,
        relationship_id: str,
        user_id: str
    ) -> bool:
        """
        Remove a related flow relationship.

        Args:
            db: Database session
            relationship_id: ID of the relationship to remove
            user_id: User ID for authorization

        Returns:
            True if removed successfully
        """
        rel = db.query(MicroSaasRelatedFlow).filter(
            MicroSaasRelatedFlow.relationship_id == relationship_id
        ).first()

        if not rel:
            raise RelatedFlowsError("Relationship not found")

        # Verify access to main app
        main_app = self._verify_app_access(db, str(rel.frontend_app_id), user_id)
        if not main_app:
            raise RelatedFlowsError("Access denied")

        db.delete(rel)
        db.commit()

        return True

    def reorder_related_flows(
        self,
        db: Session,
        frontend_app_id: str,
        user_id: str,
        relationship_type: str,
        ordered_ids: List[str]
    ) -> bool:
        """
        Reorder related flows of a specific type.

        Args:
            db: Database session
            frontend_app_id: ID of the main frontend app
            user_id: User ID for authorization
            relationship_type: Type of relationships to reorder
            ordered_ids: List of relationship IDs in desired order

        Returns:
            True if reordered successfully
        """
        # Verify access
        main_app = self._verify_app_access(db, frontend_app_id, user_id)
        if not main_app:
            raise RelatedFlowsError("Access denied")

        # Update order for each relationship
        for order, rel_id in enumerate(ordered_ids):
            rel = db.query(MicroSaasRelatedFlow).filter(
                and_(
                    MicroSaasRelatedFlow.relationship_id == rel_id,
                    MicroSaasRelatedFlow.frontend_app_id == frontend_app_id,
                    MicroSaasRelatedFlow.relationship_type == relationship_type
                )
            ).first()

            if rel:
                rel.execution_order = order

        db.commit()
        return True

    def get_available_apps_for_linking(
        self,
        db: Session,
        frontend_app_id: str,
        user_id: str,
        relationship_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get apps available for linking as prerequisites or follow-ups.

        Args:
            db: Database session
            frontend_app_id: ID of the main frontend app (to exclude from results)
            user_id: User ID for authorization
            relationship_type: Filter by relationship type
            search: Search term for filtering

        Returns:
            List of available apps
        """
        # Get user's tenant
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise RelatedFlowsError("User not found")

        # Get apps that are:
        # 1. Active
        # 2. Not the current app
        # 3. Either: same tenant, public, or marketplace approved
        query = db.query(FrontendFlowApplication).filter(
            and_(
                FrontendFlowApplication.frontend_app_id != frontend_app_id,
                FrontendFlowApplication.is_active == True
            )
        )

        # Filter by tenant or public visibility
        query = query.filter(
            or_(
                FrontendFlowApplication.tenant_id == user.tenant_id,
                FrontendFlowApplication.visibility == "public",
                FrontendFlowApplication.marketplace_status == "approved"
            )
        )

        # Search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    FrontendFlowApplication.frontend_app_name.ilike(search_pattern),
                    FrontendFlowApplication.description.ilike(search_pattern)
                )
            )

        # Get existing relationships to exclude already linked apps
        existing_rels = db.query(MicroSaasRelatedFlow.related_frontend_app_id).filter(
            MicroSaasRelatedFlow.frontend_app_id == frontend_app_id
        )
        if relationship_type:
            existing_rels = existing_rels.filter(
                MicroSaasRelatedFlow.relationship_type == relationship_type
            )

        existing_ids = [str(r[0]) for r in existing_rels.all()]

        # Exclude already linked apps
        if existing_ids:
            query = query.filter(
                ~FrontendFlowApplication.frontend_app_id.in_(existing_ids)
            )

        apps = query.order_by(FrontendFlowApplication.frontend_app_name).limit(50).all()

        result = []
        for app in apps:
            # Get input/output schema
            input_params, output_params = [], []
            if app.flow_id:
                input_schema, output_schema = self._get_flow_schemas(db, app.flow_id)
                if input_schema:
                    input_params = list(input_schema.get("properties", {}).keys())
                if output_schema:
                    output_params = list(output_schema.get("properties", {}).keys())

            result.append({
                "frontend_app_id": str(app.frontend_app_id),
                "frontend_app_name": app.frontend_app_name,
                "description": app.description,
                "public_url_slug": app.public_url_slug,
                "icon_url": app.icon_url,
                "visibility": app.visibility,
                "has_input_parameters": len(input_params) > 0,
                "has_output_parameters": len(output_params) > 0,
                "input_parameter_names": input_params,
                "output_parameter_names": output_params
            })

        return {
            "apps": result,
            "total": len(result)
        }

    def get_public_related_flows_info(
        self,
        db: Session,
        public_url_slug: str
    ) -> Dict[str, Any]:
        """
        Get related flows info for public execution page (no auth required).

        Args:
            db: Database session
            public_url_slug: Public URL slug of the main app

        Returns:
            Related flows info for public consumption
        """
        # Get main app by slug
        main_app = db.query(FrontendFlowApplication).filter(
            and_(
                FrontendFlowApplication.public_url_slug == public_url_slug,
                FrontendFlowApplication.is_active == True
            )
        ).first()

        if not main_app:
            raise RelatedFlowsError("App not found")

        # Get active relationships
        relationships = db.query(MicroSaasRelatedFlow).filter(
            and_(
                MicroSaasRelatedFlow.frontend_app_id == main_app.frontend_app_id,
                MicroSaasRelatedFlow.is_active == True
            )
        ).order_by(
            MicroSaasRelatedFlow.relationship_type,
            MicroSaasRelatedFlow.execution_order
        ).all()

        prerequisites = []
        followups = []
        mandatory_count = 0
        optional_count = 0

        for rel in relationships:
            # Get related app
            related_app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == rel.related_frontend_app_id
            ).first()

            if not related_app or not related_app.is_active:
                continue

            # Get flow input/output parameters
            input_params, output_params = [], []
            if related_app.flow_id:
                input_schema, output_schema = self._get_flow_schemas(db, related_app.flow_id)
                if input_schema and input_schema.get("properties"):
                    for name, props in input_schema["properties"].items():
                        input_params.append({
                            "name": name,
                            "type": props.get("type", "string"),
                            "required": name in input_schema.get("required", []),
                            "description": props.get("description", "")
                        })
                if output_schema and output_schema.get("properties"):
                    for name, props in output_schema["properties"].items():
                        output_params.append({
                            "name": name,
                            "type": props.get("type", "string"),
                            "description": props.get("description", "")
                        })

            rel_info = {
                "relationship_id": str(rel.relationship_id),
                "related_frontend_app_id": str(rel.related_frontend_app_id),
                "relationship_type": rel.relationship_type,
                "is_mandatory": bool(rel.is_mandatory),
                "execution_order": rel.execution_order,
                "display_name": rel.display_name or related_app.frontend_app_name,
                "documentation": rel.documentation,
                "auto_map_enabled": bool(rel.auto_map_enabled),
                "app_name": related_app.frontend_app_name,
                "app_description": related_app.description,
                "public_url_slug": related_app.public_url_slug,
                "icon_url": related_app.icon_url,
                "input_parameters": input_params,
                "output_parameters": output_params,
                "parameter_mappings": parse_json_field(rel.parameter_mappings)
            }

            if rel.relationship_type == "prerequisite":
                prerequisites.append(rel_info)
                if rel.is_mandatory:
                    mandatory_count += 1
                else:
                    optional_count += 1
            else:
                followups.append(rel_info)

        return {
            "prerequisites": prerequisites,
            "followups": followups,
            "mandatory_prerequisites_count": mandatory_count,
            "optional_prerequisites_count": optional_count
        }

    def auto_map_parameters(
        self,
        source_outputs: Dict[str, Any],
        target_input_schema: Dict[str, Any],
        mapping_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Auto-map parameters from source outputs to target inputs.

        Matching rules (in priority order):
        1. Manual mappings from config
        2. Exact name match (case-insensitive)
        3. Partial match (source contains target or vice versa)

        Args:
            source_outputs: Output values from source flow
            target_input_schema: Input schema of target flow
            mapping_config: Optional manual mapping configuration

        Returns:
            Dictionary of mapped parameters with metadata
        """
        if not target_input_schema or not target_input_schema.get("properties"):
            return {"auto_mapped": [], "unmapped_required": [], "unmapped_optional": []}

        target_properties = target_input_schema.get("properties", {})
        required_inputs = target_input_schema.get("required", [])

        mapped = []
        unmapped_required = []
        unmapped_optional = []

        # Build lookup for source outputs (lowercase keys)
        source_lower = {k.lower(): (k, v) for k, v in source_outputs.items()}

        # Apply manual mappings first
        manual_mapped = set()
        if mapping_config and mapping_config.get("mappings"):
            for mapping in mapping_config["mappings"]:
                source_param = mapping.get("source_param")
                target_param = mapping.get("target_param")

                if source_param in source_outputs and target_param in target_properties:
                    mapped.append({
                        "source_name": source_param,
                        "target_name": target_param,
                        "source_value": source_outputs[source_param],
                        "match_type": "manual"
                    })
                    manual_mapped.add(target_param)

        # Auto-map remaining parameters
        for target_name, target_props in target_properties.items():
            if target_name in manual_mapped:
                continue

            target_lower = target_name.lower()
            matched = False

            # Try exact match
            if target_lower in source_lower:
                source_name, source_value = source_lower[target_lower]
                mapped.append({
                    "source_name": source_name,
                    "target_name": target_name,
                    "source_value": source_value,
                    "match_type": "exact"
                })
                matched = True

            # Try partial match
            if not matched:
                for source_key, (source_name, source_value) in source_lower.items():
                    if target_lower in source_key or source_key in target_lower:
                        mapped.append({
                            "source_name": source_name,
                            "target_name": target_name,
                            "source_value": source_value,
                            "match_type": "partial"
                        })
                        matched = True
                        break

            if not matched:
                if target_name in required_inputs:
                    unmapped_required.append(target_name)
                else:
                    unmapped_optional.append(target_name)

        return {
            "auto_mapped": mapped,
            "unmapped_required": unmapped_required,
            "unmapped_optional": unmapped_optional
        }

    def preview_auto_mapping(
        self,
        db: Session,
        frontend_app_id: str,
        source_outputs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Preview auto-mapping for all follow-up flows of an app.

        Args:
            db: Database session
            frontend_app_id: ID of the main frontend app
            source_outputs: Output values from the main flow execution

        Returns:
            List of auto-mapping previews for each follow-up
        """
        # Get follow-up relationships
        followups = db.query(MicroSaasRelatedFlow).filter(
            and_(
                MicroSaasRelatedFlow.frontend_app_id == frontend_app_id,
                MicroSaasRelatedFlow.relationship_type == "followup",
                MicroSaasRelatedFlow.is_active == True
            )
        ).order_by(MicroSaasRelatedFlow.execution_order).all()

        previews = []

        for rel in followups:
            related_app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == rel.related_frontend_app_id
            ).first()

            if not related_app or not related_app.flow_id:
                continue

            input_schema, _ = self._get_flow_schemas(db, related_app.flow_id)

            mapping_config = parse_json_field(rel.parameter_mappings)

            if rel.auto_map_enabled:
                mapping_result = self.auto_map_parameters(
                    source_outputs,
                    input_schema,
                    mapping_config
                )
            else:
                # Only manual mappings
                mapping_result = self.auto_map_parameters(
                    source_outputs,
                    input_schema,
                    mapping_config
                )
                # Keep only manual mappings
                mapping_result["auto_mapped"] = [
                    m for m in mapping_result["auto_mapped"]
                    if m["match_type"] == "manual"
                ]

            previews.append({
                "followup_app_id": str(rel.related_frontend_app_id),
                "followup_app_name": related_app.frontend_app_name,
                "public_url_slug": related_app.public_url_slug,
                "auto_mapped": mapping_result["auto_mapped"],
                "unmapped_required": mapping_result["unmapped_required"],
                "unmapped_optional": mapping_result["unmapped_optional"]
            })

        return previews

    def _verify_app_access(
        self,
        db: Session,
        frontend_app_id: str,
        user_id: str
    ) -> Optional[FrontendFlowApplication]:
        """
        Verify user has access to a frontend app.

        Returns the app if access is granted, None otherwise.
        """
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return None

        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app:
            return None

        # Check if user is creator or same tenant
        if str(app.created_by) == user_id or str(app.tenant_id) == str(user.tenant_id):
            return app

        return None

    def _get_flow_schemas(
        self,
        db: Session,
        flow_id: Optional[str]
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Get input and output schemas from a flow definition.

        Returns (input_schema, output_schema) tuple.
        """
        if not flow_id:
            return None, None

        flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
        if not flow or not flow.flow_definition:
            return None, None

        try:
            flow_def = parse_json_field(flow.flow_definition) or {}

            nodes = flow_def.get("nodes", [])

            input_schema = {"type": "object", "properties": {}, "required": []}
            output_schema = {"type": "object", "properties": {}}

            # Extract input from trigger node
            for node in nodes:
                if node.get("type") == "trigger":
                    data = node.get("data", {})
                    manual_vars = data.get("manualVariables", [])
                    for var in manual_vars:
                        var_name = var.get("name", var.get("id", ""))
                        var_type = var.get("dataType", "string")
                        input_schema["properties"][var_name] = {
                            "type": var_type,
                            "description": var.get("displayName", var_name)
                        }
                        if var.get("required", False):
                            input_schema["required"].append(var_name)

                # Extract output from response node
                elif node.get("type") == "response":
                    data = node.get("data", {})
                    # Simple output schema - actual output depends on execution
                    output_schema["properties"]["result"] = {
                        "type": "object",
                        "description": "Flow execution result"
                    }

            return input_schema, output_schema

        except Exception as e:
            logger.error(f"Error parsing flow schemas: {e}")
            return None, None


# Singleton instance
related_flows_service = RelatedFlowsService()
