"""
Admin Onboarding Wizard API Endpoints
Manages the guided setup wizard for TENANT_ADMIN and INSTANCE_ADMIN users
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
from pydantic import BaseModel
import logging

from db.database import get_db
from core.config import settings
from db.user_settings_models import UserSettingsHelper, SettingType
from db.pricing_models import TenantBalance
from db.application_models import ApplicationSubscription

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models_sqlite import User, UserRole
else:
    from db.models import User, UserRole

from core.auth_utils import get_current_user_required as get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/onboarding",
    tags=["onboarding"]
)

# Admin roles that should see the onboarding wizard (both enum and string values for compatibility)
ADMIN_ROLES = [UserRole.TENANT_ADMIN, UserRole.INSTANCE_ADMIN]
ADMIN_ROLE_VALUES = ["TENANT_ADMIN", "INSTANCE_ADMIN"]
ONBOARDING_SETTING_TYPE = SettingType.ONBOARDING_WIZARD.value


def is_admin_role(user_role) -> bool:
    """Check if user role is an admin role (handles both enum and string)"""
    if user_role in ADMIN_ROLES:
        return True
    if hasattr(user_role, 'value') and user_role.value in ADMIN_ROLE_VALUES:
        return True
    if isinstance(user_role, str) and user_role in ADMIN_ROLE_VALUES:
        return True
    return False


class SkipStepRequest(BaseModel):
    step_id: str


class OnboardingStepDetails(BaseModel):
    completed: bool
    skipped: bool
    details: Dict[str, Any]


class OnboardingStatusResponse(BaseModel):
    wizard_completed: bool
    wizard_skipped: bool
    show_wizard: bool
    reason: str = None
    steps: Dict[str, OnboardingStepDetails] = None


class SuccessResponse(BaseModel):
    success: bool
    message: str = None


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get onboarding wizard status for the current user.
    Only TENANT_ADMIN and INSTANCE_ADMIN users see the wizard.
    """
    try:
        # Non-admin users don't see the wizard
        if not is_admin_role(current_user.role):
            return OnboardingStatusResponse(
                wizard_completed=True,
                wizard_skipped=False,
                show_wizard=False,
                reason="not_admin"
            )

        # Get wizard settings from user_settings
        wizard_setting = UserSettingsHelper.get_setting(
            db, str(current_user.user_id), ONBOARDING_SETTING_TYPE
        )
        wizard_settings = wizard_setting.setting_data if wizard_setting else {}

        # Check AI configuration status
        ai_config = UserSettingsHelper.get_ai_config(db, str(current_user.user_id))
        ai_completed = bool(ai_config.get('provider') and ai_config.get('api_key_hash'))
        ai_skipped = wizard_settings.get('ai_configuration_skipped', False)

        # Check balance status (any positive balance > $0.01 counts)
        balance = db.query(TenantBalance).filter(
            TenantBalance.tenant_id == str(current_user.tenant_id)
        ).first()
        current_balance = float(balance.current_balance) if balance and balance.current_balance else 0.0
        balance_completed = current_balance >= 0.01
        balance_skipped = wizard_settings.get('balance_topup_skipped', False)

        # Check application subscription status
        subscribed_count = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.tenant_id == str(current_user.tenant_id),
            ApplicationSubscription.status == 'active'
        ).count()
        apps_completed = subscribed_count > 0
        apps_skipped = wizard_settings.get('application_setup_skipped', False)

        # Determine if wizard should show
        wizard_completed = wizard_settings.get('wizard_completed', False)
        all_steps_done = (
            (ai_completed or ai_skipped) and
            (balance_completed or balance_skipped) and
            (apps_completed or apps_skipped)
        )

        show_wizard = not wizard_completed and not all_steps_done

        return OnboardingStatusResponse(
            wizard_completed=wizard_completed,
            wizard_skipped=wizard_settings.get('wizard_skipped', False),
            show_wizard=show_wizard,
            steps={
                "ai_configuration": OnboardingStepDetails(
                    completed=ai_completed,
                    skipped=ai_skipped,
                    details={
                        "has_provider": bool(ai_config.get('provider')),
                        "has_api_key": bool(ai_config.get('api_key_hash'))
                    }
                ),
                "balance_topup": OnboardingStepDetails(
                    completed=balance_completed,
                    skipped=balance_skipped,
                    details={
                        "current_balance": current_balance
                    }
                ),
                "application_setup": OnboardingStepDetails(
                    completed=apps_completed,
                    skipped=apps_skipped,
                    details={
                        "subscribed_count": subscribed_count
                    }
                )
            }
        )

    except Exception as e:
        logger.error(f"Error getting onboarding status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve onboarding status"
        )


@router.post("/skip-step")
async def skip_onboarding_step(
    request: SkipStepRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Skip a specific onboarding step"""
    try:
        if not is_admin_role(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can access onboarding wizard"
            )

        valid_steps = ["ai_configuration", "balance_topup", "application_setup"]

        if request.step_id not in valid_steps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid step_id: {request.step_id}. Valid steps: {valid_steps}"
            )

        # Get current wizard settings
        wizard_setting = UserSettingsHelper.get_setting(
            db, str(current_user.user_id), ONBOARDING_SETTING_TYPE
        )
        wizard_settings = wizard_setting.setting_data if wizard_setting else {}

        # Mark step as skipped
        wizard_settings[f"{request.step_id}_skipped"] = True

        # Save updated settings
        UserSettingsHelper.set_setting(
            db, str(current_user.user_id), ONBOARDING_SETTING_TYPE, wizard_settings
        )

        return {"success": True, "step_id": request.step_id, "skipped": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping onboarding step: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip onboarding step"
        )


@router.post("/complete", response_model=SuccessResponse)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark the onboarding wizard as completed"""
    try:
        if not is_admin_role(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can access onboarding wizard"
            )

        # Get current wizard settings
        wizard_setting = UserSettingsHelper.get_setting(
            db, str(current_user.user_id), ONBOARDING_SETTING_TYPE
        )
        wizard_settings = wizard_setting.setting_data if wizard_setting else {}

        # Mark wizard as completed
        wizard_settings['wizard_completed'] = True

        # Save updated settings
        UserSettingsHelper.set_setting(
            db, str(current_user.user_id), ONBOARDING_SETTING_TYPE, wizard_settings
        )

        return SuccessResponse(success=True, message="Onboarding wizard completed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding wizard"
        )


@router.post("/reset", response_model=SuccessResponse)
async def reset_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reset the onboarding wizard (for testing or re-running setup).
    Only INSTANCE_ADMIN can reset.
    """
    try:
        is_instance_admin = (
            current_user.role == UserRole.INSTANCE_ADMIN or
            (hasattr(current_user.role, 'value') and current_user.role.value == "INSTANCE_ADMIN") or
            current_user.role == "INSTANCE_ADMIN"
        )
        if not is_instance_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only instance admins can reset onboarding wizard"
            )

        # Delete wizard settings to reset
        UserSettingsHelper.delete_setting(
            db, str(current_user.user_id), ONBOARDING_SETTING_TYPE
        )

        return SuccessResponse(success=True, message="Onboarding wizard reset successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset onboarding wizard"
        )
