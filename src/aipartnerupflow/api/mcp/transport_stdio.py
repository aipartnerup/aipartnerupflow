"""
MCP stdio Transport Implementation

Handles MCP protocol communication via standard input/output.
"""

import asyncio
import json
import sys
from typing import Any, Callable, Dict, Optional, Union

from aipartnerupflow import __version__
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class StdioTransport:
    """MCP transport via stdio"""

    def __init__(self, request_handler: Callable[[Dict[str, Any]], Any]):
        """
        Initialize stdio transport

        Args:
            request_handler: Async function to handle MCP requests
        """
        self.request_handler = request_handler
        self.running = False

    async def start(self):
        """Start stdio transport loop"""
        self.running = True
        logger.info("Starting MCP stdio transport")

        # Read from stdin line by line
        loop = asyncio.get_event_loop()

        # Use asyncio to read from stdin
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while self.running:
            try:
                # Read a line from stdin
                line = await reader.readline()
                if not line:
                    # EOF
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                # Parse JSON-RPC request
                try:
                    request = json.loads(line_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in request: {e}")
                    response = self._create_error_response(None, -32700, "Parse error", str(e))
                    await self._send_response(response)
                    continue

                # Handle request
                response = await self._handle_request(request)

                # Send response
                await self._send_response(response)

            except Exception as e:
                logger.error(f"Error in stdio transport: {e}", exc_info=True)
                response = self._create_error_response(None, -32603, "Internal error", str(e))
                await self._send_response(response)

    async def stop(self):
        """Stop stdio transport"""
        self.running = False
        logger.info("Stopping MCP stdio transport")

    async def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a JSON-RPC request

        Args:
            request: JSON-RPC request

        Returns:
            JSON-RPC response
        """
        request_id = request.get("id")
        method = request.get("method")

        # Handle initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": "aipartnerupflow", "version": __version__},
                },
            }

        # Handle other methods
        try:
            result = await self.request_handler(request)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            return self._create_error_response(request_id, -32603, "Internal error", str(e))

    async def _send_response(self, response: Dict[str, Any]):
        """Send JSON-RPC response to stdout"""
        response_json = json.dumps(response, ensure_ascii=False)
        sys.stdout.write(response_json + "\n")
        sys.stdout.flush()

    def _create_error_response(
        self,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create JSON-RPC error response"""
        error = {"code": code, "message": message}
        if data:
            error["data"] = data

        return {"jsonrpc": "2.0", "id": request_id, "error": error}
