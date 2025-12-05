"""
OpenAPI schema generator for aipartnerupflow API

Generates OpenAPI 3.0 schema for JSON-RPC 2.0 endpoints.
"""

from typing import Optional, Dict, Any
from aipartnerupflow import __version__


def generate_openapi_schema(
    base_url: str = "http://localhost:8000",
    title: str = "AIPartnerUpFlow API",
    version: Optional[str] = None,
    description: str = "Agent workflow orchestration and execution platform API",
) -> Dict[str, Any]:
    """
    Generate OpenAPI 3.0 schema for AIPartnerUpFlow API
    
    Args:
        base_url: Base URL of the API server
        title: API title
        version: API version (defaults to package version if not provided)
        description: API description
        
    Returns:
        OpenAPI 3.0 schema dictionary
    """
    # Use provided version or default to package version
    api_version = version if version is not None else __version__
    
    schema = {
        "openapi": "3.0.0",
        "info": {
            "title": title,
            "version": api_version,
            "description": description,
            "contact": {
                "name": "aipartnerupflow",
                "url": "https://flow.aipartnerup.com",
            },
        },
        "servers": [
            {
                "url": base_url,
                "description": "Default server",
            }
        ],
        "tags": [
            {"name": "A2A Protocol", "description": "A2A Protocol endpoints"},
            {"name": "Task Management", "description": "Task CRUD and execution operations"},
            {"name": "System", "description": "System operations"},
            {"name": "Agent Card", "description": "Agent discovery endpoints"},
        ],
        "paths": {
            "/.well-known/agent-card": {
                "get": {
                    "tags": ["Agent Card"],
                    "summary": "Get Agent Card",
                    "description": "Retrieve the agent card describing service capabilities (A2A Protocol standard)",
                    "operationId": "getAgentCard",
                    "responses": {
                        "200": {
                            "description": "Agent card",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/AgentCard"},
                                    "example": {
                                        "name": "aipartnerupflow",
                                        "description": "Agent workflow orchestration and execution platform",
                                        "url": "http://localhost:8000",
                                        "version": api_version,
                                        "capabilities": {
                                            "streaming": True,
                                            "push_notifications": True,
                                        },
                                        "skills": [
                                            {
                                                "id": "execute_task_tree",
                                                "name": "Execute Task Tree",
                                                "description": "Execute a complete task tree with multiple tasks",
                                                "tags": ["task", "orchestration", "workflow"],
                                            }
                                        ],
                                    },
                                }
                            },
                        }
                    },
                }
            },
            "/": {
                "post": {
                    "tags": ["A2A Protocol"],
                    "summary": "A2A Protocol RPC Endpoint",
                    "description": "Main A2A Protocol RPC endpoint. Handles all A2A protocol requests using JSON-RPC 2.0 format.",
                    "operationId": "a2aRpc",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/JsonRpcRequest"},
                                "examples": {
                                    "executeTaskTree": {
                                        "summary": "Execute Task Tree",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "execute_task_tree",
                                            "params": {
                                                "tasks": [
                                                    {
                                                        "id": "task1",
                                                        "name": "my_task",
                                                        "user_id": "user123",
                                                        "schemas": {"method": "system_info_executor"},
                                                        "inputs": {},
                                                    }
                                                ]
                                            },
                                            "id": "request-123",
                                        },
                                    },
                                    "executeTaskTreeWithStreaming": {
                                        "summary": "Execute Task Tree with Streaming",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "execute_task_tree",
                                            "params": {
                                                "tasks": [
                                                    {
                                                        "id": "task1",
                                                        "name": "my_task",
                                                        "user_id": "user123",
                                                        "schemas": {"method": "system_info_executor"},
                                                        "inputs": {},
                                                    }
                                                ]
                                            },
                                            "metadata": {"stream": True},
                                            "id": "request-123",
                                        },
                                    },
                                    "executeTaskTreeWithCallback": {
                                        "summary": "Execute Task Tree with Push Notification",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "execute_task_tree",
                                            "params": {
                                                "tasks": [
                                                    {
                                                        "id": "task1",
                                                        "name": "my_task",
                                                        "user_id": "user123",
                                                        "schemas": {"method": "system_info_executor"},
                                                        "inputs": {},
                                                    }
                                                ]
                                            },
                                            "configuration": {
                                                "push_notification_config": {
                                                    "url": "https://your-server.com/callback",
                                                    "headers": {
                                                        "Authorization": "Bearer your-token"
                                                    }
                                                }
                                            },
                                            "id": "request-123",
                                        },
                                    },
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "JSON-RPC response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/JsonRpcResponse"},
                                }
                            },
                        }
                    },
                    "security": [{"BearerAuth": []}] if True else [],  # Optional JWT auth
                }
            },
            "/tasks": {
                "post": {
                    "tags": ["Task Management"],
                    "summary": "Task Management Endpoint",
                    "description": "Task management endpoint supporting multiple operations via JSON-RPC 2.0 format.",
                    "operationId": "taskManagement",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/JsonRpcRequest"},
                                "examples": {
                                    "createTasks": {
                                        "summary": "Create Tasks",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.create",
                                            "params": [
                                                {
                                                    "id": "root",
                                                    "name": "Root Task",
                                                    "user_id": "user123",
                                                    "schemas": {"method": "my_executor"},
                                                    "inputs": {"data": "test"},
                                                },
                                                {
                                                    "id": "child",
                                                    "name": "Child Task",
                                                    "user_id": "user123",
                                                    "parent_id": "root",
                                                    "schemas": {"method": "another_executor"},
                                                    "inputs": {},
                                                }
                                            ],
                                            "id": "create-request-1",
                                        },
                                    },
                                    "getTask": {
                                        "summary": "Get Task",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.get",
                                            "params": {"task_id": "task-abc-123"},
                                            "id": "get-request-1",
                                        },
                                    },
                                    "updateTask": {
                                        "summary": "Update Task",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.update",
                                            "params": {
                                                "task_id": "task-abc-123",
                                                "status": "in_progress",
                                                "progress": 0.5,
                                            },
                                            "id": "update-request-1",
                                        },
                                    },
                                    "deleteTask": {
                                        "summary": "Delete Task",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.delete",
                                            "params": {"task_id": "task-abc-123"},
                                            "id": "delete-request-1",
                                        },
                                    },
                                    "copyTask": {
                                        "summary": "Copy Task Tree",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.copy",
                                            "params": {"task_id": "task-abc-123"},
                                            "id": "copy-request-1",
                                        },
                                    },
                                    "getTaskTree": {
                                        "summary": "Get Task Tree",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.tree",
                                            "params": {"task_id": "child-task-id"},
                                            "id": "tree-request-1",
                                        },
                                    },
                                    "listRunningTasks": {
                                        "summary": "List Running Tasks",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.running.list",
                                            "params": {"user_id": "user123", "limit": 50},
                                            "id": "list-request-1",
                                        },
                                    },
                                    "getRunningTaskStatus": {
                                        "summary": "Get Running Task Status",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.running.status",
                                            "params": {"task_ids": ["task-1", "task-2"]},
                                            "id": "status-request-1",
                                        },
                                    },
                                    "cancelTasks": {
                                        "summary": "Cancel Tasks",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.cancel",
                                            "params": {
                                                "task_ids": ["task-1", "task-2"],
                                                "force": False,
                                            },
                                            "id": "cancel-request-1",
                                        },
                                    },
                                    "executeTask": {
                                        "summary": "Execute Task",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.execute",
                                            "params": {
                                                "task_id": "task-abc-123"
                                            },
                                            "id": "execute-request-1"
                                        }
                                    },
                                    "executeTaskWithStreaming": {
                                        "summary": "Execute Task with SSE Streaming",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.execute",
                                            "params": {
                                                "task_id": "task-abc-123",
                                                "use_streaming": True
                                            },
                                            "id": "execute-streaming-request-1"
                                        }
                                    },
                                    "executeTaskWithWebhook": {
                                        "summary": "Execute Task with Webhook Callback",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.execute",
                                            "params": {
                                                "task_id": "task-abc-123",
                                                "webhook_config": {
                                                    "url": "https://your-server.com/callback",
                                                    "headers": {
                                                        "Authorization": "Bearer your-token"
                                                    },
                                                    "method": "POST",
                                                    "timeout": 30.0,
                                                    "max_retries": 3
                                                }
                                            },
                                            "id": "execute-webhook-request-1"
                                        }
                                    },
                                    "executeTaskWithStreamingAndWebhook": {
                                        "summary": "Execute Task with SSE Streaming and Webhook",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "tasks.execute",
                                            "params": {
                                                "task_id": "task-abc-123",
                                                "use_streaming": True,
                                                "webhook_config": {
                                                    "url": "https://your-server.com/callback",
                                                    "headers": {
                                                        "Authorization": "Bearer your-token"
                                                    }
                                                }
                                            },
                                            "id": "execute-combined-request-1"
                                        }
                                    },
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "JSON-RPC response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/JsonRpcResponse"},
                                }
                            },
                        }
                    },
                    "security": [{"BearerAuth": []}] if True else [],  # Optional JWT auth
                }
            },
            "/system": {
                "post": {
                    "tags": ["System"],
                    "summary": "System Operations Endpoint",
                    "description": "System operations endpoint for health checks and system management.",
                    "operationId": "systemOperations",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/JsonRpcRequest"},
                                "examples": {
                                    "healthCheck": {
                                        "summary": "Health Check",
                                        "value": {
                                            "jsonrpc": "2.0",
                                            "method": "system.health",
                                            "params": {},
                                            "id": "health-request-1",
                                        },
                                    },
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "JSON-RPC response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/JsonRpcResponse"},
                                }
                            },
                        }
                    },
                }
            },
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Optional JWT authentication. Include token in Authorization header: 'Bearer <token>'",
                }
            },
            "schemas": {
                "JsonRpcRequest": {
                    "type": "object",
                    "required": ["jsonrpc", "method", "id"],
                    "properties": {
                        "jsonrpc": {
                            "type": "string",
                            "enum": ["2.0"],
                            "description": "JSON-RPC version (must be '2.0')",
                        },
                        "method": {
                            "type": "string",
                            "description": "Method name (e.g., 'tasks.create', 'execute_task_tree')",
                        },
                        "params": {
                            "description": "Method parameters (can be object or array)",
                            "oneOf": [
                                {"type": "object"},
                                {"type": "array"},
                            ],
                        },
                        "id": {
                            "description": "Request ID (string or number)",
                            "oneOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "null"},
                            ],
                        },
                        "configuration": {
                            "type": "object",
                            "description": "Optional configuration (e.g., push_notification_config)",
                            "properties": {
                                "push_notification_config": {
                                    "type": "object",
                                    "properties": {
                                        "url": {"type": "string", "format": "uri"},
                                        "headers": {"type": "object"},
                                        "method": {"type": "string", "default": "POST"},
                                    },
                                }
                            },
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Optional metadata (e.g., stream flag)",
                            "properties": {
                                "stream": {"type": "boolean", "description": "Enable streaming mode"},
                            },
                        },
                    },
                },
                "JsonRpcResponse": {
                    "type": "object",
                    "properties": {
                        "jsonrpc": {
                            "type": "string",
                            "enum": ["2.0"],
                            "description": "JSON-RPC version",
                        },
                        "id": {
                            "description": "Request ID (matches request)",
                            "oneOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "null"},
                            ],
                        },
                        "result": {
                            "description": "Result data (structure depends on method)",
                        },
                        "error": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "description": "Error code"},
                                "message": {"type": "string", "description": "Error message"},
                                "data": {"description": "Additional error data"},
                            },
                        },
                    },
                },
                "AgentCard": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "url": {"type": "string", "format": "uri"},
                        "version": {"type": "string"},
                        "capabilities": {
                            "type": "object",
                            "properties": {
                                "streaming": {"type": "boolean"},
                                "push_notifications": {"type": "boolean"},
                            },
                        },
                        "skills": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "tags": {"type": "array", "items": {"type": "string"}},
                                },
                            },
                        },
                    },
                },
                "Task": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Task ID"},
                        "name": {"type": "string", "description": "Task name"},
                        "user_id": {"type": "string", "description": "User ID"},
                        "parent_id": {"type": "string", "description": "Parent task ID (optional)"},
                        "priority": {
                            "type": "integer",
                            "description": "Priority level (0=urgent, 1=high, 2=normal, 3=low)",
                            "default": 1,
                        },
                        "dependencies": {
                            "type": "array",
                            "description": "Dependency list",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "required": {"type": "boolean"},
                                },
                            },
                        },
                        "inputs": {
                            "type": "object",
                            "description": "Execution-time input parameters",
                        },
                        "schemas": {
                            "type": "object",
                            "description": "Task schemas (must include 'method' field with executor ID)",
                            "properties": {
                                "method": {"type": "string", "description": "Executor ID"},
                            },
                        },
                        "params": {
                            "type": "object",
                            "description": "Executor initialization parameters",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "failed", "cancelled"],
                        },
                        "progress": {"type": "number", "minimum": 0, "maximum": 1},
                        "result": {"type": "object", "description": "Execution result"},
                        "error": {"type": "string", "description": "Error message"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "updated_at": {"type": "string", "format": "date-time"},
                        "started_at": {"type": "string", "format": "date-time"},
                        "completed_at": {"type": "string", "format": "date-time"},
                    },
                },
            },
        },
    }
    
    return schema

