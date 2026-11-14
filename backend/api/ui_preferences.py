"""
UI Preferences API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from db.database import get_db
from api.auth import get_current_user
from core.config import settings as app_settings

if app_settings.database_url.startswith("sqlite"):
    from db.models import User
else:
    from db.models import User

from db.user_settings_models import UserSettingsHelper, UIPreferencesData

router = APIRouter(prefix="/api/v1", tags=["ui_preferences"])


class UIPreferences(BaseModel):
    """UI Preferences model"""
    theme: Optional[str] = "light"
    sidebar_collapsed: Optional[bool] = False
    default_view: Optional[str] = "flows"
    items_per_page: Optional[int] = 25
    retain_cache_on_logout: Optional[bool] = False


class UIPreferencesUpdate(BaseModel):
    """Update model for UI preferences"""
    theme: Optional[str] = None
    sidebar_collapsed: Optional[bool] = None
    default_view: Optional[str] = None
    items_per_page: Optional[int] = None
    retain_cache_on_logout: Optional[bool] = None


@router.get("/ui-preferences")
async def get_ui_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> UIPreferences:
    """Get current user's UI preferences"""
    try:
        setting = UserSettingsHelper.get_setting(db, current_user.user_id, "ui_preferences")

        if setting and setting.setting_data:
            return UIPreferences(**setting.setting_data)

        # Return defaults if no preferences set
        return UIPreferences()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get UI preferences: {str(e)}"
        )


@router.put("/ui-preferences")
async def update_ui_preferences(
    preferences: UIPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> UIPreferences:
    """Update user's UI preferences"""
    try:
        # Get existing preferences or defaults
        existing_setting = UserSettingsHelper.get_setting(db, current_user.user_id, "ui_preferences")

        if existing_setting and existing_setting.setting_data:
            current_prefs = existing_setting.setting_data
        else:
            current_prefs = UIPreferencesData.create_ui_preferences()

        # Update only provided fields
        update_data = preferences.dict(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                current_prefs[key] = value

        # Save updated preferences
        UserSettingsHelper.set_setting(db, current_user.user_id, "ui_preferences", current_prefs)

        return UIPreferences(**current_prefs)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update UI preferences: {str(e)}"
        )


@router.patch("/ui-preferences/cache-retention")
async def update_cache_retention(
    retain_cache: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """Quick endpoint to update only the cache retention setting"""
    try:
        # Get existing preferences or defaults
        existing_setting = UserSettingsHelper.get_setting(db, current_user.user_id, "ui_preferences")

        if existing_setting and existing_setting.setting_data:
            current_prefs = existing_setting.setting_data
        else:
            current_prefs = UIPreferencesData.create_ui_preferences()

        # Update cache retention setting
        current_prefs["retain_cache_on_logout"] = retain_cache

        # Save updated preferences
        UserSettingsHelper.set_setting(db, current_user.user_id, "ui_preferences", current_prefs)

        return {"retain_cache_on_logout": retain_cache}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update cache retention setting: {str(e)}"
        )