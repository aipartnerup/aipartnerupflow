"""
MCP (Model Context Protocol) Executor

This executor allows tasks to interact with MCP servers, enabling
AI applications to access external tools and data sources through
the standardized MCP protocol.

MCP supports two transport modes:
- stdio: Communication via standard input/output (for local processes)
- http/sse: Communication via HTTP with Server-Sent Events (for remote servers)
"""

import asyncio
import json
import subprocess
from typing import Dict, Any, Optional
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning(
        "httpx is not installed. HTTP/SSE transport mode will not be available. "
        "Install it with: pip install httpx"
    )


@executor_register()
class McpExecutor(BaseTask):
    """
    Executor for interacting with MCP (Model Context Protocol) servers
    
    Supports both stdio and HTTP/SSE transport modes for communication
    with MCP servers, enabling access to external tools and data sources.
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "mcp_executor"  # Executor id
        },
        "inputs": {
            "transport": "stdio",
            "command": ["python", "-m", "mcp_server"],
            "operation": "call_tool",
            "tool_name": "search_web",
            "arguments": {"query": "Python async"}
        }
    }
    """
    
    id = "mcp_executor"
    name = "MCP Executor"
    description = "Interact with MCP (Model Context Protocol) servers for tool and resource access"
    tags = ["mcp", "protocol", "tools", "resources"]
    examples = [
        "Call MCP tool",
        "List available MCP tools",
        "Read MCP resource",
        "Access external data sources via MCP"
    ]
    
    # Cancellation support: Can be cancelled by closing connection
    cancelable: bool = True
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "mcp"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP operation
        
        Args:
            inputs: Dictionary containing:
                - transport: Transport mode - "stdio" or "http" (required)
                - operation: MCP operation type (required):
                    - "list_tools": List available tools
                    - "call_tool": Call a tool with arguments
                    - "list_resources": List available resources
                    - "read_resource": Read a resource
                - For stdio transport:
                    - command: Command to run MCP server (list of strings, required)
                    - env: Optional environment variables dict
                    - cwd: Optional working directory
                - For http transport:
                    - url: MCP server URL (required)
                    - headers: Optional HTTP headers dict
                - For call_tool operation:
                    - tool_name: Name of tool to call (required)
                    - arguments: Tool arguments dict (required)
                - For read_resource operation:
                    - resource_uri: Resource URI (required)
                - timeout: Optional timeout in seconds (default: 30.0)
        
        Returns:
            Dictionary with operation result
        """
        transport = inputs.get("transport")
        if not transport:
            raise ValueError("transport is required in inputs (stdio or http)")
        
        operation = inputs.get("operation")
        if not operation:
            raise ValueError("operation is required in inputs (list_tools, call_tool, list_resources, read_resource)")
        
        timeout = inputs.get("timeout", 30.0)
        
        # Check for cancellation before execution
        if self.cancellation_checker and self.cancellation_checker():
            logger.info("MCP operation cancelled before execution")
            return {
                "success": False,
                "error": "Operation was cancelled",
                "transport": transport,
                "operation": operation
            }
        
        try:
            if transport == "stdio":
                return await self._execute_stdio(inputs, operation, timeout)
            elif transport == "http":
                if not HTTPX_AVAILABLE:
                    return {
                        "success": False,
                        "error": "httpx is not installed. Install it with: pip install httpx",
                        "transport": transport
                    }
                return await self._execute_http(inputs, operation, timeout)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported transport mode: {transport}. Use 'stdio' or 'http'",
                    "transport": transport
                }
        except asyncio.TimeoutError:
            logger.error(f"MCP operation timeout after {timeout} seconds")
            return {
                "success": False,
                "error": f"Operation timeout after {timeout} seconds",
                "transport": transport,
                "operation": operation
            }
        except Exception as e:
            logger.error(f"Error executing MCP operation: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "transport": transport,
                "operation": operation
            }
    
    async def _execute_stdio(
        self,
        inputs: Dict[str, Any],
        operation: str,
        timeout: float
    ) -> Dict[str, Any]:
        """Execute MCP operation via stdio transport"""
        command = inputs.get("command")
        if not command:
            raise ValueError("command is required for stdio transport (list of strings)")
        
        if not isinstance(command, list):
            raise ValueError("command must be a list of strings")
        
        env = inputs.get("env")
        cwd = inputs.get("cwd")
        
        # Prepare MCP request
        request_id = f"mcp_{asyncio.get_event_loop().time()}"
        mcp_request = self._build_mcp_request(operation, inputs, request_id)
        
        logger.info(f"Executing MCP {operation} via stdio: {command}")
        
        try:
            # Run MCP server process
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd
            )
            
            # Send MCP request
            request_json = json.dumps(mcp_request) + "\n"
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=request_json.encode('utf-8')),
                timeout=timeout
            )
            
            # Check for cancellation
            if self.cancellation_checker and self.cancellation_checker():
                process.kill()
                logger.info("MCP operation cancelled during execution")
                return {
                    "success": False,
                    "error": "Operation was cancelled",
                    "operation": operation
                }
            
            # Parse response
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else "Unknown error"
                logger.error(f"MCP server error: {error_msg}")
                return {
                    "success": False,
                    "error": f"MCP server error: {error_msg}",
                    "return_code": process.returncode,
                    "stderr": error_msg,
                    "operation": operation
                }
            
            response_text = stdout.decode('utf-8', errors='replace').strip()
            if not response_text:
                return {
                    "success": False,
                    "error": "Empty response from MCP server",
                    "operation": operation
                }
            
            # Parse JSON response (MCP uses JSON-RPC-like format)
            try:
                response = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse MCP response: {e}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {str(e)}",
                    "raw_response": response_text[:500],  # First 500 chars
                    "operation": operation
                }
            
            # Extract result from MCP response
            if "error" in response:
                error = response["error"]
                return {
                    "success": False,
                    "error": error.get("message", "Unknown error"),
                    "error_code": error.get("code"),
                    "error_data": error.get("data"),
                    "operation": operation
                }
            
            result = response.get("result", {})
            return {
                "success": True,
                "result": result,
                "operation": operation,
                "transport": "stdio"
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"MCP stdio operation timeout after {timeout} seconds")
            return {
                "success": False,
                "error": f"Operation timeout after {timeout} seconds",
                "operation": operation
            }
    
    async def _execute_http(
        self,
        inputs: Dict[str, Any],
        operation: str,
        timeout: float
    ) -> Dict[str, Any]:
        """Execute MCP operation via HTTP/SSE transport"""
        url = inputs.get("url")
        if not url:
            raise ValueError("url is required for http transport")
        
        headers = inputs.get("headers", {})
        headers.setdefault("Content-Type", "application/json")
        
        # Prepare MCP request
        request_id = f"mcp_{asyncio.get_event_loop().time()}"
        mcp_request = self._build_mcp_request(operation, inputs, request_id)
        
        logger.info(f"Executing MCP {operation} via HTTP: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Check for cancellation before request
                if self.cancellation_checker and self.cancellation_checker():
                    logger.info("MCP HTTP operation cancelled before request")
                    return {
                        "success": False,
                        "error": "Operation was cancelled",
                        "operation": operation
                    }
                
                # Send MCP request
                response = await client.post(
                    url,
                    json=mcp_request,
                    headers=headers
                )
                
                # Check for cancellation after request
                if self.cancellation_checker and self.cancellation_checker():
                    logger.info("MCP HTTP operation cancelled after request")
                    return {
                        "success": False,
                        "error": "Operation was cancelled",
                        "operation": operation,
                        "status_code": response.status_code
                    }
                
                if response.status_code != 200:
                    logger.error(f"MCP HTTP error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"HTTP error {response.status_code}: {response.text[:200]}",
                        "status_code": response.status_code,
                        "operation": operation
                    }
                
                # Parse response
                json_response = response.json()
                
                if "error" in json_response:
                    error = json_response["error"]
                    return {
                        "success": False,
                        "error": error.get("message", "Unknown error"),
                        "error_code": error.get("code"),
                        "error_data": error.get("data"),
                        "operation": operation
                    }
                
                result = json_response.get("result", {})
                return {
                    "success": True,
                    "result": result,
                    "operation": operation,
                    "transport": "http"
                }
                
        except httpx.TimeoutException:
            logger.error(f"MCP HTTP operation timeout after {timeout} seconds")
            return {
                "success": False,
                "error": f"Request timeout after {timeout} seconds",
                "operation": operation
            }
        except httpx.RequestError as e:
            logger.error(f"MCP HTTP request error: {e}")
            return {
                "success": False,
                "error": f"Request error: {str(e)}",
                "operation": operation
            }
    
    def _build_mcp_request(
        self,
        operation: str,
        inputs: Dict[str, Any],
        request_id: str
    ) -> Dict[str, Any]:
        """Build MCP protocol request"""
        # MCP uses JSON-RPC 2.0 format
        request = {
            "jsonrpc": "2.0",
            "id": request_id
        }
        
        if operation == "list_tools":
            request["method"] = "tools/list"
            request["params"] = {}
        elif operation == "call_tool":
            tool_name = inputs.get("tool_name")
            if not tool_name:
                raise ValueError("tool_name is required for call_tool operation")
            arguments = inputs.get("arguments", {})
            request["method"] = "tools/call"
            request["params"] = {
                "name": tool_name,
                "arguments": arguments
            }
        elif operation == "list_resources":
            request["method"] = "resources/list"
            request["params"] = {}
        elif operation == "read_resource":
            resource_uri = inputs.get("resource_uri")
            if not resource_uri:
                raise ValueError("resource_uri is required for read_resource operation")
            request["method"] = "resources/read"
            request["params"] = {
                "uri": resource_uri
            }
        else:
            raise ValueError(f"Unsupported operation: {operation}")
        
        return request
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "transport": {
                    "type": "string",
                    "enum": ["stdio", "http"],
                    "description": "Transport mode: 'stdio' for local processes, 'http' for remote servers"
                },
                "operation": {
                    "type": "string",
                    "enum": ["list_tools", "call_tool", "list_resources", "read_resource"],
                    "description": "MCP operation type"
                },
                "command": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command to run MCP server (required for stdio transport)"
                },
                "url": {
                    "type": "string",
                    "description": "MCP server URL (required for http transport)"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers (optional, for http transport)"
                },
                "env": {
                    "type": "object",
                    "description": "Environment variables (optional, for stdio transport)"
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional, for stdio transport)"
                },
                "tool_name": {
                    "type": "string",
                    "description": "Name of tool to call (required for call_tool operation)"
                },
                "arguments": {
                    "type": "object",
                    "description": "Tool arguments (required for call_tool operation)"
                },
                "resource_uri": {
                    "type": "string",
                    "description": "Resource URI (required for read_resource operation)"
                },
                "timeout": {
                    "type": "number",
                    "description": "Operation timeout in seconds (default: 30.0)"
                }
            },
            "required": ["transport", "operation"]
        }
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo MCP operation result"""
        operation = inputs.get("operation", "list_tools")
        transport = inputs.get("transport", "stdio")
        
        if operation == "list_tools":
            return {
                "tools": [
                    {
                        "name": "demo_tool",
                        "description": "Demo MCP tool",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "input": {"type": "string"}
                            }
                        }
                    }
                ],
                "transport": transport,
                "success": True,
                "_demo_sleep": 0.15  # Simulate MCP protocol communication latency
            }
        elif operation == "call_tool":
            tool_name = inputs.get("tool_name", "demo_tool")
            arguments = inputs.get("arguments", {})
            return {
                "tool": tool_name,
                "arguments": arguments,
                "result": {
                    "output": "Demo tool execution result",
                    "success": True
                },
                "transport": transport,
                "success": True,
                "_demo_sleep": 0.2  # Simulate tool execution time
            }
        elif operation == "list_resources":
            return {
                "resources": [
                    {
                        "uri": "demo://resource/1",
                        "name": "Demo Resource",
                        "description": "A demo resource",
                        "mimeType": "text/plain"
                    }
                ],
                "transport": transport,
                "success": True,
                "_demo_sleep": 0.15  # Simulate MCP protocol communication latency
            }
        elif operation == "read_resource":
            resource_uri = inputs.get("resource_uri", "demo://resource/1")
            return {
                "uri": resource_uri,
                "contents": [
                    {
                        "uri": resource_uri,
                        "mimeType": "text/plain",
                        "text": "Demo resource content"
                    }
                ],
                "transport": transport,
                "success": True,
                "_demo_sleep": 0.15  # Simulate resource read latency
            }
        else:
            return {
                "operation": operation,
                "transport": transport,
                "result": "Demo MCP operation completed",
                "success": True,
                "_demo_sleep": 0.15  # Simulate MCP protocol communication latency
            }

