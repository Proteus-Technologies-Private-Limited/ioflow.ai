"""
Test cases for Transform Node functionality
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from services.variable_manager import FlowVariableManager
from services.transform_executor import TransformExecutor
from services.execution_engine import ExecutionEngine


class TestVariableManager:
    """Test cases for FlowVariableManager"""
    
    def test_set_and_get_global_variable(self):
        """Test setting and getting global variables"""
        vm = FlowVariableManager()
        
        # Set a global variable
        vm.set_global('test_var', 'test_value')
        
        # Get the variable
        assert vm.get_global('test_var') == 'test_value'
        assert vm.get_global('non_existent', 'default') == 'default'
    
    def test_set_and_get_node_output(self):
        """Test storing and retrieving node outputs"""
        vm = FlowVariableManager()
        
        # Set node output
        vm.set_node_output('node_123', {'result': 'success', 'data': [1, 2, 3]})
        
        # Get node output
        output = vm.get_node_output('node_123')
        assert output == {'result': 'success', 'data': [1, 2, 3]}
        assert vm.get_node_output('non_existent') is None
    
    def test_get_context(self):
        """Test context building"""
        vm = FlowVariableManager()
        vm.set_global('global1', 'value1')
        vm.set_node_output('node_123', {'output': 'data'})
        
        context = vm.get_context('current_node', {'input': 'data'})
        
        assert context['input'] == {'input': 'data'}
        assert context['global_vars'] == {'global1': 'value1'}
        assert context['node_outputs'] == {'node_123': {'output': 'data'}}
        assert context['current_node_id'] == 'current_node'
    
    def test_get_variable_paths(self):
        """Test getting available variable paths"""
        vm = FlowVariableManager()
        vm.set_global('user_count', 10)
        vm.set_global('total_price', 100.50)
        vm.set_node_output('transform_1', {'name': 'John', 'age': 30})
        
        paths = vm.get_variable_paths()
        
        assert 'global.user_count' in paths['global']
        assert 'global.total_price' in paths['global']
        assert 'node_outputs.transform_1' in paths['node_outputs']
        assert 'node_outputs.transform_1.name' in paths['node_outputs']
        assert 'node_outputs.transform_1.age' in paths['node_outputs']


class TestTransformExecutor:
    """Test cases for TransformExecutor"""
    
    def test_basic_transformation(self):
        """Test basic transformation script"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        script = """
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['count'] = len(input.get('items', []))
output['processed'] = True
"""
        
        context = {
            'input': {'name': 'Alice', 'items': [1, 2, 3]},
            'global_vars': {},
            'node_outputs': {}
        }
        
        result = executor.execute(script, context, vm)
        
        assert result['message'] == "Hello, Alice!"
        assert result['count'] == 3
        assert result['processed'] is True
    
    def test_string_operations(self):
        """Test string operation functions"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        script = """
local['name'] = input.get('name', '')
output['upper'] = string['upper'](local['name'])
output['lower'] = string['lower'](local['name'])
output['split'] = string['split'](local['name'], ' ')
output['joined'] = string['join']('-', output['split'])
output['replaced'] = string['replace'](local['name'], 'John', 'Jane')
"""
        
        context = {
            'input': {'name': 'John Doe'},
            'global_vars': {},
            'node_outputs': {}
        }
        
        result = executor.execute(script, context, vm)
        
        assert result['upper'] == 'JOHN DOE'
        assert result['lower'] == 'john doe'
        assert result['split'] == ['John', 'Doe']
        assert result['joined'] == 'John-Doe'
        assert result['replaced'] == 'Jane Doe'
    
    def test_math_operations(self):
        """Test math operation functions"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        script = """
local['a'] = 10
local['b'] = 3
output['add'] = math['add'](local['a'], local['b'])
output['subtract'] = math['subtract'](local['a'], local['b'])
output['multiply'] = math['multiply'](local['a'], local['b'])
output['divide'] = math['divide'](local['a'], local['b'])
output['power'] = math['power'](2, 3)
output['sqrt'] = math['sqrt'](16)
"""
        
        context = {
            'input': {},
            'global_vars': {},
            'node_outputs': {}
        }
        
        result = executor.execute(script, context, vm)
        
        assert result['add'] == 13
        assert result['subtract'] == 7
        assert result['multiply'] == 30
        assert result['divide'] == 10/3
        assert result['power'] == 8
        assert result['sqrt'] == 4
    
    def test_loop_and_aggregation(self):
        """Test loops and data aggregation"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        script = """
local['items'] = input.get('items', [])
local['total'] = 0
local['active_count'] = 0

for item in local['items']:
    local['total'] = math['add'](local['total'], item['price'])
    if item.get('active'):
        local['active_count'] = math['add'](local['active_count'], 1)

output['total_price'] = local['total']
output['active_items'] = local['active_count']
output['average_price'] = math['divide'](local['total'], len(local['items'])) if local['items'] else 0
"""
        
        context = {
            'input': {
                'items': [
                    {'name': 'Item 1', 'price': 10.0, 'active': True},
                    {'name': 'Item 2', 'price': 20.0, 'active': False},
                    {'name': 'Item 3', 'price': 15.0, 'active': True}
                ]
            },
            'global_vars': {},
            'node_outputs': {}
        }
        
        result = executor.execute(script, context, vm)
        
        assert result['total_price'] == 45.0
        assert result['active_items'] == 2
        assert result['average_price'] == 15.0
    
    def test_global_variable_setting(self):
        """Test setting global variables from transform"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        script = """
output['local_result'] = 'test'
set_global('shared_value', 42)
set_global('user_name', input.get('name', 'Unknown'))
"""
        
        context = {
            'input': {'name': 'Bob'},
            'global_vars': {},
            'node_outputs': {}
        }
        
        result = executor.execute(script, context, vm)
        
        assert result['local_result'] == 'test'
        assert vm.get_global('shared_value') == 42
        assert vm.get_global('user_name') == 'Bob'
    
    def test_accessing_node_outputs(self):
        """Test accessing outputs from other nodes"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        # Set up previous node outputs
        vm.set_node_output('action_1', {'user': {'id': 123, 'name': 'Alice'}})
        vm.set_node_output('action_2', {'status': 'success', 'count': 5})
        
        script = """
output['user_id'] = node_outputs['action_1']['user']['id']
output['user_name'] = node_outputs['action_1']['user']['name']
output['status'] = node_outputs['action_2']['status']
output['total'] = math['multiply'](node_outputs['action_2']['count'], 10)
"""
        
        context = vm.get_context('transform_1', {})
        
        result = executor.execute(script, context, vm)
        
        assert result['user_id'] == 123
        assert result['user_name'] == 'Alice'
        assert result['status'] == 'success'
        assert result['total'] == 50
    
    def test_script_validation(self):
        """Test script validation for forbidden patterns"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        # Test forbidden patterns
        forbidden_scripts = [
            "__import__('os').system('ls')",
            "exec('malicious code')",
            "eval('malicious code')",
            "compile('malicious', 'eval', 'exec')",
            "open('/etc/passwd', 'r')",
            "locals()['__builtins__']",
            "globals()['__builtins__']",
        ]
        
        context = {'input': {}, 'global_vars': {}, 'node_outputs': {}}
        
        for script in forbidden_scripts:
            with pytest.raises(ValueError) as exc_info:
                executor.execute(script, context, vm)
            assert "forbidden pattern" in str(exc_info.value).lower()
    
    def test_execution_timeout(self):
        """Test execution timeout protection"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        # Script with infinite loop
        script = """
while True:
    pass
"""
        
        context = {'input': {}, 'global_vars': {}, 'node_outputs': {}}
        
        with pytest.raises(ValueError) as exc_info:
            executor.execute(script, context, vm)
        
        # Should timeout or hit iteration limit
        assert "exceeded" in str(exc_info.value).lower()
    
    def test_iteration_limit(self):
        """Test iteration limit protection"""
        executor = TransformExecutor()
        vm = FlowVariableManager()
        
        # Script with too many iterations
        script = """
local['count'] = 0
for i in range(100000):
    local['count'] = math['add'](local['count'], 1)
output['count'] = local['count']
"""
        
        context = {'input': {}, 'global_vars': {}, 'node_outputs': {}}
        
        with pytest.raises(ValueError) as exc_info:
            executor.execute(script, context, vm)
        
        assert "range too large" in str(exc_info.value).lower()


@pytest.mark.asyncio
class TestExecutionEngineIntegration:
    """Test transform node integration with execution engine"""
    
    async def test_transform_node_execution(self):
        """Test executing a transform node in a flow"""
        # Mock the database and other dependencies
        with patch('services.execution_engine.get_tenant_db'):
            engine = ExecutionEngine('test_tenant')
            
            # Set up some previous node outputs
            engine.variable_manager.set_node_output('trigger_1', {'name': 'Test User'})
            
            node_data = {
                'id': 'transform_1',
                'type': 'transform',
                'script': """
output['greeting'] = f"Hello, {node_outputs['trigger_1']['name']}!"
output['timestamp'] = 'test_time'
set_global('processed_count', 1)
"""
            }
            
            context = {
                'execution_id': 'test_exec_123',
                'data': {},
                'global_vars': engine.variable_manager.global_vars,
                'node_outputs': engine.variable_manager.node_outputs
            }
            
            # Execute the transform node
            result = await engine._execute_transform_node(node_data, context)
            
            assert result['greeting'] == "Hello, Test User!"
            assert result['timestamp'] == 'test_time'
            assert engine.variable_manager.get_global('processed_count') == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])