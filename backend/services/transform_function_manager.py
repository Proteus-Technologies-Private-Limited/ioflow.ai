"""
Transform Function Manager - Handles validation and injection of external functions for transform nodes

This module provides utilities to:
- Validate Python function syntax
- Check function definitions
- Inject functions into transform node scripts
"""

import ast
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TransformFunctionManager:
    """Manages external functions for transform nodes"""

    @staticmethod
    def validate_function(func_name: str, func_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a single Python function.

        Args:
            func_name: The expected function name
            func_code: The Python code as plain text

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Parse the Python code
            tree = ast.parse(func_code)
        except SyntaxError as e:
            # Log the actual function code for debugging
            logger.error(f"Syntax error in function '{func_name}': {e}")
            logger.error(f"Function code length: {len(func_code)} chars")
            logger.error(f"First 200 chars of function: {func_code[:200]}")

            # Log the specific line with the error
            lines = func_code.split('\n')
            error_msg = f"Syntax error in function '{func_name}': {e}"

            if e.lineno and e.lineno <= len(lines):
                error_line = lines[e.lineno - 1]
                logger.error(f"Error at line {e.lineno}: {error_line}")

                # Check for common issues and provide helpful messages
                if '\\n' in func_code:
                    logger.error("Found literal \\n in function code (not properly unescaped)")
                if '\\"' in func_code or "\\'" in func_code:
                    logger.error("Found escaped quotes in function code")
                if '"""' in func_code and '\\"' in func_code:
                    logger.error("Mixed quote escaping detected")

                # Check for multiline string issue
                if "unterminated string literal" in str(e):
                    # Check if the error line looks like it's trying to use parentheses for multiline
                    if '= (' in error_line and ('"' in error_line or "'" in error_line):
                        error_msg += (
                            "\n\nHint: It looks like you're trying to create a multiline string using "
                            "parentheses. Use triple quotes instead:\n"
                            "    Wrong: body = (\"Hello,\\n...\")\n"
                            "    Right: body = \"\"\"Hello,\\n...\"\"\""
                        )
                        logger.info("Detected likely multiline string issue - added helpful hint")

            return False, error_msg

        # Validate with RestrictedPython compiler
        try:
            from RestrictedPython import compile_restricted_exec

            # Compile the function code with RestrictedPython
            compiled = compile_restricted_exec(
                source=func_code,
                filename=f'<function_{func_name}>',
                dont_inherit=True
            )

            # Check for compilation errors
            if compiled.errors:
                error_msg = "; ".join(compiled.errors)
                return False, f"RestrictedPython compilation error in '{func_name}': {error_msg}"

            # Check for warnings (these don't fail validation but should be noted)
            if compiled.warnings:
                # Log warnings but don't fail validation
                for warning in compiled.warnings:
                    logger.warning(f"RestrictedPython warning in '{func_name}': {warning}")

        except ImportError:
            # If RestrictedPython is not available, skip this check
            # This allows testing without the full environment
            logger.debug("RestrictedPython not available, skipping compilation check")
        except Exception as e:
            return False, f"RestrictedPython validation error in '{func_name}': {str(e)}"

        # Check if the function is actually defined
        function_defs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

        if not function_defs:
            return False, f"No function definition found in code for '{func_name}'"

        # Check if the expected function name is defined
        function_names = [func.name for func in function_defs]
        if func_name not in function_names:
            return False, f"Function '{func_name}' not found. Found: {', '.join(function_names)}"

        # Validate that there are no dangerous operations
        for node in ast.walk(tree):
            # Check for dangerous imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ['os', 'sys', 'subprocess', 'eval', 'exec', '__builtin__', '__builtins__']:
                        return False, f"Import of '{alias.name}' is not allowed in transform functions"

            if isinstance(node, ast.ImportFrom):
                if node.module and node.module in ['os', 'sys', 'subprocess']:
                    return False, f"Import from '{node.module}' is not allowed in transform functions"

            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'compile', '__import__', 'open']:
                        return False, f"Call to '{node.func.id}' is not allowed in transform functions"

        return True, None

    @staticmethod
    def validate_functions(functions: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate a dictionary of functions.

        Args:
            functions: Dictionary of function_name -> python_code

        Returns:
            Tuple of (all_valid, list_of_errors)
        """
        if not functions:
            return True, []

        errors = []
        for func_name, func_code in functions.items():
            is_valid, error_msg = TransformFunctionManager.validate_function(func_name, func_code)
            if not is_valid:
                errors.append(error_msg)

        return len(errors) == 0, errors

    @staticmethod
    def inject_functions(script: str, functions_used: List[str], functions_dict: Dict[str, str]) -> str:
        """
        Inject external functions into a transform node script.

        Args:
            script: The transform node script
            functions_used: List of function names used by the script
            functions_dict: Dictionary of all available functions

        Returns:
            The combined script with functions prepended
        """
        if not functions_used or not functions_dict:
            return script

        # Collect the required functions
        function_definitions = []
        for func_name in functions_used:
            if func_name in functions_dict:
                func_code = functions_dict[func_name]
                # Add the function definition
                function_definitions.append(func_code)
                # Add a blank line after each function for readability
                function_definitions.append("")

        if not function_definitions:
            return script

        # Combine functions with the script
        combined = "\n".join(function_definitions) + "\n" + script
        return combined

    @staticmethod
    def extract_function_calls(script: str) -> List[str]:
        """
        Extract function calls from a script to help identify which functions are used.
        This is a helper method for validation.

        Args:
            script: The Python script to analyze

        Returns:
            List of function names that are called in the script
        """
        try:
            tree = ast.parse(script)
            function_calls = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        function_calls.add(node.func.id)

            return list(function_calls)
        except SyntaxError:
            # If script has syntax errors, return empty list
            return []

    @staticmethod
    def validate_script_with_functions(script: str, functions_used: List[str], functions_dict: Dict[str, str]) -> Tuple[bool, Optional[str]]:
        """
        Validate that a script with injected functions will work correctly.

        Args:
            script: The transform node script
            functions_used: List of function names the script claims to use
            functions_dict: Dictionary of available functions

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check that all required functions are available
        for func_name in functions_used:
            if func_name not in functions_dict:
                return False, f"Function '{func_name}' is referenced but not provided"

        # Create the combined script
        combined_script = TransformFunctionManager.inject_functions(script, functions_used, functions_dict)

        # Validate the combined script syntax
        try:
            ast.parse(combined_script)
        except SyntaxError as e:
            return False, f"Syntax error in combined script: {e}"

        # Optionally check if the script actually calls the functions it claims to use
        actual_calls = TransformFunctionManager.extract_function_calls(script)
        for func_name in functions_used:
            if func_name not in actual_calls:
                logger.warning(f"Function '{func_name}' is listed in functions_used but not called in script")

        return True, None

    @staticmethod
    def inject_functions_into_flow(flow_definition: dict, functions: Dict[str, str]) -> dict:
        """
        Inject external functions into all transform nodes in a flow definition.

        Args:
            flow_definition: The flow definition dictionary with nodes and edges
            functions: Dictionary of function_name -> python_code

        Returns:
            Modified flow definition with functions injected into transform nodes
        """
        if not functions or 'nodes' not in flow_definition:
            return flow_definition

        # Process each node
        for node in flow_definition.get('nodes', []):
            if node.get('type') == 'transform':
                data = node.get('data', {})
                script = data.get('script', '')
                functions_used = data.get('functions_used', [])

                if script and functions_used:
                    # Inject the functions into the script
                    combined_script = TransformFunctionManager.inject_functions(
                        script, functions_used, functions
                    )
                    # Update the node's script
                    data['script'] = combined_script
                    # Remove functions_used as they're now embedded
                    data.pop('functions_used', None)

        return flow_definition