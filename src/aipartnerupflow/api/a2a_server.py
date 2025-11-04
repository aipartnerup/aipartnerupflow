"""
A2A server implementation for aipartnerupflow
"""

import httpx
from typing import Optional, Type, List
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
from aipartnerupflow.api.agent_executor import AIPartnerUpFlowAgentExecutor
from aipartnerupflow.api.custom_starlette_app import CustomA2AStarletteApplication
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.types import TaskPreHook, TaskPostHook
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def load_skills() -> list[AgentSkill]:
    """
    Load skills for the agent card
    
    Returns:
        List of AgentSkill objects
    """
    skills = []
    
    # Add main task execution skill
    skills.append(
        AgentSkill(
            id="execute_task_tree",
            name="Execute Task Tree",
            description="Execute a complete task tree with multiple tasks",
            tags=["task", "orchestration", "workflow"],
            examples=["execute task tree", "run tasks", "process task hierarchy"],
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

# Global task_model_class (can be set via create_a2a_server)
_global_task_model_class: Optional[Type[TaskModel]] = None


def _create_request_handler(
    task_model_class: Optional[Type[TaskModel]] = None,
    pre_hooks: Optional[List[TaskPreHook]] = None,
    post_hooks: Optional[List[TaskPostHook]] = None
):
    """
    Create request handler with agent executor
    
    Args:
        task_model_class: Optional custom TaskModel class
        pre_hooks: Optional list of pre-execution hook functions
        post_hooks: Optional list of post-execution hook functions
    """
    agent_executor = AIPartnerUpFlowAgentExecutor(
        task_model_class=task_model_class,
        pre_hooks=pre_hooks,
        post_hooks=post_hooks
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
        from jose import JWTError, jwt
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError as e:
        logger.error(f"Error verifying JWT token: {e}")
        return None
    except ImportError:
        logger.error("python-jose not installed. Install it with: pip install python-jose[cryptography]")
        return None


def create_a2a_server(
    verify_token_func=None,
    verify_token_secret_key: Optional[str] = None,
    verify_token_algorithm: str = "HS256",
    base_url: Optional[str] = None,
    enable_system_routes: bool = True,
    task_model_class: Optional[Type[TaskModel]] = None,
    pre_hooks: Optional[List[TaskPreHook]] = None,
    post_hooks: Optional[List[TaskPostHook]] = None,
) -> CustomA2AStarletteApplication:
    """
    Create A2A server instance with configuration
    
    As a library: All configuration via function parameters (no env var dependency)
    This avoids conflicts with user projects.
    
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
        task_model_class: Optional custom TaskModel class.
                         Users can pass their custom TaskModel subclass that inherits TaskModel
                         to add custom fields (e.g., project_id, department, etc.).
                         If None, default TaskModel will be used.
                         Example: create_a2a_server(..., task_model_class=MyTaskModel)
        pre_hooks: Optional list of pre-execution hook functions.
                  Each hook receives (task: TaskModel) and can access/modify task.input_data.
                  Hooks can be sync or async functions.
                  Example:
                      async def my_pre_hook(task):
                          if task.input_data and task.input_data.get("url"):
                              task.input_data["url"] = task.input_data["url"].strip()
                      create_a2a_server(..., pre_hooks=[my_pre_hook])
        post_hooks: Optional list of post-execution hook functions.
                   Each hook receives (task: TaskModel, input_data: Dict[str, Any], result: Any).
                   Hooks can be sync or async functions.
                   Example:
                       async def my_post_hook(task, input_data, result):
                           logger.info(f"Task {task.id} completed with result: {result}")
                       create_a2a_server(..., post_hooks=[my_post_hook])
    
    Returns:
        CustomA2AStarletteApplication instance
    """
    global _global_task_model_class
    _global_task_model_class = task_model_class

    # Create request handler with custom TaskModel and hooks support
    request_handler = _create_request_handler(
        task_model_class=task_model_class,
        pre_hooks=pre_hooks,
        post_hooks=post_hooks
    )

    # Create agent card
    public_agent_card = AgentCard(
        name="aipartnerupflow",
        description="Agent workflow orchestration and execution platform",
        url=base_url or "http://localhost:8000",  # Default URL if None
        version="0.1.0",
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

    return CustomA2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
        verify_token_func=verify_token_func,
        enable_system_routes=enable_system_routes,
        task_model_class=task_model_class,
    )

