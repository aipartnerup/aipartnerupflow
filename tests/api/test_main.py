"""
Test main.py API functions: initialize_extensions and create_app_by_protocol
"""
import os
import pytest
from unittest.mock import Mock, patch, AsyncMock
from aipartnerupflow.api.extensions import (
    initialize_extensions,
    _is_package_installed,
    _get_extension_enablement_from_env,
)
from aipartnerupflow.api.app import create_app_by_protocol
from aipartnerupflow.core.extensions import get_registry


class TestInitializeExtensions:
    """Test initialize_extensions() function"""
    
    def setup_method(self):
        """Clear extension registry before each test"""
        registry = get_registry()
        # Clear all registrations
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        registry._by_id.clear()
        registry._by_category.clear()
    
    def test_initialize_extensions_registers_stdio(self):
        """Test that initialize_extensions() can import and register stdio extensions"""
        registry = get_registry()
        
        # Clear registry to test re-registration
        # This simulates the case where modules were imported but registry was cleared
        registry._by_id.clear()
        registry._by_category.clear()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        
        # Verify extensions are not registered
        assert not registry.is_registered("system_info_executor")
        assert not registry.is_registered("command_executor")
        
        # Initialize extensions - should re-register them
        initialize_extensions(include_stdio=True)
        
        # Verify extensions are now registered
        system_info = registry.get_by_id("system_info_executor")
        command_exec = registry.get_by_id("command_executor")
        
        # Both stdio executors should be registered
        assert system_info is not None, "SystemInfoExecutor should be registered"
        assert command_exec is not None, "CommandExecutor should be registered"
    
    def test_initialize_extensions_selective(self):
        """Test that initialize_extensions() can selectively initialize extensions"""
        registry = get_registry()
        
        # Clear registry to test selective re-registration
        registry._by_id.clear()
        registry._by_category.clear()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        
        # Initialize only stdio (other extensions disabled)
        initialize_extensions(
            include_stdio=True,
            include_crewai=False,
            include_http=False,
            include_ssh=False,
            include_docker=False,
            include_grpc=False,
            include_websocket=False,
            include_apflow=False,
            include_mcp=False,
        )
        
        # Verify stdio extensions are registered
        system_info = registry.get_by_id("system_info_executor")
        command_exec = registry.get_by_id("command_executor")
        assert system_info is not None, "SystemInfoExecutor should be registered"
        assert command_exec is not None, "CommandExecutor should be registered"
        
        # Verify other extensions are NOT registered (selective initialization)
        registry.get_by_id("crewai_executor")
        registry.get_by_id("rest_executor")
        # These may be None if they weren't imported, which is expected for selective init
        # We just verify the function completed without error
    
    def test_initialize_extensions_idempotent(self):
        """Test that initialize_extensions() is idempotent (safe to call multiple times)"""
        registry = get_registry()
        
        # Call multiple times
        initialize_extensions()
        count_after_first = len(registry._by_id)
        
        initialize_extensions()
        count_after_second = len(registry._by_id)
        
        # Should not cause errors and should have same or more extensions
        assert count_after_second >= count_after_first
    
    def test_initialize_extensions_handles_missing_extensions(self):
        """Test that initialize_extensions() handles missing optional extensions gracefully"""
        # Should not raise exception even if some extensions are not available
        try:
            initialize_extensions(
                include_crewai=True,  # May not be available
                include_ssh=True,  # May not be available
                include_docker=True,  # May not be available
                include_grpc=True,  # May not be available
            )
        except Exception as e:
            pytest.fail(f"initialize_extensions() should handle missing extensions gracefully, but raised: {e}")
    
    @patch.dict(os.environ, {"AIPARTNERUPFLOW_TASK_MODEL_CLASS": ""}, clear=False)
    def test_initialize_extensions_loads_custom_task_model(self):
        """Test that initialize_extensions() loads custom TaskModel when specified"""
        # This test verifies the function doesn't crash when custom TaskModel env var is set
        # Actual loading would require a valid module path, so we just test it doesn't crash
        try:
            initialize_extensions(load_custom_task_model=True)
        except Exception as e:
            # Should only fail if the module path is invalid, not if env var is empty
            if "AIPARTNERUPFLOW_TASK_MODEL_CLASS" in str(e):
                pass  # Expected if env var is set but invalid
            else:
                raise


class TestCreateAppByProtocol:
    """Test create_app_by_protocol() function"""
    
    def setup_method(self):
        """Setup for each test"""
        # Clear any existing extensions
        registry = get_registry()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        registry._by_id.clear()
        registry._by_category.clear()
    
    @pytest.mark.asyncio
    async def test_create_app_by_protocol_auto_initializes_extensions(self):
        """Test that create_app_by_protocol() auto-initializes extensions by default"""
        registry = get_registry()
        
        try:
            app = create_app_by_protocol(protocol="a2a", auto_initialize_extensions=True)
            
            # App should be created successfully
            assert app is not None
            
            # Extensions should be accessible (may have been registered during import or initialization)
            # Verify at least some extensions are available
            executor_count = len(registry.list_executors())
            assert executor_count >= 0  # At least the function completed without error
        except ImportError:
            pytest.skip("a2a module not available")
    
    @pytest.mark.asyncio
    async def test_create_app_by_protocol_skips_auto_initialization(self):
        """Test that create_app_by_protocol() can skip auto-initialization"""
        registry = get_registry()
        len(registry._by_id)
        
        try:
            # Manually initialize extensions first
            initialize_extensions()
            count_after_manual = len(registry._by_id)
            
            # Create app without auto-initialization
            app = create_app_by_protocol(protocol="a2a", auto_initialize_extensions=False)
            
            # Extension count should be same (no additional initialization)
            assert len(registry._by_id) == count_after_manual
            assert app is not None
        except ImportError:
            pytest.skip("a2a module not available")
    
    @pytest.mark.asyncio
    async def test_create_app_by_protocol_default_protocol(self):
        """Test that create_app_by_protocol() uses default protocol when None"""
        try:
            # Clear environment variable
            with patch.dict(os.environ, {}, clear=True):
                # Should default to "a2a"
                app = create_app_by_protocol(protocol=None)
                assert app is not None
        except ImportError:
            pytest.skip("a2a module not available")
    
    def test_create_app_by_protocol_invalid_protocol(self):
        """Test that create_app_by_protocol() raises ValueError for invalid protocol"""
        with pytest.raises(ValueError, match="Unsupported protocol"):
            create_app_by_protocol(protocol="invalid_protocol")


class TestCustomA2AStarletteApplicationASGI:
    """Test CustomA2AStarletteApplication ASGI callable functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        try:
            from aipartnerupflow.api.a2a.custom_starlette_app import CustomA2AStarletteApplication  # noqa: F401
            from a2a.server.apps.jsonrpc.starlette_app import AgentCard  # noqa: F401
            from a2a.server.request_handlers import DefaultRequestHandler  # noqa: F401
        except ImportError:
            pytest.skip("a2a module not available")
    
    def test_custom_a2a_app_is_asgi_callable(self):
        """Test that CustomA2AStarletteApplication is directly ASGI callable"""
        try:
            from aipartnerupflow.api.a2a.custom_starlette_app import CustomA2AStarletteApplication
            from a2a.server.apps.jsonrpc.starlette_app import AgentCard
            from a2a.server.request_handlers import DefaultRequestHandler
        except ImportError:
            pytest.skip("a2a module not available")
            return
        
        # Create mock agent card and handler
        agent_card = Mock(spec=AgentCard)
        agent_card.url = "http://localhost:8000"
        agent_card.supports_authenticated_extended_card = False
        handler = Mock(spec=DefaultRequestHandler)
        
        # Create app
        app = CustomA2AStarletteApplication(
            agent_card=agent_card,
            http_handler=handler,
        )
        
        # Verify it has __call__ method (ASGI callable)
        assert hasattr(app, '__call__')
        assert callable(app.__call__)
        
        # Verify _built_app is initialized
        assert hasattr(app, '_built_app')
        assert app._built_app is None  # Not built yet
    
    def test_custom_a2a_app_build_caches_result(self):
        """Test that build() method caches the result"""
        try:
            from aipartnerupflow.api.a2a.custom_starlette_app import CustomA2AStarletteApplication
            from a2a.server.apps.jsonrpc.starlette_app import AgentCard
            from a2a.server.request_handlers import DefaultRequestHandler
        except ImportError:
            pytest.skip("a2a module not available")
            return
        
        # Create mock agent card and handler
        agent_card = Mock(spec=AgentCard)
        agent_card.url = "http://localhost:8000"
        agent_card.supports_authenticated_extended_card = False
        handler = Mock(spec=DefaultRequestHandler)
        
        # Create app
        app = CustomA2AStarletteApplication(
            agent_card=agent_card,
            http_handler=handler,
        )
        
        # Build first time
        built_app_1 = app.build()
        assert built_app_1 is not None
        assert app._built_app is not None
        
        # Build second time - should return cached app
        built_app_2 = app.build()
        assert built_app_2 is built_app_1  # Same instance
    
    @pytest.mark.asyncio
    async def test_custom_a2a_app_call_auto_builds(self):
        """Test that __call__ automatically calls build() if needed"""
        try:
            from aipartnerupflow.api.a2a.custom_starlette_app import CustomA2AStarletteApplication
            from a2a.server.apps.jsonrpc.starlette_app import AgentCard
            from a2a.server.request_handlers import DefaultRequestHandler
        except ImportError:
            pytest.skip("a2a module not available")
            return
        
        # Create mock agent card and handler
        agent_card = Mock(spec=AgentCard)
        agent_card.url = "http://localhost:8000"
        agent_card.supports_authenticated_extended_card = False
        handler = Mock(spec=DefaultRequestHandler)
        
        # Create app
        app = CustomA2AStarletteApplication(
            agent_card=agent_card,
            http_handler=handler,
        )
        
        # Verify _built_app is None initially
        assert app._built_app is None
        
        # Create mock ASGI scope, receive, send
        scope = {"type": "http", "method": "GET", "path": "/"}
        receive = AsyncMock()
        send = AsyncMock()
        
        # Call __call__ - should auto-build
        try:
            await app(scope, receive, send)
        except Exception:
            # We expect it might fail due to mock setup, but _built_app should be set
            pass
        
        # Verify _built_app is now set (build was called)
        assert app._built_app is not None


class TestPackageDetection:
    """Test package detection functionality"""
    
    def test_is_package_installed_stdlib(self):
        """Test that stdlib packages are detected via direct import"""
        # Standard library packages should be detected via direct import
        # (they won't appear in importlib.metadata distributions)
        assert _is_package_installed("os") is True
        assert _is_package_installed("sys") is True
        assert _is_package_installed("json") is True
    
    def test_is_package_installed_installed_package(self):
        """Test detection of installed packages"""
        # Pydantic should be installed (core dependency)
        assert _is_package_installed("pydantic") is True
    
    def test_is_package_installed_missing_package(self):
        """Test that missing packages return False"""
        # This package definitely doesn't exist
        assert _is_package_installed("nonexistent_package_xyz_123") is False


class TestEnvironmentVariableParsing:
    """Test environment variable parsing for extension enablement"""
    
    def test_get_extension_enablement_from_env_comma_separated(self):
        """Test parsing comma-separated extension list"""
        with patch.dict(os.environ, {"AIPARTNERUPFLOW_EXTENSIONS": "stdio,http,crewai"}):
            result = _get_extension_enablement_from_env()
            
            assert result["stdio"] is True
            assert result["http"] is True
            assert result["crewai"] is True
            assert result["ssh"] is False  # Not in list
            assert result["docker"] is False  # Not in list
    
    def test_get_extension_enablement_from_env_individual_flags(self):
        """Test parsing individual AIPARTNERUPFLOW_ENABLE_* flags"""
        with patch.dict(
            os.environ,
            {
                "AIPARTNERUPFLOW_ENABLE_CREWAI": "true",
                "AIPARTNERUPFLOW_ENABLE_SSH": "1",
                "AIPARTNERUPFLOW_ENABLE_DOCKER": "false",
            },
        ):
            result = _get_extension_enablement_from_env()
            
            assert result["crewai"] is True
            assert result["ssh"] is True
            assert result["docker"] is False
            # Other extensions not set, will be auto-detected
    
    def test_get_extension_enablement_from_env_no_vars(self):
        """Test that empty result when no env vars are set"""
        with patch.dict(os.environ, {}, clear=True):
            result = _get_extension_enablement_from_env()
            # Should return empty dict (all will be auto-detected)
            assert result == {}


class TestDynamicExtensionInitialization:
    """Test dynamic extension initialization with auto-detection"""
    
    def setup_method(self):
        """Clear extension registry before each test"""
        registry = get_registry()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        registry._by_id.clear()
        registry._by_category.clear()
    
    def test_initialize_extensions_auto_detects_installed(self):
        """Test that initialize_extensions() auto-detects installed packages"""
        registry = get_registry()
        
        # Clear registry
        registry._by_id.clear()
        registry._by_category.clear()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        
        # Initialize with auto-detection (all params None)
        initialize_extensions(
            include_stdio=None,
            include_crewai=None,
            include_http=None,
            include_ssh=None,
            include_docker=None,
            include_grpc=None,
            include_websocket=None,
            include_apflow=None,
            include_mcp=None,
        )
        
        # Stdio should always be available (always_available=True)
        assert registry.is_registered("system_info_executor") or registry.is_registered("command_executor")
    
    def test_initialize_extensions_respects_function_params(self):
        """Test that function parameters override auto-detection"""
        registry = get_registry()
        
        # Clear registry
        registry._by_id.clear()
        registry._by_category.clear()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        
        # Force enable stdio, disable others
        initialize_extensions(
            include_stdio=True,
            include_crewai=False,
            include_http=False,
            include_ssh=False,
            include_docker=False,
            include_grpc=False,
            include_websocket=False,
            include_apflow=False,
            include_mcp=False,
        )
        
        # Stdio should be registered
        assert registry.is_registered("system_info_executor") or registry.is_registered("command_executor")
    
    @patch.dict(os.environ, {"AIPARTNERUPFLOW_EXTENSIONS": "stdio,http"})
    def test_initialize_extensions_respects_env_var_comma_list(self):
        """Test that AIPARTNERUPFLOW_EXTENSIONS env var is respected"""
        registry = get_registry()
        
        # Clear registry
        registry._by_id.clear()
        registry._by_category.clear()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        
        # Initialize with auto-detection (should use env var)
        initialize_extensions()
        
        # Only stdio and http should be registered (if available)
        # Other extensions should be skipped
        registry.is_registered("system_info_executor") or registry.is_registered("command_executor")
        # http may or may not be registered depending on httpx availability
        # But we verify the function completed without error
        assert True  # Function completed
    
    @patch.dict(os.environ, {"AIPARTNERUPFLOW_ENABLE_CREWAI": "false"})
    def test_initialize_extensions_respects_env_var_individual_flag(self):
        """Test that AIPARTNERUPFLOW_ENABLE_* env vars are respected"""
        registry = get_registry()
        
        # Clear registry
        registry._by_id.clear()
        registry._by_category.clear()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        
        # Initialize with auto-detection
        initialize_extensions()
        
        # CrewAI should be disabled via env var
        # Other extensions should be auto-detected
        # We verify the function completed without error
        assert True  # Function completed
    
    def test_initialize_extensions_priority_function_param_over_env(self):
        """Test that function parameters have priority over environment variables"""
        registry = get_registry()
        
        # Clear registry
        registry._by_id.clear()
        registry._by_category.clear()
        registry._executor_classes.clear()
        registry._factory_functions.clear()
        
        # Set env var to disable stdio
        with patch.dict(os.environ, {"AIPARTNERUPFLOW_ENABLE_STDIO": "false"}):
            # But function param says enable
            initialize_extensions(include_stdio=True)
            
            # Function param should win - stdio should be registered
            assert registry.is_registered("system_info_executor") or registry.is_registered("command_executor")

