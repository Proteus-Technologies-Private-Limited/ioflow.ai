"""
Shared sandboxed Jinja2 templating for service request/response templates.

Used by the api_call executor for:
  - request_config.body_jinja / query_jinja      (request templates)
  - response_config.output_jinja / error_jinja /
    success_jinja                                (response mapping)
and by the executor + OAuth2 manager for ``{{auth.<field>}}`` placeholders in
an application's base_url / auth_config.token_url.

Every template renders in a ``SandboxedEnvironment`` (no attribute access to
Python internals, no imports) with autoescape OFF — templates produce JSON,
not HTML — and a lenient ``ChainableUndefined`` so ``order.items[0].sku`` on a
missing branch renders as empty instead of raising half-way through a body.

The filters below are available in every template:
  tojson, to_float, to_int, iso8601, money, from_json, csv_list
"""
import json
import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from typing import Any, Dict, Optional

from jinja2 import ChainableUndefined, TemplateError, Undefined
from jinja2.sandbox import SandboxedEnvironment

logger = logging.getLogger(__name__)

# How much of a rendered template / response is quoted in an error message.
ERROR_EXCERPT_CHARS = 300


class TemplateRenderError(ValueError):
    """A service template failed to render or did not produce valid JSON."""


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _is_blank(value: Any) -> bool:
    return value is None or isinstance(value, Undefined) or (isinstance(value, str) and value.strip() == '')


def _json_default(obj: Any) -> Any:
    """json.dumps fallback: make template values serialisable."""
    if isinstance(obj, Undefined):
        return None
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (set, tuple)):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    return str(obj)


def filter_tojson(value: Any, indent: Optional[int] = None) -> str:
    """Serialise to JSON. Non-ASCII stays as-is (no \\uXXXX), no HTML escaping."""
    if isinstance(value, Undefined):
        value = None
    return json.dumps(value, ensure_ascii=False, default=_json_default, indent=indent)


def filter_to_float(value: Any, default: float = 0.0) -> float:
    """Number from anything: None/''/undefined -> default; '1,234.50' -> 1234.5."""
    if _is_blank(value):
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    try:
        return float(str(value).replace(',', '').strip())
    except (TypeError, ValueError):
        logger.warning(f"to_float: cannot convert {str(value)[:100]!r}; using default {default!r}")
        return default


def filter_to_int(value: Any, default: int = 0) -> int:
    """Integer from anything (truncates '3.0' -> 3); blank/invalid -> default."""
    if _is_blank(value):
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value) if isinstance(value, int) else int(float(str(value).replace(',', '').strip()))
    except (TypeError, ValueError, OverflowError):
        logger.warning(f"to_int: cannot convert {str(value)[:100]!r}; using default {default!r}")
        return default


def _to_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if dt.microsecond:
        return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f"{dt.microsecond // 1000:03d}Z"
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def filter_iso8601(value: Any, default: Any = None) -> Any:
    """Normalise a datetime / date / ISO string / epoch (s or ms) to ISO-8601 UTC 'Z'.

    Naive values are taken as UTC. Blank -> default. Unparseable -> default when
    one is given, otherwise the original value (logged) so data is not lost.
    """
    if _is_blank(value):
        return default
    try:
        if isinstance(value, datetime):
            return _to_utc_z(value)
        if isinstance(value, date):
            return _to_utc_z(datetime(value.year, value.month, value.day))
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            seconds = float(value)
            if abs(seconds) > 1e11:  # epoch milliseconds
                seconds /= 1000.0
            return _to_utc_z(datetime.fromtimestamp(seconds, tz=timezone.utc))
        text = str(value).strip()
        if re.fullmatch(r'-?\d+(\.\d+)?', text):
            return filter_iso8601(float(text), default)
        normalised = text.replace('Z', '+00:00').replace('z', '+00:00')
        # "2026-09-30 10:00:00" and "2026-09-30T10:00:00+0530" forms
        normalised = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', normalised)
        return _to_utc_z(datetime.fromisoformat(normalised))
    except (ValueError, OverflowError, OSError) as e:
        logger.warning(f"iso8601: cannot parse {str(value)[:100]!r}: {e}")
        return default if default is not None else value


def filter_money(value: Any, default: str = '0.00') -> str:
    """Format as a 2-decimal string (half-up): 12.5 -> '12.50'. Blank/invalid -> default."""
    if _is_blank(value):
        return default
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value).replace(',', '').strip())
        return str(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"money: cannot convert {str(value)[:100]!r}; using default {default!r}")
        return default


def filter_from_json(value: Any, default: Any = None) -> Any:
    """Parse a JSON string. A dict/list passes through.

    None / '' / undefined / invalid JSON -> ``default`` ({} when no default given);
    invalid JSON is logged with the first 200 chars.
    """
    fallback = {} if default is None else default
    if isinstance(value, (dict, list)):
        return value
    if _is_blank(value):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError) as e:
        logger.warning(f"from_json: invalid JSON ({e}); value starts {str(value)[:200]!r}")
        return fallback


def filter_csv_list(value: Any) -> list:
    """'a, b,,c' -> ['a', 'b', 'c']; a list/tuple passes through; blank -> []."""
    if isinstance(value, (list, tuple)):
        return list(value)
    if _is_blank(value):
        return []
    return [part.strip() for part in str(value).split(',') if part.strip()]


FILTERS = {
    'tojson': filter_tojson,
    'to_float': filter_to_float,
    'to_int': filter_to_int,
    'iso8601': filter_iso8601,
    'money': filter_money,
    'from_json': filter_from_json,
    'csv_list': filter_csv_list,
}


# ---------------------------------------------------------------------------
# Environment + rendering
# ---------------------------------------------------------------------------

def _build_environment() -> SandboxedEnvironment:
    env = SandboxedEnvironment(autoescape=False, undefined=ChainableUndefined,
                               keep_trailing_newline=False)
    env.filters.update(FILTERS)
    env.policies['json.dumps_kwargs'] = {'ensure_ascii': False, 'sort_keys': False}
    return env


_ENV = _build_environment()


@lru_cache(maxsize=512)
def _compile(template_str: str):
    return _ENV.from_string(template_str)


def now_iso() -> str:
    """Current UTC time as ISO-8601 with 'Z'."""
    return _to_utc_z(datetime.now(timezone.utc).replace(microsecond=0))


def excerpt(value: Any, limit: int = ERROR_EXCERPT_CHARS) -> str:
    """First ``limit`` chars of a value for an error message."""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False, default=_json_default)
        except Exception:
            text = str(value)
    else:
        text = '' if value is None else str(value)
    return text[:limit]


def render_template(template_str: str, context: Dict[str, Any], purpose: str) -> str:
    """Render a template string in the sandbox. Raises TemplateRenderError."""
    if not isinstance(template_str, str):
        raise TemplateRenderError(f"{purpose} must be a string template, got {type(template_str).__name__}")
    try:
        return _compile(template_str).render(**context)
    except TemplateError as e:
        location = f" (line {e.lineno})" if getattr(e, 'lineno', None) else ''
        raise TemplateRenderError(f"{purpose} template error{location}: {e}") from e
    except Exception as e:  # filters / sandbox SecurityError / arithmetic on bad data
        raise TemplateRenderError(f"{purpose} failed to render: {type(e).__name__}: {e}") from e


def render_json(template_str: str, context: Dict[str, Any], purpose: str) -> Any:
    """Render a template and parse the output as JSON.

    Returns None when the rendered text is empty/whitespace. Raises
    TemplateRenderError (with the JSON error position and the first 300 chars
    of the rendered text) when it is not valid JSON.
    """
    rendered = render_template(template_str, context, purpose)
    if not rendered or not rendered.strip():
        return None
    try:
        return json.loads(rendered)
    except json.JSONDecodeError as e:
        raise TemplateRenderError(
            f"{purpose} did not render valid JSON ({e.msg} at line {e.lineno} column {e.colno}, "
            f"char {e.pos}). Rendered text starts: {rendered[:ERROR_EXCERPT_CHARS]!r}"
        ) from e


def render_bool(template_str: str, context: Dict[str, Any], purpose: str) -> bool:
    """Render a template expected to produce true/false (JSON or common words)."""
    rendered = render_template(template_str, context, purpose).strip()
    lowered = rendered.lower()
    if lowered in ('true', '1', 'yes'):
        return True
    if lowered in ('false', '0', 'no', '', 'null', 'none'):
        return False
    raise TemplateRenderError(
        f"{purpose} must render true or false, got: {rendered[:ERROR_EXCERPT_CHARS]!r}")


# ---------------------------------------------------------------------------
# {{auth.<field>}} placeholders (base_url, token_url, endpoint_template)
# ---------------------------------------------------------------------------

AUTH_PLACEHOLDER_RE = re.compile(r'\{\{\s*auth\.([A-Za-z0-9_.\-]+)\s*\}\}')


def has_auth_placeholders(text: Any) -> bool:
    return isinstance(text, str) and bool(AUTH_PLACEHOLDER_RE.search(text))


# `{var}` subscription_config placeholders in an application base_url — single
# braces only. `{{auth.<field>}}` (rendered per call from the connection's
# credentials) must not be read as a config variable named "{auth.<field>".
CONFIG_PLACEHOLDER_RE = re.compile(r'(?<!\{)\{([^{}]+)\}(?!\})')


def config_placeholders(text: Any) -> list:
    """Names of the single-brace ``{var}`` placeholders in ``text`` (in order)."""
    if not isinstance(text, str):
        return []
    return [m.group(1).strip() for m in CONFIG_PLACEHOLDER_RE.finditer(text)]


def fill_config_placeholders(text: str, values: Dict[str, Any]) -> str:
    """Replace single-brace ``{var}`` placeholders from ``values``; leaves
    ``{{auth.*}}`` and unknown names untouched."""
    if not isinstance(text, str):
        return text

    def _one(match):
        name = match.group(1).strip()
        return str(values[name]) if name in (values or {}) else match.group(0)
    return CONFIG_PLACEHOLDER_RE.sub(_one, text)


def missing_auth_fields(text: Any, credentials: Optional[Dict[str, Any]]) -> list:
    """``{{auth.<field>}}`` placeholders in ``text`` the credentials leave blank."""
    if not has_auth_placeholders(text):
        return []
    missing = []
    for match in AUTH_PLACEHOLDER_RE.finditer(text):
        value = _resolve_dotted(credentials or {}, match.group(1))
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(match.group(1))
    return sorted(set(missing))


def _resolve_dotted(data: Any, path: str) -> Any:
    current = data
    for part in path.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def render_auth_placeholders(text: str, credentials: Optional[Dict[str, Any]], what: str,
                             encode: bool = False) -> str:
    """Replace ``{{auth.<field>}}`` in ``text`` with subscription credential values.

    A placeholder whose credential is missing or blank raises TemplateRenderError
    naming the field — a half-rendered URL would otherwise be sent to a wrong
    host. ``encode`` URL-encodes the substituted value (path segments).
    """
    if not has_auth_placeholders(text):
        return text
    credentials = credentials or {}
    missing = []

    def _replace(match):
        field = match.group(1)
        value = _resolve_dotted(credentials, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
            return match.group(0)
        value = str(value).strip()
        if encode:
            from urllib.parse import quote
            value = quote(value, safe='')
        return value

    rendered = AUTH_PLACEHOLDER_RE.sub(_replace, text)
    if missing:
        fields = ', '.join(sorted(set(missing)))
        raise TemplateRenderError(
            f"{what} needs the connection credential field(s) {fields}, which are not set on this "
            f"subscription. Edit the connection and fill in: {fields}.")
    return rendered
