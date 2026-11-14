"""
Schemas for seed application management
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class InstallationStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"


class SeedApplicationInfo(BaseModel):
    """Information about a seed application"""
    key: str = Field(..., description="Unique key for the application")
    name: str = Field(..., description="Display name of the application")
    description: str = Field(..., description="Application description")
    category: str = Field(..., description="Application category")
    auth_type: str = Field(..., description="Authentication type")
    version: str = Field(..., description="Application version")
    icon_url: Optional[str] = Field(None, description="Application icon URL")
    status: InstallationStatus = Field(..., description="Installation status")
    installed_version: Optional[str] = Field(None, description="Currently installed version")
    installed_at: Optional[str] = Field(None, description="Installation timestamp")
    app_id: Optional[str] = Field(None, description="Application ID if installed")
    subscription_count: int = Field(0, description="Number of active subscriptions")
    service_count: int = Field(0, description="Number of services")
    event_count: int = Field(0, description="Number of events")
    validation_status: Optional[Dict[str, Any]] = Field(None, description="Schema validation status")
    created_at: Optional[str] = Field(None, description="Creation timestamp from metadata")
    last_modified: Optional[str] = Field(None, description="Last modification timestamp from metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "slack",
                "name": "Slack",
                "description": "Team communication and collaboration platform",
                "category": "Communication",
                "auth_type": "oauth2",
                "version": "2.0.0",
                "icon_url": "https://cdn.brandfolder.io/5H442O3W/as/pl546j-7le8zk-4nzzs1/Slack_Mark.png",
                "status": "installed",
                "installed_version": "2.0.0",
                "installed_at": "2024-01-15T10:30:00Z",
                "subscription_count": 3,
                "service_count": 2,
                "event_count": 2
            }
        }


class SeedApplicationList(BaseModel):
    """List of available seed applications"""
    applications: List[SeedApplicationInfo] = Field(..., description="List of seed applications")
    total: int = Field(..., description="Total number of applications")
    installed_count: int = Field(..., description="Number of installed applications")


class InstallApplicationRequest(BaseModel):
    """Request to install or reinstall an application"""
    application_key: str = Field(..., description="Application key to install")
    force_reinstall: bool = Field(False, description="Force reinstall even if already installed")
    preserve_subscriptions: bool = Field(False, description="Try to preserve existing subscriptions (not recommended)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "application_key": "slack",
                "force_reinstall": False
            }
        }


class InstallApplicationResponse(BaseModel):
    """Response after installing an application"""
    success: bool = Field(..., description="Whether installation was successful")
    message: str = Field(..., description="Status message")
    application: Optional[SeedApplicationInfo] = Field(None, description="Installed application info")
    warnings: Optional[List[str]] = Field(None, description="Any warnings during installation")
    deleted_subscriptions: Optional[int] = Field(None, description="Number of subscriptions deleted (if reinstalled)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully installed Slack application",
                "application": {
                    "key": "slack",
                    "name": "Slack",
                    "status": "installed"
                }
            }
        }


class UninstallApplicationRequest(BaseModel):
    """Request to uninstall an application"""
    application_key: str = Field(..., description="Application key to uninstall")
    confirm: bool = Field(..., description="Confirmation flag - must be true")
    
    class Config:
        json_schema_extra = {
            "example": {
                "application_key": "slack",
                "confirm": True
            }
        }


class ApplicationInstallationWarning(BaseModel):
    """Warning about application installation"""
    application_name: str = Field(..., description="Application name")
    subscription_count: int = Field(..., description="Number of subscriptions that will be deleted")
    message: str = Field(..., description="Warning message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "application_name": "Slack",
                "subscription_count": 3,
                "message": "Application is already installed. Reinstalling will delete 3 existing subscriptions and all associated data."
            }
        }


class ServiceDefinition(BaseModel):
    """Service definition for seed applications"""
    name: str = Field(..., description="Service name")
    service_type: str = Field(..., description="Service type (api_call, webhook, etc.)")
    description: str = Field(..., description="Service description")
    configuration: Dict[str, Any] = Field(..., description="Service configuration")
    parameters: Optional[List[Dict[str, Any]]] = Field(None, description="Service parameters")
    sample_input: Optional[Dict[str, Any]] = Field(None, description="Sample input")
    sample_output: Optional[Dict[str, Any]] = Field(None, description="Sample output")


class EventDefinition(BaseModel):
    """Event definition for seed applications"""
    event_name: str = Field(..., description="Event name")
    event_type: str = Field(..., description="Event type (webhook, polling, etc.)")
    description: str = Field(..., description="Event description")
    configuration: Dict[str, Any] = Field(..., description="Event configuration")
    sample_payload: Optional[Dict[str, Any]] = Field(None, description="Sample payload")


class CreateSeedApplicationRequest(BaseModel):
    """Request to create a new seed application"""
    app_key: str = Field(..., description="Unique application key (lowercase, underscore separated)")
    app_name: str = Field(..., description="Human-readable application name")
    app_type: str = Field("global", description="Application type (global or tenant)")
    category: str = Field("Integration", description="Application category")
    auth_type: str = Field("api_key", description="Authentication type")
    description: str = Field(..., description="Application description")
    base_url: str = Field("", description="Base API URL")
    version: str = Field("1.0.0", description="Semantic version")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    services: Optional[List[ServiceDefinition]] = Field(None, description="Service definitions")
    events: Optional[List[EventDefinition]] = Field(None, description="Event definitions")


class UpdateSeedApplicationRequest(BaseModel):
    """Request to update an existing seed application"""
    app_name: Optional[str] = Field(None, description="Human-readable application name")
    app_type: Optional[str] = Field(None, description="Application type (global or tenant)")
    category: Optional[str] = Field(None, description="Application category")
    auth_type: Optional[str] = Field(None, description="Authentication type")
    description: Optional[str] = Field(None, description="Application description")
    base_url: Optional[str] = Field(None, description="Base API URL")
    version: Optional[str] = Field(None, description="Semantic version")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    services: Optional[List[ServiceDefinition]] = Field(None, description="Service definitions")
    events: Optional[List[EventDefinition]] = Field(None, description="Event definitions")


class ImportSeedApplicationRequest(BaseModel):
    """Request to import a seed application from JSON"""
    json_content: str = Field(..., description="JSON content of the seed application")
    validate_only: bool = Field(False, description="Only validate without saving")
    overwrite: bool = Field(False, description="Overwrite if application already exists")


class SeedApplicationResponse(BaseModel):
    """Response for seed application operations"""
    success: bool = Field(..., description="Whether operation was successful")
    message: str = Field(..., description="Status message")
    application: Optional[Dict[str, Any]] = Field(None, description="Application data")
    errors: Optional[List[str]] = Field(None, description="List of errors if any")


class ValidateSeedApplicationResponse(BaseModel):
    """Response for seed application validation"""
    valid: bool = Field(..., description="Whether the application is valid")
    errors: List[str] = Field(..., description="List of validation errors")
    warnings: List[str] = Field(..., description="List of validation warnings")
    application: Optional[Dict[str, Any]] = Field(None, description="Parsed application data if valid")