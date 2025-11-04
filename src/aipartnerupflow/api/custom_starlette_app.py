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
        
        # Store task_model_class for task management APIs
        self.task_model_class = task_model_class or TaskModel
        
        logger.info(
            f"Initialized CustomA2AStarletteApplication "
            f"(System routes: {self.enable_system_routes}, "
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
            
            logger.info(f"🔍 [handle_task_requests] [{request_id}] Method: {method}, Params: {params}")
            
            # Route to specific handler based on method
            # Task CRUD operations
            if method == "tasks.create":
                result = await self._handle_task_create_logic(params, request_id)
            elif method == "tasks.get":
                result = await self._handle_task_get_logic(params, request_id)
            elif method == "tasks.update":
                result = await self._handle_task_update_logic(params, request_id)
            elif method == "tasks.delete":
                result = await self._handle_task_delete_logic(params, request_id)
            # Task query operations
            elif method == "tasks.detail":
                result = await self._handle_task_detail_logic(params, request_id)
            elif method == "tasks.tree":
                result = await self._handle_task_tree_logic(params, request_id)
            # Running task monitoring
            elif method == "tasks.running.list":
                result = await self._handle_running_tasks_list_logic(params, request_id)
            elif method == "tasks.running.status":
                result = await self._handle_running_tasks_status_logic(params, request_id)
            elif method == "tasks.running.count":
                result = await self._handle_running_tasks_count_logic(params, request_id)
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

    async def _handle_task_detail_logic(self, params: dict, request_id: str) -> Optional[dict]:
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
            
            return task.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting task detail: {str(e)}", exc_info=True)
            raise

    async def _handle_task_tree_logic(self, params: dict, request_id: str) -> Optional[dict]:
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

    async def _handle_running_tasks_list_logic(self, params: dict, request_id: str) -> list:
        """
        Handle running tasks list - returns list of currently running tasks
        
        Params:
            user_id: Optional user ID filter
            status: Optional status filter (default: "in_progress")
            limit: Optional limit (default: 100)
        
        Returns:
            List of running tasks
        """
        try:
            user_id = params.get("user_id")
            status_filter = params.get("status", "in_progress")
            limit = params.get("limit", 100)
            
            # Get database session and create repository
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            # Query running tasks
            # Note: TaskRepository doesn't have a list method yet, so we'll use a simple query
            from sqlalchemy import select
            query = select(self.task_model_class).where(
                self.task_model_class.status == status_filter
            )
            
            if user_id:
                query = query.where(self.task_model_class.user_id == user_id)
            
            query = query.limit(limit).order_by(self.task_model_class.created_at.desc())
            
            if task_repository.is_async:
                result = await db_session.execute(query)
                tasks = result.scalars().all()
            else:
                result = db_session.execute(query)
                tasks = result.scalars().all()
            
            return [task.to_dict() for task in tasks]
            
        except Exception as e:
            logger.error(f"Error getting running tasks list: {str(e)}", exc_info=True)
            raise

    async def _handle_running_tasks_status_logic(self, params: dict, request_id: str) -> list:
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
            
            # Get database session and create repository
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            statuses = []
            for task_id in task_ids:
                task = await task_repository.get_task_by_id(task_id.strip())
                if task:
                    statuses.append({
                        "task_id": task.id,
                        "context_id": task.id,  # For A2A Protocol compatibility
                        "status": task.status,
                        "progress": float(task.progress) if task.progress else 0.0,
                        "error": task.error,
                        "started_at": task.started_at.isoformat() if task.started_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                    })
                else:
                    statuses.append({
                        "task_id": task_id,
                        "context_id": task_id,
                        "status": "not_found",
                        "progress": 0.0,
                        "error": None,
                        "started_at": None,
                        "updated_at": None,
                    })
            
            return statuses
            
        except Exception as e:
            logger.error(f"Error getting running tasks status: {str(e)}", exc_info=True)
            raise

    async def _handle_running_tasks_count_logic(self, params: dict, request_id: str) -> dict:
        """
        Handle running tasks count - returns count of tasks by status
        
        Params:
            user_id: Optional user ID filter
            status: Optional status filter (if not provided, returns counts for all statuses)
        
        Returns:
            Dictionary with status counts
        """
        try:
            user_id = params.get("user_id")
            status_filter = params.get("status")
            
            # Get database session and create repository
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            from sqlalchemy import select, func
            
            if status_filter:
                # Count specific status
                query = select(func.count(self.task_model_class.id)).where(
                    self.task_model_class.status == status_filter
                )
                if user_id:
                    query = query.where(self.task_model_class.user_id == user_id)
                
                if task_repository.is_async:
                    result = await db_session.execute(query)
                    count = result.scalar()
                else:
                    result = db_session.execute(query)
                    count = result.scalar()
                
                return {status_filter: count}
            else:
                # Count all statuses
                query = select(
                    self.task_model_class.status,
                    func.count(self.task_model_class.id).label('count')
                ).group_by(self.task_model_class.status)
                
                if user_id:
                    query = query.where(self.task_model_class.user_id == user_id)
                
                if task_repository.is_async:
                    result = await db_session.execute(query)
                    rows = result.all()
                else:
                    result = db_session.execute(query)
                    rows = result.all()
                
                return {row.status: row.count for row in rows}
            
        except Exception as e:
            logger.error(f"Error getting running tasks count: {str(e)}", exc_info=True)
            raise

    async def _handle_health(self, params: dict, request_id: str) -> dict:
        """Handle health check"""
        return {
            "status": "healthy",
            "message": "aipartnerupflow is healthy",
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "running_tasks_count": 0,  # TODO: Implement actual task count
        }

    async def _handle_task_create_logic(self, params: dict, request_id: str) -> dict:
        """Handle task creation"""
        try:
            # Get required parameters
            name = params.get("name")
            user_id = params.get("user_id")
            
            if not name:
                raise ValueError("Task name is required")
            if not user_id:
                raise ValueError("User ID is required")
            
            # Get optional parameters
            parent_id = params.get("parent_id")
            priority = params.get("priority", 1)
            dependencies = params.get("dependencies")
            input_data = params.get("input_data")
            schemas = params.get("schemas")
            params_dict = params.get("params")
            
            # Extract custom fields (any fields not in core task fields)
            core_fields = {
                "name", "user_id", "parent_id", "priority", "dependencies",
                "input_data", "schemas", "params", "method"
            }
            custom_fields = {k: v for k, v in params.items() if k not in core_fields}
            
            # Get database session and create repository with custom TaskModel
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            
            # Create task (custom fields passed via **kwargs)
            task = await task_repository.create_task(
                name=name,
                user_id=user_id,
                parent_id=parent_id,
                priority=priority,
                dependencies=dependencies,
                input_data=input_data,
                schemas=schemas,
                params=params_dict,
                **custom_fields  # Pass custom fields
            )
            
            logger.info(f"Created task {task.id} (name: {name}, user_id: {user_id})")
            return task.to_dict()
            
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}", exc_info=True)
            raise

    async def _handle_task_get_logic(self, params: dict, request_id: str) -> Optional[dict]:
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
            
            return task.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting task: {str(e)}", exc_info=True)
            raise

    async def _handle_task_update_logic(self, params: dict, request_id: str) -> dict:
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
            
            # Update input_data if provided
            input_data = params.get("input_data")
            if input_data is not None:
                await task_repository.update_task_input_data(task_id, input_data)
            
            # Refresh task to get updated values
            updated_task = await task_repository.get_task_by_id(task_id)
            if not updated_task:
                raise ValueError(f"Task {task_id} not found after update")
            
            logger.info(f"Updated task {task_id}")
            return updated_task.to_dict()
            
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}", exc_info=True)
            raise

    async def _handle_task_delete_logic(self, params: dict, request_id: str) -> dict:
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

