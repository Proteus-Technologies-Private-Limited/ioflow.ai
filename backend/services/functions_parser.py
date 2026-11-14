"""
Functions Parser - Parses Python function definitions from plain Python code.

This module handles parsing of functions that come from the agent as plain Python code blocks.
Dictionary and JSON formats are NOT supported.
"""

import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_python_code_block(text: str) -> Dict[str, str]:
    """
    Parse a string containing plain Python code with function definitions.

    Expected format: Plain Python code with one or more function definitions.
    Example:
        def func1(input):
            return result

        def func2(input):
            return output

    Args:
        text: String containing Python code with function definitions

    Returns:
        Dictionary mapping function names to their Python code
    """
    import ast
    functions = {}

    if not text or not text.strip():
        return functions

    try:
        # Parse the Python code to get accurate function boundaries
        tree = ast.parse(text)
        lines = text.split('\n')

        # Extract function definitions using AST boundaries
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                start_line = node.lineno - 1  # Convert to 0-indexed

                # Use end_lineno if available (Python 3.8+)
                if hasattr(node, 'end_lineno') and node.end_lineno:
                    end_line = node.end_lineno
                else:
                    # Fallback: find the next function or end of file
                    end_line = len(lines)
                    for other_node in tree.body:
                        if isinstance(other_node, ast.FunctionDef) and other_node.lineno > node.lineno:
                            end_line = min(end_line, other_node.lineno - 1)
                            break

                # Extract the function code
                func_lines = lines[start_line:end_line]
                func_code = '\n'.join(func_lines).rstrip()
                functions[func_name] = func_code

                logger.debug(f"Extracted function '{func_name}': lines {start_line + 1}-{end_line}")

        logger.info(f"Extracted {len(functions)} functions from Python code block using AST")
        return functions

    except SyntaxError as e:
        logger.error(f"Syntax error in Python code at line {e.lineno}: {e}")

        # Check if this might be due to truncation
        if e.msg and 'EOF' in e.msg:
            logger.error("Code appears to be truncated (unexpected EOF)")
        elif e.lineno:
            lines = text.split('\n')
            if e.lineno <= len(lines):
                error_line = lines[e.lineno - 1]
                logger.error(f"Error line content: {repr(error_line[:100])}")

        # Even with syntax error, try to extract what we can
        # This helps with debugging and partial recovery
        logger.info("Attempting simple extraction despite syntax errors")
        return extract_functions_simple(text)
    except Exception as e:
        logger.error(f"Error parsing Python code block: {e}")
        return extract_functions_simple(text)


def extract_functions_simple(text: str) -> Dict[str, str]:
    """
    Simple extraction that doesn't require valid Python syntax.
    Used as fallback when AST parsing fails.
    """
    import re
    functions = {}
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this line starts a function definition
        if line.strip().startswith('def '):
            # Extract function name
            match = re.match(r'def\s+(\w+)\s*\(', line.strip())
            if not match:
                i += 1
                continue

            func_name = match.group(1)
            func_lines = [line]
            base_indent = len(line) - len(line.lstrip())

            # Collect all lines belonging to this function
            i += 1
            while i < len(lines):
                if i >= len(lines):
                    break

                next_line = lines[i]

                # Empty lines are included
                if not next_line.strip():
                    func_lines.append(next_line)
                    i += 1
                    continue

                # Check indentation
                next_indent = len(next_line) - len(next_line.lstrip())

                # If indentation is greater than base, it's part of the function
                if next_indent > base_indent:
                    func_lines.append(next_line)
                    i += 1
                else:
                    # We've reached the end of this function
                    break

            # Store the complete function
            func_code = '\n'.join(func_lines).rstrip()
            functions[func_name] = func_code
        else:
            i += 1

    return functions


def parse_python_functions_dict(text: str) -> Dict[str, str]:
    """
    Parse a string containing Python function definitions.

    ONLY accepts plain Python code blocks with function definitions.
    Dictionary and JSON formats are NOT supported and will return an error.

    Args:
        text: String containing Python functions as plain Python code

    Returns:
        Dictionary mapping function names to their Python code
        OR
        Dictionary with error key if wrong format is detected
    """
    functions = {}

    if not text or not text.strip():
        logger.warning("Empty or None functions string provided")
        return functions

    # Log the input for debugging
    logger.info(f"Parsing functions string of length {len(text)} characters")

    # Remove leading/trailing whitespace
    text = text.strip()

    # Check if the text appears to be truncated
    if text and not text.rstrip().endswith(('}', ')', '"', "'", '\n')):
        # Last line doesn't end with typical Python endings
        last_line = text.split('\n')[-1] if '\n' in text else text[-50:]
        logger.warning(f"Functions string may be truncated. Last line: {repr(last_line)}")

    # Check if this appears to be dictionary or JSON format (which is NOT allowed)
    if text.startswith('{') and text.endswith('}'):
        logger.error("Functions provided in dictionary/JSON format instead of plain Python code block")
        # Return error that will be caught by validation
        return {
            '__error__': 'Functions must be provided as plain Python code block, not as dictionary or JSON format. Expected format: def function_name(input): ...'
        }

    # Check for other dictionary-like patterns
    if text.startswith("{'") or text.startswith('{"') or '": def ' in text or "': def " in text:
        logger.error("Functions appear to be in dictionary format instead of plain Python code")
        return {
            '__error__': 'Functions must be provided as plain Python code block, not wrapped in dictionary. Expected format: def function_name(input): ...'
        }

    # Only accept plain Python code
    logger.info("Processing as plain Python code block")
    result = parse_python_code_block(text)

    # Log parsing results
    if result:
        logger.info(f"Successfully parsed {len(result)} functions: {list(result.keys())}")
        for func_name, func_code in result.items():
            logger.debug(f"Function '{func_name}' - {len(func_code)} characters")
    else:
        logger.warning("No functions could be parsed from the provided string")

    return result


def unescape_python_string(s: str) -> str:
    """
    Unescape a Python string that has escaped characters.
    Converts \\n to newline, \\t to tab, etc.
    """
    # Replace escaped characters
    replacements = [
        ('\\n', '\n'),
        ('\\r', '\r'),
        ('\\t', '\t'),
        ('\\\\', '\\'),
        ('\\"', '"'),
        ("\\'", "'")
    ]

    result = s
    for escaped, unescaped in replacements:
        result = result.replace(escaped, unescaped)

    return result


def fix_multiline_string_issues(func_code: str) -> str:
    """
    Fix common multiline string issues in Python code.

    Detects patterns like:
        body = ("Hello,
        ...
        ")

    And converts them to use triple quotes for proper multiline strings.

    Args:
        func_code: Python function code that may have multiline string issues

    Returns:
        Fixed Python code with proper multiline string syntax
    """
    import re

    # Pattern to detect problematic multiline strings with parentheses
    # Matches: variable = ("string that spans
    # multiple lines")
    pattern = r'(\w+\s*=\s*\()(["\'])([^"\')]*?)\n([^"\')]*?)(\2)\)'

    def replace_with_triple_quotes(match):
        var_part = match.group(1)[:-1]  # Remove the opening parenthesis
        quote_char = match.group(2)
        content = match.group(3) + '\n' + match.group(4)

        # Use triple quotes
        triple_quote = quote_char * 3

        logger.debug(f"Fixing multiline string: {var_part}{triple_quote}...")
        return f"{var_part}{triple_quote}{content}{triple_quote}"

    # Apply the fix
    fixed_code = re.sub(pattern, replace_with_triple_quotes, func_code, flags=re.MULTILINE)

    if fixed_code != func_code:
        logger.info("Fixed multiline string issue in function code")

    return fixed_code


def validate_function_name_match(func_name: str, func_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that the function code actually defines a function with the expected name.

    Args:
        func_name: Expected function name
        func_code: Python code that should define the function

    Returns:
        Tuple of (is_valid, error_message)
    """
    import ast

    try:
        tree = ast.parse(func_code)
    except SyntaxError as e:
        return False, f"Syntax error in function code: {e}"

    # Find all function definitions
    function_defs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

    if not function_defs:
        return False, "No function definition found in the code"

    # Check if the expected function name is defined
    defined_names = [f.name for f in function_defs]
    if func_name not in defined_names:
        return False, f"Expected function '{func_name}' not found. Found: {', '.join(defined_names)}"

    return True, None