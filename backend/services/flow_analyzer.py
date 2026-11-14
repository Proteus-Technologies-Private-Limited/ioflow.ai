"""
Flow Analyzer Service

Analyzes flow definitions to extract structure, parameters, transformations,
and other metadata needed for converting flows to applications.
"""

import json
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NodeType(Enum):
    TRIGGER = "trigger"
    ACTION = "action"
    CONDITION = "condition"
    TRANSFORM = "transform"
    LOOP = "loop"
    RESPONSE = "response"
    PARALLEL = "parallel"


class TriggerType(Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"
    EVENT = "event"
    APP_EVENT = "app_event"  # Application event trigger
    SCHEDULE = "schedule"
    API_CALL = "api_call"
    API_DIRECT = "api_direct"
    API_DIRECT_SYNC = "api_direct_sync"


@dataclass
class FlowParameter:
    """Represents a parameter in the flow"""
    name: str
    type: str
    required: bool
    description: str = ""
    default_value: Any = None
    source: str = ""  # trigger, node, global, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "default_value": self.default_value,
            "source": self.source
        }


@dataclass
class FlowOutput:
    """Represents an output from the flow"""
    name: str
    type: str
    description: str = ""
    source_node: str = ""
    path: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "source_node": self.source_node,
            "path": self.path
        }


@dataclass
class FlowTransformation:
    """Represents a data transformation in the flow"""
    node_id: str
    input_variables: List[str]
    output_variables: List[str]
    transformation_code: str
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "input_variables": self.input_variables,
            "output_variables": self.output_variables,
            "transformation_code": self.transformation_code,
            "description": self.description
        }


@dataclass
class FlowAnalysis:
    """Complete analysis of a flow"""
    flow_id: str
    flow_name: str
    description: str
    is_synchronous: bool
    trigger_type: TriggerType
    input_parameters: List[FlowParameter]
    output_parameters: List[FlowOutput]
    transformations: List[FlowTransformation]
    dependencies: List[str]  # External services/applications used
    complexity_score: int
    estimated_execution_time: int  # in seconds
    error_handling_nodes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
            "description": self.description,
            "is_synchronous": self.is_synchronous,
            "trigger_type": self.trigger_type.value,
            "input_parameters": [p.to_dict() for p in self.input_parameters],
            "output_parameters": [o.to_dict() for o in self.output_parameters],
            "transformations": [t.to_dict() for t in self.transformations],
            "dependencies": self.dependencies,
            "complexity_score": self.complexity_score,
            "estimated_execution_time": self.estimated_execution_time,
            "error_handling_nodes": self.error_handling_nodes
        }


class FlowAnalyzer:
    """Analyzes flow definitions and extracts metadata for application generation"""
    
    def __init__(self):
        self.variable_pattern = re.compile(r'\{\{([^}]+)\}\}')
    
    def analyze_flow(self, flow_definition: Dict[str, Any], 
                    trigger_config: Dict[str, Any],
                    flow_name: str,
                    description: str = "",
                    is_synchronous: bool = False) -> FlowAnalysis:
        """
        Analyze a complete flow and return detailed analysis
        
        Args:
            flow_definition: The flow's node and edge definition
            trigger_config: The trigger configuration
            flow_name: Name of the flow
            description: Flow description
            is_synchronous: Whether the flow is synchronous
            
        Returns:
            FlowAnalysis object with complete analysis
        """
        logger.info(f"Starting analysis of flow: {flow_name}")
        
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        # Analyze trigger and input parameters
        trigger_type = TriggerType(trigger_config.get('type', 'manual'))
        input_parameters = self._extract_input_parameters(trigger_config, nodes)
        
        # Analyze transformations
        transformations = self._extract_transformations(nodes)
        
        # Analyze output parameters
        output_parameters = self._extract_output_parameters(nodes, edges, is_synchronous)
        
        # Extract dependencies
        dependencies = self._extract_dependencies(nodes)
        
        # Calculate complexity
        complexity_score = self._calculate_complexity(nodes, edges)
        
        # Estimate execution time
        estimated_time = self._estimate_execution_time(nodes, complexity_score)
        
        # Find error handling nodes
        error_nodes = self._find_error_handling_nodes(nodes)
        
        analysis = FlowAnalysis(
            flow_id="",  # Will be set by caller
            flow_name=flow_name,
            description=description,
            is_synchronous=is_synchronous,
            trigger_type=trigger_type,
            input_parameters=input_parameters,
            output_parameters=output_parameters,
            transformations=transformations,
            dependencies=dependencies,
            complexity_score=complexity_score,
            estimated_execution_time=estimated_time,
            error_handling_nodes=error_nodes
        )
        
        logger.info(f"Flow analysis completed. Found {len(input_parameters)} inputs, "
                   f"{len(output_parameters)} outputs, {len(transformations)} transformations")
        
        return analysis
    
    def _extract_input_parameters(self, trigger_config: Dict[str, Any], 
                                nodes: List[Dict[str, Any]]) -> List[FlowParameter]:
        """Extract input parameters from trigger configuration and trigger nodes"""
        parameters = []
        
        # Extract from trigger config
        if trigger_config.get('type') == 'manual':
            manual_variables = trigger_config.get('manual_variables', [])
            for var in manual_variables:
                param = FlowParameter(
                    name=var.get('name', ''),
                    type=var.get('type', 'string'),
                    required=var.get('required', False),
                    description=var.get('description', ''),
                    default_value=var.get('default_value'),
                    source='trigger_manual'
                )
                parameters.append(param)
        
        # Extract from trigger nodes
        trigger_nodes = [n for n in nodes if n.get('type') == 'trigger']
        for node in trigger_nodes:
            node_data = node.get('data', {})
            variables = node_data.get('variables', [])
            for var in variables:
                param = FlowParameter(
                    name=var.get('name', ''),
                    type=var.get('type', 'string'),
                    required=var.get('required', False),
                    description=var.get('description', ''),
                    default_value=var.get('default_value'),
                    source=f'trigger_node_{node.get("id")}'
                )
                parameters.append(param)
        
        # Extract webhook parameters if applicable
        if trigger_config.get('type') == 'webhook':
            # Webhook body will be available as input parameters
            param = FlowParameter(
                name='webhook_body',
                type='object',
                required=True,
                description='Webhook request body',
                source='trigger_webhook'
            )
            parameters.append(param)
            
            param = FlowParameter(
                name='webhook_headers',
                type='object',
                required=False,
                description='Webhook request headers',
                source='trigger_webhook'
            )
            parameters.append(param)
        
        return parameters
    
    def _extract_transformations(self, nodes: List[Dict[str, Any]]) -> List[FlowTransformation]:
        """Extract all data transformations from transform nodes"""
        transformations = []
        
        transform_nodes = [n for n in nodes if n.get('type') == 'transform']
        for node in transform_nodes:
            node_data = node.get('data', {})
            transformation_code = node_data.get('code', '')
            
            # Extract input variables from the code
            input_vars = self._extract_variables_from_code(transformation_code, 'input')
            
            # Extract output variables (variables assigned to output)
            output_vars = self._extract_output_variables_from_code(transformation_code)
            
            transformation = FlowTransformation(
                node_id=node.get('id', ''),
                input_variables=input_vars,
                output_variables=output_vars,
                transformation_code=transformation_code,
                description=node_data.get('label', node_data.get('description', ''))
            )
            transformations.append(transformation)
        
        return transformations
    
    def _extract_output_parameters(self, nodes: List[Dict[str, Any]], 
                                 edges: List[Dict[str, Any]], 
                                 is_synchronous: bool) -> List[FlowOutput]:
        """Extract output parameters from response nodes and final nodes"""
        outputs = []
        
        if is_synchronous:
            # Look for response nodes
            response_nodes = [n for n in nodes if n.get('type') == 'response']
            for node in response_nodes:
                node_data = node.get('data', {})
                variable = node_data.get('variable', '')
                
                # Parse the variable to understand the output structure
                output = FlowOutput(
                    name='response',
                    type='object',
                    description='Flow response data',
                    source_node=node.get('id', ''),
                    path=variable
                )
                outputs.append(output)
        else:
            # For async flows, identify final nodes (nodes with no outgoing edges)
            final_nodes = self._find_final_nodes(nodes, edges)
            for node_id in final_nodes:
                node = next((n for n in nodes if n.get('id') == node_id), None)
                if node and node.get('type') in ['action', 'transform']:
                    output = FlowOutput(
                        name=f'final_output_{node_id}',
                        type='object',
                        description=f'Output from final node {node_id}',
                        source_node=node_id,
                        path=f'node_outputs.{node_id}'
                    )
                    outputs.append(output)
        
        return outputs
    
    def _extract_dependencies(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Extract external service dependencies from action nodes"""
        dependencies = set()
        
        action_nodes = [n for n in nodes if n.get('type') == 'action']
        for node in action_nodes:
            node_data = node.get('data', {})
            app_id = node_data.get('selectedApp', node_data.get('app_id'))
            if app_id:
                dependencies.add(app_id)
        
        return list(dependencies)
    
    def _calculate_complexity(self, nodes: List[Dict[str, Any]], 
                            edges: List[Dict[str, Any]]) -> int:
        """Calculate flow complexity score based on various factors"""
        score = 0
        
        # Base score from node count
        score += len(nodes)
        
        # Additional complexity for different node types
        node_type_weights = {
            'action': 2,
            'condition': 3,
            'transform': 4,
            'loop': 5,
            'parallel': 3
        }
        
        for node in nodes:
            node_type = node.get('type', '')
            score += node_type_weights.get(node_type, 1)
        
        # Complexity from branching (edges)
        score += len(edges)
        
        # Additional complexity for nested structures
        loop_nodes = [n for n in nodes if n.get('type') == 'loop']
        score += len(loop_nodes) * 3
        
        return score
    
    def _estimate_execution_time(self, nodes: List[Dict[str, Any]], 
                               complexity_score: int) -> int:
        """Estimate execution time in seconds"""
        base_time = 1  # Base 1 second
        
        # Time per node type
        node_times = {
            'action': 2,      # API calls take time
            'transform': 1,   # Transform operations
            'condition': 0.5, # Simple logic
            'loop': 5,        # Loops can be expensive
            'parallel': 3     # Parallel processing
        }
        
        total_time = base_time
        for node in nodes:
            node_type = node.get('type', '')
            total_time += node_times.get(node_type, 0.5)
        
        # Factor in complexity
        total_time += complexity_score * 0.1
        
        return int(total_time)
    
    def _find_error_handling_nodes(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Find nodes that handle errors"""
        error_nodes = []
        
        for node in nodes:
            node_data = node.get('data', {})
            node_type = node.get('type', '')
            
            # Check for error handling in conditions
            if node_type == 'condition':
                condition = node_data.get('condition', '')
                if 'error' in condition.lower() or 'fail' in condition.lower():
                    error_nodes.append(node.get('id', ''))
            
            # Check for error handling in transforms
            elif node_type == 'transform':
                code = node_data.get('code', '')
                if 'except' in code or 'error' in code.lower() or 'try:' in code:
                    error_nodes.append(node.get('id', ''))
        
        return error_nodes
    
    def _extract_variables_from_code(self, code: str, variable_type: str) -> List[str]:
        """Extract variables of a specific type from transformation code"""
        variables = set()
        
        # Find all variable references like {{input.variable}} or input.variable
        patterns = [
            rf'{variable_type}\.(\w+)',
            rf'\{{\{{{variable_type}\.(\w+)\}}}}',
            rf'{variable_type}\[[\'""](\w+)[\'""]\]'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, code)
            variables.update(matches)
        
        return list(variables)
    
    def _extract_output_variables_from_code(self, code: str) -> List[str]:
        """Extract output variables assigned in transformation code"""
        variables = set()
        
        # Find assignments to output dictionary
        patterns = [
            r'output\[[\'""](\w+)[\'""]\]',
            r'output\.(\w+)\s*=',
            r'output\[[\'""]([^\'""]+)[\'""]\]'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, code)
            variables.update(matches)
        
        return list(variables)
    
    def _find_final_nodes(self, nodes: List[Dict[str, Any]], 
                         edges: List[Dict[str, Any]]) -> List[str]:
        """Find nodes that have no outgoing edges (final nodes)"""
        all_node_ids = {node.get('id') for node in nodes}
        nodes_with_outgoing = {edge.get('source') for edge in edges}
        
        final_nodes = all_node_ids - nodes_with_outgoing
        return list(final_nodes)
    
    def extract_variable_references(self, text: str) -> Set[str]:
        """Extract all variable references from text (like {{variable.path}})"""
        variables = set()
        matches = self.variable_pattern.findall(text)
        
        for match in matches:
            # Clean up the variable path
            var_path = match.strip()
            variables.add(var_path)
        
        return variables
    
    def analyze_parameter_flow(self, flow_definition: Dict[str, Any]) -> Dict[str, List[str]]:
        """Analyze how parameters flow through the system"""
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        parameter_flow = {}
        
        # Build execution graph
        execution_graph = {}
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source not in execution_graph:
                execution_graph[source] = []
            execution_graph[source].append(target)
        
        # Trace parameter usage through the flow
        for node in nodes:
            node_id = node.get('id')
            node_data = node.get('data', {})
            node_type = node.get('type')
            
            variables_used = set()
            
            # Extract variables based on node type
            if node_type == 'action':
                # Check parameter mappings in action nodes
                parameters = node_data.get('parameters', {})
                for param_name, param_value in parameters.items():
                    if isinstance(param_value, str):
                        variables_used.update(self.extract_variable_references(param_value))
            
            elif node_type == 'condition':
                condition = node_data.get('condition', '')
                variables_used.update(self.extract_variable_references(condition))
            
            elif node_type == 'transform':
                code = node_data.get('code', '')
                variables_used.update(self.extract_variable_references(code))
            
            elif node_type == 'response':
                variable = node_data.get('variable', '')
                variables_used.update(self.extract_variable_references(variable))
            
            parameter_flow[node_id] = list(variables_used)
        
        return parameter_flow