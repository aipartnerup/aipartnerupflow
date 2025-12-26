"""
Test decorators functionality

Tests for the unified decorators system (Flask-style API):
- register_pre_hook
- register_post_hook
- set_task_model_class / get_task_model_class
- executor_register
"""
import pytest
from aipartnerupflow import (
    register_pre_hook,
    register_post_hook,
    set_task_model_class,
    get_task_model_class,
    clear_config,
    executor_register,
)
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.extensions.types import ExtensionCategory
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TestConfigDecorators:
    """Test configuration decorators (hooks, task_model_class)"""
    
    def setup_method(self):
        """Clear config registry before each test"""
        clear_config()
    
    def test_register_pre_hook_as_decorator(self):
        """Test @register_pre_hook decorator syntax"""
        hook_called = []
        
        @register_pre_hook
        async def my_pre_hook(task):
            hook_called.append(task.id)
        
        # Verify hook was registered
        from aipartnerupflow.core.config import get_pre_hooks
        hooks = get_pre_hooks()
        assert len(hooks) == 1
        assert hooks[0] == my_pre_hook
        
        # Verify the function is still callable
        assert callable(my_pre_hook)
    
    def test_register_pre_hook_as_function(self):
        """Test register_pre_hook() function call syntax"""
        hook_called = []
        
        async def my_pre_hook(task):
            hook_called.append(task.id)
        
        # Register using function call
        register_pre_hook(my_pre_hook)
        
        # Verify hook was registered
        from aipartnerupflow.core.config import get_pre_hooks
        hooks = get_pre_hooks()
        assert len(hooks) == 1
        assert hooks[0] == my_pre_hook
    
    def test_register_post_hook_as_decorator(self):
        """Test @register_post_hook decorator syntax"""
        hook_called = []
        
        @register_post_hook
        async def my_post_hook(task, inputs, result):
            hook_called.append((task.id, result))
        
        # Verify hook was registered
        from aipartnerupflow.core.config import get_post_hooks
        hooks = get_post_hooks()
        assert len(hooks) == 1
        assert hooks[0] == my_post_hook
        
        # Verify the function is still callable
        assert callable(my_post_hook)
    
    def test_register_post_hook_as_function(self):
        """Test register_post_hook() function call syntax"""
        hook_called = []
        
        async def my_post_hook(task, inputs, result):
            hook_called.append((task.id, result))
        
        # Register using function call
        register_post_hook(my_post_hook)
        
        # Verify hook was registered
        from aipartnerupflow.core.config import get_post_hooks
        hooks = get_post_hooks()
        assert len(hooks) == 1
        assert hooks[0] == my_post_hook
    
    def test_multiple_pre_hooks(self):
        """Test registering multiple pre-hooks"""
        @register_pre_hook
        async def hook1(task):
            pass
        
        @register_pre_hook
        async def hook2(task):
            pass
        
        @register_pre_hook
        async def hook3(task):
            pass
        
        from aipartnerupflow.core.config import get_pre_hooks
        hooks = get_pre_hooks()
        assert len(hooks) == 3
        assert hooks == [hook1, hook2, hook3]
    
    def test_multiple_post_hooks(self):
        """Test registering multiple post-hooks"""
        @register_post_hook
        async def hook1(task, inputs, result):
            pass
        
        @register_post_hook
        async def hook2(task, inputs, result):
            pass
        
        from aipartnerupflow.core.config import get_post_hooks
        hooks = get_post_hooks()
        assert len(hooks) == 2
        assert hooks == [hook1, hook2]
    
    def test_sync_hooks(self):
        """Test registering synchronous hooks"""
        @register_pre_hook
        def sync_pre_hook(task):
            pass
        
        @register_post_hook
        def sync_post_hook(task, inputs, result):
            pass
        
        from aipartnerupflow.core.config import get_pre_hooks, get_post_hooks
        assert len(get_pre_hooks()) == 1
        assert len(get_post_hooks()) == 1
    
    def test_set_and_get_task_model_class(self):
        """Test set_task_model_class and get_task_model_class"""
        # Test that we can set and get TaskModel (using default)
        # Since set_task_model_class requires TaskModel subclass,
        # we'll test with the default TaskModel itself
        
        # Set to default TaskModel explicitly
        set_task_model_class(TaskModel)
        
        # Get and verify
        retrieved_class = get_task_model_class()
        assert retrieved_class == TaskModel
        
        # Test that get returns the same instance after multiple calls
        assert get_task_model_class() == TaskModel
    
    def test_task_model_class_default(self):
        """Test that default TaskModel is returned when not set"""
        # Clear any custom model
        clear_config()
        
        # Get default model
        model_class = get_task_model_class()
        assert model_class == TaskModel
    
    @pytest.mark.asyncio
    async def test_hooks_with_agent_executor(self):
        """Test that hooks registered via decorators work with AgentExecutor"""
        try:
            from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
        except ImportError:
            pytest.skip("a2a module not available, skipping AgentExecutor test")
            return
        
        pre_hook_called = []
        post_hook_called = []
        
        @register_pre_hook
        async def test_pre_hook(task):
            pre_hook_called.append(task.id)
        
        @register_post_hook
        async def test_post_hook(task, inputs, result):
            post_hook_called.append((task.id, result))
        
        # Create executor (should pick up hooks from registry)
        executor = AIPartnerUpFlowAgentExecutor()
        
        # Verify hooks were loaded
        assert len(executor.pre_hooks) == 1
        assert len(executor.post_hooks) == 1
        assert executor.pre_hooks[0] == test_pre_hook
        assert executor.post_hooks[0] == test_post_hook
    
    @pytest.mark.asyncio
    async def test_hooks_with_a2a_server(self):
        """Test that hooks registered via decorators work with create_a2a_server"""
        try:
            from aipartnerupflow.api.a2a.server import create_a2a_server
        except ImportError:
            pytest.skip("a2a module not available, skipping create_a2a_server test")
            return
        
        pre_hook_called = []
        
        @register_pre_hook
        async def test_pre_hook(task):
            pre_hook_called.append(task.id)
        
        # Create server (should pick up hooks from registry)
        server = create_a2a_server(
            verify_token_secret_key=None,
            base_url="http://localhost:8000",
        )
        
        # Verify server was created (hooks are used internally)
        assert server is not None


class TestExtensionDecorator:
    """Test @executor_register decorator"""
    
    def setup_method(self):
        """Clear extension registry before each test"""
        from aipartnerupflow.core.extensions import get_registry
        registry = get_registry()
        # Clear all registrations
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        # Note: _extensions is a dict keyed by extension.id, not a list
        # We'll let tests register their own extensions
    
    def test_executor_register_decorator(self):
        """Test @executor_register decorator"""
        from aipartnerupflow.core.base import BaseTask
        
        @executor_register()
        class TestExecutor(BaseTask):
            id = "test_executor"
            name = "Test Executor"
            description = "Test executor for decorator testing"
            category = ExtensionCategory.EXECUTOR
            
            def __init__(self, inputs=None):
                super().__init__(inputs=inputs or {})
            
            async def execute(self, inputs):
                return {"result": "test"}
            
            def get_input_schema(self):
                return {"type": "object"}
        
        # Verify extension was registered
        from aipartnerupflow.core.extensions import get_registry
        registry = get_registry()
        
        # Check if executor can be retrieved
        executor_instance = registry.create_executor_instance(
            "test_executor",
            inputs={}
        )
        assert executor_instance is not None
        assert executor_instance.id == "test_executor"
        assert executor_instance.name == "Test Executor"
    
    def test_executor_register_with_factory(self):
        """Test @executor_register with custom factory"""
        from aipartnerupflow.core.base import BaseTask
        
        def custom_factory(inputs):
            executor = TestExecutorWithFactory(inputs=inputs)
            executor.custom_initialized = True
            return executor
        
        @executor_register(factory=custom_factory)
        class TestExecutorWithFactory(BaseTask):
            id = "test_executor_factory"
            name = "Test Executor Factory"
            description = "Test executor with custom factory"
            category = ExtensionCategory.EXECUTOR
            custom_initialized = False
            
            def __init__(self, inputs=None):
                super().__init__(inputs=inputs or {})
            
            async def execute(self, inputs):
                return {"result": "test"}
            
            def get_input_schema(self):
                return {"type": "object"}
        
        # Verify extension was registered with custom factory
        from aipartnerupflow.core.extensions import get_registry
        registry = get_registry()
        
        executor_instance = registry.create_executor_instance(
            "test_executor_factory",
            inputs={}
        )
        assert executor_instance is not None
        assert executor_instance.custom_initialized is True


class TestDecoratorIntegration:
    """Test integration of decorators with real components"""
    
    def setup_method(self):
        """Clear config before each test"""
        clear_config()
    
    @pytest.mark.asyncio
    async def test_full_decorator_workflow(self):
        """Test complete workflow using all decorators"""
        try:
            from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
        except ImportError:
            pytest.skip("a2a module not available, skipping full workflow test")
            return
        
        pre_hooks_called = []
        post_hooks_called = []
        
        # Register hooks using decorators
        @register_pre_hook
        async def pre_hook1(task):
            pre_hooks_called.append(f"hook1-{task.id}")
        
        @register_pre_hook
        async def pre_hook2(task):
            pre_hooks_called.append(f"hook2-{task.id}")
        
        @register_post_hook
        async def post_hook1(task, inputs, result):
            post_hooks_called.append(f"hook1-{task.id}")
        
        # Set custom TaskModel (if needed)
        # For this test, we'll use default TaskModel
        
        # Create executor (should use registered hooks)
        executor = AIPartnerUpFlowAgentExecutor()
        
        # Verify hooks were registered
        assert len(executor.pre_hooks) == 2
        assert len(executor.post_hooks) == 1
        
        # Verify hooks are in correct order
        assert executor.pre_hooks[0] == pre_hook1
        assert executor.pre_hooks[1] == pre_hook2
        assert executor.post_hooks[0] == post_hook1
    
    def test_decorator_imports(self):
        """Test that all decorators can be imported from main package"""
        # Test that decorators are available from main package
        from aipartnerupflow import (
            register_pre_hook,
            register_post_hook,
            set_task_model_class,
            get_task_model_class,
            executor_register,
        )
        
        # Verify they are callable
        assert callable(register_pre_hook)
        assert callable(register_post_hook)
        assert callable(set_task_model_class)
        assert callable(get_task_model_class)
        assert callable(executor_register)


class TestConfigRegistryIsolation:
    """Test that config registry is properly isolated between tests"""
    
    def setup_method(self):
        """Clear config before each test"""
        clear_config()
    
    def test_config_isolation(self):
        """Test that config changes don't leak between tests"""
        # Register a hook
        @register_pre_hook
        async def isolated_hook(task):
            pass
        
        # Verify it's registered
        from aipartnerupflow.core.config import get_pre_hooks
        assert len(get_pre_hooks()) == 1
        
        # Clear config
        clear_config()
        
        # Verify it's cleared
        assert len(get_pre_hooks()) == 0

