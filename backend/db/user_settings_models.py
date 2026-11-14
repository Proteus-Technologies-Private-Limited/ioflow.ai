"""
User Settings Helper Functions and Schemas - PostgreSQL Only
Utilities for working with user settings stored in the main models
"""
import enum
from sqlalchemy.sql import func
from sqlalchemy.orm.attributes import flag_modified

from db.models import UserSettings


class SettingType(enum.Enum):
    """Types of user settings"""
    AI_CONFIG = "ai_config"
    ASSISTANT_CONFIG = "assistant_config"
    NOTIFICATION_PREFS = "notification_prefs"
    UI_PREFERENCES = "ui_preferences"
    API_KEYS = "api_keys"
    INTEGRATION_SETTINGS = "integration_settings"
    ONBOARDING_WIZARD = "onboarding_wizard"


class AISettingsData:
    """
    Schema for AI configuration data stored in user_settings.setting_data
    when setting_type = 'ai_config'
    """

    @staticmethod
    def create_ai_config(provider, model_name, api_key_hash, api_endpoint=None, **kwargs):
        """Create AI configuration data structure"""
        return {
            "provider": provider,
            "model_name": model_name,
            "api_key_hash": api_key_hash,
            "api_endpoint": api_endpoint,
            "model_config": {
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 4000),
                "top_p": kwargs.get("top_p", 1.0)
            },
            "extra_settings": kwargs.get("extra_settings", {}),
            "agent_framework": kwargs.get("agent_framework", "google_adk")
        }

    @staticmethod
    def get_ai_config_default():
        """Get default AI configuration"""
        return {
            "provider": None,
            "model_name": None,
            "api_key_hash": None,
            "api_endpoint": None,
            "model_config": {
                "temperature": 0.7,
                "max_tokens": 4000,
                "top_p": 1.0
            },
            "extra_settings": {},
            "agent_framework": "google_adk"
        }


class NotificationSettingsData:
    """Schema for notification preferences"""

    @staticmethod
    def create_notification_config(email_enabled=True, push_enabled=True, **kwargs):
        return {
            "email_notifications": email_enabled,
            "push_notifications": push_enabled,
            "flow_completion": kwargs.get("flow_completion", True),
            "flow_failures": kwargs.get("flow_failures", True),
            "system_updates": kwargs.get("system_updates", False)
        }


class UIPreferencesData:
    """Schema for UI preferences"""

    @staticmethod
    def create_ui_preferences(theme="light", **kwargs):
        return {
            "theme": theme,
            "sidebar_collapsed": kwargs.get("sidebar_collapsed", False),
            "default_view": kwargs.get("default_view", "flows"),
            "items_per_page": kwargs.get("items_per_page", 25),
            "retain_cache_on_logout": kwargs.get("retain_cache_on_logout", False)
        }


class AssistantSettingsData:
    """Schema for assistant-specific configuration"""

    @staticmethod
    def create_assistant_config(use_defaults=True, provider=None, model=None, custom_api_key_hash=None, **kwargs):
        """Create assistant configuration data structure"""
        return {
            "use_defaults": use_defaults,
            "provider": provider,
            "model": model,
            "custom_api_key_hash": custom_api_key_hash,
            "extra_settings": kwargs.get("extra_settings", {})
        }

    @staticmethod
    def get_assistant_config_default():
        """Get default assistant configuration"""
        return {
            "use_defaults": True,
            "provider": None,
            "model": None,
            "custom_api_key_hash": None,
            "extra_settings": {}
        }


class UserSettingsHelper:
    """Helper class for managing user settings"""

    @staticmethod
    def get_setting(db, user_id: str, setting_type: str):
        """Get a specific setting for a user"""
        return db.query(UserSettings).filter(
            UserSettings.user_id == user_id,
            UserSettings.setting_type == setting_type
        ).first()

    @staticmethod
    def set_setting(db, user_id: str, setting_type: str, setting_data: dict):
        """Set or update a setting for a user"""
        existing = UserSettingsHelper.get_setting(db, user_id, setting_type)

        if existing:
            existing.setting_data = setting_data
            flag_modified(existing, 'setting_data')
            existing.updated_at = func.current_timestamp()
        else:
            new_setting = UserSettings(
                user_id=user_id,
                setting_type=setting_type,
                setting_data=setting_data
            )
            db.add(new_setting)

        db.commit()
        return True

    @staticmethod
    def delete_setting(db, user_id: str, setting_type: str):
        """Delete a specific setting for a user"""
        existing = UserSettingsHelper.get_setting(db, user_id, setting_type)
        if existing:
            db.delete(existing)
            db.commit()
            return True
        return False

    @staticmethod
    def get_ai_config(db, user_id: str):
        """Get AI configuration for a user"""
        setting = UserSettingsHelper.get_setting(db, user_id, SettingType.AI_CONFIG.value)
        if setting and setting.setting_data:
            return setting.setting_data
        return AISettingsData.get_ai_config_default()

    @staticmethod
    def set_ai_config(db, user_id: str, provider: str, model_name: str, api_key_hash: str,
                      api_endpoint: str = None, **kwargs):
        """Set AI configuration for a user"""
        ai_config = AISettingsData.create_ai_config(
            provider=provider,
            model_name=model_name,
            api_key_hash=api_key_hash,
            api_endpoint=api_endpoint,
            **kwargs
        )
        return UserSettingsHelper.set_setting(db, user_id, SettingType.AI_CONFIG.value, ai_config)

    @staticmethod
    def get_assistant_config(db, user_id: str):
        """Get assistant-specific configuration for a user"""
        setting = UserSettingsHelper.get_setting(db, user_id, SettingType.ASSISTANT_CONFIG.value)
        if setting and setting.setting_data:
            return setting.setting_data
        return AssistantSettingsData.get_assistant_config_default()

    @staticmethod
    def set_assistant_config(db, user_id: str, use_defaults: bool = True, provider: str = None,
                           model: str = None, custom_api_key_hash: str = None, **kwargs):
        """Set assistant-specific configuration for a user"""
        assistant_config = AssistantSettingsData.create_assistant_config(
            use_defaults=use_defaults,
            provider=provider,
            model=model,
            custom_api_key_hash=custom_api_key_hash,
            **kwargs
        )
        return UserSettingsHelper.set_setting(db, user_id, SettingType.ASSISTANT_CONFIG.value, assistant_config)
