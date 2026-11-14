"""
Find an application by the identifier a flow or an agent names it with.

An application can be named by its ``app_id`` (UUID), its ``seed_key`` or its
``app_name``. A seed key used to be unique to the global catalog; tenant seed
applications (``/api/v1/tenant-seed-applications``) let every tenant install a
connector under a key of its own choosing, so two tenants can both own
``acme_inventory``. A bare ``.filter(seed_key == key).first()`` then returned
whichever row the database met first — another tenant's connector, its
services, URLs and auth configuration included.

The key / name lookups here therefore search only what the caller may see —
the rule ``list_applications`` already applies: global seed applications plus
the applications the caller's tenant owns — and prefer the caller's OWN
application when both a tenant and a global one answer to the same name. An
instance admin sees everything, global first. A lookup by ``app_id`` is
unchanged.
"""
from typing import Optional

from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from db.application_models import Application


def _role(user) -> str:
    role = getattr(user, "role", "") or ""
    role = getattr(role, "value", role)
    return str(role).replace("UserRole.", "")


def _visible(query, user):
    """Restrict a query to the applications ``user`` may see, own tenant's first."""
    if user is None:
        return query.filter(Application.app_scope != "tenant")
    if _role(user) == "INSTANCE_ADMIN":
        return query.order_by(case((Application.app_scope == "tenant", 1), else_=0))
    tenant_id = getattr(user, "tenant_id", None)
    shared = and_(Application.app_scope == "global", Application.is_seed_app == True)  # noqa: E712
    if not tenant_id:
        return query.filter(shared)
    own = Application.tenant_id_owner == str(tenant_id)
    return query.filter(or_(shared, own)).order_by(case((own, 0), else_=1))


def visible_to(app: Application, user=None) -> bool:
    """May ``user`` use ``app``? Another tenant's own application is the one
    thing they may not, whatever identifier names it."""
    if app is None:
        return False
    if app.app_scope != "tenant":
        return True
    if user is None:
        return False
    if _role(user) == "INSTANCE_ADMIN":
        return True
    tenant_id = getattr(user, "tenant_id", None)
    return bool(tenant_id) and str(app.tenant_id_owner or "") == str(tenant_id)


def find_application(db: Session, ref: str, user=None) -> Optional[Application]:
    """The application ``ref`` names for ``user``: by app_id, then seed_key,
    then app_name — the last two only among applications the caller may see."""
    if not ref:
        return None
    app = db.query(Application).filter(Application.app_id == ref).first()
    if app is not None:
        return app
    app = _visible(db.query(Application).filter(Application.seed_key == ref), user).first()
    if app is not None:
        return app
    return _visible(db.query(Application).filter(Application.app_name == ref), user).first()


def find_by_seed_key(db: Session, key: str, user=None) -> Optional[Application]:
    """The application installed from seed ``key`` that ``user`` may see."""
    if not key:
        return None
    return _visible(db.query(Application).filter(Application.seed_key == key), user).first()
