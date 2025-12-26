"""
Test TaskRoutes extension mechanism
"""
import pytest
from unittest.mock import Mock
from aipartnerupflow.api.routes.tasks import TaskRoutes


class CustomTaskRoutes(TaskRoutes):
    """Custom TaskRoutes for testing extension mechanism"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_initialized = True
    
    async def handle_task_create(self, params, request, request_id):
        """Override handle_task_create to add custom logic"""
        # Call parent implementation
        result = await super().handle_task_create(params, request, request_id)
        # Add custom field
        if isinstance(result, dict) and "result" in result:
            result["custom_field"] = "custom_value"
        return result


class TestTaskRoutesExtension:
    """Test TaskRoutes extension mechanism"""
    
    @pytest.mark.asyncio
    async def test_create_a2a_server_with_custom_task_routes(self):
        """Test creating A2A server with custom TaskRoutes class"""
        try:
            from aipartnerupflow.api.a2a.server import create_a2a_server
        except ImportError:
            pytest.skip("a2a module not available")
            return
        
        # Create server with custom TaskRoutes
        server = create_a2a_server(
            verify_token_secret_key=None,
            base_url="http://localhost:8000",
            task_routes_class=CustomTaskRoutes
        )
        
        # Verify custom TaskRoutes was used
        assert hasattr(server, 'task_routes')
        assert isinstance(server.task_routes, CustomTaskRoutes)
        assert server.task_routes.custom_initialized is True
    
    @pytest.mark.asyncio
    async def test_create_a2a_server_default_task_routes(self):
        """Test that default TaskRoutes is used when not specified"""
        try:
            from aipartnerupflow.api.a2a.server import create_a2a_server
        except ImportError:
            pytest.skip("a2a module not available")
            return
        
        # Create server without custom TaskRoutes
        server = create_a2a_server(
            verify_token_secret_key=None,
            base_url="http://localhost:8000"
        )
        
        # Verify default TaskRoutes was used
        assert hasattr(server, 'task_routes')
        assert isinstance(server.task_routes, TaskRoutes)
        assert not isinstance(server.task_routes, CustomTaskRoutes)
    
    def test_custom_starlette_app_with_task_routes_class(self):
        """Test CustomA2AStarletteApplication with custom TaskRoutes class"""
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
        
        # Create app with custom TaskRoutes
        app = CustomA2AStarletteApplication(
            agent_card=agent_card,
            http_handler=handler,
            task_routes_class=CustomTaskRoutes
        )
        
        # Verify custom TaskRoutes was used
        assert hasattr(app, 'task_routes')
        assert isinstance(app.task_routes, CustomTaskRoutes)
        assert app.task_routes.custom_initialized is True
    
    def test_custom_starlette_app_with_custom_routes(self):
        """Test CustomA2AStarletteApplication with custom routes"""
        try:
            from aipartnerupflow.api.a2a.custom_starlette_app import CustomA2AStarletteApplication
            from starlette.routing import Route
            from starlette.responses import JSONResponse
            from a2a.server.apps.jsonrpc.starlette_app import AgentCard
            from a2a.server.request_handlers import DefaultRequestHandler
        except ImportError:
            pytest.skip("a2a module not available")
            return
        
        # Create custom route
        async def custom_handler(request):
            return JSONResponse({"custom": "route"})
        
        custom_route = Route("/custom", custom_handler, methods=["GET"])
        
        # Create mock agent card and handler
        agent_card = Mock(spec=AgentCard)
        agent_card.url = "http://localhost:8000"
        agent_card.supports_authenticated_extended_card = False
        handler = Mock(spec=DefaultRequestHandler)
        
        # Create app with custom routes
        app = CustomA2AStarletteApplication(
            agent_card=agent_card,
            http_handler=handler,
            custom_routes=[custom_route]
        )
        
        # Verify custom routes are included
        routes = app.routes()
        route_paths = [route.path for route in routes]
        assert "/custom" in route_paths

