"""
Patch for handling malformed JSON in LLM tool calls

LLM models sometimes return malformed JSON in function arguments when
passing large nested JSON strings, causing JSONDecodeError. This patch
provides clear error reporting without attempting auto-fixes.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def get_json_error_context(json_string: str, error: json.JSONDecodeError) -> Dict[str, str]:
    """
    Extract context around a JSON parsing error for better debugging.

    Args:
        json_string: The malformed JSON string
        error: The JSONDecodeError that occurred

    Returns:
        Dictionary with error context including before/after snippets
    """
    context = {
        "error_msg": str(error),
        "error_type": error.__class__.__name__,
        "position": f"line {error.lineno}, column {error.colno}" if hasattr(error, 'lineno') else "unknown"
    }

    # Show first and last 200 chars
    if len(json_string) > 400:
        context["preview_start"] = json_string[:200] + "..."
        context["preview_end"] = "..." + json_string[-200:]
    else:
        context["preview_start"] = json_string
        context["preview_end"] = ""

    # Try to extract the problematic area if we have position info
    if hasattr(error, 'pos') and error.pos:
        start = max(0, error.pos - 100)
        end = min(len(json_string), error.pos + 100)

        before = json_string[start:error.pos]
        after = json_string[error.pos:end]

        context["before_error"] = ("..." if start > 0 else "") + before
        context["after_error"] = after + ("..." if end < len(json_string) else "")
        context["error_char"] = json_string[error.pos] if error.pos < len(json_string) else "EOF"

    return context

def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """
    Safely parse JSON with detailed error reporting - NO AUTO-FIXING.

    Args:
        json_string: The JSON string to parse
        default: Default value to return on error

    Returns:
        Parsed JSON or default value with error logged
    """
    if not json_string:
        return default or {}

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        # Get detailed error context
        error_context = get_json_error_context(json_string, e)

        logger.error("=" * 80)
        logger.error("MALFORMED JSON IN TOOL CALL ARGUMENTS")
        logger.error("=" * 80)
        logger.error(f"Error: {error_context['error_msg']}")
        logger.error(f"Position: {error_context['position']}")
        logger.error("")
        logger.error("First 200 characters:")
        logger.error(error_context['preview_start'])
        logger.error("")
        logger.error("Last 200 characters:")
        logger.error(error_context['preview_end'])

        if 'before_error' in error_context:
            logger.error("")
            logger.error("Context around error:")
            logger.error(f"BEFORE: {error_context['before_error']}")
            logger.error(f"  ERROR AT: '{error_context['error_char']}'")
            logger.error(f"AFTER:  {error_context['after_error']}")

        logger.error("=" * 80)

        # TARGETED FIX: Try to extract flow_json parameter if this is the specific pattern we see with DeepSeek
        # This is ONLY for the pattern: {"flow_json": "...unescaped json..."}
        # The error can be either "Unterminated string" or "Invalid control character" (newlines)
        if ('{"flow_json": "' in json_string and
            ('Unterminated string' in str(e) or 'Invalid control character' in str(e))):
            logger.error("ATTEMPTING TARGETED EXTRACTION for flow_json parameter...")
            try:
                # The issue: DeepSeek is trying to pass raw JSON in a string but not escaping it
                # Pattern looks like: {"flow_json": "{\n  "version": "1.0.0"...}"}
                # The inner JSON has literal newlines and unescaped quotes

                # Strategy: Extract everything between 'flow_json": ' and the end of the outer JSON
                start_marker = '"flow_json": "'
                start_idx = json_string.index(start_marker) + len(start_marker)

                # Find the actual JSON content
                # Look for the starting { of the actual flow JSON
                if json_string[start_idx:start_idx+1] == '{':
                    # Now we need to find the matching closing brace
                    # Count braces to find the end of the flow JSON
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    extracted_end = -1

                    for i in range(start_idx, len(json_string)):
                        char = json_string[i]

                        if escape_next:
                            escape_next = False
                            continue

                        if char == '\\':
                            escape_next = True
                            continue

                        if char == '"' and not in_string:
                            in_string = True
                        elif char == '"' and in_string:
                            in_string = False
                        elif not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    # Found the end of the flow JSON
                                    extracted_end = i + 1
                                    break

                    if extracted_end > start_idx:
                        extracted_json = json_string[start_idx:extracted_end]

                        # The extracted JSON has literal newlines - it's actually valid JSON
                        # but was incorrectly embedded in the outer JSON string
                        try:
                            # Try to parse it to validate
                            parsed = json.loads(extracted_json)

                            # Success! Return the properly extracted flow_json
                            logger.error(f"SUCCESSFULLY EXTRACTED flow_json (length: {len(extracted_json)} chars)")
                            logger.error("The issue was that the LLM passed raw JSON without escaping it properly")
                            logger.error("=" * 80)
                            return {"flow_json": extracted_json}

                        except json.JSONDecodeError as parse_error:
                            logger.error(f"Extracted JSON still not valid: {parse_error}")
                            # Try one more thing - the JSON might have actual newlines that need to be preserved
                            # This happens when the agent outputs a code block
                            logger.error("Extracted JSON preview (first 500 chars):")
                            logger.error(extracted_json[:500])
                    else:
                        logger.error(f"Could not find matching closing brace. Brace count ended at: {brace_count}")

            except Exception as extraction_error:
                logger.error(f"Extraction attempt failed: {extraction_error}")

            logger.error("TARGETED EXTRACTION FAILED - returning empty args")
        else:
            logger.error("NOTE: This is likely caused by the LLM trying to pass a large")
            logger.error("JSON string as a function parameter, which creates nested JSON")
            logger.error("that cannot be properly escaped. The function will receive")
            logger.error("empty args and should handle this gracefully.")

        logger.error("=" * 80)

        # Return default - DO NOT try to fix (except for targeted extraction above)
        return default or {}

def patch_litellm_json_parsing():
    """
    Monkey patch the LiteLLM JSON parsing to provide clear error reporting.
    This is model-agnostic and applies to all LLMs that use Google ADK + LiteLLM.
    """
    try:
        import google.adk.models.lite_llm as lite_llm

        # Save original function
        original_message_to_response = lite_llm._message_to_generate_content_response

        def patched_message_to_generate_content_response(message, *, is_partial=False, **kwargs):
            """
            Patched version that handles malformed JSON in tool calls.
            ADK 1.22+ uses keyword-only arguments after message.
            Accepts **kwargs for forward compatibility with new ADK versions.
            """
            # Handle tool calls with safe JSON parsing
            # Check if message has tool_calls attribute (object) or is a dict
            tool_calls = None
            if hasattr(message, 'tool_calls'):
                tool_calls = message.tool_calls
            elif isinstance(message, dict) and message.get("tool_calls"):
                tool_calls = message.get("tool_calls")

            if tool_calls:
                patched_tool_calls = []
                for tool_call in tool_calls:
                    tc_type = getattr(tool_call, 'type', None) or (tool_call.get('type') if isinstance(tool_call, dict) else None)
                    if tc_type == "function":
                        # Get function info
                        if hasattr(tool_call, 'function'):
                            func = tool_call.function
                            func_name = getattr(func, 'name', 'unknown')
                            raw_args = getattr(func, 'arguments', '{}') or '{}'
                            tc_id = getattr(tool_call, 'id', 'unknown')
                        elif isinstance(tool_call, dict):
                            func = tool_call.get('function', {})
                            func_name = func.get('name', 'unknown')
                            raw_args = func.get('arguments', '{}') or '{}'
                            tc_id = tool_call.get('id', 'unknown')
                        else:
                            continue

                        # LOG IMMEDIATELY - BEFORE ANY PROCESSING
                        logger.info("=" * 80)
                        logger.info(f"🔍 RAW TOOL CALL from LLM: {func_name}")
                        logger.info(f"   Raw arguments length: {len(raw_args)} characters")
                        logger.info(f"   Raw arguments first 200 chars: {raw_args[:200]}")
                        logger.info(f"   Raw arguments last 200 chars: {raw_args[-200:]}")
                        logger.info("=" * 80)

                        try:
                            # Try normal parsing first
                            args = json.loads(raw_args)
                            logger.info(f"✓ Successfully parsed tool call {func_name} args (keys: {list(args.keys())})")
                        except json.JSONDecodeError as e:
                            logger.error(f"✗ LLM returned malformed JSON in tool call {func_name}: {e}")
                            logger.error(f"   Error position: {e.pos if hasattr(e, 'pos') else 'unknown'}")
                            # Use safe parsing with detailed error reporting
                            args = safe_json_loads(raw_args, {})
                            logger.info(f"   After safe_json_loads, args keys: {list(args.keys())}")
                            if args:
                                logger.info(f"   Tool call will receive args: {args if not args.get('flow_json') else {k: f'<{len(v)} chars>' if k == 'flow_json' else v for k, v in args.items()}}")
                            else:
                                logger.error(f"   ⚠️  EXTRACTION FAILED - tool will receive empty args!")

                        # Create a new tool call with the parsed args
                        patched_tool_calls.append({
                            "type": "function",
                            "id": tc_id,
                            "function": {
                                "name": func_name,
                                "arguments": json.dumps(args)  # Re-stringify the parsed args
                            }
                        })

                # Create a modified message with patched tool calls
                if patched_tool_calls:
                    # Create a new message dict with patched tool calls
                    import copy
                    patched_message = copy.deepcopy(message)

                    # Replace tool_calls with our patched version
                    class PatchedToolCall:
                        def __init__(self, tc_dict):
                            self.type = tc_dict["type"]
                            self.id = tc_dict["id"]
                            self.function = type('obj', (object,), {
                                "name": tc_dict["function"]["name"],
                                "arguments": tc_dict["function"]["arguments"]
                            })

                    if hasattr(patched_message, 'tool_calls'):
                        patched_message.tool_calls = [PatchedToolCall(tc) for tc in patched_tool_calls]
                    elif isinstance(patched_message, dict):
                        patched_message["tool_calls"] = [PatchedToolCall(tc) for tc in patched_tool_calls]

                    # Call original with patched message - use keyword arguments
                    return original_message_to_response(patched_message, is_partial=is_partial, **kwargs)

            # No tool calls or no issues - call original with keyword arguments
            return original_message_to_response(message, is_partial=is_partial, **kwargs)

        # Apply the patch
        lite_llm._message_to_generate_content_response = patched_message_to_generate_content_response
        logger.info("Successfully patched LiteLLM JSON parsing for better error reporting")
        return True

    except Exception as e:
        logger.error(f"Failed to patch LiteLLM JSON parsing: {e}")
        return False

def apply_json_error_handling_patches():
    """
    Apply JSON error handling patches for all LLM models.
    This is model-agnostic and provides clear error reporting when
    LLMs generate malformed JSON in tool call arguments.
    """
    success = patch_litellm_json_parsing()
    if success:
        logger.info("JSON error handling patches applied successfully (model-agnostic)")
    else:
        logger.warning("Could not apply JSON error handling patches")
    return success