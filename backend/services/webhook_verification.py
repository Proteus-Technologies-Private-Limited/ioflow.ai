"""
Webhook Verification Service

Provides flexible webhook verification for multiple providers including:
- HMAC signature verification (Slack, GitHub, Stripe, etc.)
- URL verification challenges (Slack, Facebook)
- Token-based verification (SendGrid, custom APIs)
"""
import hmac
import hashlib
import time
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


class WebhookVerifier(ABC):
    """Base class for webhook verification strategies"""
    
    @abstractmethod
    async def verify(self, request: Request, config: Dict[str, Any], 
                    credentials: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify the webhook request
        
        Returns:
            Tuple of (is_valid, response_data)
            response_data is used for challenge responses
        """
        pass


class HMACVerifier(WebhookVerifier):
    """HMAC signature verification for providers like Slack, GitHub, Stripe"""
    
    SUPPORTED_ALGORITHMS = {
        'sha256': hashlib.sha256,
        'sha1': hashlib.sha1,
        'sha512': hashlib.sha512
    }
    
    async def verify(self, request: Request, config: Dict[str, Any], 
                    credentials: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verify HMAC signature"""
        
        # Get configuration
        signature_header = config.get('signature_header', 'X-Webhook-Signature')
        timestamp_header = config.get('timestamp_header')
        algorithm = config.get('signature_algorithm', 'sha256').lower()
        timestamp_tolerance = config.get('timestamp_tolerance', 300)  # 5 minutes default
        
        # Get signing secret from credentials
        if not credentials or 'signing_secret' not in credentials:
            logger.error("No signing secret found in credentials")
            return False, None
        
        signing_secret = credentials['signing_secret']
        
        # Get signature from header
        provided_signature = request.headers.get(signature_header)
        if not provided_signature:
            logger.error(f"No signature found in header {signature_header}")
            return False, None
        
        # Verify timestamp if required
        if timestamp_header:
            timestamp_str = request.headers.get(timestamp_header)
            if not timestamp_str:
                logger.error(f"No timestamp found in header {timestamp_header}")
                return False, None
            
            try:
                request_timestamp = int(timestamp_str)
                current_timestamp = int(time.time())
                
                if abs(current_timestamp - request_timestamp) > timestamp_tolerance:
                    logger.error(f"Request timestamp too old: {request_timestamp}")
                    return False, None
            except ValueError:
                logger.error(f"Invalid timestamp format: {timestamp_str}")
                return False, None
        
        # Get request body - store it for later use
        if not hasattr(request, '_body'):
            body = await request.body()
            # Store the body so it can be read again later
            request._body = body
        else:
            body = request._body
        body_str = body.decode('utf-8')
        
        # Build signature base string using configurable format
        timestamp_str = request.headers.get(timestamp_header) if timestamp_header else None
        
        # Get signature base format from config
        if timestamp_str:
            # Use format with timestamp if available
            base_format = config.get('signature_base_format_with_timestamp', '{{timestamp}}:{{body}}')
        else:
            # Use format without timestamp
            base_format = config.get('signature_base_format', '{{body}}')
        
        # Replace template variables
        base_string = base_format.replace('{{timestamp}}', timestamp_str or '') \
                                 .replace('{{body}}', body_str)
        
        # Compute signature
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            logger.error(f"Unsupported algorithm: {algorithm}")
            return False, None
        
        hash_func = self.SUPPORTED_ALGORITHMS[algorithm]
        computed_signature = hmac.new(
            signing_secret.encode('utf-8'),
            base_string.encode('utf-8'),
            hash_func
        ).hexdigest()
        
        # Apply signature format template if provided
        signature_format = config.get('signature_format', '{{signature}}')
        computed_signature = signature_format.replace('{{signature}}', computed_signature)
        
        # Constant-time comparison
        is_valid = hmac.compare_digest(computed_signature, provided_signature)
        
        if not is_valid:
            logger.error(f"Signature mismatch. Provided: {provided_signature}, Computed: {computed_signature}")
        
        return is_valid, None


SIGNATURE_ALGORITHMS = {
    'sha256': hashlib.sha256,
    'sha1': hashlib.sha1,
    'sha512': hashlib.sha512,
}


def get_signature_config(event_configuration: Any, app_webhook_config: Any) -> Optional[Dict[str, Any]]:
    """Return the opt-in ``signature`` block: the event's wins over the application's.

    Shape: {"header": "X-Shopify-Hmac-Sha256", "algorithm": "sha256",
            "encoding": "base64" | "hex", "secret_field": "client_secret",
            "prefix": "sha256="  (optional, stripped from the header value)}
    """
    for source in (event_configuration, app_webhook_config):
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except (json.JSONDecodeError, TypeError):
                source = None
        if isinstance(source, dict) and isinstance(source.get('signature'), dict):
            return source['signature']
    return None


def verify_body_signature(raw_body: bytes, headers: Any, signature_config: Dict[str, Any],
                          credentials: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """Verify an HMAC signature of the RAW request body.

    Returns (is_valid, reason). The secret is read from
    ``credentials[signature_config.secret_field]`` (default "signing_secret"), i.e.
    from the subscription the webhook belongs to, so each connection (shop) is
    checked against its own app secret.
    """
    header_name = signature_config.get('header')
    if not header_name:
        return False, "signature config has no 'header'"
    algorithm = str(signature_config.get('algorithm') or 'sha256').lower()
    hash_func = SIGNATURE_ALGORITHMS.get(algorithm)
    if hash_func is None:
        return False, f"unsupported signature algorithm '{algorithm}'"
    encoding = str(signature_config.get('encoding') or 'hex').lower()
    if encoding not in ('hex', 'base64'):
        return False, f"unsupported signature encoding '{encoding}'"
    secret_field = signature_config.get('secret_field') or 'signing_secret'

    secret = (credentials or {}).get(secret_field)
    if not secret:
        return False, f"the connection has no '{secret_field}' to verify the signature with"

    provided = headers.get(header_name) if headers is not None else None
    if not provided:
        return False, f"missing signature header '{header_name}'"
    provided = provided.strip()
    prefix = signature_config.get('prefix')
    if prefix and provided.startswith(prefix):
        provided = provided[len(prefix):]

    digest = hmac.new(str(secret).encode('utf-8'), raw_body or b'', hash_func).digest()
    if encoding == 'base64':
        import base64
        computed = base64.b64encode(digest).decode('ascii')
        is_valid = hmac.compare_digest(computed, provided)
    else:
        computed = digest.hex()
        is_valid = hmac.compare_digest(computed, provided.lower())
    return (True, 'ok') if is_valid else (False, 'signature mismatch')


class ChallengeVerifier(WebhookVerifier):
    """URL verification challenge handler for providers like Slack, Facebook"""
    
    async def verify(self, request: Request, config: Dict[str, Any], 
                    credentials: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Handle URL verification challenges"""
        
        # Get challenge configurations
        challenge_configs = config.get('challenge_configs', [])
        if not challenge_configs:
            # No challenge configuration, not a challenge request
            return True, None
        
        # Ensure it's a list
        if isinstance(challenge_configs, dict):
            challenge_configs = [challenge_configs]
        
        # Try each challenge configuration
        for challenge_config in challenge_configs:
            method = challenge_config.get('method', 'POST').upper()
            
            # Check if request method matches
            if request.method != method:
                continue
            
            if method == "POST":
                # Handle POST-based challenges (e.g., Slack)
                if not hasattr(request, '_body'):
                    body = await request.body()
                    request._body = body
                else:
                    body = request._body
                    
                try:
                    data = json.loads(body)
                    
                    # Check challenge conditions
                    conditions = challenge_config.get('conditions', {})
                    all_match = True
                    
                    for field, expected_value in conditions.items():
                        if data.get(field) != expected_value:
                            all_match = False
                            break
                    
                    if all_match:
                        # Extract challenge value
                        challenge_field = challenge_config.get('challenge_field', 'challenge')
                        challenge_value = data.get(challenge_field)
                        
                        if challenge_value:
                            response_field = challenge_config.get('response_field', 'challenge')
                            plain_text_response = challenge_config.get('plain_text_response', False)
                            logger.info(f"Handling {challenge_config.get('name', 'webhook')} verification challenge (plain_text={plain_text_response})")

                            if plain_text_response:
                                # Return special marker for plain text response
                                return True, {"__plain_text__": challenge_value}
                            else:
                                return True, {response_field: challenge_value}

                except json.JSONDecodeError:
                    pass
            
            elif method == "GET":
                # Handle GET-based challenges (e.g., Facebook)
                params = dict(request.query_params)
                
                # Check challenge conditions
                conditions = challenge_config.get('conditions', {})
                all_match = True
                
                for field, expected_value in conditions.items():
                    if params.get(field) != expected_value:
                        all_match = False
                        break
                
                if all_match:
                    # Extract challenge value
                    challenge_field = challenge_config.get('challenge_field', 'challenge')
                    challenge_value = params.get(challenge_field)
                    
                    if challenge_value:
                        # Verify token if configured
                        token_field = challenge_config.get('token_field')
                        if token_field:
                            provided_token = params.get(token_field)
                            expected_token = config.get('verify_token')
                            
                            if expected_token and provided_token != expected_token:
                                logger.error("Invalid verification token")
                                return False, None
                        
                        response_field = challenge_config.get('response_field', 'challenge')
                        plain_text_response = challenge_config.get('plain_text_response', False)
                        logger.info(f"Handling {challenge_config.get('name', 'webhook')} verification challenge (plain_text={plain_text_response})")

                        if plain_text_response:
                            # Return special marker for plain text response (required by META/Facebook)
                            return True, {"__plain_text__": challenge_value}
                        else:
                            return True, {response_field: challenge_value}
        
        # Not a challenge request or no matching configuration
        return True, None


class TokenVerifier(WebhookVerifier):
    """Token-based verification for simple API key authentication"""
    
    async def verify(self, request: Request, config: Dict[str, Any], 
                    credentials: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verify API token/key"""
        
        token_header = config.get('token_header', 'Authorization')  # Default to standard Authorization header
        token_param = config.get('token_param')
        
        # Try Authorization header first (standard Bearer token format)
        provided_token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            provided_token = auth_header[7:]
        
        # Fallback to custom header (e.g., X-API-Key) for backward compatibility
        if not provided_token:
            if token_header != 'Authorization':
                provided_token = request.headers.get(token_header)
            # Also check X-API-Key headers for backward compatibility
            if not provided_token:
                provided_token = request.headers.get('X-API-Key') or request.headers.get('x-api-key')
        
        # Try query parameter if not in header
        if not provided_token and token_param:
            provided_token = request.query_params.get(token_param)
        
        if not provided_token:
            logger.error("No token found in request")
            return False, None
        
        # Get expected token from credentials
        if not credentials or 'webhook_token' not in credentials:
            logger.error("No webhook token found in credentials")
            return False, None
        
        expected_token = credentials['webhook_token']
        
        # Constant-time comparison
        is_valid = hmac.compare_digest(provided_token, expected_token)
        
        if not is_valid:
            logger.error("Token mismatch")
        
        return is_valid, None


class WebhookVerificationService:
    """Main service for webhook verification"""

    def __init__(self):
        # Try to load verifiers from plugin registry; fall back to hardcoded if not yet discovered
        try:
            from plugins.registry import PluginRegistry
            registry_verifiers = {
                k: PluginRegistry.get_webhook_verifier(k)
                for k in PluginRegistry.list_webhook_verifiers()
            }
            if registry_verifiers:
                self.verifiers = registry_verifiers
            else:
                # Registry empty (plugins not yet discovered) — use defaults
                self.verifiers = {
                    'hmac': HMACVerifier(),
                    'challenge': ChallengeVerifier(),
                    'token': TokenVerifier()
                }
        except ImportError:
            self.verifiers = {
                'hmac': HMACVerifier(),
                'challenge': ChallengeVerifier(),
                'token': TokenVerifier()
            }
    
    async def verify_webhook(self, request: Request, app_config: Dict[str, Any], 
                           credentials: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify incoming webhook based on application configuration
        
        Args:
            request: FastAPI request object
            app_config: Application webhook configuration
            credentials: Application credentials (signing secret, tokens, etc.)
            
        Returns:
            Tuple of (is_valid, response_data)
        """
        
        webhook_config = app_config.get('webhook_config', {})
        if isinstance(webhook_config, str):
            try:
                webhook_config = json.loads(webhook_config)
            except json.JSONDecodeError:
                webhook_config = {}
        
        # Get verification method
        verification_method = webhook_config.get('verification_method', 'none')
        
        # No verification required
        if verification_method == 'none':
            return True, None
        
        # Handle multiple verification methods
        methods = [verification_method] if isinstance(verification_method, str) else verification_method
        
        # Special handling for URL verification challenges
        if webhook_config.get('url_verification_enabled'):
            # Check challenge first
            challenge_verifier = self.verifiers.get('challenge')
            if challenge_verifier:
                is_valid, response_data = await challenge_verifier.verify(request, webhook_config, credentials)
                if response_data:  # This is a challenge request
                    return is_valid, response_data
        
        # Verify using configured method(s)
        for method in methods:
            verifier = self.verifiers.get(method)
            if not verifier:
                logger.warning(f"Unknown verification method: {method}")
                continue
            
            is_valid, response_data = await verifier.verify(request, webhook_config, credentials)
            if is_valid:
                return True, response_data
        
        return False, None


# Global instance
webhook_verification_service = WebhookVerificationService()