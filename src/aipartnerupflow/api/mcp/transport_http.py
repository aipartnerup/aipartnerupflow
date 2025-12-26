"""
MCP HTTP/SSE Transport Implementation

Handles MCP protocol communication via HTTP with Server-Sent Events support.
"""

import json
from typing import Dict, Any, Optional, Callable
from aipartnerupflow import __version__
try:
    from starlette.requests import Request
    from starlette.responses import JSONResponse, StreamingResponse
    from starlette.routing import Route
except ImportError:
    # Fallback for environments without starlette
    Request = None
    JSONResponse = None
    StreamingResponse = None
    Route = None
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class HttpTransport:
    """MCP transport via HTTP/SSE"""
    
    def __init__(
        self,
        request_handler: Callable[[Dict[str, Any], Request], Any]
    ):
        """
        Initialize HTTP transport
        
        Args:
            request_handler: Async function to handle MCP requests
        """
        self.request_handler = request_handler
    
    def create_routes(self) -> list[Route]:
        """
        Create Starlette routes for MCP HTTP endpoints
        
        Returns:
            List of Route objects
        """
        return [
            Route("/mcp", self.handle_post, methods=["POST"]),
            Route("/mcp/sse", self.handle_sse, methods=["GET"]),
        ]
    
    async def handle_post(self, request: Request) -> JSONResponse:
        """
        Handle HTTP POST request for MCP JSON-RPC
        
        Args:
            request: Starlette Request object
        
        Returns:
            JSONResponse with JSON-RPC response
        """
        try:
            # Parse JSON-RPC request
            body = await request.json()
            
            # Handle request
            response = await self._handle_request(body, request)
            
            # Check if response is an error to set appropriate status code
            # JSON-RPC error responses have an "error" field
            status_code = 500 if "error" in response else 200
            
            return JSONResponse(content=response, status_code=status_code)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request: {e}")
            return JSONResponse(
                status_code=400,
                content=self._create_error_response(
                    None,
                    -32700,
                    "Parse error",
                    str(e)
                )
            )
        except Exception as e:
            logger.error(f"Error handling HTTP request: {e}", exc_info=True)
            error_response = self._create_error_response(
                None,
                -32603,
                "Internal error",
                str(e)
            )
            return JSONResponse(
                status_code=500,
                content=error_response
            )
    
    async def handle_sse(self, request: Request) -> StreamingResponse:
        """
        Handle Server-Sent Events for streaming responses
        
        Args:
            request: Starlette Request object
        
        Returns:
            StreamingResponse with SSE events
        """
        # For now, SSE is not fully implemented
        # This would be used for streaming task execution updates
        async def event_generator():
            yield f"data: {json.dumps({'type': 'error', 'message': 'SSE not yet implemented'})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
    
    async def _handle_request(
        self,
        request: Dict[str, Any],
        http_request: Request
    ) -> Dict[str, Any]:
        """
        Handle a JSON-RPC request
        
        Args:
            request: JSON-RPC request
            http_request: Starlette Request object
        
        Returns:
            JSON-RPC response
        """
        request_id = request.get("id")
        method = request.get("method")
        request.get("params", {})
        
        # Handle initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {}
                    },
                    "serverInfo": {
                        "name": "aipartnerupflow",
                        "version": __version__
                    }
                }
            }
        
        # Handle other methods
        try:
            result = await self.request_handler(request, http_request)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            return self._create_error_response(
                request_id,
                -32603,
                "Internal error",
                str(e)
            )
    
    def _create_error_response(
        self,
        request_id: Any,
        code: int,
        message: str,
        data: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create JSON-RPC error response"""
        error = {
            "code": code,
            "message": message
        }
        if data:
            error["data"] = data
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error
        }

