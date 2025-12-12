"""
MCP Server Implementation

Main MCP server that integrates tools, resources, and transports.
"""

import asyncio
from typing import Dict, Any, Optional, Type, TYPE_CHECKING
from starlette.requests import Request
from aipartnerupflow.api.mcp.adapter import TaskRoutesAdapter
from aipartnerupflow.api.mcp.tools import McpToolsRegistry
from aipartnerupflow.api.mcp.resources import McpResourcesRegistry
from aipartnerupflow.api.mcp.transport_stdio import StdioTransport
from aipartnerupflow.api.mcp.transport_http import HttpTransport
from aipartnerupflow.core.utils.logger import get_logger

if TYPE_CHECKING:
    from aipartnerupflow.api.routes.tasks import TaskRoutes

logger = get_logger(__name__)


class McpServer:
    """
    MCP Server for aipartnerupflow
    
    Exposes task orchestration capabilities as MCP tools and resources.
    Supports both stdio and HTTP/SSE transport modes.
    """
    
    def __init__(self, task_routes_class: Optional["Type[TaskRoutes]"] = None):
        """
        Initialize MCP server
        
        Args:
            task_routes_class: Optional custom TaskRoutes class to use instead of default TaskRoutes.
                             Allows extending TaskRoutes functionality without monkey patching.
                             Example: task_routes_class=MyCustomTaskRoutes
        """
        self.adapter = TaskRoutesAdapter(task_routes_class=task_routes_class)
        self.tools_registry = McpToolsRegistry(self.adapter)
        self.resources_registry = McpResourcesRegistry(self.adapter)
        self.stdio_transport: Optional[StdioTransport] = None
        self.http_transport: Optional[HttpTransport] = None
    
    async def handle_request(
        self,
        request: Dict[str, Any],
        http_request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Handle MCP JSON-RPC request
        
        Args:
            request: JSON-RPC request
            http_request: Optional Starlette Request (for HTTP mode)
        
        Returns:
            JSON-RPC response result
        """
        method = request.get("method")
        params = request.get("params", {})
        
        # Handle MCP protocol methods
        if method == "tools/list":
            return {
                "tools": self.tools_registry.list_tools()
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                raise ValueError("Tool name is required")
            
            result = await self.tools_registry.call_tool(
                tool_name,
                arguments,
                http_request
            )
            return result
        
        elif method == "resources/list":
            return {
                "resources": self.resources_registry.list_resources()
            }
        
        elif method == "resources/read":
            uri = params.get("uri")
            
            if not uri:
                raise ValueError("Resource URI is required")
            
            result = await self.resources_registry.read_resource(
                uri,
                http_request
            )
            return result
        
        else:
            raise ValueError(f"Unknown MCP method: {method}")
    
    def create_stdio_transport(self) -> StdioTransport:
        """
        Create stdio transport
        
        Returns:
            StdioTransport instance
        """
        self.stdio_transport = StdioTransport(self.handle_request)
        return self.stdio_transport
    
    def create_http_transport(self) -> HttpTransport:
        """
        Create HTTP transport
        
        Returns:
            HttpTransport instance
        """
        async def request_handler(req: Dict[str, Any], http_req: Request):
            return await self.handle_request(req, http_req)
        
        self.http_transport = HttpTransport(request_handler)
        return self.http_transport
    
    async def run_stdio(self):
        """Run MCP server in stdio mode"""
        transport = self.create_stdio_transport()
        await transport.start()
    
    def get_http_routes(self) -> list:
        """
        Get HTTP routes for integration with FastAPI/Starlette
        
        Returns:
            List of Route objects
        """
        transport = self.create_http_transport()
        return transport.create_routes()


async def main_stdio():
    """Main entry point for stdio mode"""
    server = McpServer()
    await server.run_stdio()


if __name__ == "__main__":
    # Run in stdio mode
    asyncio.run(main_stdio())

