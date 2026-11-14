from cryptography.fernet import Fernet
import json
import os
import re
from typing import Any, Dict, Optional

# Global cipher suite (initialized lazily)
_cipher_suite: Optional[Fernet] = None

def get_cipher_suite() -> Fernet:
    """Get or create the cipher suite using the encryption key from settings."""
    global _cipher_suite
    
    if _cipher_suite is None:
        from core.config import settings
        
        # Get encryption key from settings
        ENCRYPTION_KEY = settings.encryption_key
        if not ENCRYPTION_KEY:
            # Generate a new key if not provided (should be set in production)
            ENCRYPTION_KEY = Fernet.generate_key().decode()
            print(f"WARNING: Generated new encryption key. Set ENCRYPTION_KEY in .env file.")
        
        _cipher_suite = Fernet(ENCRYPTION_KEY.encode())
    
    return _cipher_suite

def encrypt_credentials(credentials: Dict[str, Any]) -> Any:
    """Encrypt sensitive credential data."""
    if not credentials:
        return {}
    
    # Convert to JSON string
    json_str = json.dumps(credentials)
    
    # Encrypt
    encrypted = get_cipher_suite().encrypt(json_str.encode())
    
    # Return as dict with encrypted data - PostgreSQL stores JSONB natively
    return {"encrypted": encrypted.decode()}

def decrypt_credentials(encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt credential data."""
    if not encrypted_data:
        return {}
    
    # Handle case where encrypted_data is a JSON string (SQLite)
    if isinstance(encrypted_data, str):
        try:
            encrypted_data = json.loads(encrypted_data)
        except json.JSONDecodeError:
            print(f"Error parsing encrypted data as JSON: {encrypted_data}")
            return {}
    
    if not isinstance(encrypted_data, dict) or 'encrypted' not in encrypted_data:
        return {}
    
    try:
        # Decrypt
        decrypted = get_cipher_suite().decrypt(encrypted_data['encrypted'].encode())
        
        # Parse JSON
        return json.loads(decrypted.decode())
    except Exception as e:
        # Only log if it's not an empty credential case
        if encrypted_data and encrypted_data.get('encrypted'):
            print(f"Error decrypting credentials: {e}")
        return {}

def encrypt_data(data: Any) -> str:
    """Encrypt any data type by converting to JSON first."""
    if data is None:
        return None
    
    # Convert to JSON string
    json_str = json.dumps(data)
    
    # Encrypt
    encrypted = get_cipher_suite().encrypt(json_str.encode())
    
    # Return as base64 encoded string
    return encrypted.decode()

def decrypt_data(encrypted_str: str) -> Any:
    """Decrypt data and return the original type."""
    if not encrypted_str:
        return None
    
    try:
        # Decrypt
        decrypted = get_cipher_suite().decrypt(encrypted_str.encode())
        
        # Parse JSON to get original data type
        return json.loads(decrypted.decode())
    except Exception as e:
        print(f"Error decrypting data: {e}")
        return None

# ---------------------------------------------------------------------------
# Log redaction
# ---------------------------------------------------------------------------
# `mask_sensitive_data` is opt-in per call site and keeps a prefix of every
# value; several log paths never called it (a service_config dump carrying
# `request_config.headers.Authorization: Bearer <inbound key>`, raw header
# dicts, URLs with `?api_key=`). `redact_secrets` is the one used at the choke
# points — every ExecutionLog row, the live log WebSocket, and server-log lines
# that dump configs/headers — and redacts COMPLETELY: by key name, and inside
# free text (Bearer/Basic tokens, secret query parameters, IOFlow invocation
# keys), so a secret embedded in a message string does not survive either.

REDACTED = "***redacted***"

# Normalised (lower-case, '-' and ' ' -> '_') key names whose value is a secret.
_SECRET_KEYS_EXACT = {
    "authorization", "proxy_authorization", "cookie", "set_cookie",
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "access_token", "refresh_token", "id_token", "session_token", "auth_token",
    "bearer", "client_secret", "private_key", "signing_key", "webhook_secret",
    "invocation_api_key", "x_api_key", "x_amz_access_token",
    "x_shopify_access_token", "x_auth_token", "x_access_token", "api_token",
    "consumer_secret", "app_secret", "secret_key", "access_key_secret",
    "mqtt_password", "smtp_password", "db_password",
}
_SECRET_KEY_SUFFIXES = ("_token", "_secret", "_password", "_api_key", "_apikey",
                        "_private_key", "_access_key")
# "..._token" names that are paging cursors, not credentials (kept readable —
# they are what one debugs a paginated flow with).
_NOT_SECRET_KEYS = {"page_token", "next_page_token", "pagination_token", "next_token",
                    "continuation_token", "prev_page_token", "cursor_token"}

_TEXT_PATTERNS = [
    # Authorization schemes inside any string: "Bearer abc…", "Basic dXNlcj…"
    (re.compile(r"(?i)\b(Bearer|Basic|Token|Digest)\s+[A-Za-z0-9._~+/=\-]{6,}"),
     lambda m: f"{m.group(1)} {REDACTED}"),
    # secret query-string / form parameters: ?api_key=…&access_token=…
    (re.compile(r"(?i)([?&;](?:api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|token|"
                r"client[_-]?secret|password|secret|signature|sig|key)=)[^&#\s\"']+"),
     lambda m: f"{m.group(1)}{REDACTED}"),
    # IOFlow subscription invocation keys (ioflow_<urlsafe 32 bytes>)
    (re.compile(r"\bioflow_[A-Za-z0-9_\-]{20,}"), lambda m: f"ioflow_{REDACTED}"),
    # "Authorization": "…" / 'x-api-key': '…' written into a string (repr of a dict)
    (re.compile(r"(?i)([\"']?(?:authorization|x-api-key|x-amz-access-token|x-shopify-access-token|"
                r"client_secret|access_token|refresh_token|api_key|password)[\"']?\s*[:=]\s*[\"'])"
                r"[^\"']+([\"'])"),
     lambda m: f"{m.group(1)}{REDACTED}{m.group(2)}"),
]


def is_secret_key(key: Any) -> bool:
    """True when a dict key / header name names a secret value."""
    if not isinstance(key, str):
        return False
    k = key.strip().lower().replace("-", "_").replace(" ", "_")
    if not k or k in _NOT_SECRET_KEYS:
        return False
    if k in _SECRET_KEYS_EXACT or "authorization" in k:
        return True
    return k.endswith(_SECRET_KEY_SUFFIXES)


def redact_text(text: Any) -> Any:
    """Scrub secrets embedded in free text (log messages, URLs, reprs)."""
    if not isinstance(text, str) or not text:
        return text
    for pattern, repl in _TEXT_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_secrets(data: Any, _depth: int = 0) -> Any:
    """Deep copy of ``data`` with every secret replaced by ``REDACTED``.

    Keys naming a secret lose their whole value (never a prefix/suffix);
    every other string is scrubbed with :func:`redact_text`. Non-container,
    non-string values pass through. Never raises: a value it cannot walk is
    returned as-is rather than breaking the log write.
    """
    if _depth > 40:
        return data
    try:
        if isinstance(data, dict):
            out = {}
            for key, value in data.items():
                if is_secret_key(key) and value not in (None, "", {}, []):
                    out[key] = REDACTED
                else:
                    out[key] = redact_secrets(value, _depth + 1)
            return out
        if isinstance(data, (list, tuple)):
            items = [redact_secrets(v, _depth + 1) for v in data]
            return items if isinstance(data, list) else tuple(items)
        if isinstance(data, str):
            return redact_text(data)
        return data
    except Exception:  # noqa: BLE001 — redaction must never fail a log write
        return data


def mask_sensitive_data(data: Any, keys_to_mask: list = None) -> Any:
    """Mask sensitive data for logging purposes."""
    if keys_to_mask is None:
        keys_to_mask = [
            'password', 'api_key', 'secret', 'token', 'credential', 
            'auth', 'key', 'client_secret', 'access_token', 'refresh_token'
        ]
    
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            # Check if key contains sensitive terms
            if any(term in key.lower() for term in keys_to_mask):
                if isinstance(value, str) and len(value) > 4:
                    masked[key] = f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
                else:
                    masked[key] = "*" * len(str(value))
            elif isinstance(value, (dict, list)):
                masked[key] = mask_sensitive_data(value, keys_to_mask)
            else:
                masked[key] = value
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_data(item, keys_to_mask) for item in data]
    else:
        return data