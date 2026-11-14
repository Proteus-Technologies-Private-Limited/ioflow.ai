"""
Simplified Transform Debugger for line-by-line execution
This version focuses on the core functionality needed for debugging
"""
import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class TransformDebugState:
    """State for a transform debug session"""
    execution_id: str
    node_id: str
    script: str
    script_lines: List[str]
    current_line: int
    executed_lines: List[int]
    variables: Dict[str, Any]
    breakpoints: Set[int]
    is_complete: bool
    last_error: Optional[str]
    output: Dict[str, Any]


class SimpleTransformDebugger:
    """Simplified transform debugger that simulates line-by-line execution"""
    
    def __init__(self):
        self.sessions: Dict[str, TransformDebugState] = {}
    
    def start_debug_session(
        self,
        execution_id: str,
        node_id: str,
        script: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start a debug session for a transform node"""
        
        # Split script into lines
        lines = script.splitlines()
        
        # Create debug state
        session_key = f"{execution_id}:{node_id}"
        state = TransformDebugState(
            execution_id=execution_id,
            node_id=node_id,
            script=script,
            script_lines=lines,
            current_line=0,  # Start at first line
            executed_lines=[],
            variables={
                'input': context.get('input', {}),
                'local': {},
                'output': {},
                'global': context.get('global_vars', {}),
                'node_outputs': context.get('node_outputs', {})
            },
            breakpoints=set(),
            is_complete=False,
            last_error=None,
            output={}
        )
        
        self.sessions[session_key] = state
        
        return self._get_debug_info(state)
    
    def step_line(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """Simulate stepping to the next line"""
        session_key = f"{execution_id}:{node_id}"
        
        if session_key not in self.sessions:
            return {'error': 'No debug session found'}
        
        state = self.sessions[session_key]
        
        if state.is_complete:
            return self._get_debug_info(state)
        
        # Move to next non-empty line
        while state.current_line < len(state.script_lines):
            line = state.script_lines[state.current_line].strip()
            
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                # Simulate execution of this line
                self._simulate_line_execution(state, line)
                state.executed_lines.append(state.current_line)
                state.current_line += 1
                break
            
            state.current_line += 1
        
        # Check if we've reached the end
        if state.current_line >= len(state.script_lines):
            state.is_complete = True
            state.output = state.variables.get('output', {})
        
        return self._get_debug_info(state)
    
    def _simulate_line_execution(self, state: TransformDebugState, line: str):
        """Simulate the execution of a line (simplified)"""
        # This is a very simplified simulation
        # In the real implementation, this would use RestrictedPython
        
        # Simulate some common patterns
        if "local['count']" in line:
            if '= 0' in line:
                state.variables['local']['count'] = 0
            elif '+ 1' in line:
                state.variables['local']['count'] = state.variables['local'].get('count', 0) + 1
        
        elif "local['result']" in line:
            if '= []' in line:
                state.variables['local']['result'] = []
            elif '.append(' in line:
                if 'result' not in state.variables['local']:
                    state.variables['local']['result'] = []
                # Simulate appending a value
                state.variables['local']['result'].append("simulated_value")
        
        elif "output[" in line:
            # Extract key and simulate setting output
            if "output['count']" in line:
                state.variables['output']['count'] = state.variables['local'].get('count', 0)
            elif "output['result']" in line:
                state.variables['output']['result'] = state.variables['local'].get('result', [])
            elif "output['message']" in line:
                state.variables['output']['message'] = 'Processing complete'
            # Handle output['pdfdata'] pattern
            elif "output['pdfdata']" in line:
                # Simulate setting pdfdata output
                state.variables['output']['pdfdata'] = state.variables['local'].get('pdf_content', 'simulated_pdf_data')
        
        # Handle set_global function calls
        elif 'set_global(' in line:
            # Extract the variable name and value from set_global('varname', value)
            import re
            match = re.search(r"set_global\(['\"]([^'\"]+)['\"],\s*(.+)\)", line)
            if match:
                var_name = match.group(1)
                # For simulation, just set a placeholder value
                if var_name == 'pdfdata':
                    # This is the PDF data being set as global
                    state.variables['global']['pdfdata'] = state.variables['output'].get('pdfdata', 'simulated_pdf_global')
                else:
                    state.variables['global'][var_name] = f'simulated_{var_name}_value'
                logger.info(f"Simulated set_global('{var_name}', ...)")
        
        # Handle global['varname'] = value pattern
        elif "global[" in line:
            # Extract key and simulate setting global variable
            import re
            match = re.search(r"global\[['\"]([\w_]+)['\"]\]\s*=", line)
            if match:
                var_name = match.group(1)
                if var_name == 'pdfdata':
                    # Special handling for pdfdata
                    state.variables['global']['pdfdata'] = state.variables.get('output', {}).get('pdfdata', 'simulated_pdf_global')
                else:
                    state.variables['global'][var_name] = f'simulated_{var_name}_value'
                logger.info(f"Simulated global['{var_name}'] = ...")
        
        # Simulate loop variables
        elif 'for item in' in line:
            state.variables['local']['_loop_active'] = True
            state.variables['local']['_loop_items'] = state.variables['input'].get('items', [])
    
    def continue_execution(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """Continue execution until completion or breakpoint"""
        session_key = f"{execution_id}:{node_id}"
        
        if session_key not in self.sessions:
            return {'error': 'No debug session found'}
        
        state = self.sessions[session_key]
        
        while not state.is_complete:
            # Check for breakpoint
            if state.current_line in state.breakpoints:
                break
            
            # Step one line
            result = self.step_line(execution_id, node_id)
            
            if state.is_complete or state.last_error:
                break
        
        return self._get_debug_info(state)
    
    def set_breakpoint(self, execution_id: str, node_id: str, line_number: int) -> bool:
        """Set a breakpoint at a line"""
        session_key = f"{execution_id}:{node_id}"
        
        if session_key not in self.sessions:
            return False
        
        state = self.sessions[session_key]
        # Convert to 0-based index
        state.breakpoints.add(line_number - 1)
        return True
    
    def clear_breakpoint(self, execution_id: str, node_id: str, line_number: int) -> bool:
        """Clear a breakpoint"""
        session_key = f"{execution_id}:{node_id}"
        
        if session_key not in self.sessions:
            return False
        
        state = self.sessions[session_key]
        state.breakpoints.discard(line_number - 1)
        return True
    
    def get_variables(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """Get current variables"""
        session_key = f"{execution_id}:{node_id}"
        
        if session_key not in self.sessions:
            return {}
        
        state = self.sessions[session_key]
        return {
            'input': state.variables.get('input', {}),
            'local': state.variables.get('local', {}),
            'output': state.variables.get('output', {}),
            'global': state.variables.get('global', {}),
            'node_outputs': state.variables.get('node_outputs', {})
        }
    
    def end_session(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """End debug session and return output"""
        session_key = f"{execution_id}:{node_id}"
        
        if session_key not in self.sessions:
            return {}
        
        state = self.sessions[session_key]
        output = state.output or state.variables.get('output', {})
        
        # Clean up
        del self.sessions[session_key]
        
        return output
    
    def _get_debug_info(self, state: TransformDebugState) -> Dict[str, Any]:
        """Get debug information for current state"""
        current_line_text = ""
        if 0 <= state.current_line < len(state.script_lines):
            current_line_text = state.script_lines[state.current_line]
        
        # Preview next few lines
        preview_lines = []
        for i in range(state.current_line, min(state.current_line + 3, len(state.script_lines))):
            preview_lines.append({
                'line_number': i + 1,  # 1-based for display
                'text': state.script_lines[i],
                'is_current': i == state.current_line,
                'has_breakpoint': i in state.breakpoints
            })
        
        return {
            'execution_id': state.execution_id,
            'node_id': state.node_id,
            'current_line': state.current_line + 1,  # 1-based for display
            'total_lines': len(state.script_lines),
            'current_line_text': current_line_text,
            'preview_lines': preview_lines,
            'is_complete': state.is_complete,
            'is_stepping': True,
            'breakpoints': [b + 1 for b in state.breakpoints],  # 1-based
            'variables': self.get_variables(state.execution_id, state.node_id),
            'last_error': state.last_error,
            'script_lines': state.script_lines,
            'executed_lines': [l + 1 for l in state.executed_lines]  # 1-based
        }


# Global instance for use in the application
simple_transform_debugger = SimpleTransformDebugger()