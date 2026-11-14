"""
Debug endpoints for troubleshooting
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from db.database import get_db
from api.auth import get_current_user
from db.models import User
from db.application_models import ApplicationSubscription
from utils.crypto_utils import decrypt_credentials
from core.config import settings
import json

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])

@router.get("/subscription/{subscription_id}/auth-info")
async def get_subscription_auth_info(
    subscription_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed auth info for debugging"""
    # Get subscription with application
    subscription = db.query(ApplicationSubscription).options(
        joinedload(ApplicationSubscription.application)
    ).filter(
        ApplicationSubscription.subscription_id == subscription_id,
        ApplicationSubscription.tenant_id == current_user.tenant_id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Prepare response
    response = {
        "subscription_id": subscription_id,
        "app_id": subscription.app_id,
        "app_name": subscription.application.app_name if subscription.application else "Unknown",
        "auth_type": subscription.application.auth_type if subscription.application else None,
        "has_credentials": bool(subscription.auth_credentials),
        "credential_fields": None,
        "auth_config": None,
        "subscription_config": None
    }
    
    # Get auth config
    if subscription.application and subscription.application.auth_config:
        auth_config = subscription.application.auth_config
        if isinstance(auth_config, str):
            try:
                auth_config = json.loads(auth_config)
            except:
                pass
        response["auth_config"] = auth_config
    
    # Get subscription config
    if subscription.subscription_config:
        sub_config = subscription.subscription_config
        if isinstance(sub_config, str):
            try:
                sub_config = json.loads(sub_config)
            except:
                pass
        response["subscription_config"] = sub_config
    
    # Decrypt and mask credentials
    if subscription.auth_credentials:
        try:
            # Show raw encrypted data info
            response["raw_auth_credentials_type"] = type(subscription.auth_credentials).__name__
            response["raw_auth_credentials_value"] = str(subscription.auth_credentials)[:100] + "..." if len(str(subscription.auth_credentials)) > 100 else str(subscription.auth_credentials)
            
            if isinstance(subscription.auth_credentials, dict):
                response["raw_auth_credentials_keys"] = list(subscription.auth_credentials.keys())
            elif isinstance(subscription.auth_credentials, str):
                try:
                    parsed = json.loads(subscription.auth_credentials)
                    response["raw_auth_credentials_parsed_type"] = type(parsed).__name__
                    if isinstance(parsed, dict):
                        response["raw_auth_credentials_parsed_keys"] = list(parsed.keys())
                except:
                    response["raw_auth_credentials_parse_error"] = True
            
            decrypted = decrypt_credentials(subscription.auth_credentials)
            response["decrypted_type"] = type(decrypted).__name__
            response["decrypted_empty"] = not bool(decrypted)
            response["credential_fields"] = list(decrypted.keys()) if decrypted else []
            
            # Show masked values
            masked_creds = {}
            if decrypted:
                for key, value in decrypted.items():
                    if isinstance(value, str) and len(value) > 3:
                        masked_creds[key] = f"{'*' * (len(value)-3)}{value[-3:]}"
                    else:
                        masked_creds[key] = f"[{type(value).__name__}]"
            response["masked_credentials"] = masked_creds
        except Exception as e:
            response["credential_error"] = str(e)
            import traceback
            response["credential_traceback"] = traceback.format_exc()
    
    return response

@router.post("/test-credential-flow")
async def test_credential_flow(
    credentials: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test the complete credential encryption/decryption flow"""
    from utils.crypto_utils import encrypt_credentials, decrypt_credentials
    from api.applications import serialize_json_field, deserialize_json_field
    
    result = {
        "original": credentials,
        "steps": []
    }
    
    # Step 1: Encrypt
    encrypted = encrypt_credentials(credentials)
    result["steps"].append({
        "step": "encrypt_credentials",
        "output": encrypted,
        "type": type(encrypted).__name__
    })
    
    # Step 2: Serialize for SQLite
    serialized = serialize_json_field(encrypted)
    result["steps"].append({
        "step": "serialize_json_field",
        "output": serialized,
        "type": type(serialized).__name__
    })
    
    # Step 3: Deserialize from SQLite
    deserialized = deserialize_json_field(serialized)
    result["steps"].append({
        "step": "deserialize_json_field",
        "output": deserialized,
        "type": type(deserialized).__name__
    })
    
    # Step 4: Decrypt (with deserialized data)
    try:
        decrypted_from_deserialized = decrypt_credentials(deserialized)
        result["steps"].append({
            "step": "decrypt_credentials (deserialized)",
            "output": decrypted_from_deserialized,
            "type": type(decrypted_from_deserialized).__name__,
            "success": True
        })
    except Exception as e:
        result["steps"].append({
            "step": "decrypt_credentials (deserialized)",
            "error": str(e),
            "success": False
        })
    
    # Step 5: Decrypt (with serialized/raw data)
    try:
        decrypted_from_serialized = decrypt_credentials(serialized)
        result["steps"].append({
            "step": "decrypt_credentials (serialized)",
            "output": decrypted_from_serialized,
            "type": type(decrypted_from_serialized).__name__,
            "success": True
        })
    except Exception as e:
        result["steps"].append({
            "step": "decrypt_credentials (serialized)",
            "error": str(e),
            "success": False
        })
    
    return result