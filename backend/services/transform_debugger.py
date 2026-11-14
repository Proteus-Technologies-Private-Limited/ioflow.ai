"""
Transform Debugger - Line-by-line debugging for transform nodes

This module enables step-by-step debugging of transform scripts with:
- Line-by-line execution
- Variable inspection at each step
- Breakpoint support
- State preservation between steps
"""

import ast
import sys
import time
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from RestrictedPython import compile_restricted_exec, PrintCollector
from RestrictedPython.Guards import guarded_iter_unpack_sequence, full_write_guard, safer_getattr

logger = logging.getLogger(__name__)


@dataclass
class DebugFrame:
    """Represents a debug frame with execution state"""
    line_no: int
    code: str
    locals: Dict[str, Any] = field(default_factory=dict)
    globals: Dict[str, Any] = field(default_factory=dict)
    stack: List[Any] = field(default_factory=list)
    
    
@dataclass 
class TransformDebugState:
    """Complete debug state for a transform execution"""
    execution_id: str
    node_id: str
    script: str
    lines: List[str]
    current_line: int = 0
    breakpoints: Set[int] = field(default_factory=set)
    frames: List[DebugFrame] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    status: str = "initialized"  # initialized, running, paused, completed, error
    error: Optional[str] = None
    execution_globals: Dict[str, Any] = field(default_factory=dict)
    execution_locals: Dict[str, Any] = field(default_factory=dict)
    executed_lines: Set[int] = field(default_factory=set)  # Track which lines have been executed
    
    # AST tracking
    ast_tree: Optional[ast.Module] = None
    line_to_ast: Dict[int, ast.AST] = field(default_factory=dict)
    

class TransformDebugger:
    """Debugger for transform scripts with line-by-line execution"""
    
    # Maximum execution time per line in seconds
    MAX_LINE_EXECUTION_TIME = 1.0
    
    # Maximum number of lines to execute
    MAX_LINES = 1000
    
    def __init__(self):
        """Initialize the transform debugger"""
        self.debug_sessions: Dict[str, TransformDebugState] = {}
        
    def create_debug_session(
        self, 
        execution_id: str,
        node_id: str, 
        script: str,
        context: Dict[str, Any]
    ) -> TransformDebugState:
        """
        Create a new debug session for a transform script
        
        Args:
            execution_id: Execution ID
            node_id: Node ID
            script: Transform script to debug
            context: Execution context with variables
            
        Returns:
            Debug state for the session
        """
        # Parse script into lines
        lines = script.splitlines()
        
        # Parse AST for better code understanding
        try:
            ast_tree = ast.parse(script)
            line_to_ast = self._build_line_to_ast_map(ast_tree)
        except SyntaxError as e:
            logger.error(f"Failed to parse script: {e}")
            ast_tree = None
            line_to_ast = {}
        
        # Create safe built-ins (similar to TransformExecutor)
        safe_builtins = self._create_safe_builtins()
        
        # We'll update safe_builtins['__import__'] after exec_globals is created
        
        # Create a PrintCollector for safe print functionality
        print_collector = PrintCollector()
        
        # Pre-import allowed modules to make them available
        # Phase 1: Time and date modules
        import base64 as base64_module
        import uuid as uuid_module  
        import datetime as datetime_module
        import json as json_module
        import time as time_module
        import calendar as calendar_module
        
        # Phase 2: Essential data processing modules
        import urllib.parse as urllib_parse_module
        import re as re_module
        import html as html_module
        import string as string_module
        import textwrap as textwrap_module
        import csv as csv_module
        import hashlib as hashlib_module
        import binascii as binascii_module
        import io as io_module
        
        # Phase 3: Advanced processing modules  
        import collections as collections_module
        import itertools as itertools_module
        import functools as functools_module
        import operator as operator_module
        import difflib as difflib_module
        import unicodedata as unicodedata_module
        import decimal as decimal_module
        import fractions as fractions_module
        import email.utils as email_utils_module
        import math as math_module
        import statistics as statistics_module
        import random as random_module
        import heapq as heapq_module
        import bisect as bisect_module
        
        # Prepare execution globals
        exec_globals = {
            '__builtins__': safe_builtins,
            '_getattr_': safer_getattr,
            '_getitem_': self._safe_getitem,
            '_getiter_': iter,
            '_write_': full_write_guard,
            '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
            '_print_': PrintCollector,  # Required for RestrictedPython print support
            '_printed': print_collector,  # Collector instance for print output
            'input': context.get('input', {}),
            'input_data': context.get('input', {}),
            'global': context.get('global_vars', {}),
            'node_outputs': context.get('node_outputs', {}),
            'loop': context.get('loop', {}),
            'loop_data': context.get('loop', {}),
            'local': {},
            'output': {},
            'string': self._create_string_ops(),
            'math': self._create_math_ops(),
            
            # Make actual modules available for import (overriding helper operations)
            # Phase 1: Time and date modules
            'base64': base64_module,
            'uuid': uuid_module,
            'datetime': datetime_module,  
            'json': json_module,
            'time': time_module,
            'calendar': calendar_module,
            
            # Phase 2: Essential data processing modules
            'urllib': urllib_parse_module,  # Note: only urllib.parse is imported for safety
            're': re_module,
            'html': html_module,
            'string': string_module,
            'textwrap': textwrap_module,
            'csv': csv_module,
            'hashlib': hashlib_module,
            'binascii': binascii_module,
            'io': io_module,
            
            # Phase 3: Advanced processing modules
            'collections': collections_module,
            'itertools': itertools_module,
            'functools': functools_module,
            'operator': operator_module,
            'difflib': difflib_module,
            'unicodedata': unicodedata_module,
            'decimal': decimal_module,
            'fractions': fractions_module,
            'email': email_utils_module,  # Note: only email.utils is imported for safety
            'math': math_module,
            'statistics': statistics_module,
            'random': random_module,
            'heapq': heapq_module,
            'bisect': bisect_module,
        }
        
        # Phase 4: PDF generation modules
        try:
            from reportlab.pdfgen import canvas as reportlab_canvas
            from reportlab.lib import pagesizes as reportlab_pagesizes
            from reportlab.lib import styles as reportlab_styles  
            from reportlab.lib import units as reportlab_units
            from reportlab.lib import colors as reportlab_colors
            from reportlab.lib import utils as reportlab_utils
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
            HAS_REPORTLAB = True
        except ImportError:
            HAS_REPORTLAB = False
            logger.warning("ReportLab not installed - PDF generation features unavailable")
        
        # Add reportlab support if available
        if HAS_REPORTLAB:
            exec_globals['reportlab'] = {
                'canvas': reportlab_canvas,
                'pagesizes': reportlab_pagesizes,
                'styles': reportlab_styles,
                'units': reportlab_units,
                'colors': reportlab_colors,
                'utils': reportlab_utils,
                'SimpleDocTemplate': SimpleDocTemplate,
                'Paragraph': Paragraph,
                'Spacer': Spacer,
                'Table': Table,
                'TableStyle': TableStyle,
                'Image': Image,
                'PageBreak': PageBreak,
                'getSampleStyleSheet': getSampleStyleSheet,
                'ParagraphStyle': ParagraphStyle,
                'TA_CENTER': TA_CENTER,
                'TA_LEFT': TA_LEFT,
                'TA_RIGHT': TA_RIGHT,
                'TA_JUSTIFY': TA_JUSTIFY
            }
        
        # Add set_global function
        variable_manager = context.get('variable_manager')
        if variable_manager:
            def set_global(name: str, value: Any):
                """Set a global variable"""
                if not isinstance(name, str):
                    raise TypeError("Variable name must be a string")
                variable_manager.set_global(name, value)
            exec_globals['set_global'] = set_global
            # CRITICAL: Store variable_manager in exec_globals so we can extract global vars later
            exec_globals['variable_manager'] = variable_manager
        else:
            # Provide a fallback set_global that stores in the global dict
            def set_global(name: str, value: Any):
                """Set a global variable (fallback implementation)"""
                if not isinstance(name, str):
                    raise TypeError("Variable name must be a string")
                # Store in the global dict
                exec_globals['global'][name] = value
            exec_globals['set_global'] = set_global
        
        # Add safe import function for allowed modules
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Safe import that returns pre-imported modules instead of importing"""
            # For modules that are already available, return them
            if name in exec_globals:
                return exec_globals[name]
            
            # Handle special cases
            if name == 'datetime' and 'datetime' in exec_globals:
                return exec_globals['datetime']
            elif name == 'io' and 'io' in exec_globals:
                return exec_globals['io']
            
            # Log attempt to import unavailable module
            logger.warning(f"Attempted to import '{name}' which is not pre-imported")
            
            # Return a mock module to prevent errors
            class MockModule:
                def __getattr__(self, attr):
                    raise ImportError(f"Module '{name}' is not available in transform debug mode")
            
            return MockModule()
        
        # Update both safe_builtins and exec_globals with the proper __import__
        safe_builtins['__import__'] = safe_import
        exec_globals['__import__'] = safe_import
        
        # Create debug state
        state = TransformDebugState(
            execution_id=execution_id,
            node_id=node_id,
            script=script,
            lines=lines,
            variables=context.get('variables', {}),
            ast_tree=ast_tree,
            line_to_ast=line_to_ast,
            execution_globals=exec_globals,
            execution_locals={},
            status="paused"
        )
        
        # Store print collector reference for accessing printed output
        state.print_collector = print_collector
        
        # Store session
        session_key = f"{execution_id}_{node_id}"
        self.debug_sessions[session_key] = state
        
        return state
    
    def step_into(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """
        Execute the next line in the transform script
        
        Args:
            execution_id: Execution ID
            node_id: Node ID
            
        Returns:
            Debug information including variables and next line
        """
        session_key = f"{execution_id}_{node_id}"
        state = self.debug_sessions.get(session_key)
        
        if not state:
            return {
                'error': 'Debug session not found',
                'execution_id': execution_id,
                'node_id': node_id
            }
        
        if state.status == "completed":
            return {
                'status': 'completed',
                'output': state.output,
                'variables': self._extract_variables(state)
            }
        
        if state.status == "error":
            return {
                'status': 'error',
                'error': state.error,
                'line': state.current_line,
                'variables': self._extract_variables(state)
            }
        
        # Execute current line/statement
        try:
            if state.current_line < len(state.lines):
                line = state.lines[state.current_line]
                
                # For empty lines and comments, advance the pointer but still pause
                # so the user sees the pointer move through every line
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith('#'):
                    logger.debug(f"Stepping over empty/comment line {state.current_line}: '{stripped_line}'")
                    state.executed_lines.add(state.current_line)
                    state.current_line += 1

                    if state.current_line >= len(state.lines):
                        state.status = "completed"
                        state.output = state.execution_globals.get('output', {})
                    else:
                        state.status = "paused"

                    return {
                        'status': state.status,
                        'current_line': state.current_line,
                        'total_lines': len(state.lines),
                        'next_line': state.lines[state.current_line] if state.current_line < len(state.lines) else None,
                        'variables': self._extract_variables(state),
                        'output': state.execution_globals.get('output', {}),
                    }
                
                # Collect lines for a complete statement
                statement_lines = [line]
                current_index = state.current_line + 1
                
                # Check if this is a compound statement (if, for, while, def, class, with, try)
                first_word = stripped_line.rstrip(':').split()[0] if stripped_line else ''
                if first_word in ('if', 'for', 'while', 'def', 'class', 'with', 'try'):
                    # This starts a compound statement, we need to collect its entire body
                    # and any related clauses (elif, else, except, finally)
                    base_indent = len(line) - len(line.lstrip())
                    
                    # Collect all lines in the block and related clauses
                    while current_index < len(state.lines):
                        next_line = state.lines[current_index]
                        next_stripped = next_line.strip()
                        
                        if next_stripped:  # Non-empty line
                            next_indent = len(next_line) - len(next_line.lstrip())
                            
                            # Check if this is a related clause at the same indentation level
                            next_first_word = next_stripped.rstrip(':').split()[0] if next_stripped else ''
                            
                            if next_indent == base_indent:
                                # Same indentation - check if it's a related clause
                                if first_word == 'if' and next_first_word in ('elif', 'else'):
                                    # This is part of the if-elif-else chain
                                    statement_lines.append(next_line)
                                    current_index += 1
                                    continue
                                elif first_word == 'try' and next_first_word in ('except', 'finally'):
                                    # This is part of the try-except-finally block
                                    statement_lines.append(next_line)
                                    current_index += 1
                                    continue
                                else:
                                    # Different statement at same level, we're done
                                    break
                            elif next_indent < base_indent:
                                # We've dedented past the original level, block is complete
                                break
                            else:
                                # This line is indented (part of the block body)
                                statement_lines.append(next_line)
                                current_index += 1
                        else:
                            # Empty line, include it
                            statement_lines.append(next_line)
                            current_index += 1
                
                elif first_word in ('elif', 'else', 'except', 'finally'):
                    # These should have been handled with their parent statement
                    # If we encounter them alone, it's an error
                    raise SyntaxError(f"'{first_word}' found without matching 'if' or 'try' statement")
                
                else:
                    # For non-compound statements, use AST parsing to determine completeness
                    while current_index <= len(state.lines):
                        code_to_test = '\n'.join(statement_lines)
                        
                        # Try to compile the current set of lines
                        try:
                            # Try to parse as a complete statement
                            ast.parse(code_to_test)
                            # Check if it's actually executable (not just parseable)
                            compile(code_to_test, '<test>', 'exec')
                            # If successful, we have a complete statement
                            break
                        except SyntaxError as e:
                            # Need more lines - but check if we're at the end
                            if current_index >= len(state.lines):
                                # No more lines available, try to execute what we have
                                break
                            
                            # Check the error to see if it's about incomplete input
                            error_msg = str(e)
                            if ('unexpected EOF' in error_msg or 
                                'was never closed' in error_msg or 
                                'invalid syntax' in error_msg or 
                                'expected an indented block' in error_msg or
                                'unterminated' in error_msg or  # For unterminated strings
                                'triple-quoted' in error_msg):  # Specifically for triple-quoted strings
                                # Add the next line and continue
                                if current_index < len(state.lines):
                                    statement_lines.append(state.lines[current_index])
                                    current_index += 1
                                else:
                                    break
                            else:
                                # Some other syntax error, stop here
                                break
                
                # Join the lines and execute as a complete statement
                complete_statement = '\n'.join(statement_lines)
                
                # Handle import statements specially since modules are pre-imported
                # Check if this is an import statement
                if complete_statement.strip().startswith('import ') or complete_statement.strip().startswith('from '):
                    # Parse the import statement to make the names available
                    logger.debug(f"Handling import statement: {complete_statement.strip()}")
                    self._handle_import_statement(state, complete_statement)
                else:
                    logger.debug(f"Executing statement: {complete_statement.strip()[:50]}...")
                    self._execute_line(state, complete_statement)
                
                # Mark all lines in the statement as executed
                for i in range(state.current_line, state.current_line + len(statement_lines)):
                    if i < len(state.lines):
                        state.executed_lines.add(i)
                
                # Move past all lines we've executed
                # If we consumed multiple lines, jump to the line after the last one
                if len(statement_lines) > 1:
                    state.current_line = state.current_line + len(statement_lines)
                else:
                    state.current_line += 1
                
                # Check if we've completed
                if state.current_line >= len(state.lines):
                    state.status = "completed"
                    state.output = state.execution_globals.get('output', {})
                else:
                    state.status = "paused"
                
                return {
                    'status': state.status,
                    'current_line': state.current_line,
                    'total_lines': len(state.lines),
                    'next_line': state.lines[state.current_line] if state.current_line < len(state.lines) else None,
                    'variables': self._extract_variables(state),
                    'output': state.execution_globals.get('output', {}),
                }
                
        except Exception as e:
            logger.error(f"Error executing line {state.current_line}: {e}")
            state.status = "error"
            state.error = str(e)
            
            return {
                'status': 'error',
                'error': str(e),
                'line': state.current_line,
                'line_content': state.lines[state.current_line] if state.current_line < len(state.lines) else None,
                'variables': self._extract_variables(state)
            }
    
    def step_over(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """
        Execute until the next line at the same level (skip function calls)
        For now, this behaves the same as step_into
        """
        return self.step_into(execution_id, node_id)
    
    def continue_execution(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """
        Continue execution until a breakpoint or completion
        
        Args:
            execution_id: Execution ID
            node_id: Node ID
            
        Returns:
            Debug information
        """
        session_key = f"{execution_id}_{node_id}"
        state = self.debug_sessions.get(session_key)
        
        if not state:
            return {
                'error': 'Debug session not found',
                'execution_id': execution_id,
                'node_id': node_id
            }
        
        # Execute lines until breakpoint or completion
        while state.current_line < len(state.lines) and state.status != "error":
            # Check for breakpoint
            if state.current_line in state.breakpoints:
                state.status = "paused"
                return {
                    'status': 'paused',
                    'reason': 'breakpoint',
                    'current_line': state.current_line,
                    'total_lines': len(state.lines),
                    'next_line': state.lines[state.current_line],
                    'variables': self._extract_variables(state)
                }
            
            # Execute line
            result = self.step_into(execution_id, node_id)
            
            if result['status'] in ['completed', 'error']:
                return result
        
        # Check if we've reached the end of the script
        if state.current_line >= len(state.lines):
            state.status = "completed"
            state.output = state.execution_globals.get('output', {})
        
        return {
            'status': state.status,
            'current_line': state.current_line,
            'output': state.output,
            'variables': self._extract_variables(state)
        }
    
    def set_breakpoint(self, execution_id: str, node_id: str, line_no: int) -> bool:
        """
        Set a breakpoint at a specific line
        
        Args:
            execution_id: Execution ID
            node_id: Node ID
            line_no: Line number (0-based)
            
        Returns:
            True if breakpoint was set
        """
        session_key = f"{execution_id}_{node_id}"
        state = self.debug_sessions.get(session_key)
        
        if not state:
            return False
        
        if 0 <= line_no < len(state.lines):
            state.breakpoints.add(line_no)
            return True
        
        return False
    
    def remove_breakpoint(self, execution_id: str, node_id: str, line_no: int) -> bool:
        """
        Remove a breakpoint from a specific line
        
        Args:
            execution_id: Execution ID
            node_id: Node ID
            line_no: Line number (0-based)
            
        Returns:
            True if breakpoint was removed
        """
        session_key = f"{execution_id}_{node_id}"
        state = self.debug_sessions.get(session_key)
        
        if not state:
            return False
        
        if line_no in state.breakpoints:
            state.breakpoints.remove(line_no)
            return True
        
        return False
    
    def get_debug_state(self, execution_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current debug state
        
        Args:
            execution_id: Execution ID
            node_id: Node ID
            
        Returns:
            Current debug state or None
        """
        session_key = f"{execution_id}_{node_id}"
        state = self.debug_sessions.get(session_key)
        
        if not state:
            return None
        
        return {
            'status': state.status,
            'current_line': state.current_line,
            'total_lines': len(state.lines),
            'lines': state.lines,
            'breakpoints': list(state.breakpoints),
            'variables': self._extract_variables(state),
            'output': state.execution_globals.get('output', {}),
            'error': state.error
        }
    
    def cleanup_session(self, execution_id: str, node_id: str):
        """
        Clean up a debug session
        
        Args:
            execution_id: Execution ID
            node_id: Node ID
        """
        session_key = f"{execution_id}_{node_id}"
        if session_key in self.debug_sessions:
            del self.debug_sessions[session_key]
    
    def _handle_import_statement(self, state: TransformDebugState, import_line: str):
        """
        Handle import statements by making pre-imported modules available in the local namespace
        
        Args:
            state: Debug state
            import_line: The import statement to handle
        """
        import_line = import_line.strip()
        
        try:
            if import_line.startswith('import '):
                # Handle "import module" or "import module as alias"
                parts = import_line[7:].strip()  # Remove "import "
                
                if ' as ' in parts:
                    module_name, alias = parts.split(' as ')
                    module_name = module_name.strip()
                    alias = alias.strip()
                else:
                    module_name = parts.strip()
                    alias = module_name
                
                # Get the module from execution_globals if it exists
                if module_name in state.execution_globals:
                    state.execution_locals[alias] = state.execution_globals[module_name]
                    state.execution_globals[alias] = state.execution_globals[module_name]
                    
            elif import_line.startswith('from '):
                # Handle "from module import name" or "from module import name as alias"
                parts = import_line[5:].strip()  # Remove "from "
                
                if ' import ' in parts:
                    module_name, imports = parts.split(' import ', 1)
                    module_name = module_name.strip()
                    
                    # Handle multiple imports: from module import a, b, c
                    import_items = [item.strip() for item in imports.split(',')]
                    logger.debug(f"Processing imports from {module_name}: {import_items}")
                    
                    for item in import_items:
                        if ' as ' in item:
                            name, alias = item.split(' as ')
                            name = name.strip()
                            alias = alias.strip()
                        else:
                            name = item.strip()
                            alias = name
                        
                        # Special handling for common "from" imports
                        if module_name == 'io' and name == 'BytesIO':
                            # Get BytesIO from the io module
                            if 'io' in state.execution_globals:
                                io_module = state.execution_globals['io']
                                if hasattr(io_module, 'BytesIO'):
                                    state.execution_locals[alias] = io_module.BytesIO
                                    state.execution_globals[alias] = io_module.BytesIO
                        elif module_name == 'datetime':
                            # Special handling for datetime module imports
                            # We need to get the actual datetime module, not any overwritten values
                            import datetime as actual_datetime_module
                            
                            if name == 'datetime' and hasattr(actual_datetime_module, 'datetime'):
                                state.execution_locals[alias] = actual_datetime_module.datetime
                                state.execution_globals[alias] = actual_datetime_module.datetime
                                logger.debug(f"Imported datetime.datetime as {alias}")
                            elif name == 'timedelta' and hasattr(actual_datetime_module, 'timedelta'):
                                state.execution_locals[alias] = actual_datetime_module.timedelta
                                state.execution_globals[alias] = actual_datetime_module.timedelta
                                logger.debug(f"Imported datetime.timedelta as {alias}")
                            elif name == 'date' and hasattr(actual_datetime_module, 'date'):
                                state.execution_locals[alias] = actual_datetime_module.date
                                state.execution_globals[alias] = actual_datetime_module.date
                                logger.debug(f"Imported datetime.date as {alias}")
                            elif name == 'time' and hasattr(actual_datetime_module, 'time'):
                                state.execution_locals[alias] = actual_datetime_module.time
                                state.execution_globals[alias] = actual_datetime_module.time
                                logger.debug(f"Imported datetime.time as {alias}")
                            elif name == 'timezone' and hasattr(actual_datetime_module, 'timezone'):
                                state.execution_locals[alias] = actual_datetime_module.timezone
                                state.execution_globals[alias] = actual_datetime_module.timezone
                                logger.debug(f"Imported datetime.timezone as {alias}")
                            else:
                                # Try generic attribute access
                                if hasattr(actual_datetime_module, name):
                                    attr = getattr(actual_datetime_module, name)
                                    state.execution_locals[alias] = attr
                                    state.execution_globals[alias] = attr
                                    logger.debug(f"Imported datetime.{name} as {alias}")
                        else:
                            # Try to get the attribute from the module
                            if module_name in state.execution_globals:
                                module = state.execution_globals[module_name]
                                if hasattr(module, name):
                                    attr = getattr(module, name)
                                    state.execution_locals[alias] = attr
                                    state.execution_globals[alias] = attr
                                    
        except Exception as e:
            # If there's an error handling the import, log it but continue
            logger.warning(f"Could not handle import statement '{import_line}': {e}")
    
    def _execute_line(self, state: TransformDebugState, line: str):
        """
        Execute a single line or statement of code
        
        Args:
            state: Debug state
            line: Line(s) of code to execute (can be multi-line statement)
        """
        try:
            # Skip empty lines
            if not line.strip():
                return
                
            # Use regular exec for execution with our safe globals
            # This allows datetime.now() and other operations to work
            exec(line, state.execution_globals, state.execution_locals)
            
            # Update local variables in globals for accessibility
            state.execution_globals.update(state.execution_locals)
            
        except Exception as e:
            # If execution fails, try to provide a more helpful error
            logger.error(f"Error executing line '{line.strip()}': {e}")
            # Check for specific errors and provide better messages
            if "'__import__'" in str(e):
                logger.error("Import error - modules should be pre-imported")
            raise
    
    def _extract_variables(self, state: TransformDebugState) -> Dict[str, Any]:
        """
        Extract all visible variables from the current execution state
        
        Args:
            state: Debug state
            
        Returns:
            Dictionary of variables categorized by type
        """
        # Separate system variables from user-defined local variables
        # Include all pre-imported modules and system variables
        system_vars = {
            '__builtins__', '_getattr_', '_getitem_', '_getiter_', 
            '_write_', '_iter_unpack_sequence_', '_print_', '_printed',
            'set_global', 'variable_manager',
            'input', 'input_data', 'global', 'node_outputs', 
            'loop', 'loop_data', 'local', 'output',
            # Pre-imported modules
            'string', 'math', 'base64', 'datetime', 
            'uuid', 'json', 'time', 'calendar',
            'urllib', 're', 'html', 'textwrap', 
            'csv', 'hashlib', 'binascii', 'io',
            'collections', 'itertools', 'functools', 'operator',
            'difflib', 'unicodedata', 'decimal', 'fractions',
            'email', 'statistics', 'random', 'heapq', 'bisect',
            'reportlab', 'PIL'
        }
        
        # Extract user-defined local variables
        local_vars = {}
        for key, value in state.execution_globals.items():
            if key not in system_vars and not key.startswith('_'):
                # This is a user-defined variable
                local_vars[key] = self._make_json_safe(value)
        
        # Also add any variables explicitly stored in 'local'
        explicit_local = state.execution_globals.get('local', {})
        if isinstance(explicit_local, dict):
            for key, value in explicit_local.items():
                local_vars[key] = self._make_json_safe(value)
        
        return {
            'input': self._make_json_safe(state.execution_globals.get('input', {})),
            'global': self._make_json_safe(state.execution_globals.get('global', {})),
            'local': local_vars,  # Now contains all user-defined variables
            'output': self._make_json_safe(state.execution_globals.get('output', {})),
            'loop': self._make_json_safe(state.execution_globals.get('loop', {})),
            'node_outputs': self._make_json_safe(state.execution_globals.get('node_outputs', {}))
        }
    
    def _make_json_safe(self, obj, seen=None, max_depth=10, current_depth=0):
        """
        Convert an object to a JSON-safe representation
        
        Args:
            obj: Object to convert
            seen: Set of object ids already processed (to handle circular references)
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
            
        Returns:
            JSON-safe version of the object
        """
        if current_depth > max_depth:
            return f"<Max depth reached>"
        
        if seen is None:
            seen = set()
        
        # Handle None, bool, int, float, str - already JSON safe
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        
        # Early check for reportlab/PIL objects to avoid deep inspection
        type_name = type(obj).__name__
        obj_module = getattr(obj, '__module__', '')
        if isinstance(obj_module, str) and ('reportlab' in obj_module or 'PIL' in obj_module):
            return f"<{type_name} from {obj_module}>"
        
        # Handle circular references
        obj_id = id(obj)
        if obj_id in seen:
            return f"<Circular reference to {type(obj).__name__}>"
        
        # Handle bytes
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except:
                return f"<bytes: {len(obj)} bytes>"
        
        # Add to seen set for collections
        if isinstance(obj, (dict, list, tuple, set)):
            seen = seen.copy()
            seen.add(obj_id)
        
        # Handle dictionaries
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                # Make sure the key is also JSON safe (must be string)
                safe_key = str(key) if not isinstance(key, str) else key
                result[safe_key] = self._make_json_safe(value, seen, max_depth, current_depth + 1)
            return result
        
        # Handle lists and tuples
        if isinstance(obj, (list, tuple)):
            result = [self._make_json_safe(item, seen, max_depth, current_depth + 1) for item in obj]
            return result
        
        # Handle sets
        if isinstance(obj, set):
            return [self._make_json_safe(item, seen, max_depth, current_depth + 1) for item in obj]
        
        # Handle modules - check for module type directly
        import types
        if isinstance(obj, types.ModuleType):
            return f"<module '{obj.__name__}'>"
        
        # Handle module-like objects (classes from modules like reportlab)
        if hasattr(obj, '__module__') and hasattr(obj, '__name__'):
            if hasattr(obj, '__class__') and obj.__class__.__name__ == 'module':
                return f"<module '{obj.__name__}'>"
        
        # Handle functions and methods
        if callable(obj):
            if hasattr(obj, '__name__'):
                return f"<function '{obj.__name__}'>"
            return f"<callable {type(obj).__name__}>"
        
        # Handle classes
        if isinstance(obj, type):
            return f"<class '{obj.__name__}'>"
        
        # Special handling for reportlab and other library objects
        obj_module = getattr(obj, '__module__', '')
        if isinstance(obj_module, str) and ('reportlab' in obj_module or 'PIL' in obj_module):
            # Don't try to serialize internals of reportlab/PIL objects
            return f"<{type(obj).__name__} from {obj_module}>"
        
        # Handle objects with __dict__
        if hasattr(obj, '__dict__'):
            try:
                # Skip serializing __dict__ for certain types that are known to be problematic
                type_name = type(obj).__name__
                if type_name in ('mappingproxy', 'module', 'type', 'function', 'method'):
                    return f"<{type_name} object>"
                
                return {
                    '_type': type_name,
                    '_data': self._make_json_safe(obj.__dict__, seen, max_depth, current_depth + 1)
                }
            except:
                pass
        
        # Handle objects with __str__ or __repr__
        try:
            return f"<{type(obj).__name__}: {str(obj)[:100]}>"
        except:
            return f"<{type(obj).__name__} object>"
    
    def _build_line_to_ast_map(self, tree: ast.Module) -> Dict[int, ast.AST]:
        """
        Build a mapping from line numbers to AST nodes
        
        Args:
            tree: AST tree
            
        Returns:
            Dictionary mapping line numbers to AST nodes
        """
        line_map = {}
        
        for node in ast.walk(tree):
            if hasattr(node, 'lineno'):
                # Store 0-based line number
                line_map[node.lineno - 1] = node
        
        return line_map
    
    def _safe_getitem(self, obj, index):
        """Safely get item from dict/list with better error handling"""
        try:
            return obj[index]
        except (KeyError, IndexError, TypeError) as e:
            obj_type = type(obj).__name__
            if isinstance(e, KeyError):
                available_keys = list(obj.keys()) if hasattr(obj, 'keys') else []
                raise KeyError(f"Key '{index}' not found in {obj_type}. Available keys: {available_keys[:10]}{'...' if len(available_keys) > 10 else ''}")
            elif isinstance(e, IndexError):
                length = len(obj) if hasattr(obj, '__len__') else 'unknown'
                raise IndexError(f"Index {index} is out of range for {obj_type} of length {length}")
            else:
                raise TypeError(f"Object of type '{obj_type}' does not support indexing")
    
    def _create_safe_builtins(self) -> Dict[str, Any]:
        """Create safe built-in functions"""
        
        # Create a safe __import__ function that will be added later
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Safe import that returns pre-imported modules"""
            # This will be replaced with the proper safe_import in start_debug
            # For now, just raise an error if called
            raise ImportError(f"Direct imports not allowed in transform debug mode")
        
        return {
            'None': None,
            'True': True,
            'False': False,
            'bool': bool,
            'int': int,
            'float': float,
            'str': str,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'sorted': sorted,
            'reversed': reversed,
            'sum': sum,
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'all': all,
            'any': any,
            'isinstance': isinstance,
            'type': type,
            '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
            '__import__': safe_import,  # Add __import__ to builtins
            '__builtins__': None,
        }
    
    def _create_string_ops(self) -> Dict[str, Any]:
        """Create string operations"""
        return {
            'upper': lambda s: str(s).upper(),
            'lower': lambda s: str(s).lower(),
            'capitalize': lambda s: str(s).capitalize(),
            'title': lambda s: str(s).title(),
            'strip': lambda s, chars=None: str(s).strip(chars),
            'lstrip': lambda s, chars=None: str(s).lstrip(chars),
            'rstrip': lambda s, chars=None: str(s).rstrip(chars),
            'split': lambda s, sep=' ', maxsplit=-1: str(s).split(sep, maxsplit),
            'join': lambda sep, items: str(sep).join(str(i) for i in items),
            'replace': lambda s, old, new, count=-1: str(s).replace(str(old), str(new), count),
            'startswith': lambda s, prefix: str(s).startswith(str(prefix)),
            'endswith': lambda s, suffix: str(s).endswith(str(suffix)),
            'find': lambda s, sub: str(s).find(str(sub)),
            'count': lambda s, sub: str(s).count(str(sub)),
            'format': lambda s, *args, **kwargs: str(s).format(*args, **kwargs),
        }
    
    def _create_math_ops(self) -> Dict[str, Any]:
        """Create math operations"""
        return {
            'add': lambda a, b: a + b,
            'subtract': lambda a, b: a - b,
            'multiply': lambda a, b: a * b,
            'divide': lambda a, b: a / b if b != 0 else None,
            'floor_divide': lambda a, b: a // b if b != 0 else None,
            'modulo': lambda a, b: a % b if b != 0 else None,
            'power': lambda a, b: a ** b,
            'sqrt': lambda x: x ** 0.5 if x >= 0 else None,
        }
    
    def _create_base64_ops(self) -> Dict[str, Any]:
        """Create base64 operations"""
        import base64
        return {
            'b64encode': lambda data: base64.b64encode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
            'b64decode': lambda data: base64.b64decode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
            'urlsafe_b64encode': lambda data: base64.urlsafe_b64encode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
            'urlsafe_b64decode': lambda data: base64.urlsafe_b64decode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
        }
    
    def _create_datetime_ops(self) -> Dict[str, Any]:
        """Create enhanced datetime operations with timezone support"""
        import datetime as dt
        import calendar as cal
        return {
            # Basic date/time functions
            'now': lambda: dt.datetime.now().isoformat(),
            'utcnow': lambda: dt.datetime.utcnow().isoformat(),
            'today': lambda: dt.date.today().isoformat(),
            'timestamp': lambda: int(dt.datetime.now().timestamp()),
            'format_date': lambda date_str, fmt='%Y-%m-%d': dt.datetime.fromisoformat(date_str).strftime(fmt),
            'parse_date': lambda date_str, fmt='%Y-%m-%d': dt.datetime.strptime(date_str, fmt).isoformat(),
            
            # Enhanced time operations
            'add_days': lambda date_str, days: (dt.datetime.fromisoformat(date_str) + dt.timedelta(days=days)).isoformat(),
            'add_hours': lambda date_str, hours: (dt.datetime.fromisoformat(date_str) + dt.timedelta(hours=hours)).isoformat(),
            'add_minutes': lambda date_str, minutes: (dt.datetime.fromisoformat(date_str) + dt.timedelta(minutes=minutes)).isoformat(),
            'subtract_days': lambda date_str, days: (dt.datetime.fromisoformat(date_str) - dt.timedelta(days=days)).isoformat(),
            'days_between': lambda date1, date2: (dt.datetime.fromisoformat(date2) - dt.datetime.fromisoformat(date1)).days,
            
            # Timezone operations (basic UTC support)
            'to_utc': lambda date_str: dt.datetime.fromisoformat(date_str).replace(tzinfo=dt.timezone.utc).isoformat(),
            'from_timestamp': lambda ts: dt.datetime.fromtimestamp(ts).isoformat(),
            'to_timestamp': lambda date_str: int(dt.datetime.fromisoformat(date_str).timestamp()),
            
            # Calendar operations
            'weekday': lambda date_str: dt.datetime.fromisoformat(date_str).weekday(),  # 0=Monday, 6=Sunday
            'weekday_name': lambda date_str: cal.day_name[dt.datetime.fromisoformat(date_str).weekday()],
            'month_name': lambda date_str: cal.month_name[dt.datetime.fromisoformat(date_str).month],
            'is_weekend': lambda date_str: dt.datetime.fromisoformat(date_str).weekday() >= 5,
            'first_day_of_month': lambda date_str: dt.datetime.fromisoformat(date_str).replace(day=1).date().isoformat(),
            'last_day_of_month': lambda date_str: (dt.datetime.fromisoformat(date_str).replace(day=cal.monthrange(dt.datetime.fromisoformat(date_str).year, dt.datetime.fromisoformat(date_str).month)[1])).date().isoformat(),
            
            # Business logic helpers
            'age_in_years': lambda birth_date: (dt.date.today() - dt.date.fromisoformat(birth_date)).days // 365,
            'quarter': lambda date_str: (dt.datetime.fromisoformat(date_str).month - 1) // 3 + 1,
            'days_until': lambda target_date: (dt.date.fromisoformat(target_date) - dt.date.today()).days,
        }
    
    def _create_json_ops(self) -> Dict[str, Any]:
        """Create JSON operations"""
        import json
        return {
            'loads': lambda data: json.loads(data),
            'dumps': lambda data: json.dumps(data, ensure_ascii=False, default=str),
            'dumps_pretty': lambda data: json.dumps(data, ensure_ascii=False, default=str, indent=2),
        }


# Global debugger instance
transform_debugger = TransformDebugger()