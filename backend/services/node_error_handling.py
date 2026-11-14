"""
Node-level error handling for flow execution.

Each flow node may carry an ``errorHandling`` block in its data:

    "errorHandling": {
        "retry": {
            "enabled": true,
            "maxAttempts": 3,             # total attempts, including the first
            "initialDelayMs": 1000,
            "backoff": "exponential",     # "fixed" | "exponential"
            "maxDelayMs": 30000,
            "jitter": true,
            "retryOn": ["connection", "timeout", "rate_limit", "server"]   # or ["any"]
        },
        "onError": "stop",                # "stop" | "continue" | "error_branch"
        "continueOutput": {...},          # optional fallback output used by "continue"
        "failOnUnsuccessfulResponse": false
    }

- ``stop``          the failure fails the whole execution (the default, and the
                    behaviour of every node without an errorHandling block)
- ``continue``      the node's output becomes ``{success: false, error: {...}}``
                    (merged with ``continueOutput``) and the normal outgoing
                    edges run as if the node had succeeded
- ``error_branch``  only the edges leaving the node's ``error`` handle
                    (edge.sourceHandle == "error") run; the normal edges are skipped

Failures are classified into a small set of error types so that retry rules and
downstream nodes can reason about them (``{{node_x.error.type}}``).
"""
import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Source handle id used by the error output of a node
ERROR_HANDLE = 'error'

ON_ERROR_STOP = 'stop'
ON_ERROR_CONTINUE = 'continue'
ON_ERROR_BRANCH = 'error_branch'
ON_ERROR_MODES = (ON_ERROR_STOP, ON_ERROR_CONTINUE, ON_ERROR_BRANCH)

# Error types
ERR_CONNECTION = 'connection'
ERR_TIMEOUT = 'timeout'
ERR_RATE_LIMIT = 'rate_limit'
ERR_AUTH = 'auth'
ERR_NOT_FOUND = 'not_found'
ERR_VALIDATION = 'validation'
ERR_CLIENT = 'client'
ERR_SERVER = 'server'
ERR_BILLING = 'billing'
ERR_UNKNOWN = 'unknown'

ERROR_TYPES = (
    ERR_CONNECTION, ERR_TIMEOUT, ERR_RATE_LIMIT, ERR_AUTH, ERR_NOT_FOUND,
    ERR_VALIDATION, ERR_CLIENT, ERR_SERVER, ERR_BILLING, ERR_UNKNOWN,
)

# Errors that are worth retrying by default
TRANSIENT_ERROR_TYPES = (ERR_CONNECTION, ERR_TIMEOUT, ERR_RATE_LIMIT, ERR_SERVER)

# Errors that must always fail the execution: no retry, no continue, no branch
FATAL_ERROR_TYPES = (ERR_BILLING,)

RETRY_ON_ANY = 'any'

# Node types that never get an error policy
NO_POLICY_NODE_TYPES = {'trigger'}

# Node types that must not be re-executed: they drive other nodes, pause the
# execution or wait on humans/events, so a retry would repeat side effects
NON_RETRYABLE_NODE_TYPES = {'trigger', 'loop', 'parallel', 'human_in_loop', 'wait_for_event'}

# Hard limits so a flow definition cannot stall an execution indefinitely
MAX_ATTEMPTS_LIMIT = 10
MAX_DELAY_MS_LIMIT = 300_000


class NodeExecutionError(Exception):
    """A node failure carrying structured details used for classification."""

    def __init__(self, message: str, *, error_type: Optional[str] = None,
                 status_code: Optional[int] = None, response: Any = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.response = response
        self.details = details or {}


class ServiceExecutionError(NodeExecutionError):
    """Raised when a service executor returned an error result."""


def _to_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


@dataclass
class RetryPolicy:
    enabled: bool = False
    max_attempts: int = 1
    initial_delay_ms: int = 1000
    backoff: str = 'exponential'
    max_delay_ms: int = 30_000
    jitter: bool = True
    retry_on: List[str] = field(default_factory=lambda: list(TRANSIENT_ERROR_TYPES))

    @classmethod
    def from_config(cls, config: Any) -> 'RetryPolicy':
        if not isinstance(config, dict):
            return cls()
        retry_on = config.get('retryOn', config.get('retry_on'))
        if isinstance(retry_on, str):
            retry_on = [retry_on]
        if not isinstance(retry_on, list) or not retry_on:
            retry_on = list(TRANSIENT_ERROR_TYPES)
        retry_on = [str(t) for t in retry_on if str(t) in ERROR_TYPES or str(t) == RETRY_ON_ANY]
        backoff = config.get('backoff', 'exponential')
        return cls(
            enabled=bool(config.get('enabled', False)),
            max_attempts=_to_int(config.get('maxAttempts', config.get('max_attempts')), 3, 1, MAX_ATTEMPTS_LIMIT),
            initial_delay_ms=_to_int(config.get('initialDelayMs', config.get('initial_delay_ms')), 1000, 0, MAX_DELAY_MS_LIMIT),
            backoff=backoff if backoff in ('fixed', 'exponential') else 'exponential',
            max_delay_ms=_to_int(config.get('maxDelayMs', config.get('max_delay_ms')), 30_000, 0, MAX_DELAY_MS_LIMIT),
            jitter=bool(config.get('jitter', True)),
            retry_on=retry_on or list(TRANSIENT_ERROR_TYPES),
        )

    def applies_to(self, error_type: str) -> bool:
        return RETRY_ON_ANY in self.retry_on or error_type in self.retry_on

    def delay_seconds(self, attempt: int) -> float:
        """Delay before the attempt following ``attempt`` (1-based)."""
        if self.backoff == 'fixed':
            delay_ms = self.initial_delay_ms
        else:
            delay_ms = self.initial_delay_ms * (2 ** (attempt - 1))
        delay_ms = min(delay_ms, self.max_delay_ms)
        if self.jitter and delay_ms > 0:
            delay_ms *= random.uniform(0.8, 1.2)
        return max(delay_ms, 0) / 1000.0


@dataclass
class ErrorPolicy:
    node_type: str = ''
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    on_error: str = ON_ERROR_STOP
    continue_output: Any = None
    fail_on_unsuccessful_response: bool = False

    @classmethod
    def from_node(cls, node_type: str, node_data: Any) -> 'ErrorPolicy':
        """Build the policy for a node. Invalid or missing config yields the
        default policy (no retry, stop on error), which preserves the
        behaviour of flows designed before error handling existed."""
        if node_type in NO_POLICY_NODE_TYPES or not isinstance(node_data, dict):
            return cls(node_type=node_type)
        config = node_data.get('errorHandling', node_data.get('error_handling'))
        if not isinstance(config, dict):
            return cls(node_type=node_type)
        on_error = config.get('onError', config.get('on_error', ON_ERROR_STOP))
        if on_error not in ON_ERROR_MODES:
            logger.warning(f"Unknown onError mode '{on_error}' for {node_type} node, using 'stop'")
            on_error = ON_ERROR_STOP
        retry = RetryPolicy.from_config(config.get('retry'))
        if node_type in NON_RETRYABLE_NODE_TYPES:
            retry.enabled = False
        return cls(
            node_type=node_type,
            retry=retry,
            on_error=on_error,
            continue_output=config.get('continueOutput', config.get('continue_output')),
            fail_on_unsuccessful_response=bool(
                config.get('failOnUnsuccessfulResponse', config.get('fail_on_unsuccessful_response', False))
            ),
        )

    @property
    def handles_errors(self) -> bool:
        return self.on_error in (ON_ERROR_CONTINUE, ON_ERROR_BRANCH)

    def should_retry(self, error_type: str, attempt: int) -> bool:
        return (self.retry.enabled
                and error_type not in FATAL_ERROR_TYPES
                and attempt < self.retry.max_attempts
                and self.retry.applies_to(error_type))


_STATUS_IN_MESSAGE = re.compile(r'\b(?:status(?: code)?|HTTP)\s*[:=]?\s*(\d{3})\b', re.IGNORECASE)


def _status_code_of(exc: BaseException) -> Optional[int]:
    status = getattr(exc, 'status_code', None)
    if isinstance(status, int):
        return status
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None)
    if isinstance(status, int):
        return status
    match = _STATUS_IN_MESSAGE.search(str(exc))
    if match:
        return int(match.group(1))
    return None


def error_type_for_status(status_code: int) -> str:
    if status_code in (401, 403):
        return ERR_AUTH
    if status_code == 404:
        return ERR_NOT_FOUND
    if status_code == 408:
        return ERR_TIMEOUT
    if status_code == 429:
        return ERR_RATE_LIMIT
    if status_code in (400, 409, 422):
        return ERR_VALIDATION
    if 500 <= status_code <= 599:
        return ERR_SERVER
    if 400 <= status_code <= 499:
        return ERR_CLIENT
    return ERR_UNKNOWN


def classify_exception(exc: BaseException) -> Tuple[str, Optional[int]]:
    """Return ``(error_type, status_code)`` for an exception."""
    status_code = _status_code_of(exc)

    explicit = getattr(exc, 'error_type', None)
    if explicit in ERROR_TYPES:
        return explicit, status_code

    try:
        from exceptions.billing_exceptions import BillingException
        if isinstance(exc, BillingException):
            return ERR_BILLING, status_code
    except ImportError:
        pass

    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return ERR_TIMEOUT, status_code
        if isinstance(exc, (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError)):
            return ERR_CONNECTION, status_code
    except ImportError:
        pass

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return ERR_TIMEOUT, status_code
    if isinstance(exc, ConnectionError):
        return ERR_CONNECTION, status_code

    if status_code is not None:
        return error_type_for_status(status_code), status_code

    message = str(exc).lower()
    if 'timed out' in message or 'timeout' in message:
        return ERR_TIMEOUT, status_code
    if 'rate limit' in message or 'too many requests' in message:
        return ERR_RATE_LIMIT, status_code
    if ('authentication failed' in message or 'unauthorized' in message
            or 'invalid token' in message or ('access token' in message and 'expired' in message)):
        return ERR_AUTH, status_code
    if ('connection refused' in message or 'connection reset' in message
            or 'name or service not known' in message or 'connection error' in message):
        return ERR_CONNECTION, status_code
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return ERR_VALIDATION, status_code
    return ERR_UNKNOWN, status_code


def is_control_flow_exception(exc: BaseException) -> bool:
    """Exceptions the engine uses for flow control, never treated as node failures."""
    return 'Loop exit' in str(exc)


def unsuccessful_result_error(result: Any) -> Optional[NodeExecutionError]:
    """When a node returned a result flagged as unsuccessful (``success: false``
    or ``error: true``) build the error to raise for it, else None."""
    if not isinstance(result, dict):
        return None
    if result.get('success') is not False and result.get('error') is not True:
        return None
    status_code = result.get('status_code', result.get('status'))
    status_code = status_code if isinstance(status_code, int) else None
    message = result.get('message') or result.get('error_message')
    if not isinstance(message, str) or not message:
        message = (f"Node returned an unsuccessful response (HTTP {status_code})"
                   if status_code else "Node returned an unsuccessful response")
    return NodeExecutionError(
        message,
        error_type=error_type_for_status(status_code) if status_code else None,
        status_code=status_code,
        response=result.get('response', result.get('data')),
    )


def build_error_object(exc: BaseException, *, node_id: str, node_type: str,
                       node_label: str, attempts: int, handled_by: str) -> Dict[str, Any]:
    """The error object exposed to downstream nodes as ``{{<node_id>.error.*}}``
    and ``{{error.*}}``."""
    error_type, status_code = classify_exception(exc)
    message = getattr(exc, 'message', None) or str(exc) or type(exc).__name__
    error = {
        'message': message,
        'type': error_type,
        'status_code': status_code,
        'exception': type(exc).__name__,
        'node_id': node_id,
        'node_type': node_type,
        'node_label': node_label,
        'attempts': attempts,
        'retryable': error_type in TRANSIENT_ERROR_TYPES,
        'handled_by': handled_by,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
    }
    response = getattr(exc, 'response', None)
    if response is not None and not hasattr(response, 'status_code'):
        # Structured response body from a service error (not an httpx.Response)
        error['response'] = response
    elif response is not None:
        try:
            error['response'] = response.json()
        except Exception:
            error['response'] = getattr(response, 'text', None)
    return error


def build_handled_output(policy: ErrorPolicy, error: Dict[str, Any]) -> Dict[str, Any]:
    """Output stored for a node whose failure was handled."""
    output: Dict[str, Any] = {}
    if policy.on_error == ON_ERROR_CONTINUE and policy.continue_output is not None:
        if isinstance(policy.continue_output, dict):
            output.update(policy.continue_output)
        else:
            output['data'] = policy.continue_output
    output['success'] = False
    output['error'] = error
    output['_error_handled'] = True
    return output


def mark_skip_policy(exc: BaseException, node_id: str) -> None:
    """Mark an exception raised by nodes *downstream* of ``node_id`` (reached
    through the node's own handler, e.g. a loop's continue path) so that
    ``node_id``'s error policy does not treat it as the node's own failure."""
    skip = getattr(exc, '_ioflow_skip_policy_for', None)
    if skip is None:
        skip = set()
        try:
            exc._ioflow_skip_policy_for = skip
        except Exception:
            return
    skip.add(node_id)


def should_skip_policy(exc: BaseException, node_id: str) -> bool:
    return node_id in (getattr(exc, '_ioflow_skip_policy_for', None) or ())
