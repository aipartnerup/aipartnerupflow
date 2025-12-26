"""
Adapter class to convert between A2A protocol format and TaskRoutes format

This module provides an adapter that bridges A2A protocol (RequestContext, EventQueue)
with the protocol-agnostic TaskRoutes handlers, enabling all task management operations
to work through the A2A "/" endpoint.
"""

from typing import Dict, Any, Optional, List, Union, TYPE_CHECKING
from starlette.requests import Request
from a2a.server.agent_execution import RequestContext
from a2a.types import Task, TaskStatus, TaskState, DataPart, Artifact, Part
from a2a.utils import new_agent_text_message
from aipartnerupflow.api.routes.tasks import TaskRoutes
from aipartnerupflow.core.utils.logger import get_logger

if TYPE_CHECKING:
    from typing import Callable

logger = get_logger(__name__)


class TaskRoutesAdapter:
    """
    Adapter to convert between A2A protocol format and TaskRoutes format
    
    This adapter:
    1. Extracts method and parameters from RequestContext
    2. Creates a Request object for permission checking
    3. Calls appropriate TaskRoutes handler
    4. Converts results to A2A protocol format (Task objects, TaskStatusUpdateEvent)
    """
    
    def __init__(
        self,
        task_routes: TaskRoutes,
        verify_token_func: Optional["Callable[[str], Optional[dict]]"] = None,
    ):
        """
        Initialize adapter
        
        Args:
            task_routes: TaskRoutes instance with handlers
            verify_token_func: Optional JWT verification function
        """
        self.task_routes = task_routes
        self.verify_token_func = verify_token_func
    
    def extract_method(self, context: RequestContext) -> Optional[str]:
        """
        Extract method name from RequestContext
        
        Checks multiple sources:
        1. context.metadata.get("method")
        2. context.configuration.get("method")
        3. context.metadata.get("skill_id") (A2A protocol skill identifier)
        
        Args:
            context: RequestContext from A2A protocol
            
        Returns:
            Method name (e.g., "tasks.create", "tasks.get") or None
        """
        # Try metadata first
        if context.metadata:
            method = context.metadata.get("method")
            if method:
                return method
            
            # Try skill_id (A2A protocol uses skill_id to identify operations)
            skill_id = context.metadata.get("skill_id")
            if skill_id:
                # Map skill_id to method name
                # Most skill_ids match method names directly, but we keep backward compatibility
                skill_to_method = {
                    "execute_task_tree": "tasks.execute",  # Backward compatibility
                    "tasks.create": "tasks.create",
                    "tasks.get": "tasks.get",
                    "tasks.update": "tasks.update",
                    "tasks.delete": "tasks.delete",
                    "tasks.detail": "tasks.detail",
                    "tasks.tree": "tasks.tree",
                    "tasks.list": "tasks.list",
                    "tasks.children": "tasks.children",
                    "tasks.running.list": "tasks.running.list",
                    "tasks.running.status": "tasks.running.status",
                    "tasks.running.count": "tasks.running.count",
                    "tasks.cancel": "tasks.cancel",
                    "tasks.copy": "tasks.copy",
                    "tasks.generate": "tasks.generate",
                    "tasks.execute": "tasks.execute",
                }
                return skill_to_method.get(skill_id, skill_id)
        
        # Try configuration (if it has a method attribute)
        if context.configuration:
            method = getattr(context.configuration, "method", None)
            if method:
                return method
        
        return None
    
    def extract_params(self, context: RequestContext, method: str) -> Dict[str, Any]:
        """
        Extract parameters from RequestContext
        
        Parameters can be in:
        1. context.message.parts (DataPart format)
        2. context.metadata (direct key-value pairs)
        3. context.configuration
        
        Args:
            context: RequestContext from A2A protocol
            method: Method name to extract params for
            
        Returns:
            Dictionary of parameters
        """
        params = {}
        
        # Extract from metadata (highest priority)
        if context.metadata:
            # Copy all metadata except internal fields
            for key, value in context.metadata.items():
                if key not in ["method", "skill_id", "stream", "copy_execution", "copy_children"]:
                    params[key] = value
        
        # Extract from message.parts (DataPart format)
        if context.message and hasattr(context.message, "parts"):
            parts = context.message.parts
            if parts:
                # Try to extract data from first part
                first_part = parts[0]
                part_data = self._extract_part_data(first_part)
                
                if part_data:
                    if isinstance(part_data, dict):
                        # Merge into params (don't overwrite existing params)
                        for key, value in part_data.items():
                            if key not in params:
                                params[key] = value
                    elif isinstance(part_data, list) and method == "tasks.create":
                        # For tasks.create, if part_data is a list, it's the tasks array
                        params = part_data  # Return list directly for tasks.create
                        return params
        
        # Extract from configuration (lowest priority)
        # Note: configuration is a Pydantic model, use model_dump() to get dict
        if context.configuration:
            try:
                # Try model_dump() first (Pydantic v2)
                config_dict = context.configuration.model_dump(exclude_none=True)
            except AttributeError:
                try:
                    # Fallback to dict() for Pydantic v1
                    config_dict = context.configuration.dict(exclude_none=True)
                except AttributeError:
                    # If neither works, skip configuration extraction
                    config_dict = {}
            
            for key, value in config_dict.items():
                if key not in ["method"] and key not in params:
                    params[key] = value
        
        return params
    
    def _extract_part_data(self, part) -> Any:
        """
        Extract data from a single A2A part
        
        Args:
            part: A2A part object (may have root attribute with DataPart)
            
        Returns:
            Extracted data from the part
        """
        # Check if part has a root attribute (A2A Part structure)
        if hasattr(part, "root"):
            data_part = part.root
            if hasattr(data_part, "kind") and data_part.kind == "data" and hasattr(data_part, "data"):
                return data_part.data
        
        # Fallback: try direct access
        if hasattr(part, "kind") and part.kind == "data" and hasattr(part, "data"):
            return part.data
        
        return None
    
    def create_request_object(self, context: RequestContext) -> Request:
        """
        Create a Request object from RequestContext for permission checking
        
        This creates a minimal Request object that can be used with TaskRoutes handlers
        for permission checking. The Request object will have user info in state if
        JWT token is available.
        
        Args:
            context: RequestContext from A2A protocol
            
        Returns:
            Request object with user info in state
        """
        # Create a minimal Request object
        # We need to extract user info from JWT if available
        # For now, we'll create a Request with empty state and let TaskRoutes handle it
        # The actual JWT verification happens at the middleware level
        
        # Create a mock Request object
        # Note: This is a simplified approach - in production, we might need to
        # extract JWT from context and verify it here
        class MockRequest:
            def __init__(self):
                self.state = type('State', (), {})()
                # Try to extract user_id from metadata if available
                if context.metadata:
                    user_id = context.metadata.get("user_id")
                    if user_id:
                        self.state.user_id = user_id
                        self.state.token_payload = {"sub": user_id}
        
        return MockRequest()
    
    async def call_handler(
        self,
        method: str,
        params: Union[Dict[str, Any], List[Dict[str, Any]]],
        context: RequestContext,
        request_id: str
    ) -> Any:
        """
        Call the appropriate TaskRoutes handler based on method name
        
        Args:
            method: Method name (e.g., "tasks.create", "tasks.get")
            params: Parameters for the handler
            context: RequestContext for creating Request object
            request_id: Request ID for logging
            
        Returns:
            Result from TaskRoutes handler
        """
        request = self.create_request_object(context)
        
        # Route to appropriate handler
        if method == "tasks.create":
            return await self.task_routes.handle_task_create(params, request, request_id)
        elif method == "tasks.get":
            return await self.task_routes.handle_task_get(params, request, request_id)
        elif method == "tasks.update":
            return await self.task_routes.handle_task_update(params, request, request_id)
        elif method == "tasks.delete":
            return await self.task_routes.handle_task_delete(params, request, request_id)
        elif method == "tasks.detail":
            return await self.task_routes.handle_task_detail(params, request, request_id)
        elif method == "tasks.tree":
            return await self.task_routes.handle_task_tree(params, request, request_id)
        elif method == "tasks.list":
            return await self.task_routes.handle_tasks_list(params, request, request_id)
        elif method == "tasks.children":
            return await self.task_routes.handle_task_children(params, request, request_id)
        elif method == "tasks.running.list":
            return await self.task_routes.handle_running_tasks_list(params, request, request_id)
        elif method == "tasks.running.status":
            return await self.task_routes.handle_running_tasks_status(params, request, request_id)
        elif method == "tasks.running.count":
            return await self.task_routes.handle_running_tasks_count(params, request, request_id)
        elif method == "tasks.cancel" or method == "tasks.running.cancel":
            return await self.task_routes.handle_task_cancel(params, request, request_id)
        elif method == "tasks.copy":
            return await self.task_routes.handle_task_copy(params, request, request_id)
        elif method == "tasks.generate":
            return await self.task_routes.handle_task_generate(params, request, request_id)
        elif method == "tasks.execute":
            # tasks.execute is handled separately in agent_executor
            # This should not be called through the adapter
            raise ValueError("tasks.execute should be handled by agent_executor directly")
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def convert_to_a2a_task(
        self,
        task_dict: Dict[str, Any],
        task_id: Optional[str] = None,
        context_id: Optional[str] = None
    ) -> Task:
        """
        Convert task dictionary to A2A Task object
        
        Args:
            task_dict: Task dictionary from TaskRoutes handler
            task_id: Optional task ID (defaults to task_dict["id"])
            context_id: Optional context ID (defaults to task_id)
            
        Returns:
            A2A Task object
        """
        task_id = task_id or task_dict.get("id")
        context_id = context_id or task_id
        
        # Map status to TaskState
        status_str = task_dict.get("status", "pending")
        status_map = {
            "pending": TaskState.pending,
            "in_progress": TaskState.in_progress,
            "completed": TaskState.completed,
            "failed": TaskState.failed,
            "cancelled": TaskState.canceled,
        }
        task_state = status_map.get(status_str, TaskState.pending)
        
        # Create status message
        status_message = f"Task {status_str}"
        if task_dict.get("error"):
            status_message = f"Task failed: {task_dict.get('error')}"
        
        # Create artifacts from result
        artifacts = []
        if task_dict.get("result") is not None:
            artifacts.append(
                Artifact(
                    artifact_id=str(task_dict.get("id", task_id)),
                    parts=[
                        Part(
                            root=DataPart(
                                kind="data",
                                data={
                                    "protocol": "a2a",
                                    "task_id": task_id,
                                    "status": status_str,
                                    "result": task_dict.get("result"),
                                    "progress": float(task_dict.get("progress", 0.0)),
                                }
                            )
                        )
                    ]
                )
            )
        
        # Create metadata
        metadata = {
            "protocol": "a2a",
            "task_id": task_id,
        }
        if task_dict.get("user_id"):
            metadata["user_id"] = task_dict["user_id"]
        if task_dict.get("root_task_id"):
            metadata["root_task_id"] = task_dict["root_task_id"]
        
        return Task(
            id=task_id,
            context_id=context_id,
            kind="task",
            status=TaskStatus(
                state=task_state,
                message=new_agent_text_message(status_message)
            ),
            artifacts=artifacts,
            metadata=metadata
        )
    
    def convert_list_to_a2a_tasks(
        self,
        task_list: List[Dict[str, Any]],
        context_id: Optional[str] = None
    ) -> List[Task]:
        """
        Convert list of task dictionaries to A2A Task objects
        
        Args:
            task_list: List of task dictionaries
            context_id: Optional context ID for all tasks
            
        Returns:
            List of A2A Task objects
        """
        return [
            self.convert_to_a2a_task(task_dict, context_id=context_id)
            for task_dict in task_list
        ]
    
    def convert_result_to_a2a_format(
        self,
        result: Any,
        method: str,
        context: RequestContext
    ) -> Any:
        """
        Convert TaskRoutes handler result to A2A protocol format
        
        Args:
            result: Result from TaskRoutes handler
            method: Method name that was called
            context: RequestContext for extracting IDs
            
        Returns:
            Result in A2A protocol format (Task, List[Task], or dict)
        """
        task_id = context.task_id or context.context_id
        context_id = context.context_id or task_id
        
        # Handle different result types
        if result is None:
            return None
        
        if isinstance(result, dict):
            # Single task dictionary
            if "id" in result or "task_id" in result:
                # It's a task dictionary
                return self.convert_to_a2a_task(result, task_id=task_id, context_id=context_id)
            else:
                # It's a result dictionary (e.g., from tasks.delete, tasks.copy)
                # Wrap in A2A format
                return {
                    "protocol": "a2a",
                    "result": result,
                    "task_id": task_id,
                    "context_id": context_id,
                }
        
        elif isinstance(result, list):
            # List of task dictionaries
            if result and isinstance(result[0], dict) and ("id" in result[0] or "task_id" in result[0]):
                # List of tasks
                return self.convert_list_to_a2a_tasks(result, context_id=context_id)
            else:
                # List of other objects (e.g., status dictionaries)
                return {
                    "protocol": "a2a",
                    "result": result,
                    "task_id": task_id,
                    "context_id": context_id,
                }
        
        else:
            # Other types (string, number, etc.)
            return {
                "protocol": "a2a",
                "result": result,
                "task_id": task_id,
                "context_id": context_id,
            }

