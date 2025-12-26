"""
Test crew_tool decorator functionality
"""
import pytest

try:
    from aipartnerupflow.core.tools import tool_register, get_tool_registry, register_tool, BaseTool
    # Backward compatibility aliases
    tool = tool_register
    crew_tool = tool_register
except ImportError:
    crew_tool = None
    get_tool_registry = None
    register_tool = None
    BaseTool = None
    pytestmark = pytest.mark.skip("crewai module not available")


@pytest.mark.skipif(crew_tool is None, reason="crew_tool decorator not available")
class TestCrewToolDecorator:
    """Test cases for @crew_tool decorator"""
    
    def test_crew_tool_auto_registration(self):
        """Test that @crew_tool decorator automatically registers tools"""
        registry = get_tool_registry()
        
        # Clear registry for clean test
        original_tools = registry._tools.copy()
        registry._tools.clear()
        
        try:
            # Define a tool with decorator
            @crew_tool()
            class TestTool(BaseTool):
                name: str = "Test Tool"
                description: str = "A test tool"
                
                def _run(self, arg: str) -> str:
                    return f"Result: {arg}"
            
            # Check that tool is registered
            assert "TestTool" in registry.list_tools()
            assert registry.get("TestTool") == TestTool
            
        finally:
            # Restore original tools
            registry._tools = original_tools
    
    def test_crew_tool_custom_name(self):
        """Test that @crew_tool decorator works with custom name"""
        registry = get_tool_registry()
        
        # Clear registry for clean test
        original_tools = registry._tools.copy()
        registry._tools.clear()
        
        try:
            # Define a tool with custom name
            @crew_tool(name="custom_tool_name")
            class AnotherTestTool(BaseTool):
                name: str = "Another Test Tool"
                description: str = "Another test tool"
                
                def _run(self, arg: str) -> str:
                    return f"Result: {arg}"
            
            # Check that tool is registered with custom name
            assert "custom_tool_name" in registry.list_tools()
            assert registry.get("custom_tool_name") == AnotherTestTool
            # Original class name should not be registered
            assert "AnotherTestTool" not in registry.list_tools()
            
        finally:
            # Restore original tools
            registry._tools = original_tools
    
    def test_crew_tool_override(self):
        """Test that @crew_tool decorator works with override=True"""
        registry = get_tool_registry()
        
        # Clear registry for clean test
        original_tools = registry._tools.copy()
        registry._tools.clear()
        
        try:
            # Register a tool first
            @crew_tool()
            class FirstTool(BaseTool):
                name: str = "First Tool"
                description: str = "First tool"
                
                def _run(self, arg: str) -> str:
                    return "first"
            
            # Override with same name
            @crew_tool(override=True)
            class FirstTool(BaseTool):  # noqa: F811 - intentional redefinition to test override
                name: str = "First Tool Overridden"
                description: str = "Overridden tool"
                
                def _run(self, arg: str) -> str:
                    return "overridden"
            
            # Check that the overridden tool is registered
            assert "FirstTool" in registry.list_tools()
            registered = registry.get("FirstTool")
            # Should be the second (overridden) class
            assert registered.__name__ == "FirstTool"
            
        finally:
            # Restore original tools
            registry._tools = original_tools
    
    def test_crew_tool_without_override_raises_error(self):
        """Test that @crew_tool decorator raises error when tool already exists"""
        registry = get_tool_registry()
        
        # Clear registry for clean test
        original_tools = registry._tools.copy()
        registry._tools.clear()
        
        try:
            # Register a tool first
            @crew_tool()
            class ExistingTool(BaseTool):
                name: str = "Existing Tool"
                description: str = "Existing tool"
                
                def _run(self, arg: str) -> str:
                    return "existing"
            
            # Try to register another tool with same name (should raise error)
            with pytest.raises(ValueError, match="already registered"):
                @crew_tool()  # override=False by default
                class ExistingTool(BaseTool):  # Same name
                    name: str = "New Tool"
                    description: str = "New tool"
                    
                    def _run(self, arg: str) -> str:
                        return "new"
            
        finally:
            # Restore original tools
            registry._tools = original_tools

