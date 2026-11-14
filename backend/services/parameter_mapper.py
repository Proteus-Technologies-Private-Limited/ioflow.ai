"""
Parameter Mapping Service

Handles mapping between flow variables and application service parameters,
including transformations and validation.
"""

import json
import re
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MappingType(Enum):
    DIRECT = "direct"           # Direct 1:1 mapping
    TRANSFORM = "transform"     # With transformation logic
    CONSTANT = "constant"       # Fixed value
    CONDITIONAL = "conditional" # Based on condition
    ARRAY_MAP = "array_map"    # Map over array elements
    COMPUTED = "computed"       # Computed from multiple inputs


@dataclass
class ParameterMapping:
    """Represents a parameter mapping"""
    source_path: str           # e.g., "input.customerEmail"
    target_parameter: str      # Service parameter name
    mapping_type: MappingType
    transformation_rule: Optional[Dict[str, Any]] = None
    default_value: Any = None
    required: bool = False
    validation_schema: Optional[Dict[str, Any]] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "target_parameter": self.target_parameter,
            "mapping_type": self.mapping_type.value,
            "transformation_rule": self.transformation_rule,
            "default_value": self.default_value,
            "required": self.required,
            "validation_schema": self.validation_schema,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ParameterMapping':
        return cls(
            source_path=data["source_path"],
            target_parameter=data["target_parameter"],
            mapping_type=MappingType(data["mapping_type"]),
            transformation_rule=data.get("transformation_rule"),
            default_value=data.get("default_value"),
            required=data.get("required", False),
            validation_schema=data.get("validation_schema"),
            description=data.get("description", "")
        )


@dataclass
class MappingResult:
    """Result of parameter mapping operation"""
    success: bool
    mapped_parameters: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "mapped_parameters": self.mapped_parameters,
            "errors": self.errors,
            "warnings": self.warnings
        }


class ParameterMapper:
    """Handles parameter mapping between flows and applications"""
    
    def __init__(self):
        self.variable_pattern = re.compile(r'\{\{([^}]+)\}\}')
    
    def create_mapping_schema(self, 
                            flow_parameters: List[Dict[str, Any]],
                            service_parameters: List[Dict[str, Any]],
                            auto_map: bool = True) -> Dict[str, List[ParameterMapping]]:
        """
        Create parameter mapping schema between flow and service parameters
        
        Args:
            flow_parameters: List of flow input parameters
            service_parameters: List of service parameters
            auto_map: Whether to automatically create mappings based on name matching
            
        Returns:
            Dictionary with input and output mappings
        """
        mappings = {
            "input": [],
            "output": []
        }
        
        if auto_map:
            # Auto-map based on name matching
            input_mappings = self._auto_map_parameters(flow_parameters, service_parameters)
            mappings["input"] = input_mappings
        
        return mappings
    
    def _auto_map_parameters(self, 
                           flow_params: List[Dict[str, Any]], 
                           service_params: List[Dict[str, Any]]) -> List[ParameterMapping]:
        """Auto-map parameters based on name similarity"""
        mappings = []
        
        for flow_param in flow_params:
            flow_name = flow_param.get("name", "")
            flow_type = flow_param.get("type", "string")
            
            # Find best matching service parameter
            best_match = None
            best_score = 0
            
            for service_param in service_params:
                service_name = service_param.get("name", "")
                score = self._calculate_name_similarity(flow_name, service_name)
                
                if score > best_score and score > 0.5:  # Minimum similarity threshold
                    best_match = service_param
                    best_score = score
            
            if best_match:
                mapping = ParameterMapping(
                    source_path=f"input.{flow_name}",
                    target_parameter=best_match.get("name", ""),
                    mapping_type=MappingType.DIRECT,
                    required=flow_param.get("required", False),
                    description=f"Auto-mapped from flow parameter '{flow_name}'"
                )
                mappings.append(mapping)
            else:
                # Create unmapped parameter for manual configuration
                mapping = ParameterMapping(
                    source_path=f"input.{flow_name}",
                    target_parameter="",  # To be configured manually
                    mapping_type=MappingType.DIRECT,
                    required=flow_param.get("required", False),
                    description=f"Unmapped flow parameter '{flow_name}'"
                )
                mappings.append(mapping)
        
        return mappings
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two parameter names"""
        if not name1 or not name2:
            return 0.0
        
        name1 = name1.lower()
        name2 = name2.lower()
        
        # Exact match
        if name1 == name2:
            return 1.0
        
        # Check for common variations
        variations = {
            'email': ['email', 'e_mail', 'mail', 'email_address'],
            'name': ['name', 'full_name', 'fullname', 'display_name'],
            'id': ['id', 'identifier', 'uuid', 'key'],
            'phone': ['phone', 'phone_number', 'mobile', 'tel'],
            'address': ['address', 'addr', 'location'],
            'date': ['date', 'datetime', 'timestamp'],
            'amount': ['amount', 'value', 'price', 'cost'],
            'count': ['count', 'quantity', 'number', 'num']
        }
        
        # Check if names are in the same variation group
        for group in variations.values():
            if name1 in group and name2 in group:
                return 0.8
        
        # Check substring match
        if name1 in name2 or name2 in name1:
            return 0.6
        
        # Levenshtein distance based similarity
        return self._levenshtein_similarity(name1, name2)
    
    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity based on Levenshtein distance"""
        if len(s1) < len(s2):
            return self._levenshtein_similarity(s2, s1)
        
        if len(s2) == 0:
            return 0.0
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        distance = previous_row[-1]
        max_len = max(len(s1), len(s2))
        return (max_len - distance) / max_len
    
    def apply_mappings(self, 
                      input_data: Dict[str, Any],
                      mappings: List[ParameterMapping],
                      node_outputs: Optional[Dict[str, Any]] = None,
                      global_vars: Optional[Dict[str, Any]] = None) -> MappingResult:
        """
        Apply parameter mappings to convert flow data to service parameters
        
        Args:
            input_data: Flow input data
            mappings: List of parameter mappings to apply
            node_outputs: Outputs from previous nodes
            global_vars: Global variables
            
        Returns:
            MappingResult with success status and mapped parameters
        """
        mapped_params = {}
        errors = []
        warnings = []
        
        # Prepare context for variable resolution
        context = {
            'input': input_data,
            'node_outputs': node_outputs or {},
            'global': global_vars or {},
            'loop': {}  # Will be populated if in loop context
        }
        
        for mapping in mappings:
            try:
                result = self._apply_single_mapping(mapping, context)
                
                if result["success"]:
                    mapped_params[mapping.target_parameter] = result["value"]
                else:
                    errors.extend(result.get("errors", []))
                    warnings.extend(result.get("warnings", []))
                
            except Exception as e:
                error_msg = f"Error applying mapping for '{mapping.target_parameter}': {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return MappingResult(
            success=len(errors) == 0,
            mapped_parameters=mapped_params,
            errors=errors,
            warnings=warnings
        )
    
    def _apply_single_mapping(self, 
                            mapping: ParameterMapping, 
                            context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a single parameter mapping"""
        try:
            if mapping.mapping_type == MappingType.DIRECT:
                return self._apply_direct_mapping(mapping, context)
            elif mapping.mapping_type == MappingType.TRANSFORM:
                return self._apply_transform_mapping(mapping, context)
            elif mapping.mapping_type == MappingType.CONSTANT:
                return self._apply_constant_mapping(mapping, context)
            elif mapping.mapping_type == MappingType.CONDITIONAL:
                return self._apply_conditional_mapping(mapping, context)
            elif mapping.mapping_type == MappingType.ARRAY_MAP:
                return self._apply_array_mapping(mapping, context)
            elif mapping.mapping_type == MappingType.COMPUTED:
                return self._apply_computed_mapping(mapping, context)
            else:
                return {
                    "success": False,
                    "errors": [f"Unknown mapping type: {mapping.mapping_type}"]
                }
                
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Mapping error: {str(e)}"]
            }
    
    def _apply_direct_mapping(self, 
                            mapping: ParameterMapping, 
                            context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply direct parameter mapping"""
        value = self._resolve_variable_path(mapping.source_path, context)
        
        if value is None and mapping.required:
            return {
                "success": False,
                "errors": [f"Required parameter '{mapping.target_parameter}' is missing"]
            }
        
        if value is None and mapping.default_value is not None:
            value = mapping.default_value
        
        # Validate if schema provided
        if mapping.validation_schema and value is not None:
            validation_result = self._validate_value(value, mapping.validation_schema)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "errors": validation_result["errors"]
                }
        
        return {
            "success": True,
            "value": value
        }
    
    def _apply_transform_mapping(self, 
                               mapping: ParameterMapping, 
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply transformation mapping"""
        if not mapping.transformation_rule:
            return {
                "success": False,
                "errors": ["Transform mapping missing transformation rule"]
            }
        
        transform_type = mapping.transformation_rule.get("type", "javascript")
        transform_code = mapping.transformation_rule.get("code", "")
        
        # Get source value
        source_value = self._resolve_variable_path(mapping.source_path, context)
        
        if transform_type == "javascript":
            # Simple JavaScript-like transformations
            result = self._apply_javascript_transform(transform_code, source_value, context)
        elif transform_type == "python":
            # Python transformations
            result = self._apply_python_transform(transform_code, source_value, context)
        elif transform_type == "template":
            # Template-based transformation
            result = self._apply_template_transform(transform_code, context)
        else:
            return {
                "success": False,
                "errors": [f"Unknown transformation type: {transform_type}"]
            }
        
        return result
    
    def _apply_constant_mapping(self, 
                              mapping: ParameterMapping, 
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply constant value mapping"""
        value = mapping.default_value
        return {
            "success": True,
            "value": value
        }
    
    def _apply_conditional_mapping(self, 
                                 mapping: ParameterMapping, 
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply conditional mapping based on condition"""
        if not mapping.transformation_rule:
            return {
                "success": False,
                "errors": ["Conditional mapping missing transformation rule"]
            }
        
        condition = mapping.transformation_rule.get("condition", "")
        true_value = mapping.transformation_rule.get("true_value")
        false_value = mapping.transformation_rule.get("false_value")
        
        # Evaluate condition
        condition_result = self._evaluate_condition(condition, context)
        
        value = true_value if condition_result else false_value
        
        return {
            "success": True,
            "value": value
        }
    
    def _apply_array_mapping(self, 
                           mapping: ParameterMapping, 
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply array mapping"""
        source_array = self._resolve_variable_path(mapping.source_path, context)
        
        if not isinstance(source_array, list):
            return {
                "success": False,
                "errors": [f"Source path '{mapping.source_path}' is not an array"]
            }
        
        if not mapping.transformation_rule:
            return {
                "success": False,
                "errors": ["Array mapping missing transformation rule"]
            }
        
        item_mapping = mapping.transformation_rule.get("item_mapping", "")
        
        # Apply mapping to each item
        result_array = []
        for i, item in enumerate(source_array):
            item_context = {**context, 'item': item, 'index': i}
            mapped_item = self._resolve_variable_path(item_mapping, item_context)
            result_array.append(mapped_item)
        
        return {
            "success": True,
            "value": result_array
        }
    
    def _apply_computed_mapping(self, 
                              mapping: ParameterMapping, 
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply computed mapping from multiple sources"""
        if not mapping.transformation_rule:
            return {
                "success": False,
                "errors": ["Computed mapping missing transformation rule"]
            }
        
        computation = mapping.transformation_rule.get("computation", "")
        sources = mapping.transformation_rule.get("sources", [])
        
        # Resolve all source values
        source_values = {}
        for source in sources:
            var_name = source.get("name", "")
            var_path = source.get("path", "")
            source_values[var_name] = self._resolve_variable_path(var_path, context)
        
        # Apply computation
        result = self._apply_computation(computation, source_values, context)
        
        return {
            "success": True,
            "value": result
        }
    
    def _resolve_variable_path(self, path: str, context: Dict[str, Any]) -> Any:
        """Resolve variable path like 'input.customerEmail' or 'node_outputs.123.data'"""
        if not path:
            return None
        
        # Handle template variables like {{input.customerEmail}}
        if path.startswith('{{') and path.endswith('}}'):
            path = path[2:-2].strip()
        
        # Split path into parts
        parts = path.split('.')
        
        # Start with the root context
        value = context
        
        # Navigate through the path
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit():
                index = int(part)
                value = value[index] if 0 <= index < len(value) else None
            else:
                return None
            
            if value is None:
                break
        
        return value
    
    def _validate_value(self, value: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate value against JSON schema"""
        # Simple validation - in production, use jsonschema library
        schema_type = schema.get("type", "string")
        
        errors = []
        
        if schema_type == "string" and not isinstance(value, str):
            errors.append(f"Expected string, got {type(value).__name__}")
        elif schema_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Expected number, got {type(value).__name__}")
        elif schema_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Expected boolean, got {type(value).__name__}")
        elif schema_type == "array" and not isinstance(value, list):
            errors.append(f"Expected array, got {type(value).__name__}")
        elif schema_type == "object" and not isinstance(value, dict):
            errors.append(f"Expected object, got {type(value).__name__}")
        
        # Check required fields for objects
        if schema_type == "object" and isinstance(value, dict):
            required = schema.get("required", [])
            for field in required:
                if field not in value:
                    errors.append(f"Missing required field: {field}")
        
        # Check array items
        if schema_type == "array" and isinstance(value, list):
            items_schema = schema.get("items")
            if items_schema:
                for i, item in enumerate(value):
                    item_validation = self._validate_value(item, items_schema)
                    if not item_validation["valid"]:
                        errors.extend([f"Item {i}: {error}" for error in item_validation["errors"]])
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _apply_javascript_transform(self, code: str, value: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply JavaScript-like transformation"""
        # Simple transformations - in production, use a proper JS engine
        try:
            # Replace common JS patterns with Python equivalents
            python_code = code
            python_code = python_code.replace('value.length', 'len(value)')
            python_code = python_code.replace('.toLowerCase()', '.lower()')
            python_code = python_code.replace('.toUpperCase()', '.upper()')
            
            # Create execution context
            exec_context = {
                'value': value,
                'context': context,
                'len': len,
                'str': str,
                'int': int,
                'float': float
            }
            
            # Execute transformation
            result = eval(python_code, {"__builtins__": {}}, exec_context)
            
            return {
                "success": True,
                "value": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"JavaScript transform error: {str(e)}"]
            }
    
    def _apply_python_transform(self, code: str, value: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Python transformation"""
        try:
            # Create execution context
            exec_context = {
                'value': value,
                'input': context.get('input', {}),
                'node_outputs': context.get('node_outputs', {}),
                'global': context.get('global', {}),
                'result': None
            }
            
            # Execute Python code
            exec(code, {"__builtins__": {}}, exec_context)
            
            return {
                "success": True,
                "value": exec_context.get('result', value)
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Python transform error: {str(e)}"]
            }
    
    def _apply_template_transform(self, template: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply template-based transformation"""
        try:
            # Simple template substitution
            result = template
            
            # Find all variable references
            variables = self.variable_pattern.findall(template)
            
            for var in variables:
                var_value = self._resolve_variable_path(var.strip(), context)
                result = result.replace(f'{{{{{var}}}}}', str(var_value) if var_value is not None else '')
            
            return {
                "success": True,
                "value": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Template transform error: {str(e)}"]
            }
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a condition expression"""
        try:
            # Simple condition evaluation
            # Replace variable references
            variables = self.variable_pattern.findall(condition)
            eval_condition = condition
            
            for var in variables:
                var_value = self._resolve_variable_path(var.strip(), context)
                eval_condition = eval_condition.replace(f'{{{{{var}}}}}', str(var_value) if var_value is not None else 'None')
            
            # Safe evaluation
            exec_context = {
                'True': True,
                'False': False,
                'None': None,
                'len': len,
                'str': str,
                'int': int,
                'float': float
            }
            
            return bool(eval(eval_condition, {"__builtins__": {}}, exec_context))
            
        except Exception as e:
            logger.error(f"Condition evaluation error: {str(e)}")
            return False
    
    def _apply_computation(self, computation: str, sources: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Apply computation using source values"""
        try:
            # Create execution context with source values
            exec_context = {
                **sources,
                'context': context,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'sum': sum,
                'max': max,
                'min': min,
                'abs': abs
            }
            
            return eval(computation, {"__builtins__": {}}, exec_context)
            
        except Exception as e:
            logger.error(f"Computation error: {str(e)}")
            return None
    
    def generate_mapping_suggestions(self, 
                                   flow_analysis: Dict[str, Any],
                                   service_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate mapping suggestions based on flow analysis and service configuration"""
        suggestions = []
        
        flow_params = flow_analysis.get("input_parameters", [])
        service_params = service_config.get("parameters", [])
        
        # Auto-map similar parameters
        for flow_param in flow_params:
            best_matches = []
            
            for service_param in service_params:
                similarity = self._calculate_name_similarity(
                    flow_param.get("name", ""),
                    service_param.get("name", "")
                )
                
                if similarity > 0.3:  # Lower threshold for suggestions
                    best_matches.append({
                        "service_param": service_param,
                        "similarity": similarity,
                        "mapping_type": MappingType.DIRECT.value,
                        "confidence": similarity
                    })
            
            # Sort by similarity
            best_matches.sort(key=lambda x: x["similarity"], reverse=True)
            
            suggestion = {
                "flow_parameter": flow_param,
                "suggested_mappings": best_matches[:3],  # Top 3 suggestions
                "auto_map": len(best_matches) > 0 and best_matches[0]["similarity"] > 0.8
            }
            
            suggestions.append(suggestion)
        
        return suggestions