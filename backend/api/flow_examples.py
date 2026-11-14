from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import logging
import os
from pathlib import Path

from db.database import get_db
from core.auth_utils import get_current_user_required as get_current_user
from core.config import settings
from middleware.permissions import has_permission

# Import models - PostgreSQL Only
from db.models import User, UserRole, Flow, FlowStatus
from db.application_models import Application, ApplicationSubscription

from services.flow_format_normalizer import FlowFormatNormalizer
from db.flow_example_models import FlowExampleRating, FlowExampleFavorite, FlowExampleUsageStats
from sqlalchemy import func

router = APIRouter(prefix="/api/v1/flow-examples", tags=["flow-examples"])
logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "flow-design-src"
EXAMPLES_METADATA_FILE = EXAMPLES_DIR / "examples.json"

# Pydantic models
class FlowExampleMetadata(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    color: str
    tags: List[str]
    difficulty: str  # "Beginner", "Intermediate", "Advanced"
    estimated_time: str  # e.g., "5-10 minutes"
    filename: str
    # Usage stats
    import_count: int = 0
    average_rating: Optional[float] = None
    rating_count: int = 0
    favorite_count: int = 0
    # User-specific data
    user_rating: Optional[int] = None
    is_favorited: bool = False

class FlowExampleList(BaseModel):
    examples: List[FlowExampleMetadata]
    categories: List[Dict[str, str]]

class FlowExampleDetail(BaseModel):
    metadata: FlowExampleMetadata
    flow_data: Dict[str, Any]

class ImportFlowExampleRequest(BaseModel):
    example_id: str

class ImportFlowExampleResponse(BaseModel):
    flow_id: str
    flow_name: str
    message: str

class ValidateFlowExampleRequest(BaseModel):
    example_id: str

class ApplicationRequirement(BaseModel):
    app_id: str
    app_name: str
    app_type: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    is_subscribed: bool
    is_connected: bool = False
    subscription_id: Optional[str] = None
    status: str  # 'ready', 'not_connected', 'not_subscribed', 'seed_available', 'not_found'
    auth_type: Optional[str] = None
    required_fields: List[Dict[str, Any]] = []
    config_fields: List[Dict[str, Any]] = []  # Subscription config fields like {domain}
    documentation_url: Optional[str] = None
    used_in_nodes: List[Dict[str, Any]] = []
    seed_application_key: Optional[str] = None  # Key for installing from seed applications

class ValidateFlowExampleResponse(BaseModel):
    can_import: bool
    required_applications: List[ApplicationRequirement]
    missing_applications: List[ApplicationRequirement]
    message: str

class PublishFlowAsExampleRequest(BaseModel):
    flow_id: str
    example_name: str
    description: str
    category: str
    tags: List[str]
    difficulty: str
    estimated_time: str

class PublishFlowAsExampleResponse(BaseModel):
    example_id: str
    filename: str
    message: str

class RateExampleRequest(BaseModel):
    rating: int  # 1-5
    review: Optional[str] = None

class RateExampleResponse(BaseModel):
    example_id: str
    rating: int
    average_rating: float
    rating_count: int
    message: str

class FavoriteExampleResponse(BaseModel):
    example_id: str
    is_favorited: bool
    favorite_count: int
    message: str

def can_access_flow_examples(user: User) -> bool:
    """Check if user has permission to access flow examples"""
    # Allow FLOW_DESIGNER and above roles
    allowed_roles = [
        UserRole.INSTANCE_ADMIN,
        UserRole.TENANT_ADMIN,
        UserRole.FLOW_DESIGNER,
        UserRole.FLOW_EXECUTOR  # Also allow flow executors to view examples
    ]
    return user.role in allowed_roles

def load_examples_metadata() -> Dict[str, Any]:
    """Load examples metadata from examples.json file"""
    if not EXAMPLES_METADATA_FILE.exists():
        logger.warning(f"Examples metadata file not found: {EXAMPLES_METADATA_FILE}")
        return {"examples": [], "categories": []}

    try:
        with open(EXAMPLES_METADATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading examples metadata: {e}")
        return {"examples": [], "categories": []}

def load_flow_example(filename: str) -> Optional[Dict[str, Any]]:
    """Load a flow example JSON file"""
    file_path = EXAMPLES_DIR / filename

    if not file_path.exists():
        logger.warning(f"Flow example file not found: {file_path}")
        return None

    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading flow example {filename}: {e}")
        return None

def extract_category_from_flow(flow_data: Dict[str, Any]) -> str:
    """Extract category from flow data"""
    # Try to get category from different locations in the flow data
    if isinstance(flow_data, dict):
        # Check top-level category
        if "category" in flow_data and flow_data["category"]:
            return flow_data["category"]

        # Check inside flow object
        if "flow" in flow_data and isinstance(flow_data["flow"], dict):
            if "category" in flow_data["flow"] and flow_data["flow"]["category"]:
                return flow_data["flow"]["category"]

    return "Uncategorized"

def get_example_stats(db: Session, example_id: str, user_id: str = None) -> Dict[str, Any]:
    """Get usage stats, ratings, and favorites for an example"""
    stats = {
        "import_count": 0,
        "average_rating": None,
        "rating_count": 0,
        "favorite_count": 0,
        "user_rating": None,
        "is_favorited": False
    }

    # Get usage stats
    usage = db.query(FlowExampleUsageStats).filter(
        FlowExampleUsageStats.example_id == example_id
    ).first()

    if usage:
        stats["import_count"] = usage.import_count

    # Get rating stats
    rating_stats = db.query(
        func.avg(FlowExampleRating.rating).label('avg_rating'),
        func.count(FlowExampleRating.id).label('rating_count')
    ).filter(
        FlowExampleRating.example_id == example_id
    ).first()

    if rating_stats and rating_stats.rating_count > 0:
        stats["average_rating"] = round(float(rating_stats.avg_rating), 1)
        stats["rating_count"] = rating_stats.rating_count

    # Get favorite count
    favorite_count = db.query(func.count(FlowExampleFavorite.id)).filter(
        FlowExampleFavorite.example_id == example_id
    ).scalar()

    stats["favorite_count"] = favorite_count or 0

    # Get user-specific data if user_id provided
    if user_id:
        user_rating = db.query(FlowExampleRating).filter(
            FlowExampleRating.example_id == example_id,
            FlowExampleRating.user_id == user_id
        ).first()

        if user_rating:
            stats["user_rating"] = user_rating.rating

        is_favorited = db.query(FlowExampleFavorite).filter(
            FlowExampleFavorite.example_id == example_id,
            FlowExampleFavorite.user_id == user_id
        ).first() is not None

        stats["is_favorited"] = is_favorited

    return stats

def enrich_example_with_stats(example: Dict[str, Any], db: Session, user_id: str = None) -> Dict[str, Any]:
    """Enrich example metadata with stats"""
    stats = get_example_stats(db, example["id"], user_id)
    example.update(stats)
    return example

def extract_required_app_ids(flow_data: Dict[str, Any]) -> List[str]:
    """Extract unique application IDs from flow definition"""
    app_ids = set()

    # Extract flow definition from different possible locations
    flow_definition = None
    if isinstance(flow_data, dict):
        if "flow" in flow_data and "flow_definition" in flow_data["flow"]:
            flow_definition = flow_data["flow"]["flow_definition"]
        elif "flow_definition" in flow_data:
            flow_definition = flow_data["flow_definition"]

    if not flow_definition or not isinstance(flow_definition, dict):
        return []

    # Extract app IDs from nodes
    nodes = flow_definition.get("nodes", [])
    for node in nodes:
        if isinstance(node, dict):
            node_data = node.get("data", {})
            app_id = node_data.get("appId")
            if app_id:
                app_ids.add(app_id)

    return list(app_ids)

def extract_config_variables(base_url: str) -> List[Dict[str, Any]]:
    """
    Extract configuration variables from base_url like {domain}, {port}, etc.

    Returns:
        List of config field definitions
    """
    import re

    if not base_url:
        return []

    # Find all variables in format {variable_name}
    pattern = r'\{([^}]+)\}'
    matches = re.findall(pattern, base_url)

    config_fields = []
    for var_name in matches:
        # Create a field definition for each variable
        field = {
            'name': var_name,
            'label': var_name.replace('_', ' ').title(),
            'type': 'text',
            'required': True,
            'description': f'Enter the {var_name} for your {var_name} instance',
            'placeholder': f'e.g., example.com' if 'domain' in var_name.lower() else f'Enter {var_name}'
        }
        config_fields.append(field)

    return config_fields

def validate_flow_requirements(
    db: Session,
    flow_data: Dict[str, Any],
    tenant_id: str
) -> Dict[str, Any]:
    """
    Validate if all required applications for a flow are available and subscribed

    Returns:
        Dict with validation results including required_applications and missing_applications
    """
    import json
    from services.json_seed_manager import json_seed_manager as seed_manager

    # Extract flow definition to get node usage information
    flow = flow_data.get('flow', {})
    flow_definition = flow.get('flow_definition', {})
    nodes = flow_definition.get('nodes', [])

    # Extract application IDs from nodes and track which nodes use each app
    app_usage = {}  # {app_id: [{"node_id": ..., "node_label": ..., "service_name": ...}]}

    for node in nodes:
        if isinstance(node, dict) and node.get('type') in ['action', 'trigger']:
            node_data = node.get('data', {})
            app_id = node_data.get('appId')

            if app_id:
                if app_id not in app_usage:
                    app_usage[app_id] = []

                app_usage[app_id].append({
                    'node_id': node.get('id'),
                    'node_label': node_data.get('label', 'Unnamed Node'),
                    'service_name': node_data.get('serviceDisplayName') or node_data.get('service', 'Unknown Service'),
                    'node_type': node.get('type')
                })

    # Check trigger config for app usage
    trigger_config = flow.get('trigger_config', {})
    if trigger_config.get('app_id'):
        app_id = trigger_config['app_id']
        if app_id not in app_usage:
            app_usage[app_id] = []

        app_usage[app_id].append({
            'node_id': 'trigger',
            'node_label': f"Trigger ({trigger_config.get('type', 'Unknown')})",
            'service_name': trigger_config.get('trigger_type', 'Unknown Trigger'),
            'node_type': 'trigger'
        })

    if not app_usage:
        return {
            "can_import": True,
            "required_applications": [],
            "missing_applications": [],
            "message": "No applications required for this flow"
        }

    # Get application details and subscription status
    required_applications = []
    missing_applications = []

    for app_id, usage_list in app_usage.items():
        # Get application details
        app = db.query(Application).filter(Application.app_id == app_id).first()

        if not app:
            # App not found in database - check if it exists as a seed application
            seed_applications = seed_manager.discover_applications()
            seed_app_key = None
            seed_app_data = None

            # Find seed application by app_id
            for key, seed_data in seed_applications.items():
                if seed_data.get('application', {}).get('app_id') == app_id:
                    seed_app_key = key
                    seed_app_data = seed_data
                    break

            if seed_app_data:
                # Seed application exists but not installed
                app_info = seed_app_data.get('application', {})

                # Extract config variables from base_url
                config_fields = extract_config_variables(app_info.get('base_url', ''))

                missing_applications.append({
                    'app_id': app_id,
                    'app_name': app_info.get('app_name', 'Unknown Application'),
                    'app_type': app_info.get('app_type', 'api'),
                    'description': app_info.get('description', 'This application is available for installation'),
                    'icon_url': app_info.get('icon_url'),
                    'is_subscribed': False,
                    'is_connected': False,
                    'subscription_id': None,
                    'auth_type': app_info.get('auth_type', 'none'),
                    'required_fields': [],
                    'config_fields': config_fields,
                    'documentation_url': app_info.get('documentation_url'),
                    'used_in_nodes': usage_list,
                    'status': 'seed_available',
                    'seed_application_key': seed_app_key
                })
            else:
                # App not found anywhere
                missing_applications.append({
                    'app_id': app_id,
                    'app_name': 'Unknown Application',
                    'app_type': 'unknown',
                    'description': 'This application is not available in your instance',
                    'icon_url': None,
                    'is_subscribed': False,
                    'is_connected': False,
                    'subscription_id': None,
                    'auth_type': None,
                    'required_fields': [],
                    'documentation_url': None,
                    'used_in_nodes': usage_list,
                    'status': 'not_found'
                })
            continue

        # Check if tenant has an active subscription
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.tenant_id == tenant_id,
            ApplicationSubscription.status == "active"
        ).first()

        is_subscribed = subscription is not None

        # Determine if credentials are configured (connection ready)
        is_connected = False
        if subscription and subscription.auth_credentials:
            # Check if auth_credentials has actual data
            auth_creds = subscription.auth_credentials
            if isinstance(auth_creds, str):
                try:
                    auth_creds = json.loads(auth_creds)
                except:
                    pass
            is_connected = bool(auth_creds and len(auth_creds) > 0)

        # Get authentication requirements
        auth_type = app.auth_type or 'none'
        required_fields = []

        if app.auth_config:
            auth_config = app.auth_config
            if isinstance(auth_config, str):
                try:
                    auth_config = json.loads(auth_config)
                except:
                    auth_config = {}

            # Extract required fields from auth_config
            if auth_type == 'api_key':
                required_fields.append({
                    'name': 'api_key',
                    'label': auth_config.get('key_name', 'API Key'),
                    'type': 'password',
                    'required': True,
                    'description': 'Your API key for authentication'
                })
            elif auth_type == 'oauth2':
                required_fields.append({
                    'name': 'access_token',
                    'label': 'Access Token',
                    'type': 'password',
                    'required': True,
                    'description': 'OAuth 2.0 access token'
                })
            elif auth_type == 'basic':
                required_fields.extend([
                    {'name': 'username', 'label': 'Username', 'type': 'text', 'required': True},
                    {'name': 'password', 'label': 'Password', 'type': 'password', 'required': True}
                ])
            elif auth_type == 'database':
                required_fields.extend([
                    {'name': 'host', 'label': 'Host', 'type': 'text', 'required': True},
                    {'name': 'port', 'label': 'Port', 'type': 'number', 'required': True},
                    {'name': 'database', 'label': 'Database Name', 'type': 'text', 'required': True},
                    {'name': 'username', 'label': 'Username', 'type': 'text', 'required': True},
                    {'name': 'password', 'label': 'Password', 'type': 'password', 'required': True}
                ])
            elif auth_type == 'custom':
                # Extract fields from auth_config
                fields = auth_config.get('fields', [])
                for field in fields:
                    required_fields.append({
                        'name': field.get('name'),
                        'label': field.get('label', field.get('name')),
                        'type': field.get('type', 'text'),
                        'required': field.get('required', True),
                        'description': field.get('description', '')
                    })

        # Extract config variables from base_url
        config_fields = extract_config_variables(app.base_url) if app.base_url else []

        # Determine status
        if not is_subscribed:
            status = 'not_subscribed'
        elif not is_connected and auth_type != 'none':
            status = 'not_connected'
        else:
            status = 'ready'

        app_requirement = {
            "app_id": str(app.app_id),
            "app_name": app.app_name,
            "app_type": app.app_type or "api",
            "description": app.description,
            "icon_url": app.icon_url,
            "is_subscribed": is_subscribed,
            "is_connected": is_connected,
            "subscription_id": str(subscription.subscription_id) if subscription else None,
            "auth_type": auth_type,
            "required_fields": required_fields,
            "config_fields": config_fields,
            "documentation_url": app.documentation_url if hasattr(app, 'documentation_url') else None,
            "used_in_nodes": usage_list,
            "status": status
        }

        required_applications.append(app_requirement)

        if status != 'ready':
            missing_applications.append(app_requirement)

    can_import = len(missing_applications) == 0

    if can_import:
        message = 'All required applications are installed and connected'
    else:
        not_subscribed = [app for app in missing_applications if app['status'] == 'not_subscribed']
        not_connected = [app for app in missing_applications if app['status'] == 'not_connected']

        message_parts = []
        if not_subscribed:
            message_parts.append(f"{len(not_subscribed)} application(s) need to be installed")
        if not_connected:
            message_parts.append(f"{len(not_connected)} application(s) need credentials")

        message = " and ".join(message_parts)

    return {
        "can_import": can_import,
        "required_applications": required_applications,
        "missing_applications": missing_applications,
        "message": message
    }

@router.get("/", response_model=FlowExampleList)
async def list_flow_examples(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    sort_by: Optional[str] = "name",  # name, rating, imports, favorites
    favorites_only: Optional[bool] = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all available flow examples with optional filtering and sorting.
    Accessible to FLOW_DESIGNER role and above.
    """
    # Check permissions
    if not can_access_flow_examples(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access flow examples"
        )

    # Load metadata
    metadata = load_examples_metadata()
    examples = metadata.get("examples", [])
    categories = metadata.get("categories", [])

    # Enrich examples with stats
    enriched_examples = []
    for example in examples:
        enriched = enrich_example_with_stats(example.copy(), db, current_user.user_id)
        enriched_examples.append(enriched)

    # Apply filters
    if category:
        enriched_examples = [ex for ex in enriched_examples if ex.get("category") == category]

    if difficulty:
        enriched_examples = [ex for ex in enriched_examples if ex.get("difficulty") == difficulty]

    if favorites_only:
        enriched_examples = [ex for ex in enriched_examples if ex.get("is_favorited")]

    # Apply sorting
    if sort_by == "rating":
        enriched_examples.sort(key=lambda x: (x.get("average_rating") or 0, x.get("rating_count") or 0), reverse=True)
    elif sort_by == "imports":
        enriched_examples.sort(key=lambda x: x.get("import_count", 0), reverse=True)
    elif sort_by == "favorites":
        enriched_examples.sort(key=lambda x: x.get("favorite_count", 0), reverse=True)
    else:  # name (default)
        enriched_examples.sort(key=lambda x: x.get("name", ""))

    return FlowExampleList(
        examples=enriched_examples,
        categories=categories
    )

@router.get("/{example_id}", response_model=FlowExampleDetail)
async def get_flow_example(
    example_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific flow example by ID.
    Accessible to FLOW_DESIGNER role and above.
    """
    # Check permissions
    if not can_access_flow_examples(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access flow examples"
        )

    # Load metadata
    metadata = load_examples_metadata()
    examples = metadata.get("examples", [])

    # Find the example
    example = next((ex for ex in examples if ex.get("id") == example_id), None)

    if not example:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow example with ID '{example_id}' not found"
        )

    # Load the flow data
    flow_data = load_flow_example(example["filename"])

    if not flow_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading flow example data for '{example_id}'"
        )

    return FlowExampleDetail(
        metadata=FlowExampleMetadata(**example),
        flow_data=flow_data
    )

@router.post("/{example_id}/validate", response_model=ValidateFlowExampleResponse)
async def validate_flow_example(
    example_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate if a flow example can be imported by checking required applications.
    Returns list of required and missing applications.
    Accessible to FLOW_DESIGNER role and above.
    """
    # Check permissions
    if not can_access_flow_examples(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access flow examples"
        )

    # Load metadata
    metadata = load_examples_metadata()
    examples = metadata.get("examples", [])

    # Find the example
    example = next((ex for ex in examples if ex.get("id") == example_id), None)

    if not example:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow example with ID '{example_id}' not found"
        )

    # Load the flow data
    flow_data = load_flow_example(example["filename"])

    if not flow_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading flow example data for '{example_id}'"
        )

    try:
        # Validate flow requirements
        validation_result = validate_flow_requirements(
            db=db,
            flow_data=flow_data,
            tenant_id=current_user.tenant_id
        )

        return ValidateFlowExampleResponse(**validation_result)

    except Exception as e:
        logger.error(f"Error validating flow example '{example_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating flow example: {str(e)}"
        )

@router.post("/{example_id}/import", response_model=ImportFlowExampleResponse)
async def import_flow_example(
    example_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import a flow example into the user's flows.
    Accessible to FLOW_DESIGNER role and above.
    """
    # Check permissions
    if not can_access_flow_examples(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to import flow examples"
        )

    # Check if user has permission to create flows
    if not has_permission(current_user, "flows", "create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create flows"
        )

    # Load metadata
    metadata = load_examples_metadata()
    examples = metadata.get("examples", [])

    # Find the example
    example = next((ex for ex in examples if ex.get("id") == example_id), None)

    if not example:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow example with ID '{example_id}' not found"
        )

    # Load the flow data
    flow_data = load_flow_example(example["filename"])

    if not flow_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading flow example data for '{example_id}'"
        )

    # Validate requirements before importing
    validation_result = validate_flow_requirements(
        db=db,
        flow_data=flow_data,
        tenant_id=current_user.tenant_id
    )

    if not validation_result["can_import"]:
        missing_apps = validation_result["missing_applications"]
        app_names = [app["app_name"] for app in missing_apps]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot import flow: Missing required applications - {', '.join(app_names)}. Please subscribe to these applications first."
        )

    try:
        # Use FlowFormatNormalizer to normalize the flow data
        normalizer = FlowFormatNormalizer()
        normalized_data = normalizer.normalize_to_import_format(flow_data)

        # Extract flow information from the normalized structure
        flow_data_normalized = normalized_data.get("flow", {})
        flow_name = flow_data_normalized.get("flow_name", example["name"])
        description = flow_data_normalized.get("description", example["description"])
        category = flow_data_normalized.get("category", example["category"])
        trigger_config = flow_data_normalized.get("trigger_config", {})
        flow_definition = flow_data_normalized.get("flow_definition", {"nodes": [], "edges": []})
        is_synchronous = flow_data_normalized.get("is_synchronous", False)
        sync_timeout = flow_data_normalized.get("sync_timeout", 30)

        # Create a new flow with a unique name
        base_name = flow_name
        counter = 1
        while db.query(Flow).filter(
            Flow.flow_name == flow_name,
            Flow.tenant_id == current_user.tenant_id
        ).first():
            flow_name = f"{base_name} ({counter})"
            counter += 1

        # Create the new flow
        new_flow = Flow(
            flow_name=flow_name,
            description=f"{description} (Imported from example)",
            category=category,
            trigger_config=trigger_config,  # Pass dict directly, SQLAlchemy JSON type handles serialization
            flow_definition=flow_definition,  # Pass dict directly, SQLAlchemy JSON type handles serialization
            is_synchronous=is_synchronous,
            sync_timeout=sync_timeout,
            status=FlowStatus.DRAFT,
            tenant_id=current_user.tenant_id,
            created_by=current_user.user_id,
            flow_scope="user",  # Create as user-scoped flow
            last_modified_by=current_user.user_id
        )

        db.add(new_flow)
        db.commit()
        db.refresh(new_flow)

        # Update usage stats
        usage_stats = db.query(FlowExampleUsageStats).filter(
            FlowExampleUsageStats.example_id == example_id
        ).first()

        if usage_stats:
            usage_stats.import_count += 1
            usage_stats.last_imported_at = datetime.now()
        else:
            usage_stats = FlowExampleUsageStats(
                example_id=example_id,
                import_count=1,
                last_imported_at=datetime.now()
            )
            db.add(usage_stats)

        db.commit()

        logger.info(f"Flow example '{example_id}' imported as flow '{new_flow.flow_id}' by user '{current_user.email}'")

        return ImportFlowExampleResponse(
            flow_id=new_flow.flow_id,
            flow_name=new_flow.flow_name,
            message=f"Flow example '{example['name']}' imported successfully"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error importing flow example '{example_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error importing flow example: {str(e)}"
        )

@router.get("/categories/list")
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of all available categories.
    Accessible to FLOW_DESIGNER role and above.
    """
    # Check permissions
    if not can_access_flow_examples(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access flow examples"
        )

    # Load metadata
    metadata = load_examples_metadata()
    categories = metadata.get("categories", [])

    return {"categories": categories}

@router.post("/publish", response_model=PublishFlowAsExampleResponse)
async def publish_flow_as_example(
    request: PublishFlowAsExampleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Publish a flow as an example. Only accessible to INSTANCE_ADMIN.
    """
    # Check if user is instance admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instance admins can publish flows as examples"
        )

    # Get the flow
    flow = db.query(Flow).filter(Flow.flow_id == request.flow_id).first()

    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow with ID '{request.flow_id}' not found"
        )

    try:
        # Parse flow definition
        flow_definition = json.loads(flow.flow_definition) if isinstance(flow.flow_definition, str) else flow.flow_definition
        trigger_config = json.loads(flow.trigger_config) if isinstance(flow.trigger_config, str) else flow.trigger_config

        # Create export data structure
        export_data = {
            "version": "1.0",
            "export_timestamp": datetime.now().isoformat() + "Z",
            "flow": {
                "flow_name": request.example_name,
                "description": request.description,
                "category": request.category,
                "trigger_config": trigger_config,
                "flow_definition": flow_definition,
                "is_synchronous": flow.is_synchronous,
                "sync_timeout": flow.sync_timeout
            },
            "metadata": {
                "required_applications": [],
                "source_instance": {
                    "name": "IOFlow",
                    "version": "1.0"
                }
            }
        }

        # Generate unique example ID and filename
        example_id = request.example_name.lower().replace(" ", "-").replace("&", "and")
        # Remove special characters
        example_id = "".join(c for c in example_id if c.isalnum() or c == "-")

        # Generate filename
        base_filename = f"{example_id}.json"
        filename = base_filename
        counter = 1

        # Check if file exists and generate unique name
        while (EXAMPLES_DIR / filename).exists():
            filename = f"{example_id}_{counter}.json"
            counter += 1

        # Save flow to file
        file_path = EXAMPLES_DIR / filename
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Flow '{flow.flow_name}' exported to {file_path}")

        # Update examples.json metadata
        metadata = load_examples_metadata()
        examples = metadata.get("examples", [])
        categories = metadata.get("categories", [])

        # Get icon and color for the category
        category_info = next((cat for cat in categories if cat["name"] == request.category), None)
        icon = category_info["icon"] if category_info else "SparklesIcon"
        color = category_info["color"] if category_info else "purple"

        # Create new example metadata entry
        new_example = {
            "id": example_id,
            "name": request.example_name,
            "description": request.description,
            "category": request.category,
            "icon": icon,
            "color": color,
            "tags": request.tags,
            "difficulty": request.difficulty,
            "estimated_time": request.estimated_time,
            "filename": filename
        }

        # Check if example already exists (by id) and update it
        existing_index = next((i for i, ex in enumerate(examples) if ex["id"] == example_id), None)
        if existing_index is not None:
            examples[existing_index] = new_example
            logger.info(f"Updated existing example metadata for '{example_id}'")
        else:
            examples.append(new_example)
            logger.info(f"Added new example metadata for '{example_id}'")

        # Save updated metadata
        metadata["examples"] = examples
        with open(EXAMPLES_METADATA_FILE, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Flow '{flow.flow_name}' published as example '{example_id}' by admin '{current_user.email}'")

        return PublishFlowAsExampleResponse(
            example_id=example_id,
            filename=filename,
            message=f"Flow published successfully as '{request.example_name}'"
        )

    except Exception as e:
        logger.error(f"Error publishing flow '{request.flow_id}' as example: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error publishing flow as example: {str(e)}"
        )

@router.post("/{example_id}/rate", response_model=RateExampleResponse)
async def rate_flow_example(
    example_id: str,
    request: RateExampleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Rate a flow example (1-5 stars).
    Creates or updates the user's rating.
    """
    # Check permissions
    if not can_access_flow_examples(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to rate flow examples"
        )

    # Validate rating
    if request.rating < 1 or request.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5"
        )

    # Verify example exists
    metadata = load_examples_metadata()
    examples = metadata.get("examples", [])
    example = next((ex for ex in examples if ex.get("id") == example_id), None)

    if not example:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow example with ID '{example_id}' not found"
        )

    try:
        # Check if user already rated this example
        existing_rating = db.query(FlowExampleRating).filter(
            FlowExampleRating.example_id == example_id,
            FlowExampleRating.user_id == current_user.user_id
        ).first()

        if existing_rating:
            # Update existing rating
            existing_rating.rating = request.rating
            existing_rating.review = request.review
            existing_rating.updated_at = datetime.now()
            logger.info(f"Updated rating for example '{example_id}' by user '{current_user.email}'")
        else:
            # Create new rating
            new_rating = FlowExampleRating(
                example_id=example_id,
                user_id=current_user.user_id,
                tenant_id=current_user.tenant_id,
                rating=request.rating,
                review=request.review
            )
            db.add(new_rating)
            logger.info(f"Created rating for example '{example_id}' by user '{current_user.email}'")

        db.commit()

        # Get updated stats
        stats = get_example_stats(db, example_id)

        return RateExampleResponse(
            example_id=example_id,
            rating=request.rating,
            average_rating=stats["average_rating"] or 0.0,
            rating_count=stats["rating_count"],
            message="Rating submitted successfully"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error rating example '{example_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting rating: {str(e)}"
        )

@router.post("/{example_id}/favorite", response_model=FavoriteExampleResponse)
async def toggle_favorite_example(
    example_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle favorite status for a flow example.
    If already favorited, removes the favorite. Otherwise, adds it.
    """
    # Check permissions
    if not can_access_flow_examples(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to favorite flow examples"
        )

    # Verify example exists
    metadata = load_examples_metadata()
    examples = metadata.get("examples", [])
    example = next((ex for ex in examples if ex.get("id") == example_id), None)

    if not example:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow example with ID '{example_id}' not found"
        )

    try:
        # Check if already favorited
        existing_favorite = db.query(FlowExampleFavorite).filter(
            FlowExampleFavorite.example_id == example_id,
            FlowExampleFavorite.user_id == current_user.user_id
        ).first()

        if existing_favorite:
            # Remove favorite
            db.delete(existing_favorite)
            is_favorited = False
            message = "Removed from favorites"
            logger.info(f"Removed favorite for example '{example_id}' by user '{current_user.email}'")
        else:
            # Add favorite
            new_favorite = FlowExampleFavorite(
                example_id=example_id,
                user_id=current_user.user_id,
                tenant_id=current_user.tenant_id
            )
            db.add(new_favorite)
            is_favorited = True
            message = "Added to favorites"
            logger.info(f"Added favorite for example '{example_id}' by user '{current_user.email}'")

        db.commit()

        # Get updated favorite count
        favorite_count = db.query(func.count(FlowExampleFavorite.id)).filter(
            FlowExampleFavorite.example_id == example_id
        ).scalar()

        return FavoriteExampleResponse(
            example_id=example_id,
            is_favorited=is_favorited,
            favorite_count=favorite_count or 0,
            message=message
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error toggling favorite for example '{example_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating favorite status: {str(e)}"
        )

@router.delete("/{example_id}")
async def delete_flow_example(
    example_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a flow example. Only accessible to INSTANCE_ADMIN.
    Deletes the example file, metadata entry, and all related data (ratings, favorites, stats).
    """
    # Check if user is instance admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instance admins can delete flow examples"
        )

    try:
        # Load metadata
        if not EXAMPLES_METADATA_FILE.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Examples metadata file not found"
            )

        with open(EXAMPLES_METADATA_FILE, 'r') as f:
            metadata = json.load(f)

        examples = metadata.get("examples", [])

        # Find the example
        example = next((ex for ex in examples if ex.get("id") == example_id), None)

        if not example:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flow example with ID '{example_id}' not found"
            )

        # Delete the flow example file
        example_file = EXAMPLES_DIR / example["filename"]
        if example_file.exists():
            example_file.unlink()
            logger.info(f"Deleted flow example file: {example_file}")

        # Remove from metadata
        metadata["examples"] = [ex for ex in examples if ex.get("id") != example_id]

        # Save updated metadata
        with open(EXAMPLES_METADATA_FILE, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Delete related database records
        # Delete ratings
        db.query(FlowExampleRating).filter(
            FlowExampleRating.example_id == example_id
        ).delete()

        # Delete favorites
        db.query(FlowExampleFavorite).filter(
            FlowExampleFavorite.example_id == example_id
        ).delete()

        # Delete usage stats
        db.query(FlowExampleUsageStats).filter(
            FlowExampleUsageStats.example_id == example_id
        ).delete()

        db.commit()

        logger.info(f"Flow example '{example_id}' deleted by admin '{current_user.email}'")

        return {
            "message": f"Flow example '{example['name']}' deleted successfully",
            "example_id": example_id
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting flow example '{example_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting flow example: {str(e)}"
        )
