"""
Token Exchange Authentication Manager

Handles authentication flows where username/password are exchanged for JWT tokens
"""
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import json
from sqlalchemy.orm import Session

from db.database import get_db
from db.application_models import ApplicationSubscription
from utils.crypto_utils import encrypt_credentials, decrypt_credentials, mask_sensitive_data

logger = logging.getLogger(__name__)


class TokenExchangeManager:
    """Manages token exchange authentication with automatic refresh"""
    
    def __init__(self):
        self.token_cache = {}  # In-memory cache for tokens
        self.lock = asyncio.Lock()
    
    def _log_to_execution(self, execution_context: Optional[Dict[str, Any]], level: str, message: str, data: Any = None):
        """Log to execution log if context is available"""
        if execution_context and execution_context.get('log_callback'):
            log_callback = execution_context['log_callback']
            execution_id = execution_context.get('execution_id')
            node_id = execution_context.get('node_id')
            if execution_id and node_id:
                log_callback(execution_id, node_id, level, message, data)
    
    async def get_valid_token(
        self, 
        subscription_id: str,
        auth_config: Dict[str, Any],
        current_credentials: Dict[str, Any],
        db: Session,
        execution_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get a valid token, performing login or refresh if necessary
        
        Args:
            subscription_id: The subscription ID
            auth_config: The application's auth configuration
            current_credentials: Current decrypted credentials
            db: Database session
            execution_context: Optional execution context for logging
            
        Returns:
            Updated credentials with valid access token
        """
        async with self.lock:
            # Check if token is still valid
            if self._is_token_valid(current_credentials):
                logger.debug(f"Token for subscription {subscription_id} is still valid")
                self._log_to_execution(execution_context, "debug", "Token is still valid", {
                    "subscription_id": subscription_id,
                    "has_expires_at": "expires_at" in current_credentials,
                    "expires_at": current_credentials.get('expires_at')
                })
                return current_credentials
            
            # Token needs refresh or initial login
            logger.info(f"Token for subscription {subscription_id} needs refresh or login")
            self._log_to_execution(execution_context, "info", "Token expired or missing, attempting refresh/login", {
                "subscription_id": subscription_id,
                "has_access_token": bool(current_credentials.get('access_token')),
                "has_refresh_url": bool(auth_config.get('refresh_url')),
                "expires_at": current_credentials.get('expires_at')
            })
            
            # Check if we have a refresh token and refresh URL
            if current_credentials.get('access_token') and auth_config.get('refresh_url'):
                try:
                    # Try to refresh the token
                    new_token_data = await self._refresh_token(
                        auth_config=auth_config,
                        current_credentials=current_credentials,
                        execution_context=execution_context
                    )
                    
                    if new_token_data and new_token_data.get(auth_config.get('token_field', 'access_token')) is not None:
                        # Update credentials with new token
                        updated_credentials = current_credentials.copy()
                        updated_credentials.update({
                            'access_token': new_token_data.get('access_token', new_token_data.get(self._extract_field_value(new_token_data, auth_config['token_field']))),
                            'expires_at': new_token_data.get('expires_at'),
                        })
                        # Preserve login_response if it exists
                        if 'login_response' in current_credentials:
                            updated_credentials['login_response'] = current_credentials['login_response']
                        
                        # Preserve additional fields from original credentials
                        if auth_config.get('additional_fields'):
                            for field_name in auth_config['additional_fields'].keys():
                                if field_name in current_credentials:
                                    updated_credentials[field_name] = current_credentials[field_name]
                        
                        # Save updated credentials back to database
                        await self._save_updated_credentials(subscription_id, updated_credentials, db)
                        
                        return updated_credentials
                except Exception as e:
                    logger.warning(f"Token refresh failed, will try login: {e}")
            
            # Perform login to get new token
            try:
                new_token_data = await self._login(
                    auth_config=auth_config,
                    current_credentials=current_credentials,
                    execution_context=execution_context
                )
            except Exception as e:
                logger.error(f"Login failed with exception: {str(e)}", exc_info=True)
                raise ValueError(f"Failed to obtain access token through login: {str(e)}")
            
            if not new_token_data:
                raise ValueError("Failed to obtain access token through login - no response data received")
            
            # Extract token and expiry from response
            token = self._extract_field_value(new_token_data, auth_config['token_field'])
            expiry = None
            if auth_config.get('expiry_field'):
                expiry = self._extract_field_value(new_token_data, auth_config['expiry_field'])
            
            if not token:
                raise ValueError(f"Token not found in response at path: {auth_config['token_field']}")
            
            # Update credentials - store entire login response
            updated_credentials = current_credentials.copy()
            updated_credentials.update({
                'access_token': token,
                'expires_at': expiry,
                'login_response': new_token_data  # Store entire response for flow variables
            })
            
            # Extract additional fields if configured
            if auth_config.get('additional_fields'):
                logger.info(f"Processing additional_fields: {auth_config['additional_fields']}")
                for field_name, field_path in auth_config['additional_fields'].items():
                    # Extract value from login response using the path with array support
                    value = self._extract_field_value_with_array_support(new_token_data, field_path)
                    if value is not None:
                        updated_credentials[field_name] = value
                        logger.info(f"Extracted {field_name} from login response: {value}")
                    else:
                        logger.warning(f"Could not extract {field_name} from path: {field_path}")
            
            # Save updated credentials back to database
            await self._save_updated_credentials(subscription_id, updated_credentials, db)
            
            return updated_credentials
    
    def _is_token_valid(self, credentials: Dict[str, Any]) -> bool:
        """Check if the current token is still valid"""
        if not credentials.get('access_token'):
            return False
        
        expires_at = credentials.get('expires_at')
        if not expires_at or expires_at == 0:
            # If no expiration or explicitly set to 0, token is invalid
            return False
        
        try:
            # Check if token expires in next 5 minutes (buffer time)
            if isinstance(expires_at, (int, float)):
                # Convert to seconds if it looks like milliseconds
                if expires_at > 10000000000:  # Likely milliseconds
                    expires_at = expires_at / 1000
                
                # Unix timestamp
                expiry_time = datetime.fromtimestamp(expires_at)
            elif isinstance(expires_at, str):
                # Try to parse ISO format date
                from dateutil import parser
                expiry_time = parser.parse(expires_at)
            else:
                # Assume it's already a datetime
                expiry_time = expires_at
                
            buffer_time = datetime.utcnow() + timedelta(minutes=5)
            
            return expiry_time > buffer_time
        except Exception as e:
            logger.error(f"Error checking token validity: {e}, expires_at value: {expires_at}")
            # If we can't parse the expiry, assume token is invalid to force refresh
            return False
    
    def _process_template_string(self, template: str, context: Dict[str, Any]) -> str:
        """Process a template string with variable substitution"""
        if not template or not isinstance(template, str):
            return template
        
        # Replace template variables
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in template:
                template = template.replace(placeholder, str(value))
        
        return template
    
    async def _login(
        self,
        auth_config: Dict[str, Any],
        current_credentials: Dict[str, Any],
        execution_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Perform login to obtain access token"""
        # Support both login_url and exchange_url for compatibility
        login_url = auth_config.get('login_url') or auth_config.get('exchange_url')
        if not login_url:
            logger.error("No login URL configured for token exchange")
            return None
        
        # Process template variables in login URL
        base_url = auth_config.get('base_url', '')
        http_base_url = auth_config.get('http_base_url', '')
        template_context = {
            'base_url': base_url,
            'http_base_url': http_base_url or base_url  # Fall back to base_url if http_base_url not provided
        }
        login_url = self._process_template_string(login_url, template_context)
        
        # Prepare login request body from template
        # Support both login_body_template and body_template for compatibility
        body_template = auth_config.get('login_body_template') or auth_config.get('body_template', {})
        
        # Log credentials (without sensitive data) for debugging
        logger.info(f"Current credentials fields: {list(current_credentials.keys())}")
        logger.debug(f"Body template: {body_template}")
        
        login_body = self._prepare_request_from_template(
            body_template,
            current_credentials
        )
        
        # Add token duration if configured
        if auth_config.get('token_duration_mins'):
            login_body['tokenDurationInMins'] = auth_config['token_duration_mins']
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Performing token exchange login to {login_url}")
                logger.debug(f"Login body (masked): {mask_sensitive_data(login_body)}")
                
                # Log to execution log
                self._log_to_execution(execution_context, "info", "Token Exchange: Sending login request", {
                    "url": login_url,
                    "method": auth_config.get('login_method', 'POST'),
                    "headers": mask_sensitive_data(headers),
                    "body": mask_sensitive_data(login_body)
                })
                
                response = await client.request(
                    method=auth_config.get('login_method', 'POST'),
                    url=login_url,
                    json=login_body,
                    headers=headers,
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                token_data = response.json()
                logger.info("Successfully obtained access token through login")
                
                # Log successful response to execution log
                self._log_to_execution(execution_context, "info", "Token Exchange: Login successful", {
                    "status_code": response.status_code,
                    "response": mask_sensitive_data(token_data),
                    "token_field": auth_config.get('token_field', 'access_token'),
                    "expiry_field": auth_config.get('expiry_field')
                })
                
                # Calculate expires_at if expires_in is provided
                expires_at = None
                if auth_config.get('expiry_field'):
                    expiry_value = self._extract_field_value(token_data, auth_config['expiry_field'])
                    if expiry_value:
                        logger.info(f"Extracted expiry value: {expiry_value} (type: {type(expiry_value)})")
                        
                        # Handle different expiry formats
                        if isinstance(expiry_value, (int, float)):
                            # Check if it's milliseconds (13 digits) or seconds (10 digits)
                            if expiry_value > 10000000000:
                                # Milliseconds - convert to seconds
                                expires_at = expiry_value / 1000
                            elif expiry_value < 10000:
                                # Likely duration in seconds, not timestamp
                                expires_at = int((datetime.utcnow() + timedelta(seconds=expiry_value)).timestamp())
                            else:
                                # Already a timestamp in seconds
                                expires_at = expiry_value
                        elif isinstance(expiry_value, str):
                            # Could be ISO date or numeric string
                            try:
                                # Try parsing as number first
                                num_value = float(expiry_value)
                                if num_value > 10000000000:
                                    expires_at = num_value / 1000
                                elif num_value < 10000:
                                    expires_at = int((datetime.utcnow() + timedelta(seconds=num_value)).timestamp())
                                else:
                                    expires_at = num_value
                            except ValueError:
                                # Not a number, try parsing as date
                                from dateutil import parser
                                expiry_date = parser.parse(expiry_value)
                                expires_at = int(expiry_date.timestamp())
                
                if expires_at:
                    try:
                        # Validate the timestamp
                        test_date = datetime.fromtimestamp(expires_at)
                        logger.info(f"Token expiry - set expires_at to: {expires_at} (datetime: {test_date})")
                        token_data['expires_at'] = expires_at
                    except (ValueError, OSError) as e:
                        logger.error(f"Invalid timestamp value {expires_at}: {e}")
                        # Don't set expires_at if invalid
                else:
                    # If no expiry returned on login, calculate based on token_duration_mins
                    if auth_config.get('token_duration_mins'):
                        duration_mins = auth_config['token_duration_mins']
                        expires_at = int((datetime.utcnow() + timedelta(minutes=duration_mins)).timestamp())
                        logger.info(f"No expiry in login response, calculated expires_at based on token_duration_mins ({duration_mins} mins): {expires_at}")
                        token_data['expires_at'] = expires_at
                    else:
                        # Default to 1 hour if nothing specified
                        expires_at = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
                        logger.info(f"No expiry in login response and no token_duration_mins, defaulting to 1 hour: {expires_at}")
                        token_data['expires_at'] = expires_at
                
                # Extract additional fields if configured
                if auth_config.get('additional_fields'):
                    logger.info(f"Processing additional_fields: {auth_config['additional_fields']}")
                    for field_name, field_path in auth_config['additional_fields'].items():
                        # Extract value from login response using the path with array support
                        value = self._extract_field_value_with_array_support(token_data, field_path)
                        if value is not None:
                            token_data[field_name] = value
                            logger.info(f"Extracted {field_name} from login response: {value}")
                        else:
                            logger.warning(f"Could not extract {field_name} from path: {field_path}")
                
                return token_data
                
        except httpx.HTTPStatusError as e:
            error_msg = f"Login failed with status {e.response.status_code}: {e.response.text}"
            logger.error(error_msg, exc_info=True)
            logger.error(f"Login URL: {login_url}")
            logger.error(f"Login body (masked): {mask_sensitive_data(login_body)}")
            
            # Log error to execution log
            self._log_to_execution(execution_context, "error", "Token Exchange: Login failed", {
                "url": login_url,
                "status_code": e.response.status_code,
                "error": e.response.text,
                "headers": mask_sensitive_data(headers),
                "body": mask_sensitive_data(login_body)
            })
            
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Login request failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            logger.error(f"Login URL: {login_url}")
            logger.error(f"Login body (masked): {mask_sensitive_data(login_body)}")
            
            # Log error to execution log
            self._log_to_execution(execution_context, "error", "Token Exchange: Login request failed", {
                "url": login_url,
                "error": str(e),
                "error_type": type(e).__name__,
                "headers": mask_sensitive_data(headers),
                "body": mask_sensitive_data(login_body)
            })
            
            raise Exception(error_msg)
    
    async def _refresh_token(
        self,
        auth_config: Dict[str, Any],
        current_credentials: Dict[str, Any],
        execution_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Refresh an existing token"""
        refresh_url = auth_config.get('refresh_url')
        if not refresh_url:
            logger.error("No refresh URL configured for token exchange")
            return None
        
        # Process template variables in refresh URL
        base_url = auth_config.get('base_url', '')
        template_context = {'base_url': base_url}
        refresh_url = self._process_template_string(refresh_url, template_context)
        
        # Prepare refresh headers from template
        headers = {
            'Content-Type': 'application/json'
        }
        
        if auth_config.get('refresh_headers_template'):
            refresh_headers = self._prepare_request_from_template(
                auth_config['refresh_headers_template'],
                current_credentials
            )
            headers.update(refresh_headers)
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Refreshing token at {refresh_url}")
                
                # Log to execution log
                self._log_to_execution(execution_context, "info", "Token Exchange: Sending refresh request", {
                    "url": refresh_url,
                    "method": auth_config.get('refresh_method', 'PUT'),
                    "headers": mask_sensitive_data(headers)
                })
                
                response = await client.request(
                    method=auth_config.get('refresh_method', 'PUT'),
                    url=refresh_url,
                    headers=headers,
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                token_data = response.json()
                logger.info("Successfully refreshed access token")
                
                # Log successful response to execution log
                self._log_to_execution(execution_context, "info", "Token Exchange: Refresh successful", {
                    "status_code": response.status_code,
                    "response": mask_sensitive_data(token_data),
                    "token_field": auth_config.get('token_field', 'access_token'),
                    "expiry_field": auth_config.get('expiry_field')
                })
                
                # Calculate expires_at if needed
                expires_at = None
                if auth_config.get('expiry_field'):
                    expiry_value = self._extract_field_value(token_data, auth_config['expiry_field'])
                    if expiry_value:
                        logger.info(f"Refresh - extracted expiry value: {expiry_value} (type: {type(expiry_value)})")
                        
                        # Handle different expiry formats (same logic as login)
                        if isinstance(expiry_value, (int, float)):
                            # Check if it's milliseconds (13 digits) or seconds (10 digits)
                            if expiry_value > 10000000000:
                                # Milliseconds - convert to seconds
                                expires_at = expiry_value / 1000
                            elif expiry_value < 10000:
                                # Likely duration in seconds, not timestamp
                                expires_at = int((datetime.utcnow() + timedelta(seconds=expiry_value)).timestamp())
                            else:
                                # Already a timestamp in seconds
                                expires_at = expiry_value
                        elif isinstance(expiry_value, str):
                            # Could be ISO date or numeric string
                            try:
                                # Try parsing as number first
                                num_value = float(expiry_value)
                                if num_value > 10000000000:
                                    expires_at = num_value / 1000
                                elif num_value < 10000:
                                    expires_at = int((datetime.utcnow() + timedelta(seconds=num_value)).timestamp())
                                else:
                                    expires_at = num_value
                            except ValueError:
                                # Not a number, try parsing as date
                                from dateutil import parser
                                expiry_date = parser.parse(expiry_value)
                                expires_at = int(expiry_date.timestamp())
                
                if expires_at:
                    try:
                        # Validate the timestamp
                        test_date = datetime.fromtimestamp(expires_at)
                        logger.info(f"Token expiry - set expires_at to: {expires_at} (datetime: {test_date})")
                        token_data['expires_at'] = expires_at
                    except (ValueError, OSError) as e:
                        logger.error(f"Invalid timestamp value {expires_at}: {e}")
                        # Don't set expires_at if invalid
                else:
                    # If no expiry returned on refresh, calculate based on token_duration_mins
                    if auth_config.get('token_duration_mins'):
                        duration_mins = auth_config['token_duration_mins']
                        expires_at = int((datetime.utcnow() + timedelta(minutes=duration_mins)).timestamp())
                        logger.info(f"No expiry in refresh response, calculated expires_at based on token_duration_mins ({duration_mins} mins): {expires_at}")
                        token_data['expires_at'] = expires_at
                    else:
                        # Default to 1 hour if nothing specified
                        expires_at = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
                        logger.info(f"No expiry in refresh response and no token_duration_mins, defaulting to 1 hour: {expires_at}")
                        token_data['expires_at'] = expires_at
                
                return token_data
                
        except httpx.HTTPStatusError as e:
            error_msg = f"Token refresh failed with status {e.response.status_code}: {e.response.text}"
            logger.error(error_msg, exc_info=True)
            logger.error(f"Refresh URL: {refresh_url}")
            
            # Log error to execution log
            self._log_to_execution(execution_context, "error", "Token Exchange: Refresh failed", {
                "url": refresh_url,
                "status_code": e.response.status_code,
                "error": e.response.text,
                "will_fallback_to_login": True
            })
            
            # Don't raise here, let it fall back to login
            return None
        except Exception as e:
            error_msg = f"Token refresh request failed: {str(e)}"
            logger.error(error_msg, exc_info=True) 
            logger.error(f"Refresh URL: {refresh_url}")
            
            # Log error to execution log
            self._log_to_execution(execution_context, "error", "Token Exchange: Refresh request failed", {
                "url": refresh_url,
                "error": str(e),
                "error_type": type(e).__name__,
                "will_fallback_to_login": True
            })
            
            # Don't raise here, let it fall back to login
            return None
    
    def _prepare_request_from_template(
        self,
        template: Dict[str, Any],
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare request data from template and credentials"""
        result = {}
        
        for key, value in template.items():
            if isinstance(value, str) and value.startswith('{{') and value.endswith('}}'):
                # Extract variable name
                var_name = value[2:-2].strip()
                # Only include the field if we have a value for it
                if var_name in credentials:
                    result[key] = credentials[var_name]
                # Skip the field if no value is available
            else:
                result[key] = value
        
        return result
    
    def _extract_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Extract value from nested JSON using dot notation"""
        parts = field_path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    def _extract_field_value_with_array_support(self, data: Dict[str, Any], field_path: str) -> Any:
        """
        Extract value from nested JSON using dot notation with array index support
        Supports paths like: data.associatedOrgs[0].organisation.id
        """
        import re
        
        # Split the path into segments including array indices
        segments = re.split(r'\.|\[|\]', field_path)
        segments = [s for s in segments if s]  # Remove empty strings
        
        current = data
        for segment in segments:
            if current is None:
                return None
                
            # Check if segment is a number (array index)
            if segment.isdigit():
                index = int(segment)
                if isinstance(current, list) and 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                # Object key
                if isinstance(current, dict) and segment in current:
                    current = current[segment]
                else:
                    return None
        
        return current
    
    async def _save_updated_credentials(
        self,
        subscription_id: str,
        updated_credentials: Dict[str, Any],
        db: Session
    ) -> None:
        """Save updated credentials to the database"""
        try:
            subscription = db.query(ApplicationSubscription).filter_by(
                subscription_id=subscription_id
            ).first()
            
            if subscription:
                # Encrypt and save credentials
                subscription.auth_credentials = encrypt_credentials(updated_credentials)
                db.commit()
                logger.info(f"Updated credentials for subscription {subscription_id}")
            else:
                logger.error(f"Subscription {subscription_id} not found")
                
        except Exception as e:
            logger.error(f"Failed to save updated credentials: {e}")
            db.rollback()
            raise


# Global instance
token_exchange_manager = TokenExchangeManager()


async def ensure_valid_token_exchange(
    subscription_id: str,
    auth_config: Dict[str, Any],
    credentials: Dict[str, Any],
    db: Session,
    execution_context: Optional[Dict[str, Any]] = None,
    base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ensure we have a valid token for token exchange auth
    
    Args:
        subscription_id: The subscription ID
        auth_config: The application's auth configuration
        credentials: Current credentials (decrypted)
        db: Database session
        execution_context: Optional execution context for logging
        
    Returns:
        Updated credentials with valid token
    """
    # If base_url is provided, add it to auth_config
    if base_url:
        auth_config = auth_config.copy()
        auth_config['base_url'] = base_url
        
    return await token_exchange_manager.get_valid_token(
        subscription_id=subscription_id,
        auth_config=auth_config,
        current_credentials=credentials,
        db=db,
        execution_context=execution_context
    )