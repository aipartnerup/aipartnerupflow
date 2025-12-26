"""
Test McpServer

Tests for MCP server main entry point.
"""

import pytest
from unittest.mock import AsyncMock, patch
from aipartnerupflow.api.mcp.server import McpServer


class TestMcpServer:
    """Test McpServer functionality"""
    
    @pytest.fixture
    def server(self):
        """Create MCP server instance"""
        return McpServer()
    
    @pytest.mark.asyncio
    async def test_handle_request_tools_list(self, server):
        """Test handling tools/list request"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        result = await server.handle_request(request)
        
        assert "tools" in result
        assert isinstance(result["tools"], list)
        assert len(result["tools"]) > 0
    
    @pytest.mark.asyncio
    async def test_handle_request_tools_call(self, server):
        """Test handling tools/call request"""
        mock_tool_result = {
            "content": [{"type": "text", "text": "test result"}]
        }
        
        with patch.object(server.tools_registry, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_tool_result
            
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "execute_task",
                    "arguments": {"task_id": "test-id"}
                }
            }
            
            result = await server.handle_request(request)
            
            assert result == mock_tool_result
            mock_call.assert_called_once_with(
                "execute_task",
                {"task_id": "test-id"},
                None
            )
    
    @pytest.mark.asyncio
    async def test_handle_request_resources_list(self, server):
        """Test handling resources/list request"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list",
            "params": {}
        }
        
        result = await server.handle_request(request)
        
        assert "resources" in result
        assert isinstance(result["resources"], list)
        assert len(result["resources"]) > 0
    
    @pytest.mark.asyncio
    async def test_handle_request_resources_read(self, server):
        """Test handling resources/read request"""
        mock_resource_result = {
            "contents": [{
                "uri": "task://test-id",
                "mimeType": "application/json",
                "text": "{}"
            }]
        }
        
        with patch.object(server.resources_registry, 'read_resource', new_callable=AsyncMock) as mock_read:
            mock_read.return_value = mock_resource_result
            
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/read",
                "params": {
                    "uri": "task://test-id"
                }
            }
            
            result = await server.handle_request(request)
            
            assert result == mock_resource_result
            mock_read.assert_called_once_with("task://test-id", None)
    
    @pytest.mark.asyncio
    async def test_handle_request_unknown_method(self, server):
        """Test handling unknown method"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown/method",
            "params": {}
        }
        
        with pytest.raises(ValueError, match="Unknown MCP method"):
            await server.handle_request(request)
    
    @pytest.mark.asyncio
    async def test_handle_request_tools_call_missing_name(self, server):
        """Test handling tools/call with missing tool name"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "arguments": {}
            }
        }
        
        with pytest.raises(ValueError, match="Tool name is required"):
            await server.handle_request(request)
    
    @pytest.mark.asyncio
    async def test_handle_request_resources_read_missing_uri(self, server):
        """Test handling resources/read with missing URI"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {}
        }
        
        with pytest.raises(ValueError, match="Resource URI is required"):
            await server.handle_request(request)
    
    def test_create_stdio_transport(self, server):
        """Test creating stdio transport"""
        transport = server.create_stdio_transport()
        
        assert transport is not None
        assert server.stdio_transport is not None
        assert server.stdio_transport == transport
    
    def test_create_http_transport(self, server):
        """Test creating HTTP transport"""
        transport = server.create_http_transport()
        
        assert transport is not None
        assert server.http_transport is not None
        assert server.http_transport == transport
    
    def test_get_http_routes(self, server):
        """Test getting HTTP routes"""
        routes = server.get_http_routes()
        
        assert isinstance(routes, list)
        assert len(routes) > 0
        
        # Check route structure
        for route in routes:
            assert hasattr(route, 'path')
            assert hasattr(route, 'methods')

