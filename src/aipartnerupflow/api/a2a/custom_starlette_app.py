"""
Custom Starlette Application that supports system-level methods and optional JWT authentication
"""
import uuid
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from a2a.server.apps.jsonrpc.starlette_app import A2AStarletteApplication
from datetime import datetime, timezone
from typing import Optional, Callable, Type, Dict, Any, List
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    DEFAULT_RPC_URL,
    EXTENDED_AGENT_CARD_PATH,
    PREV_AGENT_CARD_WELL_KNOWN_PATH,
)

from aipartnerupflow.core.storage import get_default_session
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.execution.task_creator import TaskCreator
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to verify JWT tokens for authenticated requests (optional)"""
    
    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = [
        AGENT_CARD_WELL_KNOWN_PATH,
        EXTENDED_AGENT_CARD_PATH,
        PREV_AGENT_CARD_WELL_KNOWN_PATH,
    ]
    
    def __init__(self, app, verify_token_func=None):
        """
        Initialize JWT authentication middleware
        
        Args:
            app: Starlette application
            verify_token_func: Optional function to verify JWT tokens. 
                             If None, JWT verification is disabled.
        """
        super().__init__(app)
        self.verify_token_func = verify_token_func
    
    async def dispatch(self, request: Request, call_next):
        """Verify JWT token from Authorization header"""
        
        # Skip authentication for public endpoints
        if request.url.path in self.PUBLIC_ENDPOINTS:
            return await call_next(request)
        
        # If no verify function provided, skip JWT authentication
        if not self.verify_token_func:
            return await call_next(request)
        
        # Check for Authorization header
        authorization = request.headers.get("Authorization")
        
        if not authorization:
            logger.warning(f"Missing Authorization header for {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized",
                        "data": "Missing Authorization header"
                    }
                }
            )
        
        token = authorization
        # Extract token from Bearer <token>
        if authorization.startswith("Bearer "):
            token = authorization[7:]  # Remove "Bearer " prefix
        
        # Verify token
        try:
            payload = self.verify_token_func(token)
            logger.debug(f"JWT payload: {payload}")
            if not payload:
                logger.warning(f"Invalid JWT token for {request.url.path}")
                return JSONResponse(
                    status_code=401,
                    content={
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32001,
                            "message": "Unauthorized",
                            "data": "Invalid or expired JWT token"
                        }
                    }
                )
            
            # Add user info to request state for use in handlers
            request.state.user_id = payload.get("sub")
            request.state.token_payload = payload
            
            logger.debug(f"Authenticated request from user {request.state.user_id} for {request.url.path}")
            
            return await call_next(request)
        except Exception as e:
            logger.error(f"Error verifying JWT token: {e}")
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized",
                        "data": "Invalid or expired JWT token"
                    }
                }
            )
        


class CustomA2AStarletteApplication(A2AStarletteApplication):
    """Custom A2A Starlette Application that supports system-level methods and optional JWT authentication"""
    
    def __init__(
        self, 
        *args, 
        verify_token_func: Optional[Callable[[str], Optional[dict]]] = None,
        verify_permission_func: Optional[Callable[[str, Optional[str], Optional[list]], bool]] = None,
        enable_system_routes: bool = True,
        task_model_class: Optional[Type[TaskModel]] = None,
        **kwargs
    ):
        """
        Initialize Custom A2A Starlette Application
        
        As a library: All configuration via function parameters (recommended)
        No automatic environment variable reading to avoid conflicts.
        
        For service deployment: Read environment variables in application layer (main.py)
        and pass them as explicit parameters.
        
        Args:
            *args: Positional arguments for A2AStarletteApplication
            verify_token_func: Function to verify JWT tokens.
                             If None, JWT auth will be disabled.
                             Signature: verify_token_func(token: str) -> Optional[dict]
            verify_permission_func: Function to verify user permissions.
                                  If None, permission checking is disabled.
                                  Signature: verify_permission_func(user_id: str, target_user_id: Optional[str], roles: Optional[list]) -> bool
                                  Returns True if user has permission to access target_user_id's resources.
                                  - If user is admin (roles contains "admin"), can access any user_id
                                  - If user is not admin, can only access their own user_id
                                  - If target_user_id is None, permission is granted (no specific user restriction)
            enable_system_routes: Whether to enable system routes like /system (default: True)
            task_model_class: Optional custom TaskModel class.
                             Users can pass their custom TaskModel subclass that inherits TaskModel
                             to add custom fields (e.g., project_id, department, etc.).
                             If None, default TaskModel will be used.
            **kwargs: Keyword arguments for A2AStarletteApplication
        """
        super().__init__(*args, **kwargs)
        
        # Use parameter values directly (no environment variable reading)
        self.enable_system_routes = enable_system_routes
        
        # Handle verify_token_func
        self.verify_token_func = verify_token_func
        
        # Handle verify_permission_func
        self.verify_permission_func = verify_permission_func
        
        # Store task_model_class for task management APIs
        self.task_model_class = task_model_class or TaskModel
        
        logger.info(
            f"Initialized CustomA2AStarletteApplication "
            f"(System routes: {self.enable_system_routes}, "
            f"JWT auth: {self.verify_token_func is not None}, "
            f"Permission check: {self.verify_permission_func is not None}, "
            f"TaskModel: {self.task_model_class.__name__})"
        )
    
    def build(self):
        """Build the Starlette app with optional JWT authentication middleware and system routes"""
        app = super().build()
        
        if self.verify_token_func:
            # Add JWT authentication middleware
            logger.info("JWT authentication is enabled")
            app.add_middleware(JWTAuthenticationMiddleware, verify_token_func=self.verify_token_func)
        else:
            logger.info("JWT authentication is disabled")
        
        return app
    
    def routes(
        self,
        agent_card_url: str = "/.well-known/agent-card",
        rpc_url: str = "/",
        extended_agent_card_url: str = EXTENDED_AGENT_CARD_PATH,
    ) -> list[Route]:
        """Returns the Starlette Routes for handling A2A requests plus optional system methods"""
        # Get the standard A2A routes
        app_routes = super().routes(agent_card_url, rpc_url, extended_agent_card_url)
        
        if not self.enable_system_routes:
            return app_routes
        
        # Add task management and system routes
        # Using /tasks for task management and /system for system operations
        custom_routes = [
            Route(
                "/tasks",
                self._handle_task_requests,
                methods=['POST'],
                name='task_handler',
            ),
            Route(
                "/system",
                self._handle_system_requests,
                methods=['POST'],
                name='system_handler',
            ),
        ]
        
        # Combine standard routes with custom routes
        return app_routes + custom_routes

    async def _handle_task_requests(self, request: Request) -> JSONResponse:
        """Handle all task management requests through /tasks endpoint"""
        import time
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        try:
            # Parse JSON request
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})
            
            # Support direct tasks array for tasks.create method
            # If method is tasks.create and params is a list, use it directly
            if method == "tasks.create" and isinstance(params, list):
                # params is directly the tasks array
                logger.info(f"🔍 [handle_task_requests] [{request_id}] Method: {method}, Tasks array: {len(params)} tasks")
                result = await self._handle_task_create_logic(params, request, request_id)
            else:
                # Normal case: params is a dict
                if not isinstance(params, dict):
                    params = {}  # Fallback to empty dict if params is not dict or list
                
                logger.info(f"🔍 [handle_task_requests] [{request_id}] Method: {method}, Params: {params}")
                
                # Route to specific handler based on method
                # Pass request object to handlers for access to user info and permission checking
                # Task CRUD operations
                if method == "tasks.create":
                    result = await self._handle_task_create_logic(params, request, request_id)
                elif method == "tasks.get":
                    result = await self._handle_task_get_logic(params, request, request_id)
                elif method == "tasks.update":
                    result = await self._handle_task_update_logic(params, request, request_id)
                elif method == "tasks.delete":
                    result = await self._handle_task_delete_logic(params, request, request_id)
                # Task query operations
                elif method == "tasks.detail":
                    result = await self._handle_task_detail_logic(params, request, request_id)
                elif method == "tasks.tree":
                    result = await self._handle_task_tree_logic(params, request, request_id)
                # Running task monitoring
                elif method == "tasks.running.list":
                    result = await self._handle_running_tasks_list_logic(params, request, request_id)
                elif method == "tasks.running.status":
                    result = await self._handle_running_tasks_status_logic(params, request, request_id)
                elif method == "tasks.running.count":
                    result = await self._handle_running_tasks_count_logic(params, request, request_id)
                # Task cancellation
                elif method == "tasks.cancel" or method == "tasks.running.cancel":
                    result = await self._handle_task_cancel_logic(params, request, request_id)
                # Task copy
                elif method == "tasks.copy":
                    result = await self._handle_task_copy_logic(params, request, request_id)
                else:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "jsonrpc": "2.0",
                            "id": body.get("id", request_id),
                            "error": {
                                "code": -32601,
                                "message": "Method not found",
                                "data": f"Unknown task method: {method}"
                            }
                        }
                    )
            
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"🔍 [handle_task_requests] [{request_id}] Completed in {duration:.3f}s")
            
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id", request_id),
                    "result": result
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling task request: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id", str(uuid.uuid4())),
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                }
            )

    async def _handle_system_requests(self, request: Request) -> JSONResponse:
        """Handle system operations through /system endpoint"""
        import time
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        try:
            # Parse JSON request
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})
            
            logger.info(f"🔍 [handle_system_requests] [{request_id}] Method: {method}, Params: {params}")
            
            # Route to specific handler based on method
            if method == "system.health":
                result = await self._handle_health(params, request_id)
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": body.get("id", request_id),
                        "error": {
                            "code": -32601,
                            "message": "Method not found",
                            "data": f"Unknown system method: {method}"
                        }
                    }
                )
            
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"🔍 [handle_system_requests] [{request_id}] Completed in {duration:.3f}s")
            
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id", request_id),
                    "result": result
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling system request: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id", str(uuid.uuid4())),
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                }
            )

    async def _handle_task_detail_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> Optional[dict]:
        """
        Handle task detail query - returns full task information including all fields
        
        Params:
            task_id: Task ID to get details for
        
        Returns:
            Task detail dictionary with all fields
        """
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")
            
            # Get database session and create repository
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            task = await task_repository.get_task_by_id(task_id)
            
            if not task:
                return None
            
            # Check permission to access this task
            self._check_permission(request, task.user_id, "access")
            
            return task.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting task detail: {str(e)}", exc_info=True)
            raise

    async def _handle_task_tree_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> Optional[dict]:
        """
        Handle task tree query - returns task tree structure
        
        Params:
            task_id: Root task ID (if not provided, will find root from any task_id)
            root_id: Optional root task ID (alternative to task_id)
        
        Returns:
            Task tree structure with nested children
        """
        try:
            task_id = params.get("task_id") or params.get("root_id")
            if not task_id:
                raise ValueError("Task ID or root_id is required")
            
            # Get database session and create repository
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            # Get task
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Check permission to access this task
            self._check_permission(request, task.user_id, "access")
            
            # If task has parent, find root first
            root_task = await task_repository.get_root_task(task)
            
            # Build task tree
            task_tree_node = await task_repository.build_task_tree(root_task)
            
            # Convert TaskTreeNode to dictionary format
            def tree_node_to_dict(node):
                """Convert TaskTreeNode to dictionary"""
                task_dict = node.task.to_dict()
                if node.children:
                    task_dict["children"] = [tree_node_to_dict(child) for child in node.children]
                return task_dict
            
            return tree_node_to_dict(task_tree_node)
            
        except Exception as e:
            logger.error(f"Error getting task tree: {str(e)}", exc_info=True)
            raise

    async def _handle_running_tasks_list_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> list:
        """
        Handle running tasks list - returns list of currently running tasks from memory
        
        Params:
            user_id: Optional user ID filter (will be checked for permission)
            limit: Optional limit (default: 100)
        
        Returns:
            List of running tasks
        """
        try:
            user_id = params.get("user_id")
            limit = params.get("limit", 100)
            
            # Check permission if user_id is specified
            if user_id:
                self._check_permission(request, user_id, "list tasks for")
            else:
                # No user_id specified, use authenticated user_id or None
                authenticated_user_id, _ = self._get_user_info(request)
                if authenticated_user_id:
                    user_id = authenticated_user_id
                # If no JWT and no user_id, user_id remains None (list all tasks)
            
            # Get running tasks from memory using TaskExecutor
            from aipartnerupflow.core.execution.task_executor import TaskExecutor
            task_executor = TaskExecutor()
            running_task_ids = task_executor.get_all_running_tasks()
            
            if not running_task_ids:
                return []
            
            # Get database session and create repository to fetch task details
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            # Fetch task details for running tasks
            tasks = []
            for task_id in running_task_ids[:limit]:  # Apply limit
                task = await task_repository.get_task_by_id(task_id)
                if task:
                    # Apply user_id filter if specified
                    if user_id and task.user_id != user_id:
                        continue
                    
                    # Check permission to access this task
                    try:
                        self._check_permission(request, task.user_id, "access")
                        tasks.append(task.to_dict())
                    except ValueError:
                        # Permission denied, skip this task
                        logger.warning(f"Permission denied for task {task_id}")
            
            # Sort by created_at descending
            tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
            
            return tasks
            
        except Exception as e:
            logger.error(f"Error getting running tasks list: {str(e)}", exc_info=True)
            raise

    async def _handle_running_tasks_status_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> list:
        """
        Handle running tasks status - returns status of multiple running tasks
        
        Params:
            task_ids: List of task IDs to check status for
            context_ids: Alternative - list of context IDs (task IDs)
        
        Returns:
            List of task status dictionaries
        """
        try:
            task_ids = params.get("task_ids") or params.get("context_ids", [])
            if isinstance(task_ids, str):
                task_ids = task_ids.split(',')
            
            if not task_ids:
                return []
            
            # Get TaskExecutor to check if tasks are running in memory
            from aipartnerupflow.core.execution.task_executor import TaskExecutor
            task_executor = TaskExecutor()
            
            # Get database session and create repository
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            statuses = []
            for task_id in task_ids:
                task_id = task_id.strip()
                
                # First check if task is running in memory
                is_running = task_executor.is_task_running(task_id)
                
                # Get task from database for details
                task = await task_repository.get_task_by_id(task_id)
                
                if task:
                    # Check permission to access this task
                    try:
                        self._check_permission(request, task.user_id, "access")
                        statuses.append({
                            "task_id": task.id,
                            "context_id": task.id,  # For A2A Protocol compatibility
                            "status": task.status,
                            "progress": float(task.progress) if task.progress else 0.0,
                            "error": task.error,
                            "is_running": is_running,  # Add in-memory running status
                            "started_at": task.started_at.isoformat() if task.started_at else None,
                            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                        })
                    except ValueError as e:
                        # Permission denied, skip this task
                        logger.warning(f"Permission denied for task {task_id}: {e}")
                        statuses.append({
                            "task_id": task_id,
                            "context_id": task_id,
                            "status": "permission_denied",
                            "progress": 0.0,
                            "error": str(e),
                            "is_running": is_running,
                            "started_at": None,
                            "updated_at": None,
                        })
                else:
                    # Task not found in database, but check if it's running in memory
                    if is_running:
                        statuses.append({
                            "task_id": task_id,
                            "context_id": task_id,
                            "status": "in_progress",  # Running but not yet saved to DB
                            "progress": 0.0,
                            "error": None,
                            "is_running": True,
                            "started_at": None,
                            "updated_at": None,
                        })
                    else:
                        statuses.append({
                            "task_id": task_id,
                            "context_id": task_id,
                            "status": "not_found",
                            "progress": 0.0,
                            "error": None,
                            "is_running": False,
                            "started_at": None,
                            "updated_at": None,
                        })
            
            return statuses
            
        except Exception as e:
            logger.error(f"Error getting running tasks status: {str(e)}", exc_info=True)
            raise

    async def _handle_running_tasks_count_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> dict:
        """
        Handle running tasks count - returns count of tasks by status
        
        Params:
            user_id: Optional user ID filter (will be checked for permission)
            status: Optional status filter (if not provided, returns counts for all statuses)
        
        Returns:
            Dictionary with status counts
        """
        try:
            user_id = params.get("user_id")
            status_filter = params.get("status")
            
            # Check permission if user_id is specified
            if user_id:
                self._check_permission(request, user_id, "count tasks for")
            else:
                # No user_id specified, use authenticated user_id or None
                authenticated_user_id, _ = self._get_user_info(request)
                if authenticated_user_id:
                    user_id = authenticated_user_id
                # If no JWT and no user_id, user_id remains None (count all tasks)
            
            # Get running tasks count from memory using TaskExecutor
            from aipartnerupflow.core.execution.task_executor import TaskExecutor
            task_executor = TaskExecutor()
            
            if user_id:
                # Filter by user_id: get all running tasks and filter by user_id
                running_task_ids = task_executor.get_all_running_tasks()
                if not running_task_ids:
                    return {"count": 0, "user_id": user_id}
                
                # Get database session to check user_id
                db_session = get_default_session()
                task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
                
                count = 0
                for task_id in running_task_ids:
                    task = await task_repository.get_task_by_id(task_id)
                    if task and task.user_id == user_id:
                        count += 1
                
                return {"count": count, "user_id": user_id}
            else:
                # No user_id filter, return total count from memory
                count = task_executor.get_running_tasks_count()
                return {"count": count}
            
        except Exception as e:
            logger.error(f"Error getting running tasks count: {str(e)}", exc_info=True)
            raise

    async def _handle_task_cancel_logic(
        self,
        params: dict,
        request: Request,
        request_id: str
    ) -> list:
        """
        Handle task cancellation - cancels one or more running tasks
        
        This method:
        1. Calls TaskExecutor.cancel_task() for each task
        2. Returns cancellation results with token_usage if available
        
        Params:
            task_ids: List of task IDs to cancel (required)
            context_ids: Alternative - list of context IDs (task IDs)
            force: Optional boolean, if True force immediate cancellation (default: False)
            error_message: Optional custom error message for cancellation
        
        Returns:
            List of cancellation result dictionaries:
            [
                {
                    "task_id": str,
                    "status": "cancelled" | "failed",
                    "message": str,
                    "token_usage": Dict,  # Optional, if available
                    "result": Any,  # Optional partial result if available
                },
                ...
            ]
        """
        try:
            # Get task IDs from params
            task_ids = params.get("task_ids") or params.get("context_ids", [])
            if isinstance(task_ids, str):
                task_ids = task_ids.split(',')
            
            if not task_ids:
                return []
            
            # Get force flag and error message
            force = params.get("force", False)
            error_message = params.get("error_message")
            if not error_message:
                error_message = "Force cancelled by user" if force else "Cancelled by user"
            
            # Get TaskExecutor
            from aipartnerupflow.core.execution.task_executor import TaskExecutor
            task_executor = TaskExecutor()
            
            # Get database session for permission checking
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            results = []
            for task_id in task_ids:
                try:
                    # Check permission: get task to verify user_id
                    task = await task_repository.get_task_by_id(task_id)
                    if task:
                        # Check permission if user_id is specified
                        if task.user_id:
                            self._check_permission(request, task.user_id, "cancel task for")
                    else:
                        # Task not found, but we'll still try to cancel (might be in memory)
                        logger.warning(f"Task {task_id} not found in database, attempting cancellation anyway")
                    
                    # Call TaskExecutor.cancel_task() which handles:
                    # 1. Calling executor.cancel() if executor supports cancellation
                    # 2. Updating database with cancelled status and token_usage
                    cancel_result = await task_executor.cancel_task(task_id, error_message)
                    
                    # Add task_id to result
                    cancel_result["task_id"] = task_id
                    cancel_result["force"] = force
                    
                    results.append(cancel_result)
                    
                except PermissionError as e:
                    logger.warning(f"Permission denied for cancelling task {task_id}: {str(e)}")
                    results.append({
                        "task_id": task_id,
                        "status": "failed",
                        "message": f"Permission denied: {str(e)}",
                        "error": "permission_denied"
                    })
                except Exception as e:
                    logger.error(f"Error cancelling task {task_id}: {str(e)}", exc_info=True)
                    results.append({
                        "task_id": task_id,
                        "status": "error",
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error handling task cancellation: {str(e)}", exc_info=True)
            raise

    async def _handle_health(self, params: dict, request_id: str) -> dict:
        """Handle health check"""
        return {
            "status": "healthy",
            "message": "aipartnerupflow is healthy",
            "version": "0.2.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "running_tasks_count": 0,  # TODO: Implement actual task count
        }

    def _get_user_info(self, request: Request) -> tuple[Optional[str], Optional[list]]:
        """
        Extract user information from request state (set by JWT middleware)
        
        Returns:
            Tuple of (user_id, roles):
            - user_id: User ID from JWT token payload (sub field)
            - roles: User roles from JWT token payload (roles field, optional)
        """
        user_id = getattr(request.state, "user_id", None)
        token_payload = getattr(request.state, "token_payload", None)
        roles = None
        if token_payload:
            roles = token_payload.get("roles") or token_payload.get("role")
            if roles and not isinstance(roles, list):
                roles = [roles]
        return user_id, roles

    def _check_permission(
        self, 
        request: Request, 
        target_user_id: Optional[str],
        operation: str = "access"
    ) -> Optional[str]:
        """
        Check if user has permission to access target_user_id's resources
        
        Permission rules:
        1. If JWT is not enabled (no verify_token_func) and target_user_id is None:
           - Return None (no user restriction, allow all)
        2. If JWT is not enabled but target_user_id is provided:
           - Return None (no user restriction, allow all)
        3. If JWT is enabled:
           - Get authenticated user_id from request.state (set by JWT middleware)
           - If no authenticated user_id, raise error (JWT required)
           - If target_user_id is None, return authenticated_user_id (user can access their own)
           - If verify_permission_func is provided, use it to check permission
           - If verify_permission_func is not provided, use default logic:
             * Admin users (roles contains "admin") can access any user_id
             * Non-admin users can only access their own user_id
        
        Args:
            request: Request object with user info in state
            target_user_id: Target user ID to check permission for (None means no specific user restriction)
            operation: Operation name for logging (default: "access")
        
        Returns:
            Resolved user_id to use:
            - If JWT disabled: None (no user restriction)
            - If JWT enabled: authenticated_user_id (validated)
        
        Raises:
            ValueError: If permission is denied
        """
        # If JWT is not enabled, no permission checking needed
        if not self.verify_token_func:
            # No JWT, no user restriction - return None
            return None
        
        # Get user info from request state (set by JWT middleware)
        authenticated_user_id, roles = self._get_user_info(request)
        
        # If JWT is enabled but no authenticated user (JWT not provided or invalid)
        if not authenticated_user_id:
            # JWT is enabled but no valid token - this should not happen if middleware is working
            # But if it does, we allow it (middleware should have rejected it)
            logger.warning("JWT enabled but no authenticated user_id in request.state")
            return None
        
        # If target_user_id is None, permission is granted (no specific user restriction)
        # User can access their own resources (authenticated_user_id)
        if target_user_id is None:
            return authenticated_user_id
        
        # Check permission using verify_permission_func if provided
        if self.verify_permission_func:
            has_permission = self.verify_permission_func(
                authenticated_user_id, 
                target_user_id, 
                roles
            )
            if not has_permission:
                raise ValueError(
                    f"Permission denied: User {authenticated_user_id} does not have permission "
                    f"to {operation} resources for user {target_user_id}"
                )
            return authenticated_user_id
        
        # Default permission logic: admin can access any user_id, others can only access their own
        is_admin = roles and "admin" in roles
        if is_admin:
            # Admin can access any user_id
            logger.debug(f"Admin user {authenticated_user_id} accessing user {target_user_id}'s resources")
            return authenticated_user_id
        elif authenticated_user_id == target_user_id:
            # User can access their own resources
            return authenticated_user_id
        else:
            # User cannot access other users' resources
            raise ValueError(
                f"Permission denied: User {authenticated_user_id} can only {operation} their own resources, "
                f"not user {target_user_id}'s resources"
            )

    async def _handle_task_create_logic(
        self, 
        params: dict | list, 
        request: Request, 
        request_id: str
    ) -> dict:
        """
        Handle task creation
        
        Unified processing: convert all inputs to tasks array format
        
        Params can be:
        1. List of task objects: [{"name": "Task 1", ...}, ...]
        2. Single task dict: {"name": "Task 1", ...} - will be converted to [{"name": "Task 1", ...}]
        
        All tasks in the array must have the same user_id (after resolution).
        If tasks have different user_ids, an error will be raised.
        
        Params format:
            - If list: directly the tasks array
            - If dict: single task object (will be converted to array)
        
        Each task object can have:
            - id: Task ID (optional) - if provided, ALL tasks must have id and use id for references
            - name: Task name (required)
            - user_id: User ID (optional, will be checked/validated, must be same for all tasks)
            - parent_id: Parent task ID or name (optional)
            - priority: Priority level (optional, default: 1)
            - dependencies: Dependencies list (optional)
            - inputs: Execution-time input parameters (optional)
            - schemas: Task schemas (optional)
            - params: Task parameters (optional)
            - ... (any custom fields)
        """
        try:
            # Convert params to tasks array format
            if isinstance(params, dict):
                # Single task - convert to array
                tasks_array = [params]
                logger.info(f"Creating task tree from single task (converted to array)")
            elif isinstance(params, list):
                # Already an array
                tasks_array = params
                logger.info(f"Creating task tree from {len(tasks_array)} tasks")
            else:
                raise ValueError("Params must be a dict (single task) or list (tasks array)")
            
            if not tasks_array:
                raise ValueError("Tasks array cannot be empty")
            
            # Get authenticated user_id if JWT is enabled
            authenticated_user_id = None
            if self.verify_token_func:
                authenticated_user_id, _ = self._get_user_info(request)
            
            # Collect all user_ids from tasks array
            task_user_ids = set()
            for task_data in tasks_array:
                task_user_id = task_data.get("user_id")
                if task_user_id:
                    task_user_ids.add(task_user_id)
            
            # Resolve and validate user_id for all tasks
            resolved_user_id = None
            
            if task_user_ids:
                # Tasks have user_id specified - all must be the same
                if len(task_user_ids) > 1:
                    raise ValueError(
                        f"All tasks must have the same user_id. Found multiple user_ids: {task_user_ids}"
                    )
                
                # Get the single user_id
                specified_user_id = task_user_ids.pop()
                
                # Check permission
                resolved_user_id = self._check_permission(request, specified_user_id, "create tasks for")
                if resolved_user_id:
                    # Use resolved user_id (may be authenticated_user_id for admin case)
                    resolved_user_id = resolved_user_id
                else:
                    # No JWT, use specified user_id
                    resolved_user_id = specified_user_id
                
                # Ensure all tasks use the same resolved user_id
                for task_data in tasks_array:
                    if task_data.get("user_id"):
                        task_data["user_id"] = resolved_user_id
            else:
                # No user_id in tasks - use authenticated user_id or None
                if authenticated_user_id:
                    resolved_user_id = authenticated_user_id
                    # Set user_id for all tasks
                    for task_data in tasks_array:
                        if "user_id" not in task_data:
                            task_data["user_id"] = resolved_user_id
                else:
                    # No JWT and no user_id in tasks, allow None (no user restriction)
                    resolved_user_id = None
            
            # Get database session and create TaskCreator
            db_session = get_default_session()
            task_creator = TaskCreator(db_session)
            
            # Create task tree from array
            task_tree = await task_creator.create_task_tree_from_array(
                tasks=tasks_array,
            )
            
            # Convert task tree to dictionary format for response
            def tree_node_to_dict(node):
                """Convert TaskTreeNode to dictionary"""
                task_dict = node.task.to_dict()
                if node.children:
                    task_dict["children"] = [tree_node_to_dict(child) for child in node.children]
                return task_dict
            
            result = tree_node_to_dict(task_tree)
            
            logger.info(f"Created task tree: root task {task_tree.task.name} "
                       f"with {len(task_tree.children)} direct children")
            return result
            
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}", exc_info=True)
            raise

    async def _handle_task_get_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> Optional[dict]:
        """Handle task retrieval by ID"""
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")
            
            # Get database session and create repository with custom TaskModel
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            task = await task_repository.get_task_by_id(task_id)
            
            if not task:
                return None
            
            # Check permission to access this task
            self._check_permission(request, task.user_id, "access")
            
            return task.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting task: {str(e)}", exc_info=True)
            raise

    async def _handle_task_update_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> dict:
        """Handle task update"""
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")
            
            # Get database session and create repository with custom TaskModel
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            # Get task first
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Check permission to update this task
            self._check_permission(request, task.user_id, "update")
            
            # Update status if provided
            status = params.get("status")
            if status:
                await task_repository.update_task_status(
                    task_id=task_id,
                    status=status,
                    error=params.get("error"),
                    result=params.get("result"),
                    progress=params.get("progress"),
                    started_at=params.get("started_at"),
                    completed_at=params.get("completed_at"),
                )
            
            # Update inputs if provided
            inputs = params.get("inputs")
            if inputs is not None:
                await task_repository.update_task_inputs(task_id, inputs)
            
            # Refresh task to get updated values
            updated_task = await task_repository.get_task_by_id(task_id)
            if not updated_task:
                raise ValueError(f"Task {task_id} not found after update")
            
            logger.info(f"Updated task {task_id}")
            return updated_task.to_dict()
            
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}", exc_info=True)
            raise

    async def _handle_task_delete_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> dict:
        """Handle task deletion"""
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")
            
            # Get database session and create repository with custom TaskModel
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            # Get task first to check if exists
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Check permission to delete this task
            self._check_permission(request, task.user_id, "delete")
            
            # Delete task
            # Note: TaskRepository doesn't have delete method yet, so we'll mark as deleted or remove
            # For now, we'll update status to "deleted" (if we add that status)
            # Or we can add a delete method to TaskRepository
            await task_repository.update_task_status(
                task_id=task_id,
                status="deleted",
                completed_at=datetime.now(timezone.utc),
            )
            
            logger.info(f"Deleted task {task_id}")
            return {"success": True, "task_id": task_id}
            
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}", exc_info=True)
            raise

    async def _handle_task_copy_logic(
        self, 
        params: dict, 
        request: Request, 
        request_id: str
    ) -> dict:
        """Handle task copy (create_task_copy)"""
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")
            
            # Get database session and create repository with custom TaskModel
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            # Get original task
            original_task = await task_repository.get_task_by_id(task_id)
            if not original_task:
                raise ValueError(f"Task {task_id} not found")
            
            # Check permission to copy this task
            self._check_permission(request, original_task.user_id, "copy")
            
            # Create TaskCreator and copy task
            task_creator = TaskCreator(db_session)
            
            new_tree = await task_creator.create_task_copy(original_task)
            
            # Convert task tree to dictionary format for response
            def tree_node_to_dict(node):
                """Convert TaskTreeNode to dictionary"""
                task_dict = node.task.to_dict()
                if node.children:
                    task_dict["children"] = [tree_node_to_dict(child) for child in node.children]
                return task_dict
            
            result = tree_node_to_dict(new_tree)
            
            logger.info(f"Copied task {task_id} to new task {new_tree.task.id}")
            return result
            
        except Exception as e:
            logger.error(f"Error copying task: {str(e)}", exc_info=True)
            raise

