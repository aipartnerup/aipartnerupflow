"""
Task management route handlers - protocol-agnostic

This module provides task management handlers that can be used by any protocol
(A2A, REST, GraphQL, etc.) to handle task CRUD operations, execution, and monitoring.
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from aipartnerupflow.api.routes.base import BaseRouteHandler
from aipartnerupflow.core.storage import create_pooled_session
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.execution.task_creator import TaskCreator
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.core.utils.helpers import tree_node_to_dict

logger = get_logger(__name__)

# Global event storage for task streaming (keyed by root_task_id)
# Global event storage for task streaming (keyed by root_task_id)
_task_streaming_events: Dict[str, List[Dict[str, Any]]] = {}
_task_streaming_events_lock: Optional[asyncio.Lock] = None


def _get_streaming_events_lock() -> asyncio.Lock:
    """Get or create the global lock for streaming events"""
    global _task_streaming_events_lock
    if _task_streaming_events_lock is None:
        _task_streaming_events_lock = asyncio.Lock()
    return _task_streaming_events_lock


class TaskStreamingContext:
    """
    Streaming context for JSON-RPC tasks.execute endpoint
    Similar to EventQueueBridge but stores updates in memory for SSE consumption
    """

    def __init__(self, root_task_id: str):
        """
        Initialize streaming context

        Args:
            root_task_id: Root task ID for this execution
        """
        self.root_task_id = root_task_id
        self._update_queue = asyncio.Queue()
        self._bridge_task = None

        # Start background task to process updates
        self._start_bridge_task()

    def _start_bridge_task(self):
        """Start background task to store updates"""

        async def bridge_worker():
            while True:
                try:
                    update_data = await self._update_queue.get()

                    if update_data is None:  # Sentinel to stop
                        break

                    # Store update in global event store
                    async with _get_streaming_events_lock():
                        if self.root_task_id not in _task_streaming_events:
                            _task_streaming_events[self.root_task_id] = []
                        _task_streaming_events[self.root_task_id].append(update_data)

                    self._update_queue.task_done()
                except Exception as e:
                    logger.error(f"Error in streaming bridge worker: {str(e)}")
                    # Break loop on error to prevent infinite busy loop
                    break

        self._bridge_task = asyncio.create_task(bridge_worker())

    async def put(self, update_data: Dict[str, Any]):
        """
        Put progress update to bridge

        Args:
            update_data: Progress update data from TaskManager
        """
        await self._update_queue.put(update_data)

    async def close(self):
        """Close bridge and stop background task"""
        await self._update_queue.put(None)  # Sentinel to stop worker
        if self._bridge_task:
            await self._bridge_task


async def get_task_streaming_events(root_task_id: str) -> List[Dict[str, Any]]:
    """
    Get streaming events for a task

    Args:
        root_task_id: Root task ID

    Returns:
        List of streaming events
    """
    async with _get_streaming_events_lock():
        return _task_streaming_events.get(root_task_id, []).copy()


class WebhookStreamingContext:
    """
    Streaming context for JSON-RPC tasks.execute endpoint with webhook callbacks
    Similar to TaskStreamingContext but sends updates via HTTP webhook instead of storing in memory
    """

    def __init__(self, root_task_id: str, webhook_config: Dict[str, Any]):
        """
        Initialize webhook streaming context

        Args:
            root_task_id: Root task ID for this execution
            webhook_config: Webhook configuration dict with:
                - url (str, required): Webhook callback URL
                - headers (dict, optional): HTTP headers to include in requests
                - method (str, optional): HTTP method (default: "POST")
                - timeout (float, optional): Request timeout in seconds (default: 30.0)
                - max_retries (int, optional): Maximum retry attempts (default: 3)
        """
        self.root_task_id = root_task_id
        self.webhook_url = webhook_config.get("url")
        if not self.webhook_url:
            raise ValueError("webhook_config.url is required")

        self.webhook_headers = webhook_config.get("headers", {})
        self.webhook_method = webhook_config.get("method", "POST").upper()
        self.timeout = webhook_config.get("timeout", 30.0)
        self.max_retries = webhook_config.get("max_retries", 3)

        # Create HTTP client
        self.http_client = httpx.AsyncClient(timeout=self.timeout)

        # Update queue for processing updates
        self._update_queue = asyncio.Queue()
        self._bridge_task = None

        # Start background task to process updates
        self._start_bridge_task()

    def _start_bridge_task(self):
        """Start background task to send webhook updates"""

        async def bridge_worker():
            while True:
                try:
                    update_data = await self._update_queue.get()

                    if update_data is None:  # Sentinel to stop
                        break

                    # Send update to webhook URL
                    await self._send_webhook_update(update_data)

                    self._update_queue.task_done()
                except Exception as e:
                    logger.error(f"Error in webhook bridge worker: {str(e)}")
                    # Break loop on error to prevent infinite busy loop
                    break

        self._bridge_task = asyncio.create_task(bridge_worker())

    async def _send_webhook_update(self, update_data: Dict[str, Any]) -> None:
        """
        Send update to webhook URL with retry mechanism

        Args:
            update_data: Progress update data from TaskManager
        """
        # Format webhook payload (similar to A2A protocol format)
        webhook_payload = {
            "protocol": "jsonrpc",
            "root_task_id": self.root_task_id,
            "task_id": update_data.get("task_id", self.root_task_id),
            "status": update_data.get("status", "in_progress"),
            "progress": update_data.get("progress", 0.0),
            "message": update_data.get("message", ""),
            "type": update_data.get("type", "progress"),
            "timestamp": update_data.get("timestamp"),
            "final": update_data.get("final", False),
        }

        # Add optional fields
        if "result" in update_data:
            webhook_payload["result"] = update_data["result"]
        if "error" in update_data:
            webhook_payload["error"] = update_data["error"]

        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                # Prepare headers
                headers = {"Content-Type": "application/json", **self.webhook_headers}

                # Send HTTP request
                if self.webhook_method == "POST":
                    response = await self.http_client.post(
                        self.webhook_url, json=webhook_payload, headers=headers
                    )
                elif self.webhook_method == "PUT":
                    response = await self.http_client.put(
                        self.webhook_url, json=webhook_payload, headers=headers
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {self.webhook_method}")

                # Check response status (httpx response.raise_for_status is synchronous)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    # Re-raise as HTTPStatusError for proper handling
                    raise

                logger.debug(
                    f"Webhook update sent successfully to {self.webhook_url} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                return  # Success, exit retry loop

            except httpx.HTTPStatusError as e:
                # HTTP error (4xx, 5xx) - may retry for 5xx, but not for 4xx
                if 400 <= e.response.status_code < 500:
                    # Client error (4xx) - don't retry
                    logger.error(
                        f"Webhook callback failed with client error {e.response.status_code}: {e.response.text}"
                    )
                    raise
                else:
                    # Server error (5xx) - retry
                    last_exception = e
                    logger.warning(
                        f"Webhook callback failed with server error {e.response.status_code} "
                        f"(attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                    )

            except (httpx.RequestError, httpx.TimeoutException) as e:
                # Network error or timeout - retry
                last_exception = e
                logger.warning(
                    f"Webhook callback failed with network error "
                    f"(attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                )

            except Exception as e:
                # Unexpected error - don't retry
                logger.error(f"Unexpected error sending webhook update: {str(e)}")
                raise

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2**attempt  # 1s, 2s, 4s, ...
                await asyncio.sleep(wait_time)

        # All retries failed
        logger.error(
            f"Failed to send webhook update after {self.max_retries} attempts: {str(last_exception)}"
        )
        # Don't raise exception - log error but don't fail task execution

    async def put(self, update_data: Dict[str, Any]):
        """
        Put progress update to webhook bridge

        Args:
            update_data: Progress update data from TaskManager
        """
        await self._update_queue.put(update_data)

    async def close(self):
        """Close webhook bridge and stop background task"""
        await self._update_queue.put(None)  # Sentinel to stop worker
        if self._bridge_task:
            await self._bridge_task

        # Close HTTP client
        await self.http_client.aclose()


class CombinedStreamingContext:
    """
    Combined context that supports both SSE (memory storage) and webhook callbacks

    Used when user chooses SSE mode (use_streaming=True) and also requests webhook callbacks.
    This allows real-time SSE events to be streamed to the client while simultaneously
    sending progress updates to the webhook URL.
    """

    def __init__(self, root_task_id: str, webhook_config: Dict[str, Any]):
        """
        Initialize combined streaming context

        Args:
            root_task_id: Root task ID for this execution
            webhook_config: Webhook configuration dict
        """
        self.sse_context = TaskStreamingContext(root_task_id)
        self.webhook_context = WebhookStreamingContext(root_task_id, webhook_config)
        self.root_task_id = root_task_id

    async def put(self, update_data: Dict[str, Any]):
        """
        Put progress update to both SSE and webhook contexts

        Args:
            update_data: Progress update data from TaskManager
        """
        # Forward to both contexts
        await self.sse_context.put(update_data)
        await self.webhook_context.put(update_data)

    async def close(self):
        """Close both contexts"""
        await self.sse_context.close()
        await self.webhook_context.close()


class TaskRoutes(BaseRouteHandler):
    """
    Task management route handlers

    Provides protocol-agnostic handlers for task CRUD operations, execution,
    and monitoring that can be used by any protocol implementation.
    """

    async def handle_task_requests(self, request: Request) -> JSONResponse:
        """Handle all task management requests through /tasks endpoint"""
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Note: LLM API key extraction is now handled by LLMAPIKeyMiddleware
        # for all routes including /tasks and / (A2A protocol)

        try:
            # Parse JSON request
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})

            # Support direct tasks array for tasks.create method
            # If method is tasks.create and params is a list, use it directly
            if method == "tasks.create" and isinstance(params, list):
                # params is directly the tasks array
                logger.info(
                    f"🔍 [handle_task_requests] [{request_id}] Method: {method}, Tasks array: {len(params)} tasks"
                )
                result = await self.handle_task_create(params, request, request_id)
            else:
                # Normal case: params is a dict
                if not isinstance(params, dict):
                    params = {}  # Fallback to empty dict if params is not dict or list

                logger.info(
                    f"🔍 [handle_task_requests] [{request_id}] Method: {method}, Params: {params}"
                )

                # Route to specific handler based on method
                # Pass request object to handlers for access to user info and permission checking
                # Task CRUD operations
                if method == "tasks.create":
                    result = await self.handle_task_create(params, request, request_id)
                elif method == "tasks.get":
                    result = await self.handle_task_get(params, request, request_id)
                elif method == "tasks.update":
                    result = await self.handle_task_update(params, request, request_id)
                elif method == "tasks.delete":
                    result = await self.handle_task_delete(params, request, request_id)
                # Task query operations
                elif method == "tasks.detail":
                    result = await self.handle_task_detail(params, request, request_id)
                elif method == "tasks.tree":
                    result = await self.handle_task_tree(params, request, request_id)
                elif method == "tasks.list":
                    result = await self.handle_tasks_list(params, request, request_id)
                elif method == "tasks.children":
                    result = await self.handle_task_children(params, request, request_id)
                # Running task monitoring
                elif method == "tasks.running.list":
                    result = await self.handle_running_tasks_list(params, request, request_id)
                elif method == "tasks.running.status":
                    result = await self.handle_running_tasks_status(params, request, request_id)
                elif method == "tasks.running.count":
                    result = await self.handle_running_tasks_count(params, request, request_id)
                # Task cancellation
                elif method == "tasks.cancel" or method == "tasks.running.cancel":
                    result = await self.handle_task_cancel(params, request, request_id)
                # Task copy
                elif method == "tasks.copy":
                    result = await self.handle_task_copy(params, request, request_id)
                # Task generation
                elif method == "tasks.generate":
                    result = await self.handle_task_generate(params, request, request_id)
                # Task execution
                elif method == "tasks.execute":
                    # Use id from request body if available (JSON-RPC compliance), otherwise use generated request_id
                    jsonrpc_id = body.get("id") if body.get("id") is not None else request_id
                    response = await self.handle_task_execute(
                        params, request, request_id, jsonrpc_id
                    )
                    # If handle_task_execute returns StreamingResponse (SSE mode), return it directly
                    if isinstance(response, StreamingResponse):
                        return response
                    result = response
                else:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "error": {
                                "code": -32601,
                                "message": "Method not found",
                                "data": f"Unknown task method: {method}",
                            },
                        },
                    )

            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"🔍 [handle_task_requests] [{request_id}] Completed in {duration:.3f}s")

            return JSONResponse(content={"jsonrpc": "2.0", "id": body.get("id"), "result": result})

        except Exception as e:
            logger.error(f"Error handling task request: {str(e)}", exc_info=True)
            # Get request ID safely (body might not be defined if JSON parsing failed)
            request_id_from_body = None
            try:
                if "body" in locals() and body is not None:
                    request_id_from_body = body.get("id")
            except Exception as inner_e:
                logger.debug(f"Failed to extract request ID from body: {str(inner_e)}")
                pass

            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id_from_body,
                    "error": {"code": -32603, "message": "Internal error", "data": str(e)},
                },
            )

    async def handle_task_detail(
        self, params: dict, request: Request, request_id: str
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
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

                task = await task_repository.get_task_by_id(task_id)

                if not task:
                    return None

                # Check permission to access this task
                self._check_permission(request, task.user_id, "access")

                return task.to_dict()

        except Exception as e:
            logger.error(f"Error getting task detail: {str(e)}", exc_info=True)
            raise

    async def handle_task_tree(
        self, params: dict, request: Request, request_id: str
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
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

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
                return tree_node_to_dict(task_tree_node)

        except Exception as e:
            logger.error(f"Error getting task tree: {str(e)}", exc_info=True)
            raise

    async def handle_running_tasks_list(
        self, params: dict, request: Request, request_id: str
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
                # No user_id specified
                authenticated_user_id, _ = self._get_user_info(request)
                if authenticated_user_id:
                    if self._is_admin(request):
                        # Admin: allow querying all tasks
                        user_id = None
                    else:
                        # Regular user: only query their own tasks
                        user_id = authenticated_user_id
                # If no JWT and no user_id, user_id remains None (list all tasks, backward compatibility)

            # Get running tasks from memory using TaskExecutor
            from aipartnerupflow.core.execution.task_executor import TaskExecutor

            task_executor = TaskExecutor()
            running_task_ids = task_executor.get_all_running_tasks()

            if not running_task_ids:
                return []

            # Get database session and create repository to fetch task details
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

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

    async def handle_tasks_list(self, params: dict, request: Request, request_id: str) -> list:
        """
        Handle tasks list - returns list of all tasks from database (not just running ones)

        Params:
            user_id: Optional user ID filter (will be checked for permission)
            status: Optional status filter (e.g., "completed", "pending", "in_progress", "failed")
            root_only: Optional boolean (default: True) - if True, only return root tasks (parent_id is None)
            limit: Optional limit (default: 100)
            offset: Optional offset for pagination (default: 0)

        Returns:
            List of tasks
        """
        try:
            user_id = params.get("user_id")
            status = params.get("status")
            root_only = params.get("root_only", True)  # Default to True: only show root tasks
            limit = params.get("limit", 100)
            offset = params.get("offset", 0)

            # Check permission if user_id is specified
            if user_id:
                self._check_permission(request, user_id, "list tasks for")
            else:
                # No user_id specified
                authenticated_user_id, _ = self._get_user_info(request)
                if authenticated_user_id:
                    if self._is_admin(request):
                        # Admin: allow querying all tasks
                        user_id = None
                    else:
                        # Regular user: only query their own tasks
                        user_id = authenticated_user_id
                # If no JWT and no user_id, user_id remains None (list all tasks, backward compatibility)

            # Get database session and create repository
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

                # Query tasks with filters
                # If root_only is True, set parent_id to "" to filter for root tasks (parent_id is None)
                parent_id_filter = "" if root_only else None
                tasks = await task_repository.query_tasks(
                    user_id=user_id,
                    status=status,
                    parent_id=parent_id_filter,
                    limit=limit,
                    offset=offset,
                    order_by="created_at",
                    order_desc=True,
                )

                # Convert to dictionaries and check permissions
                # Also check if tasks have children for UI optimization
                task_dicts = []
                for task in tasks:
                    # Check permission to access this task
                    try:
                        if task.user_id:
                            self._check_permission(request, task.user_id, "access")

                        task_dict = task.to_dict()

                        # Check if task has children (if has_children field is not set or False, check database)
                        if not task_dict.get("has_children"):
                            # Quick check: query if there are any child tasks
                            children = await task_repository.get_child_tasks_by_parent_id(task.id)
                            task_dict["has_children"] = len(children) > 0

                        task_dicts.append(task_dict)
                    except ValueError:
                        # Permission denied, skip this task
                        logger.warning(f"Permission denied for task {task.id}")

                return task_dicts

        except Exception as e:
            logger.error(f"Error getting tasks list: {str(e)}", exc_info=True)
            raise

    async def handle_task_children(self, params: dict, request: Request, request_id: str) -> list:
        """
        Handle task children query - returns child tasks for a given parent task

        Params:
            parent_id: Parent task ID (required)
            task_id: Alternative parameter name for parent_id

        Returns:
            List of child tasks
        """
        try:
            parent_id = params.get("parent_id") or params.get("task_id")
            if not parent_id:
                raise ValueError(
                    "Parent task ID is required. Please provide 'parent_id' or 'task_id' parameter."
                )

            # Get database session and create repository
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

                # Get parent task to check permission
                parent_task = await task_repository.get_task_by_id(parent_id)
                if not parent_task:
                    raise ValueError(f"Parent task {parent_id} not found")

                # Check permission to access parent task
                if parent_task.user_id:
                    self._check_permission(request, parent_task.user_id, "access")

                # Get child tasks
                children = await task_repository.get_child_tasks_by_parent_id(parent_id)

                # Convert to dictionaries and check permissions
                child_dicts = []
                for child in children:
                    try:
                        if child.user_id:
                            self._check_permission(request, child.user_id, "access")
                        child_dicts.append(child.to_dict())
                    except ValueError:
                        # Permission denied, skip this child task
                        logger.warning(f"Permission denied for child task {child.id}")

                return child_dicts

        except Exception as e:
            logger.error(f"Error getting child tasks: {str(e)}", exc_info=True)
            raise

    async def handle_running_tasks_status(
        self, params: dict, request: Request, request_id: str
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
                task_ids = task_ids.split(",")

            if not task_ids:
                return []

            # Get TaskExecutor to check if tasks are running in memory
            from aipartnerupflow.core.execution.task_executor import TaskExecutor

            task_executor = TaskExecutor()

            # Get database session and create repository
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

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
                            statuses.append(
                                {
                                    "task_id": task.id,
                                    "context_id": task.id,  # For A2A Protocol compatibility
                                    "status": task.status,
                                    "progress": float(task.progress) if task.progress else 0.0,
                                    "error": task.error,
                                    "is_running": is_running,  # Add in-memory running status
                                    "started_at": (
                                        task.started_at.isoformat() if task.started_at else None
                                    ),
                                    "updated_at": (
                                        task.updated_at.isoformat() if task.updated_at else None
                                    ),
                                }
                            )
                        except ValueError as e:
                            # Permission denied, skip this task
                            logger.warning(f"Permission denied for task {task_id}: {e}")
                            statuses.append(
                                {
                                    "task_id": task_id,
                                    "context_id": task_id,
                                    "status": "permission_denied",
                                    "progress": 0.0,
                                    "error": str(e),
                                    "is_running": is_running,
                                    "started_at": None,
                                    "updated_at": None,
                                }
                            )
                    else:
                        # Task not found in database, but check if it's running in memory
                        if is_running:
                            statuses.append(
                                {
                                    "task_id": task_id,
                                    "context_id": task_id,
                                    "status": "in_progress",  # Running but not yet saved to DB
                                    "progress": 0.0,
                                    "error": None,
                                    "is_running": True,
                                    "started_at": None,
                                    "updated_at": None,
                                }
                            )
                        else:
                            statuses.append(
                                {
                                    "task_id": task_id,
                                    "context_id": task_id,
                                    "status": "not_found",
                                    "progress": 0.0,
                                    "error": None,
                                    "is_running": False,
                                    "started_at": None,
                                    "updated_at": None,
                                }
                            )

                return statuses

        except Exception as e:
            logger.error(f"Error getting running tasks status: {str(e)}", exc_info=True)
            raise

    async def handle_running_tasks_count(
        self, params: dict, request: Request, request_id: str
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

            # Check permission if user_id is specified
            if user_id:
                self._check_permission(request, user_id, "count tasks for")
            else:
                # No user_id specified
                authenticated_user_id, _ = self._get_user_info(request)
                if authenticated_user_id:
                    if self._is_admin(request):
                        # Admin: allow querying all tasks
                        user_id = None
                    else:
                        # Regular user: only query their own tasks
                        user_id = authenticated_user_id
                # If no JWT and no user_id, user_id remains None (count all tasks, backward compatibility)

            # Get running tasks count from memory using TaskExecutor
            from aipartnerupflow.core.execution.task_executor import TaskExecutor

            task_executor = TaskExecutor()

            if user_id:
                # Filter by user_id: get all running tasks and filter by user_id
                running_task_ids = task_executor.get_all_running_tasks()
                if not running_task_ids:
                    return {"count": 0, "user_id": user_id}

                # Get database session to check user_id
                async with create_pooled_session() as db_session:
                    task_repository = self._get_task_repository(db_session)

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

    async def handle_task_cancel(self, params: dict, request: Request, request_id: str) -> list:
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
                task_ids = task_ids.split(",")

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
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

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
                            logger.warning(
                                f"Task {task_id} not found in database, attempting cancellation anyway"
                            )

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
                        results.append(
                            {
                                "task_id": task_id,
                                "status": "failed",
                                "message": f"Permission denied: {str(e)}",
                                "error": "permission_denied",
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error cancelling task {task_id}: {str(e)}", exc_info=True)
                        results.append({"task_id": task_id, "status": "error", "error": str(e)})

                return results

        except Exception as e:
            logger.error(f"Error handling task cancellation: {str(e)}", exc_info=True)
            raise

    async def handle_task_create(
        self, params: dict | list, request: Request, request_id: str
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
                logger.info("Creating task tree from single task (converted to array)")
            elif isinstance(params, list):
                # Already an array
                tasks_array = params
                logger.info(f"Creating task tree from {len(tasks_array)} tasks")
            else:
                raise ValueError("Params must be a dict (single task) or list (tasks array)")

            if not tasks_array:
                raise ValueError("Tasks array cannot be empty")

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
                resolved_user_id = self._check_permission(
                    request, specified_user_id, "create tasks for"
                )
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
                # No user_id in tasks - automatically extract from request
                extracted_user_id = self._extract_user_id_from_request(request)
                if extracted_user_id:
                    resolved_user_id = extracted_user_id
                    # Set user_id for all tasks
                    for task_data in tasks_array:
                        if "user_id" not in task_data:
                            task_data["user_id"] = resolved_user_id
                else:
                    # No user_id found, allow None (no user restriction)
                    resolved_user_id = None

            # Get database session and create TaskCreator
            async with create_pooled_session() as db_session:
                task_creator = TaskCreator(db_session)

                # Create task tree from array
                task_tree = await task_creator.create_task_tree_from_array(
                    tasks=tasks_array,
                )

                # Convert task tree to dictionary format for response
                result = tree_node_to_dict(task_tree)

                logger.info(
                    f"Created task tree: root task {task_tree.task.name} "
                    f"with {len(task_tree.children)} direct children"
                )
                return result

        except Exception as e:
            logger.error(f"Error creating task: {str(e)}", exc_info=True)
            raise

    async def handle_task_get(
        self, params: dict, request: Request, request_id: str
    ) -> Optional[dict]:
        """Handle task retrieval by ID"""
        try:
            task_id = params.get("task_id") or params.get("id")
            if not task_id:
                raise ValueError("Task ID is required. Please provide 'task_id' or 'id' parameter.")

            # Get database session and create repository with custom TaskModel
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

                task = await task_repository.get_task_by_id(task_id)

                if not task:
                    return None

                # Check permission to access this task
                self._check_permission(request, task.user_id, "access")

                return task.to_dict()

        except Exception as e:
            logger.error(f"Error getting task: {str(e)}", exc_info=True)
            raise

    async def handle_task_update(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle task update with critical field validation

        Critical fields (parent_id, user_id, dependencies) are validated strictly.
        All other fields can be updated freely without status restrictions.
        """
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")

            # Get database session and create repository with custom TaskModel
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

                # Get task first
                task = await task_repository.get_task_by_id(task_id)
                if not task:
                    raise ValueError(f"Task {task_id} not found")

                # Check permission to update this task
                self._check_permission(request, task.user_id, "update")

                # Collect validation errors
                validation_errors = []

                # Validate critical fields and collect errors
                for field_name, field_value in params.items():
                    if field_name == "task_id":
                        continue  # Skip task_id, it's not a field to update

                    # Validate critical fields
                    error = await self._validate_critical_field(
                        task, field_name, field_value, task_repository
                    )
                    if error:
                        validation_errors.append(error)

                # If there are validation errors, raise exception with all errors
                if validation_errors:
                    error_message = "Update failed:\n" + "\n".join(
                        f"- {err}" for err in validation_errors
                    )
                    raise ValueError(error_message)

                # Apply updates for all fields

                # Update status and related fields if provided
                status = params.get("status")
                if status is not None:
                    await task_repository.update_task_status(
                        task_id=task_id,
                        status=status,
                        error=params.get("error"),
                        result=params.get("result"),
                        progress=params.get("progress"),
                        started_at=params.get("started_at"),
                        completed_at=params.get("completed_at"),
                    )
                else:
                    # Update individual status-related fields if status is not provided
                    if "error" in params:
                        await task_repository.update_task_status(
                            task_id=task_id, status=task.status, error=params.get("error")
                        )
                    if "result" in params:
                        await task_repository.update_task_status(
                            task_id=task_id, status=task.status, result=params.get("result")
                        )
                    if "progress" in params:
                        await task_repository.update_task_status(
                            task_id=task_id, status=task.status, progress=params.get("progress")
                        )
                    if "started_at" in params:
                        await task_repository.update_task_status(
                            task_id=task_id, status=task.status, started_at=params.get("started_at")
                        )
                    if "completed_at" in params:
                        await task_repository.update_task_status(
                            task_id=task_id, status=task.status, completed_at=params.get("completed_at")
                        )

                # Update other fields
                if "inputs" in params:
                    await task_repository.update_task_inputs(task_id, params["inputs"])

                if "dependencies" in params:
                    await task_repository.update_task_dependencies(task_id, params["dependencies"])

                if "name" in params:
                    await task_repository.update_task_name(task_id, params["name"])

                if "priority" in params:
                    await task_repository.update_task_priority(task_id, params["priority"])

                if "params" in params:
                    await task_repository.update_task_params(task_id, params["params"])

                if "schemas" in params:
                    await task_repository.update_task_schemas(task_id, params["schemas"])

                # Refresh task to get updated values
                updated_task = await task_repository.get_task_by_id(task_id)
                if not updated_task:
                    raise ValueError(f"Task {task_id} not found after update")

                logger.info(f"Updated task {task_id}")
                return updated_task.to_dict()

        except ValueError:
            # Re-raise ValueError (validation errors) as-is
            raise
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}", exc_info=True)
            raise

    async def _validate_critical_field(
        self, task: Any, field_name: str, field_value: Any, task_repository: TaskRepository
    ) -> Optional[str]:
        """
        Validate critical fields that can cause fatal errors.

        Args:
            task: TaskModel instance
            field_name: Name of the field being updated
            field_value: New value for the field
            task_repository: TaskRepository instance

        Returns:
            Error message string if validation fails, None if validation passes
        """
        # Critical field 1: parent_id - Always reject
        if field_name == "parent_id":
            return "Cannot update 'parent_id': field cannot be modified (task hierarchy is fixed)"

        # Critical field 2: user_id - Always reject
        if field_name == "user_id":
            return "Cannot update 'user_id': field cannot be modified (task ownership is fixed)"

        # Critical field 3: dependencies - Conditional validation
        if field_name == "dependencies":
            return await self._validate_dependency_update(task, field_value, task_repository)

        # All other fields - No validation needed
        return None

    async def _validate_dependency_update(
        self, task: Any, new_dependencies: Any, task_repository: TaskRepository
    ) -> Optional[str]:
        """
        Validate dependency update with critical checks.

        Args:
            task: TaskModel instance being updated
            new_dependencies: New dependencies list
            task_repository: TaskRepository instance

        Returns:
            Error message string if validation fails, None if validation passes
        """
        from aipartnerupflow.core.utils.dependency_validator import (
            validate_dependency_references,
            detect_circular_dependencies,
            check_dependent_tasks_executing,
        )

        # Check 1: Task must be in pending status
        if task.status != "pending":
            return (
                f"Cannot update 'dependencies': task status is '{task.status}' (must be 'pending')"
            )

        # Validate dependencies is a list
        if not isinstance(new_dependencies, list):
            return f"Cannot update 'dependencies': must be a list, got {type(new_dependencies).__name__}"

        try:
            # Check 2: Validate all dependency references exist in the same task tree
            await validate_dependency_references(task.id, new_dependencies, task_repository)

            # Check 3: Detect circular dependencies
            root_task = await task_repository.get_root_task(task)
            all_tasks_in_tree = await task_repository.get_all_tasks_in_tree(root_task)
            detect_circular_dependencies(task.id, new_dependencies, all_tasks_in_tree)

            # Check 4: Check if any dependent tasks are executing
            executing_dependents = await check_dependent_tasks_executing(task.id, task_repository)
            if executing_dependents:
                return (
                    f"Cannot update dependencies: task '{task.id}' has dependent tasks "
                    f"that are executing: {executing_dependents}"
                )

        except ValueError as e:
            # Return the validation error message
            return str(e)

        # All validations passed
        return None

    async def _get_all_children_recursive(
        self, task_repository: TaskRepository, task_id: str
    ) -> List[Any]:
        """
        Get all children tasks recursively

        Args:
            task_repository: TaskRepository instance
            task_id: Parent task ID

        Returns:
            List of all child tasks (including grandchildren, etc.)
        """
        return await task_repository.get_all_children_recursive(task_id)

    async def _find_dependent_tasks(
        self, task_repository: TaskRepository, task_id: str
    ) -> List[Any]:
        """
        Find all tasks that depend on the given task (reverse dependencies)

        Args:
            task_repository: TaskRepository instance
            task_id: Task ID to find dependents for

        Returns:
            List of tasks that depend on the given task
        """
        return await task_repository.find_dependent_tasks(task_id)

    def _check_all_tasks_pending(self, tasks: List[Any]) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Check if all tasks are pending

        Args:
            tasks: List of task objects

        Returns:
            Tuple of (all_pending: bool, non_pending_tasks: List[Dict[task_id, status]])
        """
        non_pending = []
        for task in tasks:
            if task.status != "pending":
                non_pending.append({"task_id": task.id, "status": task.status})

        return len(non_pending) == 0, non_pending

    async def handle_task_delete(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle task deletion with validation

        Deletion conditions:
        - If all tasks (task + all children) are pending: delete all physically
        - Otherwise: check for non-pending children and dependencies, return detailed error

        Returns detailed error messages if deletion is not allowed.
        """
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")

            # Get database session and create repository
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

                # Get task first to check if exists
                task = await task_repository.get_task_by_id(task_id)
                if not task:
                    raise ValueError(f"Task {task_id} not found")

                # Check permission to delete this task
                self._check_permission(request, task.user_id, "delete")

                # Get all children recursively
                all_children = await self._get_all_children_recursive(task_repository, task_id)

                # Collect all tasks to check (task itself + all children)
                all_tasks_to_check = [task] + all_children

                # Check if all tasks are pending
                all_pending, non_pending_tasks = self._check_all_tasks_pending(all_tasks_to_check)

                # Check for dependent tasks (always check, regardless of pending status)
                dependent_tasks = await self._find_dependent_tasks(task_repository, task_id)

                # Build error message if deletion is not allowed
                error_parts = []

                # Check for non-pending tasks
                if not all_pending:
                    # Filter out the main task from non_pending_tasks to get only children
                    non_pending_children = [t for t in non_pending_tasks if t["task_id"] != task_id]

                    if non_pending_children:
                        children_info = ", ".join(
                            [f"{t['task_id']}: {t['status']}" for t in non_pending_children]
                        )
                        error_parts.append(
                            f"task has {len(non_pending_children)} non-pending children: [{children_info}]"
                        )

                    # Also check if the main task itself is not pending
                    if any(t["task_id"] == task_id for t in non_pending_tasks):
                        main_task_status = next(
                            t["status"] for t in non_pending_tasks if t["task_id"] == task_id
                        )
                        error_parts.append(f"task status is '{main_task_status}' (must be 'pending')")

                # Check for dependent tasks
                if dependent_tasks:
                    dependent_task_ids = [t.id for t in dependent_tasks]
                    error_parts.append(
                        f"{len(dependent_tasks)} tasks depend on this task: [{', '.join(dependent_task_ids)}]"
                    )

                # If there are any errors, raise exception
                if error_parts:
                    error_message = "Cannot delete task: " + "; ".join(error_parts)
                    raise ValueError(error_message)

                # All conditions met: all tasks are pending and no dependencies
                # Delete all tasks (children first, then parent)
                deleted_count = 0
                for child in all_children:
                    success = await task_repository.delete_task(child.id)
                    if success:
                        deleted_count += 1

                # Delete the main task
                success = await task_repository.delete_task(task_id)
                if success:
                    deleted_count += 1

                logger.info(
                    f"Deleted task {task_id} and {len(all_children)} children "
                    f"({deleted_count} total tasks deleted)"
                )
                return {
                    "success": True,
                    "task_id": task_id,
                    "deleted_count": deleted_count,
                    "children_deleted": len(all_children),
                }

        except ValueError as e:
            # Re-raise ValueError with detailed error message
            logger.warning(f"Task deletion failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}", exc_info=True)
            raise

    async def handle_task_copy(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle task copy (create_task_copy)

        Params:
            task_id: Task ID to copy (required)
            children: If True, also copy each direct child task with its dependencies (default: False)
            copy_mode: Copy mode - "minimal" (default), "full", or "custom"
            custom_task_ids: List of task IDs to copy (required when copy_mode="custom")
            custom_include_children: If True, also include all children recursively (used when copy_mode="custom", default: False)
            reset_fields: Optional list of field names to reset (default: None)
            save: If True (default), save to database. If False, return task array without saving.
        """
        try:
            task_id = params.get("task_id")
            if not task_id:
                raise ValueError("Task ID is required")

            children = params.get("children", False)
            copy_mode = params.get("copy_mode", "minimal")
            custom_task_ids = params.get("custom_task_ids")
            custom_include_children = params.get("custom_include_children", False)
            reset_fields = params.get("reset_fields")
            save = params.get("save", True)

            # Validate parameters
            if copy_mode == "custom" and not custom_task_ids:
                raise ValueError("custom_task_ids is required when copy_mode='custom'")

            # Get database session and create repository with custom TaskModel
            async with create_pooled_session() as db_session:
                task_repository = self._get_task_repository(db_session)

                # Get original task
                original_task = await task_repository.get_task_by_id(task_id)
                if not original_task:
                    raise ValueError(f"Task {task_id} not found")

                # Check permission to copy this task
                self._check_permission(request, original_task.user_id, "copy")

                # Create TaskCreator and copy task
                task_creator = TaskCreator(db_session)

                result = await task_creator.create_task_copy(
                    original_task,
                    children=children,
                    copy_mode=copy_mode,
                    custom_task_ids=custom_task_ids,
                    custom_include_children=custom_include_children,
                    reset_fields=reset_fields,
                    save=save
                )

                # Handle result based on save parameter
                if save:
                    # Return TaskTreeNode as dict
                    response = tree_node_to_dict(result)
                    logger.info(
                        f"Copied task {task_id} to new task {result.task.id} (children={children})"
                    )
                else:
                    # Return task array directly
                    response = {"tasks": result, "saved": False}
                    logger.info(
                        f"Generated task copy preview for {task_id}: {len(result)} tasks (not saved)"
                    )
                
                return response

        except Exception as e:
            logger.error(f"Error copying task: {str(e)}", exc_info=True)
            raise

    async def handle_task_generate(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle task tree generation from natural language requirement

        Uses generate_executor to create a valid task tree structure from natural language.

        Params:
            requirement: Natural language requirement for the task tree (required)
            user_id: Optional user ID for the generated tasks (default: authenticated user or None)
            llm_provider: Optional LLM provider ("openai" or "anthropic", default: from env or "openai")
            model: Optional LLM model name (default: from env or provider default)
            temperature: Optional LLM temperature (default: 0.7)
            max_tokens: Optional maximum tokens for LLM response (default: 4000)
            save: Optional boolean, if True, save generated tasks to database (default: False)

        Returns:
            {
                "tasks": List[Dict],  # Generated task tree JSON array
                "count": int,  # Number of generated tasks
                "root_task_id": str,  # Only present if save=True
                "message": str  # Status message
            }
        """
        try:
            import os

            # Import GenerateExecutor to ensure it's registered
            from aipartnerupflow.extensions.generate import GenerateExecutor  # noqa: F401
            from aipartnerupflow.core.execution.task_executor import TaskExecutor
            from aipartnerupflow.core.types import TaskTreeNode
            from aipartnerupflow.core.config import get_task_model_class

            requirement = params.get("requirement")
            if not requirement:
                raise ValueError("Requirement is required")

            # Get user_id - automatically extract from request if not provided
            user_id = params.get("user_id")
            if not user_id:
                # Automatically extract user_id from request (JWT or header)
                user_id = self._extract_user_id_from_request(request)
                if user_id:
                    logger.debug(f"Extracted user_id '{user_id}' from request (JWT token)")
                else:
                    logger.debug("No user_id found in request (no JWT token or verify_token_func not available)")

            if user_id:
                # Check permission for specified user_id
                resolved_user_id = self._check_permission(request, user_id, "generate tasks for")
                if resolved_user_id:
                    user_id = resolved_user_id
            # Note: Keep user_id as None if not found - don't use "api_user" default
            # This ensures generated tasks use the actual user_id from BaseTask context

            # Check if LLM API key is available
            # Priority: context (from X-LLM-API-KEY header) > environment variables
            from aipartnerupflow.core.utils.llm_key_context import get_llm_key_from_header
            
            api_key = get_llm_key_from_header()
            if not api_key:
                # Fall back to environment variables
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            
            if not api_key:
                raise ValueError(
                    "LLM API key not found. Please provide X-LLM-API-KEY header, or set "
                    "OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable or in a .env file."
                )

            # Get LLM configuration
            llm_provider = params.get("llm_provider")
            model = params.get("model")
            temperature = params.get("temperature")
            max_tokens = params.get("max_tokens")

            # Get database session and create repository
            async with create_pooled_session() as db_session:
                task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())

                # Create generate task
                # Use user_id from request (or None) - don't default to "api_user"
                # This ensures generated tasks inherit the correct user_id from BaseTask context
                generate_task = await task_repository.create_task(
                    name="generate_executor",
                    user_id=user_id,  # Use actual user_id or None (not "api_user")
                    inputs={
                        "requirement": requirement,
                        "user_id": user_id,  # Pass user_id to executor inputs
                        "llm_provider": llm_provider,
                        "model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    schemas={
                        "method": "generate_executor"
                    },  # Required for TaskManager to find executor
                )

                # Execute generate_executor
                task_tree = TaskTreeNode(generate_task)
                task_executor = TaskExecutor()
                await task_executor.execute_task_tree(
                    task_tree=task_tree,
                    root_task_id=generate_task.id,
                    use_streaming=False,
                    use_demo=False,
                    db_session=db_session,
                )

                # Get result
                result_task = await task_repository.get_task_by_id(generate_task.id)

                if result_task.status == "failed":
                    error_msg = result_task.error or "Unknown error"
                    raise ValueError(f"Task generation failed: {error_msg}")

                if result_task.status != "completed":
                    raise ValueError(f"Task generation incomplete. Status: {result_task.status}")

                # Extract generated tasks
                result_data = result_task.result or {}
                generated_tasks = result_data.get("tasks", [])

                if not generated_tasks:
                    raise ValueError("No tasks were generated")

                # Build response
                response = {
                    "tasks": generated_tasks,
                    "count": len(generated_tasks),
                    "message": f"Successfully generated {len(generated_tasks)} task(s)",
                }

                # Optionally save to database
                save = params.get("save", False)
                if save:
                    task_creator = TaskCreator(db_session)
                    final_task_tree = await task_creator.create_task_tree_from_array(generated_tasks)
                    response["root_task_id"] = final_task_tree.task.id
                    response[
                        "message"
                    ] += f" and saved to database (root_task_id: {final_task_tree.task.id})"

            logger.info(
                f"Generated {len(generated_tasks)} task(s) from requirement: {requirement[:100]}..."
            )
            return response

        except ImportError as e:
            error_msg = str(e)
            if "openai" in error_msg.lower() or "anthropic" in error_msg.lower():
                raise ValueError(
                    "LLM package not installed. Please install required package:\n"
                    "  pip install openai\n"
                    "  # or\n"
                    "  pip install anthropic"
                )
            raise ValueError(f"Import error: {error_msg}")
        except ValueError:
            # Re-raise ValueError as-is (validation errors)
            raise
        except Exception as e:
            logger.error(f"Error generating task tree: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to generate task tree: {str(e)}")


    async def _run_background_execution(
        self,
        task_executor: Any,
        execution_mode: str,
        streaming_context: Any,
        session_factory: Any,
        task_id: Optional[str] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
        copy_execution: bool = False,
        copy_children: bool = False,
        use_streaming: bool = False,
        use_demo: bool = False,
        original_task_id: Optional[str] = None,
    ):
        """
        Run task execution in background with its own session
        """
        try:
            async with session_factory() as db_session:
                if execution_mode == "task_id":
                    # Mode 1: Execute by task_id
                    if copy_execution and original_task_id:
                        # We need to copy the task first using the new session
                        # Note: The task_id passed here is the original one
                        # But wait, the logic in handle_task_execute did the copy BEFORE execution
                        # If we move it here, we need to handle it here.
                        # However, handle_task_execute already did the copy if it was synchronous.
                        # Let's assume the task_id passed here is the one to execute (already copied if needed)
                        pass

                    await task_executor.execute_task_by_id(
                        task_id=task_id,
                        use_streaming=bool(streaming_context),
                        streaming_callbacks_context=streaming_context,
                        use_demo=use_demo,
                        db_session=db_session,
                    )
                elif execution_mode == "tasks_array":
                    # Mode 2: Execute by tasks array
                    await task_executor.execute_tasks(
                        tasks=tasks,
                        root_task_id=None,
                        use_streaming=bool(streaming_context),
                        streaming_callbacks_context=streaming_context,
                        require_existing_tasks=None,
                        use_demo=use_demo,
                        db_session=db_session,
                    )
        except Exception as e:
            logger.error(f"Error in background execution: {str(e)}", exc_info=True)
            if streaming_context:
                # Try to report error to streaming context
                try:
                    await streaming_context.put(
                        {"type": "error", "error": str(e), "final": True}
                    )
                except Exception:
                    pass
        finally:
            if streaming_context:
                # Ensure we close the streaming context if it wasn't closed by the executor
                # (Executor doesn't close it, the SSE generator closes it, but if we are just pushing to it...)
                # Wait, the SSE generator closes it when the loop ends.
                # The loop ends when it sees a final event or timeout.
                # If we crash here, we should send a final event or error.
                pass

    async def handle_task_execute(
        self, params: dict, request: Request, request_id: str, jsonrpc_id: Any = None
    ) -> Union[dict, StreamingResponse]:
        """
        Handle task execution - supports both task_id and tasks array

        Design:
        - Supports two execution modes:
          1. Execute by task_id: Uses TaskExecutor.execute_task_by_id()
          2. Execute by tasks array: Uses TaskExecutor.execute_tasks()
        - Users can choose one of two response modes: regular POST or SSE
        - Users can optionally request webhook URL callbacks (independent of response mode)

        Response Modes:
        1. Regular POST (use_streaming=False): Returns JSON response immediately, task executes in background
        2. SSE (use_streaming=True): Returns StreamingResponse with Server-Sent Events for real-time updates

        Webhook Callbacks:
        - Can be used with either response mode
        - If provided, progress updates will be sent to the webhook URL via HTTP POST/PUT
        - Webhook callbacks are independent of the response mode choice

        Params:
            task_id: Optional, Task ID to execute (if provided, uses execute_task_by_id)
            tasks: Optional, Array of task dictionaries to execute (if provided, uses execute_tasks)
            use_streaming: Optional, if True, use SSE mode (default: False, regular POST mode)
            use_demo: Optional, if True, use demo mode (returns demo data instead of executing) (default: False)
            copy_execution: Optional, if True, copy the task before execution to preserve original task history (default: False)
                          Only applies to task_id mode. When True, creates a copy of the task tree and executes the copy.
            copy_children: Optional, if True and copy_execution=True, also copy each direct child task with its dependencies (default: False)
                          This parameter is only used when copy_execution=True.
            webhook_config: Optional webhook configuration for push notifications (independent of use_streaming):
                {
                    "url": str,  # Required: Webhook callback URL
                    "headers": dict,  # Optional: HTTP headers
                    "method": str,  # Optional: HTTP method (default: "POST")
                    "timeout": float,  # Optional: Request timeout in seconds (default: 30.0)
                    "max_retries": int  # Optional: Maximum retry attempts (default: 3)
                }

        Returns:
            Regular POST mode (use_streaming=False):
            {
                "success": True,
                "protocol": "jsonrpc",
                "root_task_id": str,
                "task_id": str,
                "status": "started",
                "message": str,
                "streaming": bool,  # True if webhook_config is provided
                "webhook_url": str  # Only present if webhook_config is provided
            }

            SSE mode (use_streaming=True):
            StreamingResponse with text/event-stream media type
            - Initial event contains JSON-RPC response with task info
            - Subsequent events contain real-time progress updates
            - Final event indicates completion
        Handle task execution request
        
        Supports two modes:
        1. Execute by task_id: {"task_id": "..."}
        2. Execute by tasks array: {"tasks": [...]}
        
        Supports streaming (SSE) and webhook callbacks.
        """
        try:
            # Parse parameters
            if isinstance(params, list):
                # Direct list of tasks
                execution_mode = "tasks_array"
                tasks = params
                task_id = None
            else:
                # Dict with options
                task_id = params.get("task_id")
                tasks = params.get("tasks")
                
                if task_id:
                    execution_mode = "task_id"
                elif tasks:
                    execution_mode = "tasks_array"
                else:
                    raise ValueError("Either task_id or tasks array is required")

            # Common options
            use_streaming = params.get("use_streaming", False)
            webhook_config = params.get("webhook_config", None)
            copy_execution = params.get("copy_execution", False)
            copy_children = params.get("copy_children", False)
            use_demo = params.get("use_demo", False)

            # Get TaskExecutor
            from aipartnerupflow.core.execution.task_executor import TaskExecutor
            task_executor = TaskExecutor()

            # Execution setup variables
            execution_task_id = None
            execution_tasks = None
            root_task_id = None
            original_task_id = None
            
            # Preparation phase (Foreground)
            async with create_pooled_session() as db_session:
                if execution_mode == "task_id":
                    # Mode 1: Execute by task_id
                    task_repository = self._get_task_repository(db_session)
                    task = await task_repository.get_task_by_id(task_id)
                    if not task:
                        raise ValueError(f"Task {task_id} not found")

                    # Check permission
                    self._check_permission(request, task.user_id, "execute")

                    # If copy_execution is True, create a copy first
                    original_task_id = task_id
                    if copy_execution:
                        logger.info(
                            f"Copying task {task_id} before execution (copy_children={copy_children})"
                        )
                        task_creator = TaskCreator(db_session)
                        copied_tree = await task_creator.create_task_copy(task, children=copy_children)
                        execution_task_id = copied_tree.task.id
                        logger.info(f"Task copied: original={original_task_id}, copy={execution_task_id}")
                        
                        # Use the new task for subsequent steps
                        task = copied_tree.task
                    else:
                        execution_task_id = task_id

                    # Check if task is already running
                    from aipartnerupflow.core.execution.task_tracker import TaskTracker
                    task_tracker = TaskTracker()
                    if task_tracker.is_task_running(execution_task_id):
                        return {
                            "success": False,
                            "protocol": "jsonrpc",
                            "root_task_id": execution_task_id,
                            "status": "already_running",
                            "message": f"Task {execution_task_id} is already running",
                            **({"original_task_id": original_task_id} if copy_execution else {}),
                        }

                    # Get root task ID for streaming context
                    root_task = await task_repository.get_root_task(task)
                    root_task_id = root_task.id

                elif execution_mode == "tasks_array":
                    # Mode 2: Execute by tasks array
                    execution_tasks = tasks
                    
                    # Check permission for first task if available
                    if tasks and len(tasks) > 0:
                        first_task = tasks[0]
                        user_id = first_task.get("user_id")
                        if user_id:
                            self._check_permission(request, user_id, "execute")
                    
                    # For tasks array, we don't have a root_task_id yet
                    # Use a temporary ID for streaming context initialization
                    root_task_id = str(uuid.uuid4())

            # Determine streaming context
            streaming_context = None
            if use_streaming and webhook_config:
                streaming_context = CombinedStreamingContext(root_task_id, webhook_config)
            elif use_streaming:
                streaming_context = TaskStreamingContext(root_task_id)
            elif webhook_config:
                streaming_context = WebhookStreamingContext(root_task_id, webhook_config)

            # Execution phase
            if use_streaming or webhook_config:
                # Background execution
                asyncio.create_task(self._run_background_execution(
                    task_executor=task_executor,
                    execution_mode=execution_mode,
                    streaming_context=streaming_context,
                    session_factory=create_pooled_session,
                    task_id=execution_task_id,
                    tasks=execution_tasks,
                    use_demo=use_demo
                ))
            else:
                # Foreground execution (awaiting background wrapper)
                # Note: We pass None as streaming_context here as we are not streaming
                execution_result = await self._run_background_execution(
                    task_executor=task_executor,
                    execution_mode=execution_mode,
                    streaming_context=None,
                    session_factory=create_pooled_session,
                    task_id=execution_task_id,
                    tasks=execution_tasks,
                    use_demo=use_demo
                )
                
                # Update root_task_id from result if available (especially for tasks_array mode)
                if execution_result and "root_task_id" in execution_result:
                    root_task_id = execution_result["root_task_id"]

            # Handle response based on use_streaming (response mode)
            if use_streaming:
                # SSE mode: return StreamingResponse
                if not streaming_context:
                    raise ValueError("streaming_context is required for SSE mode")

                async def sse_event_generator():
                    """Generate SSE events from task execution"""
                    try:
                        # Send initial response as JSON-RPC result
                        response_data = {
                            "success": True,
                            "protocol": "jsonrpc",
                            "root_task_id": root_task_id,
                            "task_id": execution_task_id or root_task_id,
                            "status": "started",
                            "streaming": True,
                            "message": "Task execution started with streaming",
                            **(
                                {"webhook_url": webhook_config.get("url")} if webhook_config else {}
                            ),
                        }
                        # Add original_task_id if copy_execution was used
                        if execution_mode == "task_id" and copy_execution:
                            response_data["original_task_id"] = original_task_id

                        initial_response = {
                            "jsonrpc": "2.0",
                            "id": jsonrpc_id if jsonrpc_id is not None else request_id,
                            "result": response_data,
                        }
                        yield f"data: {json.dumps(initial_response, ensure_ascii=False)}\n\n"

                        # Poll for events and stream them
                        last_event_count = 0
                        max_wait_time = 300  # Maximum wait time in seconds (5 minutes)
                        wait_time = 0
                        check_interval = 0.3  # Check for new events every 0.3 seconds

                        while wait_time < max_wait_time:
                            # Get all events for this task
                            events = await get_task_streaming_events(root_task_id)

                            # Send any new events
                            if len(events) > last_event_count:
                                for i in range(last_event_count, len(events)):
                                    event = events[i]
                                    # Format as SSE: data: {json}\n\n
                                    event_data = json.dumps(event, ensure_ascii=False)
                                    yield f"data: {event_data}\n\n"

                                last_event_count = len(events)

                                # Check if final event (task completed or failed)
                                if events and events[-1].get("final", False):
                                    # Send final event and close connection
                                    yield f"data: {json.dumps({'type': 'stream_end', 'task_id': root_task_id}, ensure_ascii=False)}\n\n"
                                    break

                            # Wait before checking again
                            await asyncio.sleep(check_interval)
                            wait_time += check_interval

                            # Send keepalive comment every 30 seconds
                            if int(wait_time) % 30 == 0:
                                yield ": keepalive\n\n"

                        # If we've exceeded max wait time, send timeout event
                        if wait_time >= max_wait_time:
                            yield f"data: {json.dumps({'type': 'timeout', 'task_id': root_task_id, 'message': 'Stream timeout'}, ensure_ascii=False)}\n\n"

                        # Clean up
                        await streaming_context.close()

                    except asyncio.CancelledError:
                        # Client disconnected
                        logger.debug(f"SSE connection closed for task {root_task_id}")
                        await streaming_context.close()
                        raise
                    except Exception as e:
                        logger.error(
                            f"Error in SSE stream for task {root_task_id}: {str(e)}", exc_info=True
                        )
                        error_data = json.dumps(
                            {"type": "error", "task_id": root_task_id, "error": str(e)},
                            ensure_ascii=False,
                        )
                        yield f"data: {error_data}\n\n"
                        await streaming_context.close()

                return StreamingResponse(
                    sse_event_generator(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",  # Disable buffering in nginx
                    },
                )

            elif streaming_context:
                # Response mode 2: Regular POST with webhook callbacks
                logger.info(f"Task execution started with webhook callbacks (root: {root_task_id})")

                response = {
                    "success": True,
                    "protocol": "jsonrpc",
                    "root_task_id": root_task_id,
                    "task_id": execution_task_id or root_task_id,
                    "status": "started",
                    "streaming": True,  # Indicates webhook callbacks are active
                    "message": (
                        f"Task execution started with webhook callbacks. "
                        f"Updates will be sent to {webhook_config.get('url')}"
                    ),
                    "webhook_url": webhook_config.get("url"),
                }
                if execution_mode == "task_id" and copy_execution:
                    response["original_task_id"] = original_task_id
                return response

            else:
                # Response mode 3: Regular POST without webhook
                logger.info(f"Task execution started (root: {root_task_id})")
                
                # Use execution_result if available (it should be for foreground execution)
                status = "started"
                if 'execution_result' in locals() and execution_result:
                    status = execution_result.get("status", "started")

                response = {
                    "success": True,
                    "protocol": "jsonrpc",
                    "root_task_id": root_task_id,
                    "task_id": execution_task_id or root_task_id,
                    "status": status,
                    "message": "Task execution started",
                }
                if execution_mode == "task_id" and copy_execution:
                    response["original_task_id"] = original_task_id
                return response

        except Exception as e:
            logger.error(f"Error executing task: {str(e)}", exc_info=True)
            raise
