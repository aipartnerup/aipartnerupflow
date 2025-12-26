"""
Test HttpTransport

Tests for MCP HTTP transport implementation.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from starlette.requests import Request
from starlette.responses import JSONResponse
from aipartnerupflow.api.mcp.transport_http import HttpTransport


class TestHttpTransport:
    """Test HttpTransport functionality"""
    
    @pytest.fixture
    def transport(self):
        """Create HTTP transport instance"""
        async def mock_handler(request, http_request):
            return {"result": "test"}
        return HttpTransport(mock_handler)
    
    def test_create_routes(self, transport):
        """Test creating HTTP routes"""
        routes = transport.create_routes()
        
        assert isinstance(routes, list)
        assert len(routes) >= 2  # At least /mcp and /mcp/sse
        
        # Check route paths
        paths = [route.path for route in routes]
        assert "/mcp" in paths
    
    @pytest.mark.asyncio
    async def test_handle_post_initialize(self, transport):
        """Test handling initialize request"""
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        
        response = await transport.handle_post(mock_request)
        
        assert isinstance(response, JSONResponse)
        content = json.loads(response.body.decode())
        assert content["jsonrpc"] == "2.0"
        assert content["id"] == 1
        assert "result" in content
        assert "protocolVersion" in content["result"]
    
    @pytest.mark.asyncio
    async def test_handle_post_tools_list(self, transport):
        """Test handling tools/list request"""
        async def mock_handler(request, http_request):
            if request.get("method") == "tools/list":
                return {"tools": []}
            return {}
        
        transport.request_handler = mock_handler
        
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        })
        
        response = await transport.handle_post(mock_request)
        
        assert isinstance(response, JSONResponse)
        content = json.loads(response.body.decode())
        assert content["jsonrpc"] == "2.0"
        assert "result" in content
    
    @pytest.mark.asyncio
    async def test_handle_post_invalid_json(self, transport):
        """Test handling invalid JSON"""
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
        
        response = await transport.handle_post(mock_request)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        content = json.loads(response.body.decode())
        assert "error" in content
        assert content["error"]["code"] == -32700
    
    @pytest.mark.asyncio
    async def test_handle_post_error(self, transport):
        """Test handling request error"""
        async def mock_handler(request, http_request):
            raise Exception("Test error")
        
        transport.request_handler = mock_handler
        
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "test",
            "params": {}
        })
        
        response = await transport.handle_post(mock_request)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        content = json.loads(response.body.decode())
        assert "error" in content
        assert content["error"]["code"] == -32603
    
    @pytest.mark.asyncio
    async def test_handle_sse(self, transport):
        """Test handling SSE request"""
        response = await transport.handle_sse(MagicMock(spec=Request))
        
        # SSE should return StreamingResponse
        # For now, it returns an error message
        assert hasattr(response, 'body_iterator')

