"""
Service executors for different service types
"""
import httpx
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
import logging

# Try to import jinja2 for template processing
try:
    from jinja2 import Template
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

from utils.retry_utils import retry_async, NETWORK_RETRY_CONFIG, RetryConfig
from utils.crypto_utils import mask_sensitive_data, redact_secrets

logger = logging.getLogger(__name__)

# Special retry config for auth operations (fewer retries)
AUTH_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    initial_delay=0.5,
    max_delay=2.0,
    exponential_base=2.0,
    retry_on=(ConnectionError, TimeoutError)
)


def process_template(template_str: str, variables: Dict[str, Any]) -> str:
    """Process a template string with variables."""
    if HAS_JINJA2:
        # Use Jinja2 for proper template processing
        template = Template(template_str)
        return template.render(**variables)
    else:
        # Fallback to simple string replacement
        result = template_str
        for key, value in variables.items():
            result = result.replace(f"{{{{ {key} }}}}", str(value))
        return result


class ServiceExecutor:
    """Base class for service executors"""

    def __init__(self, service_config: Dict[str, Any], auth_credentials: Dict[str, Any] = None,
                 subscription_id: str = None, auth_config: Dict[str, Any] = None):
        self.service_config = service_config
        self.auth_credentials = auth_credentials or {}
        self.subscription_id = subscription_id
        self.auth_config = auth_config or {}
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the service. Must be implemented by subclasses."""
        raise NotImplementedError
    
    async def _ensure_valid_oauth2_token(self, db=None):
        """Ensure OAuth2 token is valid, refreshing if needed"""
        # Only handle OAuth2 tokens
        if not self.auth_credentials or 'client_id' not in self.auth_credentials:
            return
        
        # Check if we have the necessary info for OAuth2 refresh
        if not self.subscription_id or not self.auth_config:
            return
        
        # Import here to avoid circular imports
        from services.oauth2_manager import ensure_valid_oauth2_token
        from services.token_exchange_manager import ensure_valid_token_exchange
        from db.database import get_db
        
        # Use provided db or get a new one
        if db:
            self.auth_credentials = await ensure_valid_oauth2_token(
                subscription_id=self.subscription_id,
                auth_config=self.auth_config,
                credentials=self.auth_credentials,
                db=db
            )
        else:
            # This is a fallback - ideally db should be provided
            with next(get_db()) as new_db:
                self.auth_credentials = await ensure_valid_oauth2_token(
                    subscription_id=self.subscription_id,
                    auth_config=self.auth_config,
                    credentials=self.auth_credentials,
                    db=new_db
                )
    
    async def _ensure_valid_token_exchange(self, db=None, context=None):
        """Ensure token exchange token is valid, refreshing if needed"""
        # Only handle token exchange auth
        if not self.auth_credentials or 'username' not in self.auth_credentials:
            return
        
        # Check if we have the necessary info
        if not self.subscription_id or not self.auth_config:
            return
        
        # Import here to avoid circular imports
        from services.token_exchange_manager import ensure_valid_token_exchange
        from db.database import get_db, get_tenant_db
        
        # Create execution context if context is provided
        execution_context = None
        if context and context.get('execution_id'):
            execution_context = {
                'execution_id': context.get('execution_id'),
                'node_id': context.get('current_node_id'),
                'log_callback': context.get('log_callback')
            }
        
        # Use provided db or get a new one
        if db:
            self.auth_credentials = await ensure_valid_token_exchange(
                subscription_id=self.subscription_id,
                auth_config=self.auth_config,
                credentials=self.auth_credentials,
                db=db,
                execution_context=execution_context,
                base_url=self.service_config.get('base_url')
            )
        else:
            # This is a fallback - ideally db should be provided
            with next(get_db()) as new_db:
                self.auth_credentials = await ensure_valid_token_exchange(
                    subscription_id=self.subscription_id,
                    auth_config=self.auth_config,
                    credentials=self.auth_credentials,
                    db=new_db,
                    execution_context=execution_context,
                    base_url=self.service_config.get('base_url')
                )
    
    def _validate_response(self, response_data: Any, response_config: Dict[str, Any], status_code: int) -> Dict[str, Any]:
        """Validate API response based on response_config."""
        logger.info(f"_validate_response called with status_code: {status_code}, response_config: {response_config}")
        success_check = response_config.get('success_check', {})
        error_extraction = response_config.get('error_extraction', {})
        
        # Check for success
        check_type = success_check.get('type', 'status_code')
        
        if check_type == 'status_code':
            # Check if custom success status codes are defined
            # Support both 'success_status_codes' and 'value' for backward compatibility
            success_status_codes = success_check.get('success_status_codes') or success_check.get('value')
            logger.info(f"Success check type: {check_type}, success_status_codes: {success_status_codes}")
            
            if success_status_codes is not None:
                # Use custom success status codes
                # Handle both list and single value formats
                if isinstance(success_status_codes, (list, tuple)):
                    success_codes = success_status_codes
                else:
                    success_codes = [success_status_codes]
                
                if status_code not in success_codes:
                    # Status code not in success list, treat as error
                    error_msg = self._extract_error_message(response_data, error_extraction)
                    return {
                        'error': True,
                        'status_code': status_code,
                        'message': error_msg,
                        'response': response_data
                    }
            else:
                # Use default behavior: 400+ is error
                if status_code >= 400:
                    # Extract error details if available
                    error_msg = self._extract_error_message(response_data, error_extraction)
                    return {
                        'error': True,
                        'status_code': status_code,
                        'message': error_msg,
                        'response': response_data
                    }
        
        elif check_type == 'field_value' and isinstance(response_data, dict):
            # Check a specific field for success (e.g., Slack's "ok" field)
            field_name = success_check.get('field')
            expected_value = success_check.get('expected')
            
            if field_name and field_name in response_data:
                actual_value = response_data.get(field_name)
                if actual_value != expected_value:
                    # API returned an error
                    error_msg = self._extract_error_message(response_data, error_extraction)
                    logger.error(f"API validation failed: {field_name}={actual_value}, expected {expected_value}")
                    logger.error(f"Extracted error: {error_msg}")
                    return {
                        'error': True,
                        'status_code': status_code,
                        'message': error_msg,
                        'api_error': True,
                        'response': response_data
                    }
        
        # Response is valid
        return {'error': False}
    
    def _extract_error_message(self, response_data: Any, error_extraction: Dict[str, str]) -> str:
        """Extract error message from response based on error_extraction config."""
        if not isinstance(response_data, dict):
            return f"API request failed: {str(response_data)[:200]}"
        
        if not error_extraction:
            # No error extraction config, try common error fields
            for field in ['errors', 'error', 'message', 'msg', 'detail', 'error_message']:
                if field in response_data and response_data[field]:
                    error_value = response_data[field]
                    # Handle non-string error values
                    if isinstance(error_value, str):
                        return f"API Error: {error_value}"
                    elif isinstance(error_value, bool):
                        # Skip boolean error flags, continue to next field
                        continue
                    else:
                        return f"API Error: {str(error_value)}"
            return f"API request failed: {json.dumps(response_data)[:200]}"
        
        # Try to extract error message using configured fields
        error_field = error_extraction.get('error_field', 'error')
        message_field = error_extraction.get('message_field', 'message')
        
        # First try direct error field
        if error_field in response_data:
            error_value = response_data[error_field]
            if isinstance(error_value, str):
                return f"API Error: {error_value}"
            elif isinstance(error_value, dict) and 'message' in error_value:
                return f"API Error: {error_value['message']}"
        
        # Try nested message field (e.g., "error.message")
        if '.' in message_field:
            parts = message_field.split('.')
            value = response_data
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            if value:
                return f"API Error: {value}"
        elif message_field in response_data:
            return f"API Error: {response_data[message_field]}"
        
        # Fallback to generic message with response
        return f"API request failed with response: {json.dumps(response_data)[:200]}"

    def _convert_param_types(self, params: Dict[str, Any], parameter_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert parameter values to their correct types based on schema"""
        if not parameter_schema or 'properties' not in parameter_schema:
            return params
            
        schema_properties = parameter_schema.get('properties', {})
        converted = {}
        
        for key, value in params.items():
            if key in schema_properties:
                param_schema = schema_properties[key]
                param_type = param_schema.get('type', 'string')
                
                try:
                    if param_type == 'array' and isinstance(value, str):
                        # Try to parse string as JSON array
                        if value.strip().startswith('['):
                            try:
                                converted[key] = json.loads(value)
                                logger.debug(f"Converted parameter '{key}' from string to array")
                            except json.JSONDecodeError:
                                # Try to fix JavaScript-style JSON (unquoted property names)
                                import re
                                # Fix unquoted property names by adding quotes
                                fixed_json = re.sub(r'(\w+):', r'"\1":', value)
                                # Fix single quotes to double quotes
                                fixed_json = fixed_json.replace("'", '"')
                                try:
                                    converted[key] = json.loads(fixed_json)
                                    logger.debug(f"Converted parameter '{key}' from JavaScript-style string to array")
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse array parameter '{key}' even after fixing: {e}")
                                    converted[key] = value
                        else:
                            converted[key] = value
                    elif param_type == 'object' and isinstance(value, str):
                        # Try to parse string as JSON object
                        if value.strip().startswith('{'):
                            try:
                                converted[key] = json.loads(value)
                                logger.debug(f"Converted parameter '{key}' from string to object")
                            except json.JSONDecodeError:
                                # Try to fix JavaScript-style JSON (unquoted property names)
                                import re
                                # Fix unquoted property names by adding quotes
                                fixed_json = re.sub(r'(\w+):', r'"\1":', value)
                                # Fix single quotes to double quotes
                                fixed_json = fixed_json.replace("'", '"')
                                try:
                                    converted[key] = json.loads(fixed_json)
                                    logger.debug(f"Converted parameter '{key}' from JavaScript-style string to object")
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse object parameter '{key}' even after fixing: {e}")
                                    converted[key] = value
                        else:
                            converted[key] = value
                    elif param_type == 'boolean' and isinstance(value, str):
                        # Convert string to boolean
                        if value.lower() in ['true', '1', 'yes']:
                            converted[key] = True
                        elif value.lower() in ['false', '0', 'no']:
                            converted[key] = False
                        else:
                            converted[key] = value
                    elif param_type == 'integer' and isinstance(value, str):
                        # Try to convert to integer
                        try:
                            converted[key] = int(value)
                        except ValueError:
                            converted[key] = value
                    elif param_type == 'number' and isinstance(value, str):
                        # Try to convert to float
                        try:
                            converted[key] = float(value)
                        except ValueError:
                            converted[key] = value
                    else:
                        converted[key] = value
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to convert parameter '{key}' to type '{param_type}': {e}")
                    converted[key] = value
            else:
                converted[key] = value
                
        return converted
    
    def _build_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers based on auth type"""
        headers = {}
        logger.debug(f"Building auth headers with credentials: {list(self.auth_credentials.keys()) if self.auth_credentials else 'None'}")
        logger.debug(f"Auth config available: {self.auth_config}")
        
        # Check for OAuth2/Token Exchange authentication first (highest priority)
        # This is because token exchange also has username/password but should use the access_token
        if 'access_token' in self.auth_credentials:
            auth_config = self.auth_config if isinstance(self.auth_config, dict) else {}
            if 'access_token_header' in auth_config or 'access_token_prefix' in auth_config:
                # Configurable placement (e.g. Amazon SP-API "x-amz-access-token",
                # Shopify "X-Shopify-Access-Token"): the token goes ONLY in this header.
                header_name = auth_config.get('access_token_header') or 'Authorization'
                prefix = auth_config.get('access_token_prefix')
                if prefix is None:
                    prefix = self.auth_credentials.get('token_type') or 'Bearer'
                token = self.auth_credentials.get('access_token')
                if not token:
                    logger.error(f"access_token is empty; cannot set auth header '{header_name}'")
                else:
                    prefix = str(prefix).strip()
                    headers[header_name] = f"{prefix} {token}" if prefix else str(token)
                    logger.info(f"Using OAuth2 access token in header '{header_name}' "
                                f"({'prefix ' + repr(prefix) if prefix else 'no prefix'})")
            else:
                token_type = self.auth_credentials.get('token_type', 'Bearer')
                headers['Authorization'] = f"{token_type} {self.auth_credentials['access_token']}"
                logger.info(f"Using OAuth2/Token Exchange authentication: {token_type} token")
                logger.info(f"Access token length: {len(self.auth_credentials['access_token'])}")
        
        # API Key authentication
        elif 'api_key' in self.auth_credentials:
            # Get header configuration from auth_config, not from credentials
            header_name = self.auth_config.get('header_name', 'Authorization')
            # Only use 'Bearer' as default if header_name is 'Authorization'
            # For custom headers like 'authkey', don't assume a prefix
            if header_name == 'Authorization':
                header_prefix = self.auth_config.get('header_prefix', 'Bearer')
            else:
                header_prefix = self.auth_config.get('header_prefix', '')
            
            if header_prefix:
                headers[header_name] = f"{header_prefix} {self.auth_credentials['api_key']}"
            else:
                headers[header_name] = self.auth_credentials['api_key']
            logger.info(f"Using API key authentication: {header_name} = {header_prefix} {'*' * 10}{self.auth_credentials['api_key'][-3:] if len(self.auth_credentials['api_key']) > 3 else '***'}")
        
        # Basic authentication (only if no access_token is present)
        elif 'username' in self.auth_credentials and ('password' in self.auth_credentials or 'app_password' in self.auth_credentials):
            import base64
            # Use app_password if available (WordPress), otherwise use password
            password = self.auth_credentials.get('app_password') or self.auth_credentials.get('password')
            credentials = f"{self.auth_credentials['username']}:{password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"
            logger.debug(f"Using Basic authentication for user: {self.auth_credentials['username']}")
        else:
            logger.debug("No standard authentication type found in credentials")
        
        # Always check for custom headers (in addition to standard auth)
        # This allows custom headers to be added alongside API key, OAuth2, etc.
        if 'headers' in self.auth_credentials:
            custom_headers = self.auth_credentials.get('headers', {})
            # Process custom headers as templates
            if custom_headers:
                logger.info(f"Processing subscription-level custom headers: {list(custom_headers.keys())}")
                # Create context for template processing
                template_context = {'auth': self.auth_credentials}
                processed_headers = self._process_template_dict(custom_headers, template_context)
                headers.update(processed_headers)
                logger.info(f"Added custom headers after template processing: {list(processed_headers.keys())}")
                logger.debug(f"Custom header values: {mask_sensitive_data(processed_headers)}")
        
        logger.debug(f"Final auth headers built: {mask_sensitive_data(headers)}")
        return headers


class ApiCallExecutor(ServiceExecutor):
    """Executor for API Call service type"""
    
    def _log_to_execution(self, context: Dict[str, Any], level: str, message: str, data: Dict[str, Any]):
        """Log to execution logs"""
        if context and context.get('execution_id'):
            if context.get('log_callback'):
                context['log_callback'](
                    context['execution_id'],
                    context.get('current_node_id'),
                    level,
                    message,
                    data
                )
            else:
                from db.models import ExecutionLog
                from datetime import datetime
                import uuid
                db = context.get('db')
                if db:
                    log_entry = ExecutionLog(
                        log_id=str(uuid.uuid4()),
                        execution_id=context['execution_id'],
                        step_id=context.get('current_node_id'),
                        timestamp=datetime.utcnow(),
                        level=level,
                        message=message,
                        data=data
                    )
                    db.add(log_entry)
                    db.commit()
    
    def _log_http_response(self, response: httpx.Response, context: Dict[str, Any], 
                          elapsed_time: float, response_data: Any = None):
        """Log HTTP response details to execution logs"""
        if context and 'execution_id' in context:
            # Meter what this answer cost (the connector's response_config.usage);
            # a no-op for services that declare no meters, and never raises.
            from services.flow_usage import record_response
            record_response(context, self.service_config, response_data, response.status_code)
            from db.database import get_tenant_db
            from db.models import ExecutionLog
            import uuid
            from datetime import datetime
            
            # Prepare response log data
            response_log_data = {
                'type': 'http_response',
                'status_code': response.status_code,
                'status_text': response.reason_phrase,
                'elapsed_time': f"{elapsed_time:.3f}s",
                'headers': dict(response.headers),
                'body': response_data if response_data is not None else response.text
            }
            
            # Get tenant schema from context
            # Use log callback if available, otherwise create log directly
            if context.get('log_callback'):
                context['log_callback'](
                    context['execution_id'],
                    context.get('current_node_id'),
                    'info',
                    f'API Response: {response.status_code} {response.reason_phrase}',
                    response_log_data
                )
            else:
                tenant_schema = context.get('tenant_schema', 'public')
                with get_tenant_db(tenant_schema) as db:
                    log_entry = ExecutionLog(
                        log_id=str(uuid.uuid4()),
                        execution_id=context['execution_id'],
                        step_id=context.get('current_node_id'),
                        timestamp=datetime.utcnow(),
                        level='info',
                        message=f'API Response: {response.status_code} {response.reason_phrase}',
                        data=response_log_data
                    )
                    db.add(log_entry)
                    db.commit()
    
    # ------------------------------------------------------------------
    # Jinja request/response templates (request_config.body_jinja /
    # query_jinja / no_request, response_config.output_jinja / error_jinja /
    # success_jinja / keep_raw). All opt-in: with none of these keys present
    # execute() behaves exactly as _execute_request() always has.
    # ------------------------------------------------------------------

    def _request_template_context(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Context for body_jinja / query_jinja: every parameter at top level,
        plus ``params`` (all of them), ``auth`` (credentials) and ``now_iso``."""
        from services.jinja_templating import now_iso
        params = parameters if isinstance(parameters, dict) else {}
        ctx = dict(params)
        ctx['params'] = params
        ctx['auth'] = self.auth_credentials or {}
        ctx['now_iso'] = now_iso()
        return ctx

    def _response_template_context(self, response_data: Any, parameters: Dict[str, Any],
                                   status_code: Any, headers: Any) -> Dict[str, Any]:
        """Context for output_jinja / error_jinja / success_jinja."""
        from services.jinja_templating import now_iso
        lowered = {}
        if isinstance(headers, dict):
            lowered = {str(k).lower(): v for k, v in headers.items()}
        return {
            'response': response_data,
            'params': parameters if isinstance(parameters, dict) else {},
            'status_code': status_code,
            'headers': lowered,
            'auth': self.auth_credentials or {},
            'now_iso': now_iso(),
        }

    def _render_error_message(self, response_config: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[str]:
        """Render response_config.error_jinja into a readable message (None if not configured)."""
        from services.jinja_templating import render_json, TemplateRenderError, excerpt
        error_jinja = response_config.get('error_jinja')
        if not (isinstance(error_jinja, str) and error_jinja.strip()):
            return None
        try:
            rendered = render_json(error_jinja, ctx, 'response_config.error_jinja')
        except TemplateRenderError as e:
            logger.error(f"error_jinja failed; falling back to the default error message: {e}")
            return None
        if isinstance(rendered, dict):
            message = rendered.get('message')
            if message in (None, ''):
                message = excerpt(rendered)
        elif rendered in (None, ''):
            return None
        else:
            message = rendered if isinstance(rendered, str) else excerpt(rendered)
        return str(message)

    def _mapping_error_result(self, message: str, status_code: Any = None, response_data: Any = None,
                              headers: Any = None) -> Dict[str, Any]:
        result = {
            'error': True,
            'success': False,
            'message': message,
            'template_error': True,
        }
        if status_code is not None:
            result['status_code'] = status_code
            result['status'] = status_code
        if response_data is not None:
            result['response'] = response_data
            result['data'] = response_data
        if headers is not None:
            result['headers'] = headers
        return result

    def _apply_response_templates(self, result: Any, parameters: Dict[str, Any],
                                  response_config: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Apply success_jinja / error_jinja / output_jinja to an executor result.

        The executor's outer result shape is kept; on success ONLY ``result['data']``
        is replaced by the mapped value (``data`` is what a downstream flow node
        reads: node_outputs.<node>.data, with its top-level keys also merged onto
        the node output by the execution engine).
        """
        from services.jinja_templating import render_json, render_bool, TemplateRenderError, excerpt
        if not isinstance(result, dict) or not isinstance(response_config, dict):
            return result

        output_jinja = response_config.get('output_jinja')
        success_jinja = response_config.get('success_jinja')
        error_jinja = response_config.get('error_jinja')
        has_output = isinstance(output_jinja, str) and output_jinja.strip() != ''
        has_success = isinstance(success_jinja, str) and success_jinja.strip() != ''
        has_error = isinstance(error_jinja, str) and error_jinja.strip() != ''
        if not (has_output or has_success or has_error):
            return result

        # ---- failed call: only error_jinja applies -------------------------
        if result.get('error') or result.get('success') is False:
            if has_error and ('response' in result or 'data' in result):
                response_data = result.get('response', result.get('data'))
                status_code = result.get('status_code', result.get('status'))
                ctx = self._response_template_context(response_data, parameters, status_code,
                                                      result.get('headers', {}))
                message = self._render_error_message(response_config, ctx)
                if message:
                    result = dict(result)
                    result['message'] = message
            return result

        if 'data' not in result:
            return result

        response_data = result.get('data')
        status_code = result.get('status', result.get('status_code'))
        headers = result.get('headers', {})
        ctx = self._response_template_context(response_data, parameters, status_code, headers)

        # ---- success_jinja: a 2xx can still be a business failure ----------
        if has_success:
            try:
                ok = render_bool(success_jinja, ctx, 'response_config.success_jinja')
            except TemplateRenderError as e:
                message = f"{e}. Response starts: {excerpt(response_data)!r}"
                logger.error(message)
                self._log_to_execution(context, "error", f"api_call failed: {message}", {"status_code": status_code})
                return self._mapping_error_result(message, status_code, response_data, headers)
            if not ok:
                message = (self._render_error_message(response_config, ctx)
                           or f"API reported failure (success_jinja evaluated false): {excerpt(response_data)}")
                logger.error(f"api_call treated as failed by success_jinja: {message}")
                self._log_to_execution(context, "error", f"api_call failed: {message}",
                                       {"status_code": status_code, "response": response_data})
                failed = self._mapping_error_result(message, status_code, response_data, headers)
                failed['api_error'] = True
                failed.pop('template_error', None)
                return failed

        # ---- output_jinja: map the response to the canonical shape ---------
        if has_output:
            try:
                mapped = render_json(output_jinja, ctx, 'response_config.output_jinja')
            except TemplateRenderError as e:
                message = f"{e}. Response starts: {excerpt(response_data)!r}"
                logger.error(message)
                self._log_to_execution(context, "error", f"api_call response mapping failed: {message}",
                                       {"status_code": status_code})
                return self._mapping_error_result(message, status_code, response_data, headers)
            if response_config.get('keep_raw') and isinstance(mapped, dict):
                mapped['raw'] = response_data
            result = dict(result)
            result['data'] = mapped
            logger.info(f"Response mapped by output_jinja (type {type(mapped).__name__})")
        return result

    def _no_request_result(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """request_config.no_request: answer from output_jinja without any HTTP call."""
        from services.jinja_templating import render_json, TemplateRenderError
        config = self.service_config if isinstance(self.service_config, dict) else {}
        response_config = config.get('response_config') or {}
        output_jinja = response_config.get('output_jinja') if isinstance(response_config, dict) else None
        service_name = config.get('service_name', 'service')
        mapped: Any = {}
        if isinstance(output_jinja, str) and output_jinja.strip():
            ctx = self._response_template_context({}, parameters, 200, {})
            try:
                mapped = render_json(output_jinja, ctx, 'response_config.output_jinja')
            except TemplateRenderError as e:
                logger.error(f"no_request service '{service_name}': {e}")
                self._log_to_execution(context, "error", f"api_call (no_request) failed: {e}", {})
                return self._mapping_error_result(str(e))
            if mapped is None:
                mapped = {}
        else:
            logger.warning(f"no_request service '{service_name}' has no response_config.output_jinja; returning {{}}")
        logger.info(f"no_request service '{service_name}': no HTTP call made, returning the rendered stub")
        self._log_to_execution(context, "info", f"No HTTP request for '{service_name}' (no_request stub)",
                               {"data": mapped})
        return {
            'data': mapped,
            'status': 200,
            'headers': {},
            'success': True,
            'no_request': True,
        }

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        from services.jinja_templating import TemplateRenderError
        config = self.service_config if isinstance(self.service_config, dict) else {}
        request_config = config.get('request_config') or {}
        response_config = config.get('response_config') or {}
        if not isinstance(request_config, dict):
            request_config = {}
        if not isinstance(response_config, dict):
            response_config = {}

        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                # _execute_request logs and normalises this case; mirror it here.
                parameters = {}
        if not isinstance(parameters, dict):
            parameters = {}

        if request_config.get('no_request'):
            return self._no_request_result(parameters, context)

        try:
            result = await self._execute_request(parameters, context)
        except TemplateRenderError as e:
            logger.error(f"api_call request template failed: {e}")
            self._log_to_execution(context, "error", f"api_call failed: {e}", {})
            return self._mapping_error_result(str(e))

        return self._apply_response_templates(result, parameters, response_config, context)

    async def _execute_request(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config

        # Ensure parameters is a dictionary
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
                logger.info(f"Converted parameters from string to dict in ApiCallExecutor")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse parameters string in ApiCallExecutor: {parameters}")
                parameters = {}
        elif not isinstance(parameters, dict):
            logger.error(f"Parameters is not a dict in ApiCallExecutor: {type(parameters)}")
            parameters = {}
        
        # Additional safety check - ensure parameters is dict after conversion
        if not isinstance(parameters, dict):
            logger.error(f"Parameters still not a dict after conversion: {type(parameters)}, value: {parameters}")
            parameters = {}
        
        # Apply default values from parameter schema for required parameters only
        # User flow design choices should be respected - if a user removes an optional parameter,
        # we should NOT apply its default value automatically
        parameter_schema = config.get('parameter_schema', {})
        if parameter_schema and 'properties' in parameter_schema:
            schema_properties = parameter_schema['properties']
            required_params = parameter_schema.get('required', [])
            
            for param_name, param_config in schema_properties.items():
                # Only apply defaults for REQUIRED parameters that are missing or None
                if param_name in required_params and (param_name not in parameters or parameters[param_name] is None):
                    if 'default' in param_config:
                        parameters[param_name] = param_config['default']
                        logger.info(f"Applied default value for required parameter '{param_name}': {param_config['default']}")
                    else:
                        logger.warning(f"Required parameter '{param_name}' is missing and has no default value")
        
        # Log incoming parameters for debugging (with masking)
        logger.info(f"ApiCallExecutor received parameters: {mask_sensitive_data(parameters)}")
        logger.info(f"ApiCallExecutor config: {mask_sensitive_data(config)}")
        try:
            service_type = config.get('service_type') if isinstance(config, dict) else None
            request_config = config.get('request_config', {}) if isinstance(config, dict) else {}
            method = request_config.get('method') if isinstance(config, dict) else None
            logger.info(f"Service type: {service_type}, Method: {method}")
        except AttributeError as e:
            logger.error(f"AttributeError when accessing config: {e}")
            logger.error(f"Config type: {type(config)}, Config value: {config}")
            raise
        
        # Get endpoint template - check multiple possible locations
        # First ensure config is a dict
        if not isinstance(config, dict):
            logger.error(f"Service config is not a dict: {type(config)}, value: {config}")
            config = {}
        
        endpoint_template = config.get('endpoint_template') or config.get('webhook_url')
        if not endpoint_template:
            raise ValueError("No endpoint template provided in service configuration")
        
        # Build URL from template
        url = endpoint_template
        
        # First try explicit path_params
        # Ensure parameters is still a dict before calling .get()
        if not isinstance(parameters, dict):
            logger.error(f"Parameters became non-dict before path_params extraction: {type(parameters)}")
            parameters = {}
        path_params = parameters.get('path_params', {})
        
        # Then extract any parameters that appear in the URL template
        import re
        from services.jinja_templating import render_auth_placeholders, has_auth_placeholders
        _req_cfg_for_path = config.get('request_config', {}) or {}
        encode_path_params = bool(_req_cfg_for_path.get('encode_path_params')) if isinstance(_req_cfg_for_path, dict) else False

        def _path_value(value):
            # encode_path_params (opt-in): a SKU may contain '/' or spaces
            if encode_path_params:
                from urllib.parse import quote
                return quote(str(value), safe='')
            return str(value)

        url_params = re.findall(r'\{\{(\w+)\}\}', endpoint_template)
        for param_name in url_params:
            if param_name in parameters:
                url = url.replace(f"{{{{{param_name}}}}}", _path_value(parameters[param_name]))
            elif param_name in path_params:
                url = url.replace(f"{{{{{param_name}}}}}", _path_value(path_params[param_name]))

        # {{auth.<field>}} in the endpoint (e.g. a seller id held on the connection)
        if has_auth_placeholders(url):
            url = render_auth_placeholders(url, self.auth_credentials,
                                           f"endpoint_template of service '{config.get('service_name', '')}'",
                                           encode=encode_path_params)

        # Prepend base URL if available and endpoint is not already a full URL
        base_url = config.get('base_url', '') or ''

        # {{auth.<field>}} in the application's base_url (per-connection hosts, e.g.
        # https://{{auth.shop_domain}}/admin/api/2026-07 or {{auth.endpoint}})
        if has_auth_placeholders(base_url):
            base_url = render_auth_placeholders(base_url, self.auth_credentials,
                                                "the application's base_url")
            logger.info(f"Rendered per-connection base_url: {base_url}")

        if base_url and not url.startswith(('http://', 'https://')):
            # Ensure proper URL joining
            if not base_url.endswith('/') and not url.startswith('/'):
                base_url += '/'
            elif base_url.endswith('/') and url.startswith('/'):
                base_url = base_url[:-1]
            url = base_url + url
        
        # Check if this is an internal flow call from a published application
        is_internal_flow_call = (
            config.get('flow_based', False) and  # This is a flow-based service
            '/api/v1/flows/' in url and  # Calling a flow endpoint
            (url.endswith('/execute') or url.endswith('/execute-internal-sync')) and  # Flow execution endpoint
            ('localhost' in url or '127.0.0.1' in url)  # Internal call
        )
        
        if is_internal_flow_call:
            logger.info(f"Detected internal flow call from published application: {url}")
            logger.info("Preparing user context headers for internal flow execution")
        
        # Prepare headers - start with auth headers first (unless internal flow call)
        headers = {}
        
        # Add auth headers if needed (including subscription-level custom headers)
        # Skip authentication for internal flow calls
        if self.auth_credentials and not is_internal_flow_call:
            logger.info(f"Auth credentials provided. Keys: {list(self.auth_credentials.keys())}")
            logger.info(f"Auth credentials details: headers={list(self.auth_credentials.get('headers', {}).keys())}, query_params={list(self.auth_credentials.get('query_params', {}).keys())}, body_params={list(self.auth_credentials.get('body_params', {}).keys())}")
            # Log if login_response is available
            if 'login_response' in self.auth_credentials:
                logger.info(f"Login response available with keys: {list(self.auth_credentials['login_response'].keys()) if isinstance(self.auth_credentials['login_response'], dict) else 'Not a dict'}")
            # Ensure token is valid if applicable (skip for Basic auth and API key auth)
            try:
                # Check if this is Basic auth (has app_password or password field without tokens)
                is_basic_auth = ('app_password' in self.auth_credentials or 
                                ('password' in self.auth_credentials and 'access_token' not in self.auth_credentials))
                
                # Check if this is API key auth
                is_api_key_auth = 'api_key' in self.auth_credentials
                
                # Only validate/refresh tokens for OAuth2 and token exchange auth
                if not is_basic_auth and not is_api_key_auth:
                    await self._ensure_valid_oauth2_token()
                    await self._ensure_valid_token_exchange(context=context)
                else:
                    logger.debug(f"Skipping token validation for auth type: {'Basic' if is_basic_auth else 'API Key'}")
            except Exception as auth_error:
                logger.error(f"Authentication token validation failed: {str(auth_error)}", exc_info=True)
                # Re-raise with more context
                raise Exception(f"Failed to validate/refresh authentication token: {str(auth_error)}") from auth_error
            
            auth_headers = self._build_auth_headers()
            logger.info(f"Built auth headers: {mask_sensitive_data(auth_headers)}")
            headers.update(auth_headers)
        
        # Check for service-level headers (from request_config or top-level)
        # Skip authentication headers for internal flow calls
        request_config = config.get('request_config', {})
        
        # First, add direct headers from request_config if present
        if request_config.get('headers') and not is_internal_flow_call:
            logger.info(f"Adding direct headers from request_config: {mask_sensitive_data(request_config['headers'])}")
            headers.update(request_config['headers'])
        
        # Then process headers_template if present (these can override the direct headers)
        headers_template = request_config.get('headers_template') or config.get('headers_template')
            
        if headers_template and not is_internal_flow_call:
            logger.info(f"Processing service-level headers_template: {headers_template}")
            # Create context for template processing that includes auth
            template_context = dict(parameters)
            if self.auth_credentials:
                template_context['auth'] = self.auth_credentials
                # Debug logging for auth credentials structure
                if 'login_response' in self.auth_credentials:
                    logger.info(f"Auth has login_response: Yes")
                    login_resp = self.auth_credentials.get('login_response', {})
                    if isinstance(login_resp, dict) and 'data' in login_resp:
                        logger.info(f"login_response has data: Yes")
                        if 'associatedOrgs' in login_resp.get('data', {}):
                            orgs = login_resp['data']['associatedOrgs']
                            logger.info(f"Number of associatedOrgs: {len(orgs) if isinstance(orgs, list) else 'Not a list'}")
                            if isinstance(orgs, list) and len(orgs) > 0:
                                org = orgs[0]
                                if isinstance(org, dict) and 'organisation' in org:
                                    org_id = org.get('organisation', {}).get('id')
                                    logger.info(f"First org ID found: {org_id}")
                else:
                    logger.warning("Auth credentials do not have login_response")
            
            logger.info(f"Template context keys: {list(template_context.keys())}")
            service_headers = self._process_template_dict(headers_template, template_context)
            logger.info(f"Service headers after template processing: {mask_sensitive_data(service_headers)}")
            # Service-level headers override subscription-level headers
            headers.update(service_headers)
            # Log specific headers for debugging
            for key, value in service_headers.items():
                if key == "X-ATLAS-ORG-ID":
                    logger.info(f"X-ATLAS-ORG-ID header value: {value}")
        
        # Prepare request
        # Get method from request_config
        request_config = config.get('request_config', {})
        method = request_config.get('method', 'GET')
        
        request_kwargs = {
            'method': method,
            'url': url,
            'headers': headers,
            'timeout': config.get('timeout_seconds', 30)
        }
        
        # Add query params
        # Ensure parameters is still a dict
        if not isinstance(parameters, dict):
            logger.error(f"Parameters is not a dict when getting query_params: {type(parameters)}")
            parameters = {}
        query_params = parameters.get('query_params', {})
        
        # Process query_params_template from request_config
        request_config = config.get('request_config', {})
        if request_config.get('query_params_template'):
            logger.debug(f"Processing query_params_template from request_config: {request_config['query_params_template']}")
            template_params = self._process_template_dict(request_config['query_params_template'], parameters)
            query_params.update(template_params)

        # query_jinja: a Jinja template rendering a JSON object of query parameters,
        # merged over query_params_template; None / "" values are dropped.
        query_jinja = request_config.get('query_jinja')
        if isinstance(query_jinja, str) and query_jinja.strip():
            from services.jinja_templating import render_json, TemplateRenderError
            rendered_query = render_json(query_jinja, self._request_template_context(parameters),
                                         'request_config.query_jinja')
            if rendered_query is not None and not isinstance(rendered_query, dict):
                raise TemplateRenderError(
                    f"request_config.query_jinja must render a JSON object, got {type(rendered_query).__name__}")
            if not isinstance(query_params, dict):
                query_params = {}
            for q_key, q_value in (rendered_query or {}).items():
                if q_value is None or (isinstance(q_value, str) and q_value == ''):
                    query_params.pop(q_key, None)
                    continue
                if isinstance(q_value, list):
                    q_value = [v for v in q_value if v is not None and v != '']
                    if not q_value:
                        query_params.pop(q_key, None)
                        continue
                query_params[q_key] = q_value
            logger.info(f"query_jinja produced query params: {list((rendered_query or {}).keys())}")

        # Add auth query parameters if configured
        if self.auth_credentials and 'query_params' in self.auth_credentials:
            query_params.update(self.auth_credentials['query_params'])
        
        # Filter out query parameters that still contain template placeholders
        filtered_query_params = {}
        for key, value in query_params.items():
            if isinstance(value, str) and '{{' in value and '}}' in value:
                # Skip parameters that still have unresolved template placeholders
                logger.debug(f"Skipping query param '{key}' with unresolved template: {value}")
                continue
            filtered_query_params[key] = value
        
        # Convert query parameters to correct types based on schema
        parameter_schema = config.get('parameter_schema')
        if parameter_schema and filtered_query_params:
            filtered_query_params = self._convert_param_types(filtered_query_params, parameter_schema)

        # query_list_format: "csv" joins list values with commas (e.g. SP-API
        # MarketplaceIds=A,B); default keeps lists as repeated params.
        if request_config.get('query_list_format') == 'csv':
            for q_key, q_value in list(filtered_query_params.items()):
                if isinstance(q_value, (list, tuple)):
                    filtered_query_params[q_key] = ','.join(str(v) for v in q_value)

        if filtered_query_params:
            request_kwargs['params'] = filtered_query_params
        
        # Initialize body_data to None for all requests to avoid UnboundLocalError
        body_data = None

        # body_jinja: a Jinja template rendering the JSON body. When present it takes
        # precedence over body_template and the legacy body logic (loops, dynamic
        # keys, arrays). Empty render => no body.
        body_jinja = request_config.get('body_jinja')
        use_body_jinja = isinstance(body_jinja, str) and body_jinja.strip() != ''
        if use_body_jinja:
            from services.jinja_templating import render_json
            body_data = render_json(body_jinja, self._request_template_context(parameters),
                                    'request_config.body_jinja')
            if body_data is None:
                logger.info("body_jinja rendered empty; sending no request body")
            else:
                if (isinstance(body_data, dict) and self.auth_credentials
                        and isinstance(self.auth_credentials.get('body_params'), dict)):
                    body_data.update(self.auth_credentials['body_params'])
                request_kwargs['json'] = body_data
                if 'Content-Type' not in headers:
                    headers['Content-Type'] = 'application/json'
                request_kwargs['headers'] = headers
                logger.info(f"Sending body_jinja JSON body: {mask_sensitive_data(body_data) if isinstance(body_data, dict) else type(body_data).__name__}")

        # Add body for POST/PUT/PATCH requests
        if method in ['POST', 'PUT', 'PATCH'] and not use_body_jinja:
            # If body_template is defined, use ONLY the fields specified in it
            request_config = config.get('request_config', {})
            if request_config.get('body_template'):
                logger.debug(f"Processing body template from request_config: {request_config['body_template']}")
                body_data = self._process_template_dict(request_config['body_template'], parameters)
                # Convert parameters to correct types based on schema
                parameter_schema = config.get('parameter_schema')
                if parameter_schema:
                    body_data = self._convert_param_types(body_data, parameter_schema)
                # Don't add any other parameters - body_template defines exactly what goes in the body
            else:
                # No body_template, so use the old logic
                # Ensure parameters is still a dict before checking for 'body'
                if not isinstance(parameters, dict):
                    logger.error(f"Parameters is not a dict when checking for body: {type(parameters)}")
                    parameters = {}
                
                # Check if parameters has explicit body key
                if 'body' in parameters:
                    body_data = parameters.get('body', {})
                    logger.debug(f"Using explicit body from parameters: {mask_sensitive_data(body_data)}")
                else:
                    # If no explicit body key, check if all parameters should be the body
                    # This happens when parameters is already the intended body structure
                    # Exclude special keys and URL template parameters
                    exclude_keys = ['path_params', 'query_params', 'headers'] + url_params
                    
                    # Also exclude parameters that are in query_params_template
                    request_config = config.get('request_config', {})
                    if request_config.get('query_params_template'):
                        exclude_keys.extend(list(request_config['query_params_template'].keys()))
                    non_special_keys = [k for k in parameters.keys() if k not in exclude_keys]
                    if non_special_keys:
                        # Use all non-special parameters as body
                        body_data = {k: v for k, v in parameters.items() if k not in exclude_keys}
                        logger.debug(f"Using non-special parameters as body: {mask_sensitive_data(body_data)}")
                    else:
                        body_data = {}
                        logger.debug("No body data found in parameters")
                
                # Clean up body_data - remove any undefined or null keys
                cleaned_body = {}
                for key, value in body_data.items():
                    if key not in ['undefined', 'null', None] and value is not None:
                        cleaned_body[key] = value
                body_data = cleaned_body
            
            # Add auth body parameters if configured
            if self.auth_credentials and 'body_params' in self.auth_credentials:
                body_data.update(self.auth_credentials['body_params'])
            
            # Filter out body parameters that still contain template placeholders
            filtered_body_data = {}
            for key, value in body_data.items():
                if isinstance(value, str) and '{{' in value and '}}' in value:
                    # Skip parameters that still have unresolved template placeholders
                    logger.debug(f"Skipping body param '{key}' with unresolved template: {value}")
                    continue
                filtered_body_data[key] = value
            body_data = filtered_body_data
            
            logger.info(f"API call final body data: {mask_sensitive_data(body_data)}")
            
            # Check if we should send JSON (most APIs expect JSON nowadays)
            # Get the parameter method first
            parameter_method = request_config.get('parameter_method')
            
            # Debug logging for parameter method and headers
            logger.info(f"Parameter method: {parameter_method}, Headers before decision: {redact_secrets(headers)}")
            
            # Send JSON if:
            # 1. parameter_method is 'json_payload' (explicit)
            # 2. parameter_method is 'hybrid' (URL params + JSON body)
            # 3. parameter_method is 'body' AND Content-Type is 'application/json'
            # 4. parameter_method is 'graphql' (GraphQL always uses JSON)
            # 5. parameter_method is not set AND Content-Type header is 'application/json'
            # 6. parameter_method is not set AND response_type is 'json'
            # But NOT if parameter_method is explicitly set to something else (form_data, xml_payload, etc.)
            if parameter_method in ['json_payload', 'hybrid', 'graphql']:
                # Both json_payload and hybrid send JSON body
                # hybrid = URL/path parameters + JSON body (commonly used by Google APIs)
                # graphql always sends JSON
                send_as_json = True
            elif parameter_method in ['body', 'none', None]:
                # For 'body' or 'none' parameter method, check Content-Type header
                # 'none' means no special parameter handling, use headers to determine
                send_as_json = headers.get('Content-Type') == 'application/json'
            elif parameter_method in ['form_data', 'xml_payload', 'wordpress_binary', 'multipart', 'multipart_form', 'multipart_related']:
                # Explicitly NOT JSON for these methods
                send_as_json = False
            else:
                # No explicit parameter_method, use other indicators
                # First check headers (from request_config), then response_type
                send_as_json = (
                    headers.get('Content-Type') == 'application/json' or
                    config.get('response_type') == 'json'
                )
            
            logger.info(f"Send as JSON decision: {send_as_json} (parameter_method={parameter_method}, Content-Type={headers.get('Content-Type')})")
            
            if parameter_method == 'wordpress_binary':
                logger.info(f"Preparing WordPress binary upload")
                
                # For WordPress binary uploads, send the raw file data as the body
                # The file parameter should contain base64 encoded content
                file_content = parameters.get('file', '')
                
                if file_content:
                    try:
                        import base64
                        # Decode base64 content to binary
                        if file_content.startswith('data:'):
                            # Remove data URL prefix if present
                            file_content = file_content.split(',', 1)[1]
                        file_data = base64.b64decode(file_content)
                        
                        # Set the raw binary data as the request body
                        request_kwargs['content'] = file_data
                        
                        # The Content-Type and Content-Disposition headers are already set via headers_template
                        # Just ensure they're in the request
                        request_kwargs['headers'] = headers
                        
                        logger.info(f"WordPress binary upload prepared: {len(file_data)} bytes")
                        
                    except Exception as e:
                        logger.error(f"Failed to prepare WordPress binary upload: {e}")
                        raise ValueError(f"Failed to decode file content for WordPress upload: {str(e)}")
                else:
                    raise ValueError("No file content provided for WordPress binary upload")
                    
            elif parameter_method and parameter_method.startswith('multipart'):
                logger.info(f"Preparing multipart request with body: {mask_sensitive_data(body_data)}")
                logger.info(f"Parameters passed: {list(parameters.keys())}")
                logger.info(f"Body_data keys: {list(body_data.keys())}")
                
                # Determine multipart type based on parameter_method
                # multipart or multipart_form -> multipart/form-data (standard)
                # multipart_related -> multipart/related (Google Drive style)
                if parameter_method == 'multipart_related':
                    multipart_type = 'multipart/related'
                    is_multipart_related = True
                else:
                    # Default to multipart/form-data for 'multipart' or 'multipart_form'
                    multipart_type = 'multipart/form-data'
                    is_multipart_related = False
                
                logger.info(f"Using multipart type: {multipart_type} (from parameter_method: {parameter_method})")
                
                # Extract file content if present
                # Check for file content in both body_data and parameters
                # Google Drive uses 'content' in parameters, while Google Gemini uses 'file' in body_data
                # Locate the file payload and remember which field carried it so that
                # multipart/form-data uploads can label the file part with the correct name.
                file_content = None
                file_field_name = 'file'
                for _src in (body_data, parameters):
                    if not isinstance(_src, dict):
                        continue
                    for _key in ('content', 'file'):
                        if _src.get(_key):
                            file_content = _src.get(_key)
                            file_field_name = _key
                            break
                    if file_content:
                        break
                file_data = b''
                file_mime_type = 'application/octet-stream'  # Default MIME type
                file_filename = None  # Desired filename for the multipart file part

                logger.info(f"Looking for file content. In body_data - content: {bool(body_data.get('content'))}, file: {bool(body_data.get('file'))}. In parameters - content: {bool(parameters.get('content'))}, file: {bool(parameters.get('file'))}")
                logger.info(f"File content type: {type(file_content) if file_content else 'None'}")
                
                if file_content:
                    if isinstance(file_content, dict) and 'data' in file_content:
                        # Handle content as file object with 'data' field
                        actual_data = file_content.get('data', '')
                        # Extract MIME type from file object if available
                        if 'type' in file_content:
                            file_mime_type = file_content.get('type', 'application/octet-stream')
                        # Extract a filename for the multipart file part if provided
                        file_filename = file_content.get('name') or file_content.get('filename') or file_filename
                        if actual_data.startswith('data:'):
                            # Extract MIME type from data URL if present
                            data_url_parts = actual_data.split(',', 1)
                            if len(data_url_parts) > 1:
                                mime_info = data_url_parts[0].replace('data:', '')
                                if ';' in mime_info:
                                    file_mime_type = mime_info.split(';')[0]
                            # Remove data URL prefix
                            actual_data = data_url_parts[1] if len(data_url_parts) > 1 else actual_data
                        try:
                            import base64
                            file_data = base64.b64decode(actual_data)
                        except Exception as e:
                            logger.warning(f"Failed to decode base64 content: {e}")
                            file_data = actual_data.encode('utf-8')
                    elif isinstance(file_content, str):
                        # Handle content as direct string
                        if file_content.startswith('data:'):
                            # Extract MIME type from data URL if present
                            data_url_parts = file_content.split(',', 1)
                            if len(data_url_parts) > 1:
                                mime_info = data_url_parts[0].replace('data:', '')
                                if ';' in mime_info:
                                    file_mime_type = mime_info.split(';')[0]
                            file_content = data_url_parts[1] if len(data_url_parts) > 1 else file_content
                        try:
                            import base64
                            file_data = base64.b64decode(file_content)
                        except Exception as e:
                            logger.warning(f"Failed to decode base64 content: {e}")
                            file_data = file_content.encode('utf-8')
                
                # Create multipart data
                import json
                import secrets
                
                boundary = f"boundary_{secrets.token_hex(8)}"
                
                # Prepare metadata (exclude content and file fields)
                # For multipart uploads, we need to consider both body_data and parameters
                # body_data contains fields from body_template, parameters contains all mapped params
                logger.info(f"body_data contains: {list(body_data.keys())}")
                logger.info(f"parameters contains: {list(parameters.keys()) if isinstance(parameters, dict) else 'not a dict'}")
                
                # Use body_data if it has content, otherwise merge parameters
                if body_data:
                    metadata = {k: v for k, v in body_data.items() if k not in ['content', 'file'] and v is not None}
                else:
                    # If no body_data, use parameters but exclude content/file
                    metadata = {k: v for k, v in parameters.items() if k not in ['content', 'file'] and v is not None}
                # Filter out template placeholders
                clean_metadata = {}
                for k, v in metadata.items():
                    if isinstance(v, str) and '{{' in v and '}}' in v:
                        logger.debug(f"Skipping metadata field '{k}' with unresolved template: {v}")
                        continue
                    clean_metadata[k] = v
                
                # For multipart/related uploads with displayName, wrap it properly
                # Some APIs like Google Gemini expect {"file": {"displayName": "..."}}
                if is_multipart_related and 'displayName' in clean_metadata:
                    # Create the proper structure with file wrapper
                    display_name = clean_metadata.get('displayName')
                    clean_metadata = {}
                    if display_name:
                        clean_metadata = {'file': {'displayName': display_name}}
                
                metadata_json = json.dumps(clean_metadata, separators=(',', ':'))
                
                # Build multipart body with proper RFC 2046 formatting
                multipart_body = []
                
                logger.info(f"Building multipart body. Method: {parameter_method}, is_related: {is_multipart_related}")
                logger.info(f"Clean metadata to send: {clean_metadata}")
                
                # For standard multipart/form-data, send each field as a separate part.
                # multipart/related (handled in the else) sends a single JSON metadata part.
                if not is_multipart_related:
                    # Send each parameter as a separate form field
                    for field_name, field_value in clean_metadata.items():
                        multipart_body.append(f'--{boundary}')
                        multipart_body.append(f'Content-Disposition: form-data; name="{field_name}"')
                        multipart_body.append('')  # Empty line after headers
                        multipart_body.append(str(field_value))
                else:
                    # For multipart_related (Google Drive style), send as JSON metadata
                    multipart_body.append(f'--{boundary}')
                    multipart_body.append('Content-Type: application/json; charset=UTF-8')
                    multipart_body.append('')  # Empty line after headers
                    multipart_body.append(metadata_json)
                
                # Part 2: File data (if present)
                if file_data:
                    multipart_body.append(f'--{boundary}')
                    # multipart/form-data file parts must be named (and may carry a filename);
                    # multipart/related identifies parts positionally so it omits the disposition.
                    if not is_multipart_related:
                        _part_filename = file_filename or f'{file_field_name}'
                        multipart_body.append(
                            f'Content-Disposition: form-data; name="{file_field_name}"; filename="{_part_filename}"'
                        )
                    multipart_body.append(f'Content-Type: {file_mime_type}')
                    
                    # For multipart/related, send binary data directly
                    use_base64_text = False
                    
                    multipart_body.append('')  # Empty line after headers
                    
                    # Handle binary data for multipart requests
                    # Build text part first, then add binary, then closing boundary
                    text_part = '\r\n'.join(multipart_body) + '\r\n'
                    closing_boundary = f'\r\n--{boundary}--\r\n'
                    body_content = text_part.encode('utf-8') + file_data + closing_boundary.encode('utf-8')
                    logger.info(f"Using binary file content, length: {len(file_data)}, MIME: {file_mime_type}")
                else:
                    # No file data, just metadata parts
                    # Add closing boundary
                    multipart_body.append(f'--{boundary}--')
                    body_content = '\r\n'.join(multipart_body).encode('utf-8')
                    logger.info(f"Multipart body constructed ({len(body_content)} bytes)")
                    logger.info(f"First 500 characters: {body_content[:500]}")
                
                # Set multipart headers
                headers['Content-Type'] = f'{multipart_type}; boundary={boundary}'
                headers['Content-Length'] = str(len(body_content))
                
                request_kwargs['content'] = body_content
                request_kwargs['headers'] = headers
                
                logger.info(f"Multipart request prepared: {len(body_content)} bytes, boundary={boundary[:20]}...")
                logger.info(f"Multipart body preview (first 1000 chars): {body_content[:1000]}")
                
                # Count the parts in the body
                parts_count = body_content.count(f'--{boundary}'.encode()) - 1  # Exclude the closing boundary
                logger.info(f"Number of parts in multipart body: {parts_count}")
                
            elif send_as_json:
                logger.info(f"Sending JSON body: {mask_sensitive_data(body_data)}")
                request_kwargs['json'] = body_data
                # Ensure Content-Type is set for JSON
                if 'Content-Type' not in headers:
                    headers['Content-Type'] = 'application/json'
                request_kwargs['headers'] = headers
            else:
                logger.info(f"Sending form data: {mask_sensitive_data(body_data)}")
                # Only set Content-Type for form-encoded data if not already set
                # This respects headers from request_config
                if 'Content-Type' not in headers:
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'
                request_kwargs['headers'] = headers
                request_kwargs['data'] = body_data
        
        # Add user context headers for internal flow calls
        if is_internal_flow_call:
            # Keep essential headers and add user context
            context_headers = {}
            if 'Content-Type' in request_kwargs.get('headers', {}):
                context_headers['Content-Type'] = request_kwargs['headers']['Content-Type']
            else:
                context_headers['Content-Type'] = 'application/json'
            
            # Add user context headers from the execution context
            if context:
                if context.get('tenant_id'):
                    context_headers['X-Internal-Tenant-ID'] = context['tenant_id']
                if context.get('user_id'):
                    context_headers['X-Internal-User-ID'] = context['user_id']
                if context.get('execution_id'):
                    context_headers['X-Internal-Execution-ID'] = context['execution_id']
                    
                logger.info(f"Added user context headers: tenant_id={context.get('tenant_id')}, user_id={context.get('user_id')}")
            
            request_kwargs['headers'] = context_headers
            logger.info(f"Internal flow call: Added context headers: {mask_sensitive_data(context_headers)}")
        
        # Log the final request details
        logger.info(f"Making API request: {request_kwargs['method']} {request_kwargs['url']}")
        logger.info(f"Request headers: {mask_sensitive_data(request_kwargs.get('headers', {}))}")
        logger.info(f"Request params: {mask_sensitive_data(request_kwargs.get('params', {}))}")
        if 'json' in request_kwargs:
            logger.info(f"Request JSON body: {mask_sensitive_data(request_kwargs['json'])}")
        
        # Log detailed request to execution logs if we have access to execution context
        if context and 'execution_id' in context:
            from db.database import get_tenant_db
            from services.execution_engine import ExecutionEngine
            
            # Build the full URL with query params
            full_url = request_kwargs['url']
            if request_kwargs.get('params'):
                from urllib.parse import urlencode
                full_url += '?' + urlencode(request_kwargs['params'])
            
            request_log_data = {
                'type': 'http_request',
                'method': request_kwargs['method'],
                'url': full_url,
                'headers': mask_sensitive_data(request_kwargs.get('headers', {})),
                'query_params': request_kwargs.get('params', {}),
                'body': request_kwargs.get('json') or request_kwargs.get('data', {})
            }
            
            # Get tenant schema from context
            tenant_schema = context.get('tenant_schema', 'public')
            with get_tenant_db(tenant_schema) as db:
                # Import here to avoid circular imports
                from db.models import ExecutionLog
                import uuid
                from datetime import datetime
                
                # Use log callback if available, otherwise create log directly
                if context.get('log_callback'):
                    context['log_callback'](
                        context['execution_id'],
                        context.get('current_node_id'),
                        'info',
                        f'API Request: {request_kwargs["method"]} {request_kwargs["url"]}',
                        request_log_data
                    )
                else:
                    log_entry = ExecutionLog(
                        log_id=str(uuid.uuid4()),
                        execution_id=context['execution_id'],
                        step_id=context.get('current_node_id'),
                        timestamp=datetime.utcnow(),
                        level='info',
                        message=f'API Request: {request_kwargs["method"]} {request_kwargs["url"]}',
                        data=request_log_data
                    )
                    db.add(log_entry)
                    db.commit()
        
        # Check if this is a streaming request
        sync_mode = config.get('sync_mode', 'synchronous')
        
        # Make the request with retry
        async def make_request():
            logger.info(f"About to make HTTP request to: {request_kwargs.get('url', 'unknown')}")
            logger.info(f"Method: {request_kwargs.get('method', 'unknown')}, Headers count: {len(request_kwargs.get('headers', {}))}")
            async with httpx.AsyncClient(follow_redirects=True) as client:
                # For streaming mode, we need to handle the response differently
                if sync_mode == 'streaming':
                    # Add Accept header for SSE if not already present
                    if 'Accept' not in request_kwargs['headers']:
                        request_kwargs['headers']['Accept'] = 'text/event-stream'
                
                response = await client.request(**request_kwargs)
                # Don't raise for status here - we'll handle it based on response_config
                return response
        
        # Track timing
        import time
        start_time = time.time()

        try:
            response = await retry_async(make_request, config=NETWORK_RETRY_CONFIG)
            elapsed_time = time.time() - start_time
            
            # Parse response based on type or response_config
            response_config = config.get('response_config', {})
            logger.info(f"Response config from service_config: {response_config}")
            logger.info(f"Full service config keys: {list(config.keys())}")
            logger.info(f"Response status code: {response.status_code}")
            response_type = response_config.get('response_type') or config.get('response_type', 'json')
            
            # Handle streaming response
            if sync_mode == 'streaming':
                # For streaming, collect all events
                streaming_events = []
                try:
                    # Read the streaming response
                    content_type = response.headers.get('content-type', '')
                    if 'text/event-stream' in content_type:
                        # Parse SSE format
                        for line in response.text.split('\n'):
                            if line.startswith('data: '):
                                event_data = line[6:]  # Remove 'data: ' prefix
                                if event_data.strip():
                                    try:
                                        parsed_event = json.loads(event_data)
                                        streaming_events.append(parsed_event)
                                    except json.JSONDecodeError:
                                        # If not JSON, store as plain text
                                        streaming_events.append({'text': event_data})
                    else:
                        # Not SSE format, try to parse as JSON stream
                        response_data = response.json() if response.content else {}
                        streaming_events = [response_data]
                    
                    # Return streaming response with all events
                    result = {
                        'success': True,
                        'status_code': response.status_code,
                        'data': streaming_events,
                        'streaming': True,
                        'event_count': len(streaming_events),
                        'headers': dict(response.headers)
                    }
                    
                    self._log_to_execution(context, "info", f"Streaming response received with {len(streaming_events)} events", {
                        "event_count": len(streaming_events),
                        "status_code": response.status_code
                    })
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error processing streaming response: {e}")
                    # Fall back to regular response handling
                    response_type = 'json'
            
            if response_type == 'json':
                try:
                    # Check if response has content before trying to parse JSON
                    if response.content:
                        response_data = response.json()
                    else:
                        # Handle empty response body - return raw response as text
                        logger.warning(f"Empty response body for status {response.status_code}")
                        response_data = response.text or f"Empty response (HTTP {response.status_code})"
                except Exception as json_error:
                    # If JSON parsing fails, return the raw response text
                    logger.info(f"Response is not JSON, returning raw text: {json_error}")
                    response_data = response.text
                
                self._log_http_response(response, context, elapsed_time, response_data)
                
                # Check for 401 authentication error and retry with token refresh
                if response.status_code == 401 and self.auth_credentials and ('client_id' in self.auth_credentials or 'username' in self.auth_credentials):
                    logger.info("Received 401 error, attempting token refresh...")
                    try:
                        # Force token refresh
                        self.auth_credentials['expires_at'] = 0  # Force expired
                        
                        # Get database session for token refresh
                        from db.database import get_db
                        with next(get_db()) as db:
                            await self._ensure_valid_oauth2_token()
                            await self._ensure_valid_token_exchange(db=db, context=context)
                        
                        # Retry request with new token
                        auth_headers = self._build_auth_headers()
                        request_kwargs['headers'].update(auth_headers)
                        
                        logger.info(f"Retrying request with refreshed token")
                        self._log_to_execution(context, "info", "Token refreshed successfully, retrying request", {
                            "new_headers": mask_sensitive_data(auth_headers)
                        })
                        
                        response = await retry_async(make_request, config=NETWORK_RETRY_CONFIG)
                        elapsed_time = time.time() - start_time
                        
                        # Handle JSON parsing for retry response
                        try:
                            if response.content:
                                response_data = response.json()
                            else:
                                logger.warning(f"Empty response body in retry for status {response.status_code}")
                                response_data = response.text or f"Empty response (HTTP {response.status_code})"
                        except Exception as json_error:
                            logger.info(f"Retry response is not JSON, returning raw text: {json_error}")
                            response_data = response.text
                        
                        self._log_http_response(response, context, elapsed_time, response_data)
                        
                        logger.info(f"Retry response status: {response.status_code}")
                        # Continue processing the retry response
                    except Exception as retry_error:
                        logger.error(f"Token refresh failed: {str(retry_error)}", exc_info=True)
                        self._log_to_execution(context, "warning", "Token refresh failed, attempting fresh login", {
                            "error": str(retry_error)
                        })
                        
                        # Token refresh failed, try a fresh login
                        try:
                            logger.info("Attempting fresh login after token refresh failure")
                            
                            # Force a complete re-authentication by clearing token
                            self.auth_credentials['access_token'] = None
                            self.auth_credentials['expires_at'] = 0
                            
                            # Get database session for fresh login
                            from db.database import get_db
                            with next(get_db()) as db:
                                await self._ensure_valid_token_exchange(db=db, context=context)
                            
                            # Retry request with fresh token
                            auth_headers = self._build_auth_headers()
                            request_kwargs['headers'].update(auth_headers)
                            
                            logger.info(f"Retrying request with fresh token after login")
                            self._log_to_execution(context, "info", "Fresh login successful, retrying request", {
                                "new_headers": mask_sensitive_data(auth_headers)
                            })
                            
                            response = await make_request()
                            elapsed_time = time.time() - start_time
                            
                            # Handle JSON parsing for fresh token retry
                            try:
                                if response.content:
                                    response_data = response.json()
                                else:
                                    logger.warning(f"Empty response body in fresh token retry for status {response.status_code}")
                                    response_data = response.text or f"Empty response (HTTP {response.status_code})"
                            except Exception as json_error:
                                logger.info(f"Fresh token retry response is not JSON, returning raw text: {json_error}")
                                response_data = response.text
                            
                            self._log_http_response(response, context, elapsed_time, response_data)
                            
                            logger.info(f"Retry with fresh token - response status: {response.status_code}")
                            # Continue processing the retry response
                            
                        except Exception as login_error:
                            logger.error(f"Fresh login also failed: {str(login_error)}", exc_info=True)
                            # Return the original 401 error
                            error_msg = self._extract_error_message(response_data, config.get('response_config', {}).get('error_extraction', {}))
                            result = {
                                'error': True,
                                'status_code': 401,
                                'message': error_msg or 'Authentication failed - unable to refresh or recreate token',
                                'response': response_data,
                                'data': response_data,
                                'status': 401,
                                'headers': dict(response.headers),
                                'success': False,
                                'auth_error': True,
                                'refresh_attempted': True,
                                'login_attempted': True
                            }
                            self._log_to_execution(context, "error", f"api_call failed after all auth attempts: {result['message']}", {
                                "result": result,
                                "parameters": parameters,
                                "refresh_error": str(retry_error),
                                "login_error": str(login_error),
                                "request": {
                                    "method": method,
                                    "url": url,
                                    "headers": mask_sensitive_data(headers),
                                    "body": mask_sensitive_data(body_data) if body_data else None
                                }
                            })
                            return result
                
                # Check for API-level success/errors using response_config
                if response_config:
                    validation_result = self._validate_response(response_data, response_config, response.status_code)
                    if validation_result.get('error'):
                        # Log the validation error details with request information
                        self._log_to_execution(context, "error", f"api_call failed: {validation_result.get('message', 'Validation failed')}", {
                            "result": validation_result,
                            "parameters": parameters,
                            "request": {
                                "method": method,
                                "url": url,
                                "headers": mask_sensitive_data(headers),
                                "body": mask_sensitive_data(body_data) if body_data else None
                            }
                        })
                        return validation_result
                
                # Check if this is an error response based on status code
                # First check if success_status_codes is defined in request_config
                request_config = config.get('request_config', {})
                success_status_codes = request_config.get('success_status_codes')
                
                # Determine if the response should be treated as an error
                should_treat_as_error = False
                if success_status_codes:
                    # Custom success status codes defined in request_config
                    if isinstance(success_status_codes, list):
                        should_treat_as_error = response.status_code not in success_status_codes
                    else:
                        should_treat_as_error = response.status_code != success_status_codes
                elif not response_config and not response.is_success:
                    # No custom status codes and no response_config, use default behavior
                    should_treat_as_error = True
                
                if should_treat_as_error:
                    # API returned an error status code
                    error_msg = self._extract_error_message(response_data, config.get('response_config', {}).get('error_extraction', {}))
                    result = {
                        'error': True,
                        'status_code': response.status_code,
                        'message': error_msg or f"API request failed with status {response.status_code}",
                        'response': response_data,
                        'data': response_data,
                        'status': response.status_code,
                        'headers': dict(response.headers),
                        'success': False
                    }
                    # Log the error details with request information
                    self._log_to_execution(context, "error", f"api_call failed: {result['message']}", {
                        "result": result,
                        "parameters": parameters,
                        "request": {
                            "method": method,
                            "url": url,
                            "headers": mask_sensitive_data(headers),
                            "body": mask_sensitive_data(body_data) if body_data else None
                        }
                    })
                    return result
                
                # Return successful response with metadata for use in conditions
                # Determine if this is successful based on response_config or request_config
                is_success = response.is_success
                
                # First check response_config for success_check
                if response_config:
                    success_check = response_config.get('success_check', {})
                    if success_check.get('type') == 'status_code':
                        success_status_codes = success_check.get('success_status_codes') or success_check.get('value')
                        if success_status_codes:
                            # Handle both list and single value formats
                            if isinstance(success_status_codes, (list, tuple)):
                                success_codes = success_status_codes
                            else:
                                success_codes = [success_status_codes]
                            
                            if response.status_code in success_codes:
                                is_success = True
                
                # Also check request_config for success_status_codes
                request_config = config.get('request_config', {})
                if request_config.get('success_status_codes'):
                    success_status_codes = request_config['success_status_codes']
                    if isinstance(success_status_codes, list):
                        is_success = response.status_code in success_status_codes
                    else:
                        is_success = response.status_code == success_status_codes
                
                return {
                    'data': response_data,
                    'status': response.status_code,
                    'headers': dict(response.headers),
                    'success': is_success
                }
            elif response_type == 'xml':
                # You might want to add XML parsing here
                response_data = {'body': response.text, 'content_type': 'xml'}
                self._log_http_response(response, context, elapsed_time, response.text)
                
                # Check if this is an error response
                if not response.is_success:
                    return {
                        'error': True,
                        'status_code': response.status_code,
                        'message': f"API request failed with status {response.status_code}",
                        'response': response_data,
                        'data': response_data,
                        'status': response.status_code,
                        'headers': dict(response.headers),
                        'success': False
                    }
                
                return {
                    'data': response_data,
                    'status': response.status_code,
                    'headers': dict(response.headers),
                    'success': response.is_success
                }
            elif response_type in ('binary', 'base64'):
                content_type = response.headers.get('content-type', 'application/octet-stream').split(';')[0].strip()
                if not response.is_success:
                    error_text = response.text
                    self._log_http_response(response, context, elapsed_time, error_text)
                    return {
                        'error': True,
                        'status_code': response.status_code,
                        'message': f"API request failed with status {response.status_code}",
                        'response': error_text,
                        'data': error_text,
                        'status': response.status_code,
                        'headers': dict(response.headers),
                        'success': False
                    }
                import base64 as _b64
                encoded = _b64.b64encode(response.content).decode('ascii')
                self._log_http_response(response, context, elapsed_time, f"<binary {len(response.content)} bytes, base64 {len(encoded)} chars, type={content_type}>")
                return {
                    'data': encoded,
                    'content_type': content_type,
                    'encoding': 'base64',
                    'size': len(response.content),
                    'status': response.status_code,
                    'headers': dict(response.headers),
                    'success': True
                }
            else:
                response_data = {'body': response.text}
                self._log_http_response(response, context, elapsed_time, response.text)
                
                # Check if this is an error response
                if not response.is_success:
                    return {
                        'error': True,
                        'status_code': response.status_code,
                        'message': f"API request failed with status {response.status_code}",
                        'response': response_data,
                        'data': response_data,
                        'status': response.status_code,
                        'headers': dict(response.headers),
                        'success': False
                    }
                
                return {
                    'data': response_data,
                    'status': response.status_code,
                    'headers': dict(response.headers),
                    'success': response.is_success
                }
                
        except httpx.HTTPStatusError as e:
            elapsed_time = time.time() - start_time
            # Log error response
            self._log_http_response(e.response, context, elapsed_time, e.response.text)
            
            # Check for authentication errors
            if e.response.status_code == 401:
                logger.error(f"Authentication failed: {e.response.text}")
                # If OAuth2 or token exchange, try refreshing token once
                if self.auth_credentials and ('client_id' in self.auth_credentials or 'username' in self.auth_credentials):
                    logger.info("Attempting token refresh due to 401 error")
                    try:
                        # Force token refresh
                        self.auth_credentials['expires_at'] = 0  # Force expired
                        await self._ensure_valid_oauth2_token()
                        await self._ensure_valid_token_exchange(context=context)
                        
                        # Retry request with new token
                        auth_headers = self._build_auth_headers()
                        request_kwargs['headers'].update(auth_headers)
                        
                        response = await retry_async(make_request, config=NETWORK_RETRY_CONFIG)
                        elapsed_time = time.time() - start_time
                        
                        # Parse response based on type
                        if config.get('response_type') == 'json':
                            try:
                                if response.content:
                                    response_data = response.json()
                                else:
                                    logger.warning(f"Empty response body in auth retry for status {response.status_code}")
                                    response_data = response.text or f"Empty response (HTTP {response.status_code})"
                            except Exception as json_error:
                                logger.info(f"Auth retry response is not JSON, returning raw text: {json_error}")
                                response_data = response.text
                            
                            self._log_http_response(response, context, elapsed_time, response_data)
                            return response_data
                        elif config.get('response_type') == 'xml':
                            response_data = {'body': response.text, 'content_type': 'xml'}
                            self._log_http_response(response, context, elapsed_time, response.text)
                            return response_data
                        else:
                            response_data = {'body': response.text}
                            self._log_http_response(response, context, elapsed_time, response.text)
                            return response_data
                            
                    except Exception as retry_error:
                        logger.error(f"Token refresh failed: {str(retry_error)}", exc_info=True)
                
                return {
                    'error': True,
                    'status_code': 401,
                    'message': 'Authentication failed',
                    'auth_error': True
                }
            elif e.response.status_code == 403:
                logger.error(f"Authorization failed: {e.response.text}")
                return {
                    'error': True,
                    'status_code': 403,
                    'message': 'Authorization failed - check permissions',
                    'auth_error': True
                }
            elif 400 <= e.response.status_code < 500:
                # Try to parse JSON response for better error message
                try:
                    if e.response.content:
                        error_data = e.response.json()
                    else:
                        error_data = {"error": f"Empty response body (HTTP {e.response.status_code})"}
                    error_msg = self._extract_error_message(error_data, config.get('response_config', {}).get('error_extraction', {}))
                    logger.error(f"API call failed with client error {e.response.status_code}: {error_msg}")
                    self._log_to_execution(context, "error", f"api_call failed: {error_msg}", {
                        "result": {
                            'error': True,
                            'status_code': e.response.status_code,
                            'message': error_msg,
                            'response': error_data
                        },
                        "parameters": parameters,
                        "request": {
                            "method": method,
                            "url": url,
                            "headers": mask_sensitive_data(headers),
                            "body": mask_sensitive_data(body_data) if body_data else None
                        }
                    })
                except:
                    error_msg = e.response.text
                    logger.error(f"API call failed with client error {e.response.status_code}: {error_msg}")
                    self._log_to_execution(context, "error", f"api_call failed: {error_msg}", {
                        "result": {
                            'error': True,
                            'status_code': e.response.status_code,
                            'message': error_msg,
                            'response': error_msg
                        },
                        "parameters": parameters,
                        "request": {
                            "method": method,
                            "url": url,
                            "headers": mask_sensitive_data(headers),
                            "body": mask_sensitive_data(body_data) if body_data else None
                        }
                    })
            else:
                # Server error
                try:
                    if e.response.content:
                        error_data = e.response.json()
                    else:
                        error_data = {"error": f"Empty response body (HTTP {e.response.status_code})"}
                    error_msg = self._extract_error_message(error_data, config.get('response_config', {}).get('error_extraction', {}))
                    logger.error(f"API call failed with server error {e.response.status_code}: {error_msg}")
                    self._log_to_execution(context, "error", f"api_call failed: {error_msg}", {
                        "result": {
                            'error': True,
                            'status_code': e.response.status_code,
                            'message': error_msg,
                            'response': error_data
                        },
                        "parameters": parameters,
                        "request": {
                            "method": method,
                            "url": url,
                            "headers": mask_sensitive_data(headers),
                            "body": mask_sensitive_data(body_data) if body_data else None
                        }
                    })
                except:
                    error_msg = e.response.text
                    error_data = error_msg
                    logger.error(f"API call failed with server error {e.response.status_code}: {error_msg}")
                    self._log_to_execution(context, "error", f"api_call failed: {error_msg}", {
                        "result": {
                            'error': True,
                            'status_code': e.response.status_code,
                            'message': error_msg,
                            'response': error_msg
                        },
                        "parameters": parameters,
                        "request": {
                            "method": method,
                            "url": url,
                            "headers": mask_sensitive_data(headers),
                            "body": mask_sensitive_data(body_data) if body_data else None
                        }
                    })
            
            return {
                'error': True,
                'status_code': e.response.status_code,
                'message': error_msg if 'error_msg' in locals() else e.response.text,
                'response': error_data if 'error_data' in locals() else e.response.text
            }
        except Exception as e:
            logger.error(f"API call failed: {str(e)}", exc_info=True)
            
            # Check if this was an authentication error
            auth_error = False
            error_message = str(e)
            
            if "authentication" in error_message.lower() or "token" in error_message.lower():
                auth_error = True
            
            return {
                'error': True,
                'message': error_message,
                'error_type': type(e).__name__,
                'auth_error': auth_error
            }
    
    def _resolve_template_path(self, path: str, context: Dict[str, Any]) -> Any:
        """
        Resolve a template path like 'auth.login_response.data.associatedOrgs[0].organisation.id'
        Supports both dot notation and array indexing
        Also handles input.* paths which map to flow trigger variables
        """
        import re
        
        logger.debug(f"Resolving template path: {path}")
        logger.debug(f"Context keys available: {list(context.keys())}")
        
        # Handle input.* paths specially - these map to trigger variables
        if path.startswith('input.'):
            input_var = path[6:]  # Remove 'input.' prefix
            logger.debug(f"Resolving input variable: {input_var}")
            
            # First check if the variable was extracted by the execution engine
            # These should be in the context as direct variables
            if input_var in context:
                logger.debug(f"Found input.{input_var} directly in context variables")
                return context[input_var]
            else:
                logger.debug(f"Input variable {input_var} not found in context variables")
                logger.debug(f"Available context keys: {list(context.keys())}")
                return None
        
        # Start with the context
        current = context
        
        # Split the path into segments
        # Replace array notation with dot notation for easier parsing
        # e.g., "data.associatedOrgs[0].organisation" -> ["data", "associatedOrgs", "[0]", "organisation"]
        segments = re.split(r'\.|\[|\]', path)
        segments = [s for s in segments if s]  # Remove empty strings
        
        logger.debug(f"Path segments: {segments}")
        
        # Navigate through the path
        for i, segment in enumerate(segments):
            if current is None:
                logger.debug(f"Current is None at segment {i}: {segment}")
                return None
                
            # Check if segment is a number (array index)
            if segment.isdigit():
                index = int(segment)
                if isinstance(current, list) and 0 <= index < len(current):
                    current = current[index]
                    logger.debug(f"Accessed array index [{index}], current type: {type(current).__name__}")
                else:
                    logger.debug(f"Failed to access array index [{index}], current type: {type(current).__name__}")
                    return None
            else:
                # Object key
                if isinstance(current, dict) and segment in current:
                    current = current[segment]
                    logger.debug(f"Accessed key '{segment}', current type: {type(current).__name__}")
                else:
                    logger.debug(f"Failed to access key '{segment}', current type: {type(current).__name__}, available keys: {list(current.keys()) if isinstance(current, dict) else 'Not a dict'}")
                    return None
        
        logger.debug(f"Successfully resolved path '{path}' to: {current}")
        return current
    
    def _process_template_dict(self, template_dict: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process a dictionary with template strings"""
        result = {}
        
        # Create a combined context that includes both parameters and auth
        template_context = dict(parameters)
        if self.auth_credentials:
            template_context['auth'] = self.auth_credentials
        
        logger.info(f"Template context keys: {list(template_context.keys())}")
        
        for key, value in template_dict.items():
            if isinstance(value, str):
                # Check if the value is a single template variable (e.g., "{{values}}")
                if value.strip().startswith("{{") and value.strip().endswith("}}") and value.count("{{") == 1:
                    # Extract the variable name
                    var_name = value.strip()[2:-2].strip()
                    
                    # Use the enhanced path resolution
                    logger.info(f"Attempting to resolve template variable: {{{{{{var_name}}}}}}")
                    resolved_value = self._resolve_template_path(var_name, template_context)
                    logger.info(f"Resolved '{var_name}' to: {resolved_value}")
                    if resolved_value is not None:
                        # If the resolved value is a string that contains template variables, process them
                        if isinstance(resolved_value, str) and '{{' in resolved_value and '}}' in resolved_value:
                            # Process nested templates
                            import re
                            def replace_nested_template(match):
                                nested_var_path = match.group(1).strip()
                                nested_resolved = self._resolve_template_path(nested_var_path, template_context)
                                if nested_resolved is not None:
                                    # Check if we're already inside a JSON context (array or object)
                                    # by looking at the parent string structure
                                    if isinstance(nested_resolved, str):
                                        # If the resolved value is already properly formatted (has quotes)
                                        # or if we're in a JSON array/object context, use json.dumps
                                        # to properly escape the string
                                        return json.dumps(nested_resolved)
                                    else:
                                        # For non-strings, convert to JSON representation
                                        return json.dumps(nested_resolved)
                                return match.group(0)
                            
                            processed_value = re.sub(r'\{\{([^}]+)\}\}', replace_nested_template, resolved_value)
                            
                            logger.debug(f"Processed template value for key '{key}': {processed_value}")
                            # Try to parse as JSON if it looks like JSON
                            if processed_value.strip().startswith('[') or processed_value.strip().startswith('{'):
                                try:
                                    parsed_value = json.loads(processed_value)
                                    result[key] = parsed_value
                                    logger.debug(f"Successfully parsed as JSON for key '{key}': {parsed_value}")
                                except json.JSONDecodeError as e:
                                    logger.debug(f"Failed to parse as JSON for key '{key}', error: {e}")
                                    logger.debug(f"Raw value: {repr(processed_value)}")
                                    result[key] = processed_value
                            else:
                                result[key] = processed_value
                        else:
                            result[key] = resolved_value
                    else:
                        # Template variable not found - skip adding to result to avoid sending null/empty parameters
                        logger.debug(f"Template variable '{var_name}' not found, skipping parameter '{key}'")
                else:
                    # Multiple variables or mixed content - do string replacement
                    # Use regex to find all template variables
                    import re
                    def replace_template(match):
                        var_path = match.group(1).strip()
                        resolved = self._resolve_template_path(var_path, template_context)
                        if resolved is not None:
                            # Check if we're inside a JSON array/object based on context
                            # Look for surrounding brackets or braces
                            full_text = value
                            match_start = match.start()
                            match_end = match.end()
                            
                            # Simple heuristic: if we're inside [] or {}, format as JSON
                            before = full_text[:match_start]
                            after = full_text[match_end:]
                            
                            # Count unclosed brackets/braces before the match
                            open_brackets = before.count('[') - before.count(']')
                            open_braces = before.count('{') - before.count('}')
                            
                            if open_brackets > 0 or open_braces > 0:
                                # We're inside a JSON structure
                                if isinstance(resolved, str):
                                    return json.dumps(resolved)
                                else:
                                    return json.dumps(resolved)
                            else:
                                return str(resolved)
                        return match.group(0)
                    
                    processed_value = re.sub(r'\{\{([^}]+)\}\}', replace_template, value)
                    
                    # Include parameter if:
                    # 1. Template replacement occurred and no unresolved templates remain, OR
                    # 2. No templates were present (static field)
                    has_templates = '{{' in value and '}}' in value
                    templates_resolved = processed_value != value
                    no_unresolved_templates = not ('{{' in processed_value and '}}' in processed_value)
                    
                    if (templates_resolved and no_unresolved_templates) or not has_templates:
                        # After replacement, check if the result looks like JSON and parse it
                        if processed_value.strip().startswith('[') or processed_value.strip().startswith('{'):
                            try:
                                parsed = json.loads(processed_value)
                                result[key] = parsed
                                logger.debug(f"Successfully parsed processed value as JSON for key '{key}': {parsed}")
                            except json.JSONDecodeError:
                                logger.debug(f"Processed value looks like JSON but failed to parse for key '{key}': {processed_value}")
                                result[key] = processed_value
                        else:
                            result[key] = processed_value
                    else:
                        logger.debug(f"Skipping parameter '{key}' as template variables could not be resolved")
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                nested_result = self._process_template_dict(value, template_context)
                # Only add if the nested result is not empty
                if nested_result:
                    result[key] = nested_result
            elif isinstance(value, list):
                # Process each item in the list
                processed_list = []
                for item in value:
                    if isinstance(item, dict):
                        # Recursively process dictionaries in lists
                        processed_list.append(self._process_template_dict(item, template_context))
                    elif isinstance(item, str):
                        # Process string templates in lists
                        if item.strip().startswith("{{") and item.strip().endswith("}}") and item.count("{{") == 1:
                            var_name = item.strip()[2:-2].strip()
                            resolved_value = self._resolve_template_path(var_name, template_context)
                            if resolved_value is not None:
                                processed_list.append(resolved_value)
                            else:
                                processed_list.append(item)
                        else:
                            # Process multiple variables in string
                            import re
                            def replace_template(match):
                                var_path = match.group(1).strip()
                                resolved = self._resolve_template_path(var_path, template_context)
                                if resolved is not None:
                                    return str(resolved)
                                return match.group(0)
                            processed_value = re.sub(r'\{\{([^}]+)\}\}', replace_template, item)
                            processed_list.append(processed_value)
                    else:
                        processed_list.append(item)
                result[key] = processed_list
            else:
                result[key] = value
        return result


class WebhookExecutor(ServiceExecutor):
    """Executor for Webhook service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        # Ensure parameters is a dictionary  
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
                logger.info(f"Converted parameters from string to dict in WebhookExecutor")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse parameters string in WebhookExecutor: {parameters}")
                parameters = {}
        elif not isinstance(parameters, dict):
            logger.error(f"Parameters is not a dict in WebhookExecutor: {type(parameters)}")
            parameters = {}
        
        # Log the config for debugging
        logger.info(f"WebhookExecutor config: {mask_sensitive_data(config)}")
        logger.info(f"WebhookExecutor parameters: {mask_sensitive_data(parameters)}")
        
        # Log HTTP method being used
        # Get method from request_config
        request_config = config.get('request_config', {})
        http_method = request_config.get('method', 'POST')
        logger.info(f"WebhookExecutor will use HTTP method: {http_method}")
        
        # Get the webhook URL - check multiple possible locations
        webhook_url = config.get('webhook_url') or config.get('endpoint_template') or parameters.get('url')
        if not webhook_url:
            raise ValueError("No webhook URL provided in config or parameters")
        
        # Handle URL pattern parameters
        request_config = config.get('request_config', {})
        url_pattern = config.get('url_pattern', '')
        parameter_method = request_config.get('parameter_method', 'json_payload')
        
        # Process URL template if needed
        if '{' in webhook_url and '}' in webhook_url:
            for key, value in parameters.items():
                webhook_url = webhook_url.replace(f"{{{key}}}", str(value))
        
        # Apply URL pattern for query parameters
        if parameter_method == 'url_pattern' and url_pattern:
            # Process URL pattern template
            processed_pattern = url_pattern
            for key, value in parameters.items():
                processed_pattern = processed_pattern.replace(f"{{{{{key}}}}}", str(value))
            
            # Append to URL
            if '?' in webhook_url:
                webhook_url += '&' + processed_pattern.lstrip('?')
            else:
                webhook_url += processed_pattern if processed_pattern.startswith('?') else '?' + processed_pattern
        
        # Prepare webhook payload
        payload = parameters.get('payload', parameters)
        if parameters.get('metadata'):
            payload['metadata'] = parameters['metadata']
        
        # Prepare headers - start with auth headers first
        headers = {}
        
        # Add auth headers if needed (including subscription-level custom headers)
        if self.auth_credentials:
            logger.info(f"Auth credentials provided. Keys: {list(self.auth_credentials.keys())}")
            # Ensure token is valid if applicable (skip for Basic auth and API key auth)
            # Check if this is Basic auth (has app_password or password field without tokens)
            is_basic_auth = ('app_password' in self.auth_credentials or 
                            ('password' in self.auth_credentials and 'access_token' not in self.auth_credentials))
            
            # Check if this is API key auth
            is_api_key_auth = 'api_key' in self.auth_credentials
            
            # Only validate/refresh tokens for OAuth2 and token exchange auth
            if not is_basic_auth and not is_api_key_auth:
                await self._ensure_valid_oauth2_token()
                await self._ensure_valid_token_exchange(context=context)
            else:
                logger.debug(f"Skipping token validation for auth type: {'Basic' if is_basic_auth else 'API Key'}")
            
            auth_headers = self._build_auth_headers()
            logger.info(f"Built auth headers: {mask_sensitive_data(auth_headers)}")
            headers.update(auth_headers)
        
        # Check for service-level headers_template (from request_config or top-level)
        request_config = config.get('request_config', {})
        headers_template = request_config.get('headers_template') or config.get('headers_template')
        
        if headers_template:
            logger.info(f"Processing service-level headers_template for webhook")
            # Create context for template processing that includes auth
            template_context = dict(parameters)
            if self.auth_credentials:
                template_context['auth'] = self.auth_credentials
            
            service_headers = self._process_template_dict(headers_template, template_context)
            logger.info(f"Service headers after template processing: {mask_sensitive_data(service_headers)}")
            # Service-level headers override subscription-level headers
            headers.update(service_headers)
        
        # Add content type if not set
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
        
        # Add signature if configured
        if config.get('signature_method'):
            # Implement signature generation based on method
            pass
        
        # Prepare request parameters based on parameter method
        request_kwargs = {
            'method': http_method,
            'url': webhook_url,
            'headers': headers,
            'timeout': config.get('timeout_seconds', 30)
        }
        
        # Add payload based on parameter method
        if parameter_method == 'url_pattern':
            # For URL pattern, parameters are in the URL, no body needed unless there's extra data
            if 'payload' in parameters and parameters['payload']:
                json_payload = parameters['payload']
                # Add auth body parameters if configured
                if self.auth_credentials and 'body_params' in self.auth_credentials:
                    json_payload.update(self.auth_credentials['body_params'])
                request_kwargs['json'] = json_payload
        elif parameter_method == 'json_payload':
            # Add auth body parameters if configured
            if self.auth_credentials and 'body_params' in self.auth_credentials:
                payload.update(self.auth_credentials['body_params'])
            request_kwargs['json'] = payload
        elif parameter_method == 'form_data':
            # Set content type for form-encoded data
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            # Add auth body parameters if configured
            if self.auth_credentials and 'body_params' in self.auth_credentials:
                payload.update(self.auth_credentials['body_params'])
            request_kwargs['data'] = payload
        elif parameter_method == 'xml_payload':
            headers['Content-Type'] = 'application/xml'
            request_kwargs['content'] = str(payload)  # Convert to XML string
        elif parameter_method == 'query_params':
            # Add auth query parameters if configured
            if self.auth_credentials and 'query_params' in self.auth_credentials:
                payload.update(self.auth_credentials['query_params'])
            request_kwargs['params'] = payload
        
        # Log the final request details
        logger.info(f"Sending webhook request: {request_kwargs['method']} {request_kwargs['url']}")
        logger.info(f"Request headers: {mask_sensitive_data(request_kwargs.get('headers', {}))}")
        if 'json' in request_kwargs:
            logger.debug(f"Request body: {mask_sensitive_data(request_kwargs['json'])}")
        if 'params' in request_kwargs:
            logger.debug(f"Query params: {request_kwargs['params']}")
        
        # Send webhook
        async def send_webhook():
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.request(**request_kwargs)
                # Don't raise for status here - handle based on response validation
                return response
        
        try:
            response = await retry_async(send_webhook, config=NETWORK_RETRY_CONFIG)
            
            return {
                'status_code': response.status_code,
                'success': response.is_success,
                'response': response.text
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Webhook failed with HTTP error: {e.response.status_code} - {str(e)}")
            
            # Check for authentication errors
            if e.response.status_code == 401:
                # If OAuth2 or token exchange, try refreshing token once
                if self.auth_credentials and ('client_id' in self.auth_credentials or 'username' in self.auth_credentials):
                    logger.info("Attempting token refresh due to 401 error")
                    try:
                        # Force token refresh
                        self.auth_credentials['expires_at'] = 0  # Force expired
                        await self._ensure_valid_oauth2_token()
                        await self._ensure_valid_token_exchange(context=context)
                        
                        # Retry request with new token
                        auth_headers = self._build_auth_headers()
                        request_kwargs['headers'].update(auth_headers)
                        
                        response = await retry_async(send_webhook, config=NETWORK_RETRY_CONFIG)
                        
                        return {
                            'status_code': response.status_code,
                            'success': response.is_success,
                            'response': response.text
                        }
                            
                    except Exception as retry_error:
                        logger.error(f"Token refresh failed: {str(retry_error)}", exc_info=True)
                
                return {
                    'error': True,
                    'message': 'Authentication failed',
                    'status_code': 401,
                    'auth_error': True,
                    'url': webhook_url,
                    'method': request_kwargs['method']
                }
            
            return {
                'error': True,
                'message': str(e),
                'status_code': e.response.status_code,
                'response_text': e.response.text,
                'url': webhook_url,
                'method': request_kwargs['method'],
                'auth_error': e.response.status_code in [401, 403]
            }
        except Exception as e:
            logger.error(f"Webhook failed: {str(e)}")
            return {
                'error': True,
                'message': str(e),
                'url': webhook_url,
                'method': request_kwargs['method']
            }


class EmailSendExecutor(ServiceExecutor):
    """Executor for Email Send service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        try:
            # Process templates
            template_vars = parameters.get('template_vars', {})
            
            # Process subject
            subject = process_template(config['subject_template'], template_vars)
            
            # Process body
            body = process_template(config['body_template'], template_vars)
            
            # In production, this would actually send an email
            # For now, just log and return success
            logger.info(f"Would send email to {parameters['to']} with subject: {subject}")
            
            return {
                'success': True,
                'recipients': parameters['to'],
                'subject': subject,
                'body': body,
                'message_id': f"msg_{datetime.utcnow().timestamp()}"
            }
            
        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            return {
                'error': True,
                'message': str(e)
            }


class LLMApiCallExecutor(ServiceExecutor):
    """Executor for LLM API Call service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        try:
            # Process prompt templates
            prompt_vars = parameters.get('prompt_variables', {})
            
            messages = []
            
            # Add system prompt if configured
            if config.get('system_prompt_template'):
                system_content = process_template(config['system_prompt_template'], prompt_vars)
                messages.append({"role": "system", "content": system_content})
            
            # Add conversation history if provided
            if parameters.get('conversation_history'):
                messages.extend(parameters['conversation_history'])
            
            # Add user prompt
            user_content = process_template(config['user_prompt_template'], prompt_vars)
            messages.append({"role": "user", "content": user_content})
            
            # Call appropriate LLM API
            if config['provider'] == 'openai':
                return await self._call_openai(messages, config)
            elif config['provider'] == 'anthropic':
                return await self._call_anthropic(messages, config)
            else:
                # Implement other providers or custom endpoints
                return {
                    'error': True,
                    'message': f"Provider {config['provider']} not implemented"
                }
                
        except Exception as e:
            logger.error(f"LLM API call failed: {str(e)}")
            return {
                'error': True,
                'message': str(e)
            }
    
    async def _call_openai(self, messages: list, config: dict) -> dict:
        """Call OpenAI API"""
        # This is a placeholder - actual implementation would use the OpenAI client
        logger.info(f"Would call OpenAI {config['model']} with {len(messages)} messages")
        return {
            'response': "This is a placeholder OpenAI response",
            'model': config['model'],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }
    
    async def _call_anthropic(self, messages: list, config: dict) -> dict:
        """Call Anthropic API"""
        # This is a placeholder - actual implementation would use the Anthropic client
        logger.info(f"Would call Anthropic {config['model']} with {len(messages)} messages")
        return {
            'response': "This is a placeholder Anthropic response",
            'model': config['model'],
            'usage': {'input_tokens': 100, 'output_tokens': 50}
        }


class MCPCallExecutor(ServiceExecutor):
    """Executor for MCP Call service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        try:
            # Connect to MCP server
            connection_config = config['connection_config']
            
            # Map parameters if mapping is configured
            tool_params = parameters.get('parameters', {})
            if config.get('parameter_mapping'):
                mapped_params = {}
                for mcp_param, flow_param in config['parameter_mapping'].items():
                    if flow_param in tool_params:
                        mapped_params[mcp_param] = tool_params[flow_param]
                tool_params = mapped_params
            
            # This is a placeholder - actual implementation would use MCP client
            logger.info(f"Would call MCP server {config['server_name']} tool {config['tool_name']}")
            
            return {
                'success': True,
                'result': f"MCP call result for {config['tool_name']}",
                'server': config['server_name']
            }
            
        except Exception as e:
            logger.error(f"MCP call failed: {str(e)}")
            return {
                'error': True,
                'message': str(e)
            }


class SmtpSendExecutor(ServiceExecutor):
    """Executor for SMTP Send service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        try:
            import smtplib
            import ssl
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders
            import base64
            from urllib.parse import urlparse
            
            # Parse base_url if provided (new approach)
            base_url = config.get('base_url', '')
            if base_url:
                parsed = urlparse(base_url)
                smtp_host = parsed.hostname
                # Default ports based on protocol
                if parsed.port:
                    smtp_port = parsed.port
                elif parsed.scheme == 'smtps':
                    smtp_port = 465
                else:
                    smtp_port = 587

                # Determine SSL/TLS based on protocol
                # smtp-plain:// - explicitly no TLS/SSL
                # smtps:// - SSL
                # smtp:// - TLS if port 587, otherwise check config
                if parsed.scheme == 'smtp-plain':
                    use_ssl = False
                    use_tls = False
                elif parsed.scheme == 'smtps':
                    use_ssl = True
                    use_tls = False
                else:  # smtp://
                    # Check explicit config flags first (allows UI override)
                    use_ssl = config.get('use_ssl', False)
                    use_tls = config.get('use_tls', smtp_port == 587)
            else:
                # Fallback to old configuration method for backward compatibility
                smtp_host = config.get('smtp_host')
                smtp_port = config.get('smtp_port', 587)
                use_tls = config.get('use_tls', True)
                use_ssl = config.get('use_ssl', False)
            
            timeout = config.get('timeout_seconds', 30)
            
            if not smtp_host:
                raise ValueError("SMTP host is required. Please configure base_url as smtp://host:port or smtps://host:port")
            
            # Get authentication from credentials
            username = self.auth_credentials.get('username') if self.auth_credentials else None
            password = self.auth_credentials.get('password') if self.auth_credentials else None
            
            if not username or not password:
                raise ValueError("SMTP username and password are required")
            
            # Get email parameters first
            from_param = parameters.get('from', '')  # From parameter from the service call
            to_emails = parameters.get('to', '')
            cc_emails = parameters.get('cc', '')
            bcc_emails = parameters.get('bcc', '')
            subject = parameters.get('subject', '')
            body = parameters.get('body', '')
            body_type = parameters.get('body_type', 'plain')
            attachments = parameters.get('attachments', [])
            
            # Determine the from email address
            # Priority: 1. from parameter, 2. from_email in credentials, 3. username if it's an email
            from_email = from_param  # Use from parameter if provided
            
            if not from_email:
                # Try to get from_email from credentials
                from_email = self.auth_credentials.get('from_email') if self.auth_credentials else None
            
            if not from_email:
                # Check if username looks like an email address
                if '@' in username and not username.startswith('ocid1.'):
                    from_email = username
                else:
                    # For OCI usernames or other non-email usernames, we need a from email
                    raise ValueError("The 'from' email address is required. Please provide it as a parameter or configure a valid email address in the SMTP credentials.")
            
            # Handle single attachment or array of attachments
            if attachments and not isinstance(attachments, list):
                # Single attachment - convert to list
                attachments = [attachments]
            
            if not to_emails:
                raise ValueError("Recipient email address is required")
            
            # Create message
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = from_email  # Use the proper from_email instead of username
            msg['To'] = to_emails
            
            if cc_emails:
                msg['Cc'] = cc_emails
            
            # Add body
            if body_type == 'html':
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments if provided
            for attachment in attachments:
                if isinstance(attachment, dict):
                    # Handle both formats: 
                    # 1. Expected format: {filename, content, content_type}
                    # 2. File object format from frontend: {name, data, type, size, lastModified}
                    
                    # Check which format we have
                    if 'name' in attachment and 'data' in attachment:
                        # File object format from frontend
                        filename = attachment.get('name', 'attachment')
                        content = attachment.get('data', '')
                        content_type = attachment.get('type', 'application/octet-stream')
                        logger.info(f"Processing file object attachment: {filename}, type: {content_type}, size: {attachment.get('size', 0)}")
                    else:
                        # Expected format
                        filename = attachment.get('filename', 'attachment')
                        content = attachment.get('content', '')
                        content_type = attachment.get('content_type', 'application/octet-stream')
                        logger.info(f"Processing standard attachment: {filename}, content_type: {content_type}")
                    
                    logger.info(f"Attachment content length: {len(str(content))}")
                    
                    # Decode base64 content if needed
                    if isinstance(content, str) and content:
                        try:
                            # Try to decode as base64
                            if content.startswith('data:'):
                                # Extract base64 data from data URL
                                content = content.split(',', 1)[1]
                            attachment_data = base64.b64decode(content)
                            logger.info(f"Decoded base64 attachment: {filename}, size: {len(attachment_data)} bytes")
                        except Exception as e:
                            logger.warning(f"Failed to decode base64 for {filename}: {e}, using as text")
                            # If not base64, use as text
                            attachment_data = content.encode('utf-8')
                    else:
                        attachment_data = content if content else b''
                    
                    # Check if attachment_data is empty
                    if not attachment_data or len(attachment_data) == 0:
                        logger.warning(f"Attachment {filename} has no content (0 bytes)")
                    
                    # Parse content type safely
                    if '/' in content_type:
                        maintype, subtype = content_type.split('/', 1)
                    else:
                        maintype, subtype = 'application', 'octet-stream'
                    
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(attachment_data)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{filename}"'
                    )
                    msg.attach(part)
            
            # Collect all recipients
            all_recipients = []
            if to_emails:
                all_recipients.extend([email.strip() for email in to_emails.split(',')])
            if cc_emails:
                all_recipients.extend([email.strip() for email in cc_emails.split(',')])
            if bcc_emails:
                all_recipients.extend([email.strip() for email in bcc_emails.split(',')])
            
            # Connect to SMTP server
            if use_ssl:
                # Use SSL (typically port 465)
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout, context=context)
                logger.info(f"Connected to SMTP server {smtp_host}:{smtp_port} using SSL")
            else:
                # Use TLS (typically port 587) or plain (port 25)
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=timeout)
                if use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    logger.info(f"Connected to SMTP server {smtp_host}:{smtp_port} using TLS")
                else:
                    logger.info(f"Connected to SMTP server {smtp_host}:{smtp_port} (plain)")
            
            # Login and send
            server.login(username, password)
            logger.info(f"Authenticated with SMTP server as {username}")
            logger.info(f"Sending email from {from_email} to {all_recipients}")
            
            result = server.sendmail(from_email, all_recipients, msg.as_string())
            server.quit()
            
            # Check for any failed recipients
            failed_recipients = []
            if result:
                failed_recipients = list(result.keys())
            
            logger.info(f"Email sent successfully to {len(all_recipients) - len(failed_recipients)} recipients")
            if failed_recipients:
                logger.warning(f"Failed to send to {len(failed_recipients)} recipients: {failed_recipients}")
            
            return {
                'success': True,
                'message': f"Email sent successfully to {len(all_recipients) - len(failed_recipients)} recipients",
                'recipients_sent': [r for r in all_recipients if r not in failed_recipients],
                'recipients_failed': failed_recipients,
                'subject': subject,
                'message_id': msg.get('Message-ID')
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"SMTP send failed: {error_msg}")
            
            # Check for common authentication errors
            if "authentication" in error_msg.lower() or "login" in error_msg.lower():
                return {
                    'error': True,
                    'message': f"SMTP authentication failed: {error_msg}",
                    'auth_error': True
                }
            elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                return {
                    'error': True,
                    'message': f"SMTP connection failed: {error_msg}",
                    'connection_error': True
                }
            else:
                return {
                    'error': True,
                    'message': f"SMTP send failed: {error_msg}"
                }


class Pop3ReceiveExecutor(ServiceExecutor):
    """Executor for POP3 Receive service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        try:
            import poplib
            import ssl
            import email
            from email.header import decode_header
            import base64
            from urllib.parse import urlparse
            
            # Parse base_url if provided (new approach)
            base_url = config.get('base_url', '')
            if base_url:
                parsed = urlparse(base_url)
                pop3_host = parsed.hostname
                # Default ports based on protocol
                if parsed.port:
                    pop3_port = parsed.port
                elif parsed.scheme == 'pop3s':
                    pop3_port = 995
                else:
                    pop3_port = 110
                
                # Determine SSL based on protocol
                use_ssl = parsed.scheme == 'pop3s'
            else:
                # Fallback to old configuration method for backward compatibility
                pop3_host = config.get('pop3_host')
                pop3_port = config.get('pop3_port', 995)
                use_ssl = config.get('use_ssl', True)
            
            timeout = config.get('timeout_seconds', 30)
            max_messages = config.get('max_messages', 50)
            delete_after_read = parameters.get('delete_after_read', False)
            
            if not pop3_host:
                raise ValueError("POP3 host is required. Please configure base_url as pop3://host:port or pop3s://host:port")
            
            # Get authentication from credentials
            username = self.auth_credentials.get('username') if self.auth_credentials else None
            password = self.auth_credentials.get('password') if self.auth_credentials else None
            
            if not username or not password:
                raise ValueError("POP3 username and password are required")
            
            # Get parameters
            message_count = min(parameters.get('message_count', 10), max_messages)
            include_body = parameters.get('include_body', True)
            include_attachments = parameters.get('include_attachments', False)
            
            # Connect to POP3 server
            if use_ssl:
                server = poplib.POP3_SSL(pop3_host, pop3_port, timeout=timeout)
                logger.info(f"Connected to POP3 server {pop3_host}:{pop3_port} using SSL")
            else:
                server = poplib.POP3(pop3_host, pop3_port, timeout=timeout)
                logger.info(f"Connected to POP3 server {pop3_host}:{pop3_port} (plain)")
            
            # Login
            server.user(username)
            server.pass_(password)
            logger.info(f"Authenticated with POP3 server as {username}")
            
            # Get mailbox info
            num_messages = len(server.list()[1])
            logger.info(f"Found {num_messages} messages in mailbox")
            
            messages = []
            messages_to_retrieve = min(message_count, num_messages)
            
            # Retrieve messages (POP3 indexes are 1-based, get newest first)
            for i in range(num_messages, max(0, num_messages - messages_to_retrieve), -1):
                try:
                    # Get message
                    raw_message = b'\r\n'.join(server.retr(i)[1])
                    msg = email.message_from_bytes(raw_message)
                    
                    # Parse message
                    message_data = {
                        'message_number': i,
                        'subject': self._decode_header(msg.get('Subject', '')),
                        'from': self._decode_header(msg.get('From', '')),
                        'to': self._decode_header(msg.get('To', '')),
                        'date': msg.get('Date', ''),
                        'message_id': msg.get('Message-ID', '')
                    }
                    
                    # Get CC and BCC if present
                    if msg.get('Cc'):
                        message_data['cc'] = self._decode_header(msg.get('Cc'))
                    if msg.get('Bcc'):
                        message_data['bcc'] = self._decode_header(msg.get('Bcc'))
                    
                    # Get body if requested
                    if include_body:
                        body_text, body_html = self._extract_body(msg)
                        if body_text:
                            message_data['body_text'] = body_text
                        if body_html:
                            message_data['body_html'] = body_html
                    
                    # Get attachments if requested
                    if include_attachments:
                        attachments = self._extract_attachments(msg)
                        if attachments:
                            message_data['attachments'] = attachments
                    
                    messages.append(message_data)
                    
                    # Delete message if configured
                    if delete_after_read:
                        server.dele(i)
                        logger.debug(f"Marked message {i} for deletion")
                        
                except Exception as msg_error:
                    logger.warning(f"Failed to process message {i}: {str(msg_error)}")
                    continue
            
            server.quit()
            
            logger.info(f"Retrieved {len(messages)} messages from POP3 server")
            if delete_after_read:
                logger.info(f"Marked {len(messages)} messages for deletion")
            
            return {
                'success': True,
                'message': f"Retrieved {len(messages)} messages",
                'total_messages': num_messages,
                'retrieved_messages': len(messages),
                'messages': messages
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"POP3 receive failed: {error_msg}")
            
            # Check for common authentication errors
            if "authentication" in error_msg.lower() or "login" in error_msg.lower() or "-ERR" in error_msg:
                return {
                    'error': True,
                    'message': f"POP3 authentication failed: {error_msg}",
                    'auth_error': True
                }
            elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                return {
                    'error': True,
                    'message': f"POP3 connection failed: {error_msg}",
                    'connection_error': True
                }
            else:
                return {
                    'error': True,
                    'message': f"POP3 receive failed: {error_msg}"
                }
    
    def _decode_header(self, header_value):
        """Decode email header with proper encoding handling"""
        if not header_value:
            return ""
        
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += str(part)
            return decoded_string
        except:
            return str(header_value)
    
    def _extract_body(self, msg):
        """Extract text and HTML body from email message"""
        body_text = ""
        body_html = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                if content_type == "text/plain":
                    body_text = self._get_part_content(part)
                elif content_type == "text/html":
                    body_html = self._get_part_content(part)
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                body_text = self._get_part_content(msg)
            elif content_type == "text/html":
                body_html = self._get_part_content(msg)
        
        return body_text, body_html
    
    def _get_part_content(self, part):
        """Get content from email part with proper encoding"""
        try:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors='ignore')
        except:
            try:
                return str(part.get_payload())
            except:
                return ""
        return ""
    
    def _extract_attachments(self, msg):
        """Extract attachments from email message"""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        try:
                            filename = self._decode_header(filename)
                            payload = part.get_payload(decode=True)
                            if payload:
                                # Encode as base64 for safe transport
                                content_b64 = base64.b64encode(payload).decode('utf-8')
                                attachments.append({
                                    'filename': filename,
                                    'content_type': part.get_content_type(),
                                    'size': len(payload),
                                    'content': content_b64
                                })
                        except Exception as att_error:
                            logger.warning(f"Failed to extract attachment {filename}: {str(att_error)}")
        
        return attachments


class ImapReceiveExecutor(ServiceExecutor):
    """Executor for IMAP Receive service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        try:
            import imaplib
            import ssl
            import email
            from email.header import decode_header
            import base64
            from urllib.parse import urlparse
            
            # Parse base_url if provided (new approach)
            base_url = config.get('base_url', '')
            if base_url:
                parsed = urlparse(base_url)
                imap_host = parsed.hostname
                # Default ports based on protocol
                if parsed.port:
                    imap_port = parsed.port
                elif parsed.scheme == 'imaps':
                    imap_port = 993
                else:
                    imap_port = 143
                
                # Determine SSL based on protocol
                use_ssl = parsed.scheme == 'imaps'
            else:
                # Fallback to old configuration method for backward compatibility
                imap_host = config.get('imap_host')
                imap_port = config.get('imap_port', 993)
                use_ssl = config.get('use_ssl', True)
            
            timeout = config.get('timeout_seconds', 30)
            default_mailbox = config.get('mailbox', 'INBOX')
            max_messages = config.get('max_messages', 50)
            mark_as_read = parameters.get('mark_as_read', True)
            default_search = config.get('search_criteria', 'UNSEEN')
            
            if not imap_host:
                raise ValueError("IMAP host is required. Please configure base_url as imap://host:port or imaps://host:port")
            
            # Get authentication from credentials
            username = self.auth_credentials.get('username') if self.auth_credentials else None
            password = self.auth_credentials.get('password') if self.auth_credentials else None
            
            if not username or not password:
                raise ValueError("IMAP username and password are required")
            
            # Get parameters
            folder = parameters.get('folder', default_mailbox)
            search_query = parameters.get('search_query', default_search)
            message_count = min(parameters.get('message_count', 10), max_messages)
            include_body = parameters.get('include_body', True)
            include_attachments = parameters.get('include_attachments', False)
            
            # Connect to IMAP server
            if use_ssl:
                server = imaplib.IMAP4_SSL(imap_host, imap_port)
                logger.info(f"Connected to IMAP server {imap_host}:{imap_port} using SSL")
            else:
                server = imaplib.IMAP4(imap_host, imap_port)
                logger.info(f"Connected to IMAP server {imap_host}:{imap_port} (plain)")
            
            # Login
            server.login(username, password)
            logger.info(f"Authenticated with IMAP server as {username}")
            
            # Select mailbox
            status, mailbox_data = server.select(folder)
            if status != 'OK':
                raise Exception(f"Failed to select mailbox '{folder}': {mailbox_data}")
            
            total_messages = int(mailbox_data[0])
            logger.info(f"Selected mailbox '{folder}' with {total_messages} total messages")
            
            # Search for messages
            status, message_ids = server.search(None, search_query)
            if status != 'OK':
                raise Exception(f"Failed to search messages: {message_ids}")
            
            message_ids = message_ids[0].split()
            found_messages = len(message_ids)
            logger.info(f"Found {found_messages} messages matching criteria: {search_query}")
            
            messages = []
            messages_to_retrieve = min(message_count, found_messages)
            
            # Get newest messages first (reverse order)
            for msg_id in reversed(message_ids[-messages_to_retrieve:]):
                try:
                    # Fetch message
                    status, msg_data = server.fetch(msg_id, '(RFC822)')
                    if status != 'OK':
                        logger.warning(f"Failed to fetch message {msg_id}")
                        continue
                    
                    raw_message = msg_data[0][1]
                    msg = email.message_from_bytes(raw_message)
                    
                    # Parse message
                    message_data = {
                        'message_id': msg_id.decode('utf-8'),
                        'subject': self._decode_header(msg.get('Subject', '')),
                        'from': self._decode_header(msg.get('From', '')),
                        'to': self._decode_header(msg.get('To', '')),
                        'date': msg.get('Date', ''),
                        'uid': msg.get('Message-ID', '')
                    }
                    
                    # Get CC and BCC if present
                    if msg.get('Cc'):
                        message_data['cc'] = self._decode_header(msg.get('Cc'))
                    if msg.get('Bcc'):
                        message_data['bcc'] = self._decode_header(msg.get('Bcc'))
                    
                    # Get body if requested
                    if include_body:
                        body_text, body_html = self._extract_body(msg)
                        if body_text:
                            message_data['body_text'] = body_text
                        if body_html:
                            message_data['body_html'] = body_html
                    
                    # Get attachments if requested
                    if include_attachments:
                        attachments = self._extract_attachments(msg)
                        if attachments:
                            message_data['attachments'] = attachments
                    
                    messages.append(message_data)
                    
                    # Mark as read if configured
                    if mark_as_read:
                        server.store(msg_id, '+FLAGS', '\\Seen')
                        logger.debug(f"Marked message {msg_id} as read")
                        
                except Exception as msg_error:
                    logger.warning(f"Failed to process message {msg_id}: {str(msg_error)}")
                    continue
            
            server.close()
            server.logout()
            
            logger.info(f"Retrieved {len(messages)} messages from IMAP server")
            if mark_as_read:
                logger.info(f"Marked {len(messages)} messages as read")
            
            return {
                'success': True,
                'message': f"Retrieved {len(messages)} messages",
                'total_messages': total_messages,
                'found_messages': found_messages,
                'retrieved_messages': len(messages),
                'folder': folder,
                'search_query': search_query,
                'messages': messages
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"IMAP receive failed: {error_msg}")
            
            # Check for common authentication errors
            if "authentication" in error_msg.lower() or "login" in error_msg.lower() or "AUTHENTICATIONFAILED" in error_msg:
                return {
                    'error': True,
                    'message': f"IMAP authentication failed: {error_msg}",
                    'auth_error': True
                }
            elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                return {
                    'error': True,
                    'message': f"IMAP connection failed: {error_msg}",
                    'connection_error': True
                }
            else:
                return {
                    'error': True,
                    'message': f"IMAP receive failed: {error_msg}"
                }
    
    def _decode_header(self, header_value):
        """Decode email header with proper encoding handling"""
        if not header_value:
            return ""
        
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += str(part)
            return decoded_string
        except:
            return str(header_value)
    
    def _extract_body(self, msg):
        """Extract text and HTML body from email message"""
        body_text = ""
        body_html = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                if content_type == "text/plain":
                    body_text = self._get_part_content(part)
                elif content_type == "text/html":
                    body_html = self._get_part_content(part)
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                body_text = self._get_part_content(msg)
            elif content_type == "text/html":
                body_html = self._get_part_content(msg)
        
        return body_text, body_html
    
    def _get_part_content(self, part):
        """Get content from email part with proper encoding"""
        try:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors='ignore')
        except:
            try:
                return str(part.get_payload())
            except:
                return ""
        return ""
    
    def _extract_attachments(self, msg):
        """Extract attachments from email message"""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        try:
                            filename = self._decode_header(filename)
                            payload = part.get_payload(decode=True)
                            if payload:
                                # Encode as base64 for safe transport
                                content_b64 = base64.b64encode(payload).decode('utf-8')
                                attachments.append({
                                    'filename': filename,
                                    'content_type': part.get_content_type(),
                                    'size': len(payload),
                                    'content': content_b64
                                })
                        except Exception as att_error:
                            logger.warning(f"Failed to extract attachment {filename}: {str(att_error)}")
        
        return attachments


class GraphQLExecutor(ServiceExecutor):
    """Executor for GraphQL service type"""

    def _build_graphql_value(self, value: Any) -> str:
        """Convert a Python value to GraphQL format"""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Escape quotes in strings
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        elif isinstance(value, list):
            items = [self._build_graphql_value(item) for item in value]
            return f"[{', '.join(items)}]"
        elif isinstance(value, dict):
            pairs = []
            for k, v in value.items():
                pairs.append(f"{k}: {self._build_graphql_value(v)}")
            return f"{{{', '.join(pairs)}}}"
        else:
            return str(value)

    def _build_weaviate_query(self, parameters: Dict[str, Any]) -> str:
        """Build a Weaviate-specific GraphQL query"""
        className = parameters.get('className', '')
        hybrid = parameters.get('hybrid', {})
        fields = parameters.get('fields', [])
        limit = parameters.get('limit', 10)

        # Build the hybrid search parameters
        hybrid_params = []
        if 'query' in hybrid:
            hybrid_params.append(f'query: "{hybrid["query"]}"')
        if 'alpha' in hybrid:
            # Ensure alpha is a number
            alpha_value = hybrid['alpha']
            if isinstance(alpha_value, str):
                try:
                    alpha_value = float(alpha_value)
                except ValueError:
                    alpha_value = 0.5
            hybrid_params.append(f'alpha: {alpha_value}')

        # Build the query
        query_parts = [
            "{ Get {",
            f"  {className} (",
            f"    hybrid: {{ {', '.join(hybrid_params)} }}",
            f"    limit: {limit}",
            "  ) {"
        ]

        # Add fields if specified
        if fields:
            for field in fields:
                query_parts.append(f"    {field}")

        # Always add _additional fields for Weaviate
        query_parts.append("    _additional { id score }")
        query_parts.append("  }")
        query_parts.append("} }")

        return '\n'.join(query_parts)

    def _build_generic_query(self, parameters: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Build a generic GraphQL query from parameters"""
        # Check if there's a query template in body_template
        request_config = config.get('request_config', {})
        body_template = request_config.get('body_template', {})

        if isinstance(body_template, dict) and 'query' in body_template:
            # Use the provided query template
            query_template = body_template['query']
            # Simple string replacement for parameters
            query = query_template
            for key, value in parameters.items():
                if isinstance(value, dict):
                    # Handle nested objects
                    for sub_key, sub_value in value.items():
                        placeholder = f"{{{{{key}.{sub_key}}}}}"
                        if placeholder in query:
                            if isinstance(sub_value, str):
                                query = query.replace(placeholder, sub_value)
                            else:
                                query = query.replace(placeholder, str(sub_value))
                else:
                    placeholder = f"{{{{{key}}}}}"
                    if placeholder in query:
                        if isinstance(value, str):
                            query = query.replace(placeholder, value)
                        else:
                            query = query.replace(placeholder, str(value))
            return query

        # If no template, try to build a basic query
        # This is a fallback - ideally services should provide a template
        operation = parameters.get('operation', 'query')
        selection = parameters.get('selection', '{}')
        return f"{operation} {selection}"

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query"""
        config = self.service_config

        # Determine if this is a Weaviate query based on parameters
        is_weaviate = 'className' in parameters and 'hybrid' in parameters

        # Build the GraphQL query
        if is_weaviate:
            graphql_query = self._build_weaviate_query(parameters)
        else:
            graphql_query = self._build_generic_query(parameters, config)

        # Log the constructed query
        logger.info(f"GraphQL query constructed: {graphql_query}")

        # Prepare the request body
        request_body = {
            "query": graphql_query
        }

        # Add variables if provided
        if 'variables' in parameters:
            request_body['variables'] = parameters['variables']

        # Use ApiCallExecutor to make the actual HTTP request
        # Update the config to use the constructed body
        api_config = config.copy()
        api_config['request_config'] = config.get('request_config', {}).copy()
        api_config['request_config']['method'] = 'POST'
        api_config['request_config']['headers'] = api_config['request_config'].get('headers', {})
        api_config['request_config']['headers']['Content-Type'] = 'application/json'

        # Create an ApiCallExecutor instance
        api_executor = ApiCallExecutor(api_config, self.auth_credentials,
                                      self.subscription_id, self.auth_config)

        # Execute with the GraphQL query as the body
        result = await api_executor.execute(request_body, context)

        # Check for GraphQL errors in the response
        if isinstance(result, dict) and 'data' in result:
            if 'errors' in result and result['errors']:
                # GraphQL returned errors
                error_messages = []
                for error in result['errors']:
                    if isinstance(error, dict):
                        error_messages.append(error.get('message', 'Unknown GraphQL error'))
                    else:
                        error_messages.append(str(error))

                return {
                    'error': True,
                    'message': f"GraphQL errors: {'; '.join(error_messages)}",
                    'graphql_errors': result['errors'],
                    'data': result.get('data')
                }

            # Successful GraphQL response
            return {
                'success': True,
                'data': result['data'],
                'headers': result.get('headers', {}),
                'status': result.get('status', 200)
            }

        # Return the result as-is if it's not a standard GraphQL response
        return result


def get_service_executor(service_type: str, service_config: Dict[str, Any],
                        auth_credentials: Dict[str, Any] = None,
                        subscription_id: str = None, auth_config: Dict[str, Any] = None,
                        application_base_url: str = None) -> ServiceExecutor:
    """Factory function to get the appropriate service executor.

    Uses PluginRegistry for lookup. Plugins register themselves via
    discover_plugins() at startup.
    """
    from plugins.registry import PluginRegistry

    executor_or_factory = PluginRegistry.get_service_executor(service_type)

    if executor_or_factory is None:
        raise ValueError(f"Unknown service type: {service_type}")

    # If the registered value is a callable factory (function), call it with all args
    if callable(executor_or_factory) and not isinstance(executor_or_factory, type):
        return executor_or_factory(
            service_config, auth_credentials, subscription_id,
            auth_config, application_base_url
        )

    # Otherwise it's a class — instantiate it
    return executor_or_factory(service_config, auth_credentials, subscription_id, auth_config)