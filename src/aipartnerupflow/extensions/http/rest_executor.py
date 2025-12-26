"""
REST API Executor for executing HTTP requests

This executor allows tasks to make HTTP requests to external APIs,
webhooks, and HTTP-based services.
"""

import json
import httpx
from typing import Dict, Any, Optional
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.execution.errors import ValidationError
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


@executor_register()
class RestExecutor(BaseTask):
    """
    Executor for executing HTTP/REST API requests
    
    Supports GET, POST, PUT, DELETE, PATCH methods with authentication,
    custom headers, query parameters, and request bodies.
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "rest_executor"  # Executor id
        },
        "inputs": {
            "url": "https://api.example.com/users",
            "method": "GET",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 30
        }
    }
    """
    
    id = "rest_executor"
    name = "REST API Executor"
    description = "Execute HTTP/REST API requests with authentication and custom headers"
    tags = ["http", "rest", "api", "webhook"]
    examples = [
        "Call external REST API",
        "Send webhook notification",
        "Fetch data from HTTP service"
    ]
    
    # Cancellation support: Can be cancelled by closing the HTTP client
    cancelable: bool = True
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "http"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an HTTP request
        
        Args:
            inputs: Dictionary containing:
                - url: Target URL (required)
                - method: HTTP method (GET, POST, PUT, DELETE, PATCH, default: GET)
                - headers: Optional HTTP headers dict
                - params: Optional query parameters dict
                - json: Optional JSON body (dict)
                - data: Optional form data (dict)
                - timeout: Optional timeout in seconds (default: 30.0)
                - auth: Optional authentication dict:
                    - {"type": "bearer", "token": "..."}
                    - {"type": "basic", "username": "...", "password": "..."}
                    - {"type": "apikey", "key": "...", "value": "...", "location": "header|query"}
                - verify: Optional SSL verification (default: True)
                - follow_redirects: Optional follow redirects (default: True)
        
        Returns:
            Dictionary with response data:
                - status_code: HTTP status code
                - headers: Response headers
                - body: Response body (text)
                - json: Response body (parsed JSON, if applicable)
                - success: Boolean indicating if request was successful (2xx status)
                - url: Final URL after redirects
        """
        url = inputs.get("url")
        if not url:
            raise ValidationError(f"[{self.id}] url is required in inputs")
        
        method = inputs.get("method", "GET").upper()
        headers = inputs.get("headers", {})
        params = inputs.get("params")
        json_data = inputs.get("json")
        data = inputs.get("data")
        timeout = inputs.get("timeout", 30.0)
        verify = inputs.get("verify", True)
        follow_redirects = inputs.get("follow_redirects", True)
        
        # Handle authentication
        auth_config = inputs.get("auth")
        auth = None
        if auth_config:
            auth_type = auth_config.get("type", "").lower()
            if auth_type == "bearer":
                token = auth_config.get("token")
                if token:
                    headers.setdefault("Authorization", f"Bearer {token}")
            elif auth_type == "basic":
                username = auth_config.get("username")
                password = auth_config.get("password")
                if username and password:
                    auth = httpx.BasicAuth(username, password)
            elif auth_type == "apikey":
                key = auth_config.get("key")
                value = auth_config.get("value")
                location = auth_config.get("location", "header").lower()
                if key and value:
                    if location == "header":
                        headers[key] = value
                    elif location == "query":
                        if params is None:
                            params = {}
                        params[key] = value
        
        # Prepare request kwargs (verify and timeout go to AsyncClient, not request)
        request_kwargs = {
            "method": method,
            "url": url,
            "headers": headers,
            "follow_redirects": follow_redirects,
        }
        
        if params:
            request_kwargs["params"] = params
        if json_data is not None:
            request_kwargs["json"] = json_data
        elif data is not None:
            request_kwargs["data"] = data
        if auth:
            request_kwargs["auth"] = auth
        
        logger.info(f"Executing HTTP {method} request to {url}")
        
        async with httpx.AsyncClient(verify=verify, timeout=timeout) as client:
            # Check for cancellation before making request
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("Request cancelled before execution")
                return {
                    "success": False,
                    "error": "Request was cancelled",
                    "url": url,
                    "method": method
                }
            
            # Exceptions (e.g., httpx.TimeoutException, httpx.ConnectError)
            # will propagate to TaskManager
            response = await client.request(**request_kwargs)
            
            # Check for cancellation after request
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("Request cancelled after execution")
                return {
                    "success": False,
                    "error": "Request was cancelled",
                    "url": url,
                    "method": method,
                    "status_code": response.status_code
                }
            
            # Try to parse JSON response
            json_response = None
            try:
                json_response = response.json()
            except Exception:
                pass
            
            result = {
                "url": str(response.url),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
                "json": json_response,
                "success": 200 <= response.status_code < 300,
                "method": method
            }
            
            if not result["success"]:
                logger.warning(
                    f"HTTP request returned non-success status {response.status_code}: {url}"
                )
            
            return result
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo HTTP response data"""
        url = inputs.get("url", "https://api.example.com/demo")
        method = inputs.get("method", "GET").upper()
        
        # Generate appropriate demo response based on method
        if method == "GET":
            demo_json = {
                "status": "success",
                "data": {
                    "id": "demo-123",
                    "name": "Demo Resource",
                    "value": 42
                }
            }
        elif method == "POST":
            demo_json = {
                "status": "created",
                "id": "new-resource-456",
                "message": "Resource created successfully"
            }
        else:
            demo_json = {
                "status": "success",
                "message": f"{method} operation completed"
            }
        
        return {
            "url": url,
            "status_code": 200 if method in ["GET", "POST", "PUT", "PATCH"] else 204,
            "headers": {
                "Content-Type": "application/json",
                "X-Demo": "true"
            },
            "body": json.dumps(demo_json),
            "json": demo_json,
            "success": True,
            "method": method,
            "_demo_sleep": 0.3  # Simulate HTTP request latency (network round-trip)
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Target URL for the HTTP request"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "description": "HTTP method (default: GET)"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers as key-value pairs"
                },
                "params": {
                    "type": "object",
                    "description": "Query parameters as key-value pairs"
                },
                "json": {
                    "type": "object",
                    "description": "JSON request body"
                },
                "data": {
                    "type": "object",
                    "description": "Form data as key-value pairs"
                },
                "timeout": {
                    "type": "number",
                    "description": "Request timeout in seconds (default: 30.0)"
                },
                "auth": {
                    "type": "object",
                    "description": "Authentication configuration",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["bearer", "basic", "apikey"],
                            "description": "Authentication type"
                        },
                        "token": {
                            "type": "string",
                            "description": "Bearer token (for bearer auth)"
                        },
                        "username": {
                            "type": "string",
                            "description": "Username (for basic auth)"
                        },
                        "password": {
                            "type": "string",
                            "description": "Password (for basic auth)"
                        },
                        "key": {
                            "type": "string",
                            "description": "API key name (for apikey auth)"
                        },
                        "value": {
                            "type": "string",
                            "description": "API key value (for apikey auth)"
                        },
                        "location": {
                            "type": "string",
                            "enum": ["header", "query"],
                            "description": "API key location (for apikey auth, default: header)"
                        }
                    }
                },
                "verify": {
                    "type": "boolean",
                    "description": "SSL certificate verification (default: True)"
                },
                "follow_redirects": {
                    "type": "boolean",
                    "description": "Follow HTTP redirects (default: True)"
                }
            },
            "required": ["url"]
        }

