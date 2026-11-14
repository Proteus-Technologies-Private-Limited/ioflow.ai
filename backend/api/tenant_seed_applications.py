"""
Tenant-scoped seed applications.

A global seed application (``/api/v1/seed-applications``) is one JSON file every
tenant shares, which is why writing one needs an instance admin. This router is
a tenant's OWN connector catalog: the same seed JSON shape, stored per tenant
(``seed-applications/tenants/<tenant_id>/``), visible only to that tenant, and
installed as an application with ``app_scope='tenant'`` owned by it.

Permissions follow tenant applications (``api/applications.py``): any role that
may manage applications (everyone but EXECUTION_MONITOR / FLOW_EXECUTOR) may
write the tenant's own seed applications. The tenant always comes from the
caller's identity — never from the request.

The IOFlow assistant, the Claude Code plugin and external agents (Twasta's
Ask-AI) all reach these endpoints through the MCP bridge tools
``list_tenant_seed_applications``, ``get_tenant_seed_application``,
``save_tenant_seed_application``, ``install_tenant_seed_application`` and
``delete_tenant_seed_application``.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User
from services.json_seed_manager import json_seed_manager as seed_manager
from .applications import _require_app_management_role
from .auth import get_current_user

router = APIRouter(
    prefix="/api/v1/tenant-seed-applications",
    tags=["tenant-seed-applications"],
)


class SaveTenantSeedRequest(BaseModel):
    seed: Dict[str, Any] = Field(..., description="The full seed application JSON (key, application, services, events)")
    install: bool = Field(False, description="Install / update the tenant application right after saving")


class ValidateTenantSeedRequest(BaseModel):
    seed: Dict[str, Any]


def _tenant_of(user: User) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="You must belong to a tenant to own seed applications")
    return str(user.tenant_id)


def _summary(db: Session, tenant_id: str, seed: Dict[str, Any]) -> Dict[str, Any]:
    app = seed.get("application") or {}
    installed = seed_manager.find_tenant_installation(db, tenant_id, seed["key"])
    status = "not_installed"
    if installed is not None:
        status = "installed" if installed.version == app.get("version", "1.0.0") else "update_available"
    return {
        "key": seed["key"],
        "name": app.get("app_name"),
        "description": app.get("description", ""),
        "category": app.get("category", "Other"),
        "auth_type": app.get("auth_type", "none"),
        "version": app.get("version", "1.0.0"),
        "service_count": len(seed.get("services") or []),
        "event_count": len(seed.get("events") or []),
        "status": status,
        "app_id": str(installed.app_id) if installed is not None else None,
        "installed_version": installed.version if installed is not None else None,
        "last_modified": (seed.get("metadata") or {}).get("last_modified"),
    }


@router.get("/")
async def list_tenant_seed_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The caller's tenant seed applications with their install status."""
    tenant_id = _tenant_of(current_user)
    apps = [_summary(db, tenant_id, s) for s in seed_manager.list_tenant_applications(tenant_id)]
    return {"applications": apps, "total": len(apps)}


@router.post("/validate")
async def validate_tenant_seed_application(
    request: ValidateTenantSeedRequest,
    current_user: User = Depends(get_current_user),
):
    """Validate a seed JSON exactly as a save would, without writing anything."""
    _tenant_of(current_user)
    return seed_manager.validate_seed_document(request.seed)


@router.get("/{app_key}")
async def get_tenant_seed_application(
    app_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The full JSON of one tenant seed application, plus its install status."""
    tenant_id = _tenant_of(current_user)
    try:
        seed = seed_manager.get_tenant_application(tenant_id, app_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not seed:
        raise HTTPException(status_code=404, detail=f"Tenant seed application '{app_key}' not found")
    return {"seed": seed, "status": _summary(db, tenant_id, seed)}


@router.put("/{app_key}")
async def save_tenant_seed_application(
    app_key: str,
    request: SaveTenantSeedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or replace a tenant seed application from its full JSON.

    Invalid JSON is refused with its errors and nothing is written. With
    ``install: true`` the tenant application is installed (or updated in place,
    keeping its ids and subscriptions) in the same call.
    """
    _require_app_management_role(current_user)
    tenant_id = _tenant_of(current_user)
    if (request.seed or {}).get("key") != app_key:
        raise HTTPException(status_code=400, detail="The seed's 'key' must match the key in the URL")
    try:
        saved = seed_manager.save_tenant_application(tenant_id, request.seed, user_id=current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not saved.get("success"):
        return saved
    result: Dict[str, Any] = {k: v for k, v in saved.items() if k != "seed"}
    if request.install:
        result["install"] = seed_manager.install_tenant_application(
            db, tenant_id, app_key, user_id=current_user.user_id)
        result["success"] = bool(result["install"].get("success"))
    result["status"] = _summary(db, tenant_id, saved["seed"])
    return result


@router.post("/{app_key}/install")
async def install_tenant_seed_application(
    app_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Install the tenant application, or update an existing install in place."""
    _require_app_management_role(current_user)
    tenant_id = _tenant_of(current_user)
    try:
        return seed_manager.install_tenant_application(db, tenant_id, app_key, user_id=current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{app_key}")
async def delete_tenant_seed_application(
    app_key: str,
    uninstall: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a tenant seed application (and its installation, unless it is still subscribed)."""
    _require_app_management_role(current_user)
    tenant_id = _tenant_of(current_user)
    try:
        if uninstall:
            removed = seed_manager.uninstall_tenant_application(db, tenant_id, app_key)
            if not removed.get("success"):
                raise HTTPException(status_code=409, detail=removed.get("message"))
        deleted = seed_manager.delete_tenant_application(tenant_id, app_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Tenant seed application '{app_key}' not found")
    return {"success": True, "key": app_key}
