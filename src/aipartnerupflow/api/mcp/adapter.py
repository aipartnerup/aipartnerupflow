"""
Adapter for TaskRoutes to MCP interface

This adapter bridges TaskRoutes (protocol-agnostic task handlers) with MCP protocol.
"""

from typing import Dict, Any, Optional, Type
from starlette.requests import Request
from aipartnerupflow.api.routes.tasks import TaskRoutes
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TaskRoutesAdapter:
    """
    Adapter to convert MCP tool calls to TaskRoutes method calls
    """
    
    def __init__(self, task_routes_class: Optional[Type[TaskRoutes]] = None):
        """
        Initialize adapter with TaskRoutes instance
        
        Args:
            task_routes_class: Optional custom TaskRoutes class to use instead of default TaskRoutes.
                             Allows extending TaskRoutes functionality without monkey patching.
                             Example: task_routes_class=MyCustomTaskRoutes
        """
        from aipartnerupflow.core.config import get_task_model_class
        # Use provided task_routes_class or default TaskRoutes
        task_routes_cls = task_routes_class or TaskRoutes
        self.task_routes = task_routes_cls(
            task_model_class=get_task_model_class(),
            verify_token_func=None,
            verify_permission_func=None
        )
    
    def _get_request_or_none(self, request: Optional[Request]) -> Optional[Request]:
        """
        Get request object or None
        
        For stdio mode, request will be None and TaskRoutes handlers
        should handle this gracefully. For HTTP mode, we'll pass the actual request.
        """
        return request
    
    async def execute_task(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Execute a task via TaskRoutes
        
        Args:
            params: MCP tool arguments containing:
                - task_id: Optional, task ID to execute
                - tasks: Optional, array of task dictionaries
                - use_streaming: Optional, enable streaming (default: False)
                - copy_execution: Optional, copy before execution (default: False)
                - webhook_config: Optional webhook configuration
            request: Optional Starlette Request object
        
        Returns:
            Task execution result
        """
        request_id = str(params.get("request_id", ""))
        
        result = await self.task_routes.handle_task_execute(
            params,
            self._get_request_or_none(request),
            request_id
        )
        
        # If result is StreamingResponse (SSE mode), we need to handle it differently
        # For MCP, we'll convert it to a regular response with status info
        if hasattr(result, 'status_code'):
            # It's a response object, extract the JSON
            return result
        return result
    
    async def create_task(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Create a task via TaskRoutes
        
        Args:
            params: MCP tool arguments containing task data
            request: Optional Starlette Request object
        
        Returns:
            Created task result
        """
        request_id = str(params.get("request_id", ""))
        # Handle both single task and tasks array
        if "tasks" in params:
            # Multiple tasks
            tasks = params["tasks"]
            result = await self.task_routes.handle_task_create(
                tasks,
                self._get_request_or_none(request),
                request_id
            )
        else:
            # Single task - wrap in list
            task = params
            result = await self.task_routes.handle_task_create(
                [task],
                self._get_request_or_none(request),
                request_id
            )
        return result
    
    async def get_task(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Get a task by ID via TaskRoutes
        
        Args:
            params: MCP tool arguments containing task_id
            request: Optional Starlette Request object
        
        Returns:
            Task data
        """
        request_id = str(params.get("request_id", ""))
        result = await self.task_routes.handle_task_get(
            params,
            self._get_request_or_none(request),
            request_id
        )
        return result
    
    async def update_task(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Update a task via TaskRoutes
        
        Args:
            params: MCP tool arguments containing task_id and update data
            request: Optional Starlette Request object
        
        Returns:
            Updated task result
        """
        request_id = str(params.get("request_id", ""))
        result = await self.task_routes.handle_task_update(
            params,
            self._get_request_or_none(request),
            request_id
        )
        return result
    
    async def delete_task(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Delete a task via TaskRoutes
        
        Args:
            params: MCP tool arguments containing task_id
            request: Optional Starlette Request object
        
        Returns:
            Deletion result
        """
        request_id = str(params.get("request_id", ""))
        result = await self.task_routes.handle_task_delete(
            params,
            self._get_request_or_none(request),
            request_id
        )
        return result
    
    async def list_tasks(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        List tasks via TaskRoutes
        
        Args:
            params: MCP tool arguments containing query parameters
            request: Optional Starlette Request object
        
        Returns:
            Task list result
        """
        request_id = str(params.get("request_id", ""))
        result = await self.task_routes.handle_tasks_list(
            params,
            self._get_request_or_none(request),
            request_id
        )
        return result
    
    async def get_task_status(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Get task status via TaskRoutes
        
        Args:
            params: MCP tool arguments containing task_id
            request: Optional Starlette Request object
        
        Returns:
            Task status result
        """
        request_id = str(params.get("request_id", ""))
        result = await self.task_routes.handle_running_tasks_status(
            params,
            self._get_request_or_none(request),
            request_id
        )
        return result
    
    async def cancel_task(
        self,
        params: Dict[str, Any],
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Cancel a task via TaskRoutes
        
        Args:
            params: MCP tool arguments containing task_id
            request: Optional Starlette Request object
        
        Returns:
            Cancellation result
        """
        request_id = str(params.get("request_id", ""))
        result = await self.task_routes.handle_task_cancel(
            params,
            self._get_request_or_none(request),
            request_id
        )
        return result

