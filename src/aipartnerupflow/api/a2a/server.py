"""
A2A server implementation for aipartnerupflow
"""

import httpx
from typing import Optional, Type, Dict, Any, List
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryTaskStore,
    InMemoryPushNotificationConfigStore,
    BasePushNotificationSender,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
from aipartnerupflow.api.a2a.custom_starlette_app import CustomA2AStarletteApplication
from aipartnerupflow.api.routes.tasks import TaskRoutes
from aipartnerupflow.core.config import get_task_model_class
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def load_skills() -> list[AgentSkill]:
    """
    Load skills for the agent card
    
    Returns:
        List of AgentSkill objects
    """
    skills = []
    
    # Task execution skill
    skills.append(
        AgentSkill(
            id="tasks.execute",
            name="Execute Task Tree",
            description="Execute a complete task tree with multiple tasks",
            tags=["task", "orchestration", "workflow", "execution"],
            examples=["execute task tree", "run tasks", "process task hierarchy"],
        )
    )
    
    # Task CRUD operations
    skills.append(
        AgentSkill(
            id="tasks.create",
            name="Create Task",
            description="Create a new task or task tree",
            tags=["task", "create", "crud"],
            examples=["create task", "create task tree", "add task"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.get",
            name="Get Task",
            description="Get a task by ID",
            tags=["task", "get", "crud", "read"],
            examples=["get task", "retrieve task", "fetch task"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.update",
            name="Update Task",
            description="Update an existing task",
            tags=["task", "update", "crud", "modify"],
            examples=["update task", "modify task", "edit task"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.delete",
            name="Delete Task",
            description="Delete a task and its children (if all are pending)",
            tags=["task", "delete", "crud", "remove"],
            examples=["delete task", "remove task", "drop task"],
        )
    )
    
    # Task query operations
    skills.append(
        AgentSkill(
            id="tasks.detail",
            name="Get Task Detail",
            description="Get full task details including all fields",
            tags=["task", "detail", "query", "read"],
            examples=["get task detail", "task details", "full task info"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.tree",
            name="Get Task Tree",
            description="Get task tree structure with nested children",
            tags=["task", "tree", "query", "hierarchy"],
            examples=["get task tree", "task hierarchy", "task structure"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.list",
            name="List Tasks",
            description="List all tasks with optional filters (user_id, status, root_only)",
            tags=["task", "list", "query", "search"],
            examples=["list tasks", "get all tasks", "search tasks"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.children",
            name="Get Task Children",
            description="Get child tasks for a given parent task",
            tags=["task", "children", "query", "hierarchy"],
            examples=["get task children", "list children", "child tasks"],
        )
    )
    
    # Running task monitoring
    skills.append(
        AgentSkill(
            id="tasks.running.list",
            name="List Running Tasks",
            description="List currently running tasks from memory",
            tags=["task", "running", "monitoring", "status"],
            examples=["list running tasks", "active tasks", "current tasks"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.running.status",
            name="Get Running Task Status",
            description="Get status of multiple running tasks",
            tags=["task", "running", "status", "monitoring"],
            examples=["get task status", "check task status", "task status"],
        )
    )
    
    skills.append(
        AgentSkill(
            id="tasks.running.count",
            name="Count Running Tasks",
            description="Get count of running tasks by status",
            tags=["task", "running", "count", "monitoring"],
            examples=["count running tasks", "task count", "number of tasks"],
        )
    )
    
    # Task cancellation
    skills.append(
        AgentSkill(
            id="tasks.cancel",
            name="Cancel Task",
            description="Cancel one or more running tasks",
            tags=["task", "cancel", "stop", "control"],
            examples=["cancel task", "stop task", "abort task"],
        )
    )
    
    # Task copy
    skills.append(
        AgentSkill(
            id="tasks.copy",
            name="Copy Task",
            description="Create a copy of a task (optionally with children)",
            tags=["task", "copy", "duplicate", "clone"],
            examples=["copy task", "duplicate task", "clone task"],
        )
    )
    
    # Task generation
    skills.append(
        AgentSkill(
            id="tasks.generate",
            name="Generate Task Tree",
            description="Generate a task tree JSON array from natural language requirement using LLM",
            tags=["task", "generate", "llm", "ai", "automation"],
            examples=["generate task tree", "create task from requirement", "auto-generate workflow"],
        )
    )
    
    logger.info(f"Loaded {len(skills)} skills successfully")
    return skills


# Load skills at startup
logger.info("Loading skills...")
all_skills = load_skills()

# Create HTTP client and push notification components
httpx_client = httpx.AsyncClient()
push_config_store = InMemoryPushNotificationConfigStore()
push_sender = BasePushNotificationSender(
    httpx_client=httpx_client,
    config_store=push_config_store
)

def _create_request_handler(
    verify_token_func=None,
    verify_permission_func=None,
    task_routes_class: Optional[Type[TaskRoutes]] = None,
):
    """
    Create request handler with agent executor
    
    Configuration (task_model_class, hooks) is automatically retrieved from
    the global config registry by AIPartnerUpFlowAgentExecutor.
    
    Args:
        verify_token_func: Optional JWT verification function
        verify_permission_func: Optional permission verification function
        task_routes_class: Optional custom TaskRoutes class (default: TaskRoutes)
    """
    # Get task_model_class from registry
    task_model_class = get_task_model_class()
    
    # Use provided task_routes_class or default TaskRoutes
    task_routes_cls = task_routes_class or TaskRoutes
    
    # Create TaskRoutes instance for the adapter
    task_routes = task_routes_cls(
        task_model_class=task_model_class,
        verify_token_func=verify_token_func,
        verify_permission_func=verify_permission_func
    )
    
    # Create agent executor with TaskRoutes
    agent_executor = AIPartnerUpFlowAgentExecutor(
        task_routes=task_routes,
        verify_token_func=verify_token_func
    )
    
    return DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
        push_config_store=push_config_store,
        push_sender=push_sender
    )


def verify_token(token: str, secret_key: Optional[str], algorithm: str = "HS256") -> Optional[dict]:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string to verify
        secret_key: JWT secret key for verification
        algorithm: JWT algorithm (default: "HS256")
    
    Returns:
        Decoded token payload as dict, or None if verification fails
    """
    if not secret_key:
        return None
    
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError as e:
        logger.error(f"Error verifying JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Exception verifying JWT token: {e}")
        return None


def generate_token(payload: Dict[str, Any], secret_key: str, algorithm: str = "HS256", expires_in_days: int = 30) -> str:
    """
    Generate JWT token for user
    
    Uses PyJWT to generate tokens.
    
    Args:
        user_id: User ID (from browser fingerprint or cookie)
        expires_in_days: Token expiration in days (default: 365 days / 1 year)
        
    Returns:
        JWT token string
    """

    # Create payload
    now = datetime.now(timezone.utc)
    payload.update({
        "iat": int(now.timestamp()),  # Issued at
        "exp": int((now + timedelta(days=expires_in_days)).timestamp()),  # Expiration
    })
    
    try:
        token = jwt.encode(payload, secret_key, algorithm=algorithm)
        return token
    except JWTError as e:
        raise ValueError(f"Error generating JWT token: {e}")
    except Exception:
        raise

def create_a2a_server(
    verify_token_func=None,
    verify_token_secret_key: Optional[str] = None,
    verify_token_algorithm: str = "HS256",
    base_url: Optional[str] = None,
    enable_system_routes: bool = True,
    enable_docs: bool = True,
    task_routes_class: Optional[Type[TaskRoutes]] = None,
    custom_routes: Optional[List] = None,
    custom_middleware: Optional[List] = None,
    auto_initialize_extensions: bool = False,
    verify_permission_func: Optional[Any] = None,
) -> CustomA2AStarletteApplication:
    """
    Create A2A server instance with configuration
    
    Configuration (hooks, task_model_class) should be registered using decorators
    before calling this function. See the unified decorators module for details.
    
    Example:
        from aipartnerupflow import register_pre_hook, register_post_hook, set_task_model_class
        
        @register_pre_hook
        async def my_pre_hook(task):
            task.inputs["url"] = task.inputs["url"].strip()
        
        @register_post_hook
        async def my_post_hook(task, inputs, result):
            logger.info(f"Task {task.id} completed")
        
        set_task_model_class(MyTaskModel)
        create_a2a_server(...)
    
    Args:
        verify_token_func: Custom JWT token verification function.
                          If provided, it will be used to verify JWT tokens.
                          If None and verify_token_secret_key is provided, a default verifier will be created.
                          Signature: verify_token_func(token: str) -> Optional[dict]
        verify_token_secret_key: JWT secret key for token verification.
                                Used only if verify_token_func is None.
                                If both are None, JWT authentication will be disabled.
        verify_token_algorithm: JWT algorithm (default: "HS256").
                               Used only if verify_token_secret_key is provided and verify_token_func is None.
        base_url: Base URL of the service. Used in agent card.
        enable_system_routes: Whether to enable system routes like /system (default: True)
        enable_docs: Whether to enable interactive API documentation at /docs (default: True).
                    Only available when API server is running, not when used as a library.
        task_routes_class: Optional custom TaskRoutes class to use instead of default TaskRoutes.
                         Allows extending TaskRoutes functionality without monkey patching.
                         Example: task_routes_class=MyCustomTaskRoutes
        custom_routes: Optional list of custom Starlette Route objects to add to the application.
                      Routes are merged after default routes (custom routes can override defaults if needed).
                      Example: [Route("/custom", custom_handler, methods=["GET"])]
        custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes to add to the application.
                          Middleware will be added in the order provided, after default middleware (CORS, LLM API key, JWT).
                          Each middleware class should be a subclass of BaseHTTPMiddleware.
                          Example: [MyCustomMiddleware, AnotherMiddleware]
        auto_initialize_extensions: If True, automatically initialize all extensions
                                   before creating the server (default: False).
                                   This matches the behavior of create_app_by_protocol().
        verify_permission_func: Optional function to verify user permissions.
                               If provided, it will be used to verify user permissions for accessing resources.
                               If None, permission checking is disabled.
                               Signature: verify_permission_func(user_id: str, target_user_id: Optional[str], roles: Optional[list]) -> bool
                               Returns True if user has permission to access target_user_id's resources.
    
    Returns:
        CustomA2AStarletteApplication instance
    
    Note:
        To configure hooks and TaskModel, use the unified decorators:
        - @register_pre_hook: Register pre-execution hooks
        - @register_post_hook: Register post-execution hooks
        - set_task_model_class(): Set custom TaskModel class
        
        All decorators are available from: from aipartnerupflow import ...
    """
    # Auto-initialize extensions if requested
    if auto_initialize_extensions:
        from aipartnerupflow.api.extensions import initialize_extensions
        initialize_extensions()
    
    # Create request handler (reads from config registry)
    request_handler = _create_request_handler(
        verify_token_func=verify_token_func,
        verify_permission_func=verify_permission_func,
        task_routes_class=task_routes_class,
    )

    # Create agent card
    public_agent_card = AgentCard(
        name="aipartnerupflow",
        description="Agent workflow orchestration and execution platform",
        url=base_url or "http://localhost:8000",  # Default URL if None
        version="0.2.0",
        default_input_modes=["data"],
        default_output_modes=["data"],
        capabilities=AgentCapabilities(streaming=True, push_notifications=True),
        skills=all_skills,
        supports_authenticated_extended_card=False,
    )

    # Create default JWT verifier if secret key is provided but no custom function
    if not verify_token_func and verify_token_secret_key:
        def verify_token_func_callback(token: str) -> Optional[dict]:
            """Default JWT token verifier using secret key"""
            return verify_token(token, verify_token_secret_key, verify_token_algorithm)
        verify_token_func = verify_token_func_callback

    # Get task_model_class from registry (may have been set via set_task_model_class)
    final_task_model_class = get_task_model_class()
    
    return CustomA2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
        verify_token_func=verify_token_func,
        verify_permission_func=verify_permission_func,
        enable_system_routes=enable_system_routes,
        enable_docs=enable_docs,
        task_model_class=final_task_model_class,
        task_routes_class=task_routes_class,
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
    )

