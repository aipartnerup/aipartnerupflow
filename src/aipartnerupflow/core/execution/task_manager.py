"""
Task management service for orchestrating and executing tasks
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
import asyncio
from decimal import Decimal
from inspect import iscoroutinefunction
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.execution.streaming_callbacks import StreamingCallbacks
from aipartnerupflow.core.extensions import get_registry, ExtensionCategory
from aipartnerupflow.core.types import (
    TaskTreeNode,
    TaskPreHook,
    TaskPostHook,
)
from aipartnerupflow.core.config import get_pre_hooks, get_post_hooks, get_task_model_class, get_task_tree_hooks
from aipartnerupflow.core.execution.dependency_resolver import (
    are_dependencies_satisfied,
    resolve_task_dependencies,
    get_completed_tasks_by_id,
)
from aipartnerupflow.core.execution.errors import BusinessError
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TaskManager:
    """
    Unified task management service - handles orchestration, distribution, and execution
    
    Task Re-execution Support:
    --------------------------
    TaskManager supports re-executing failed tasks and their dependencies. When a task tree
    is executed, the following re-execution logic applies:
    
    1. **Task Status Handling**:
       - `pending` tasks: Execute normally (not marked for re-execution)
       - `failed` tasks: Always re-executed
       - `completed` tasks: Only re-executed if marked for re-execution (when dependencies need re-execution)
       - `in_progress` tasks: Skipped unless marked for re-execution
    
    2. **Re-execution Marking**:
       - Failed tasks are automatically marked for re-execution
       - Completed tasks are marked for re-execution when their dependent tasks need re-execution
       - This ensures that when a task fails, all tasks that depend on it (directly or transitively)
         will also be re-executed to maintain consistency
    
    3. **Dependency Resolution**:
       - Dependencies are satisfied if the dependency task is `completed`, even if marked for re-execution
       - This allows dependent tasks to use results from completed dependencies while still allowing
         re-execution of the dependency if needed
    
    4. **Use Cases**:
       - Re-executing a failed task: The task and all its dependencies will be re-executed
       - Re-executing a completed task: The task and all dependent tasks will be re-executed
       - Partial re-execution: Only failed tasks and their dependencies are re-executed
    
    Example:
        # Re-execute a failed task
        task_manager = TaskManager(db)
        task_manager._tasks_to_reexecute = {failed_task_id}  # Set by TaskExecutor
        await task_manager.distribute_task_tree(task_tree)
    """
    
    def __init__(
        self,
        db: Union[Session, AsyncSession],
        root_task_id: Optional[str] = None,
        pre_hooks: Optional[List[TaskPreHook]] = None,
        post_hooks: Optional[List[TaskPostHook]] = None,
        executor_instances: Optional[Dict[str, Any]] = None,
        use_demo: bool = False
    ):
        """
        Initialize TaskManager
        
        Args:
            db: Database session (sync or async)
            root_task_id: Optional root task ID for streaming
            pre_hooks: Optional list of pre-execution hook functions
                Each hook receives (task: TaskModel)
                Hooks can access and modify task.inputs directly
                Hooks can be sync or async functions
                Example:
                    async def my_pre_hook(task):
                        # Custom validation or transformation
                        if task.inputs and task.inputs.get("url"):
                            task.inputs["url"] = task.inputs["url"].strip()
                    task_manager = TaskManager(db, pre_hooks=[my_pre_hook])
            post_hooks: Optional list of post-execution hook functions
                Each hook receives (task: TaskModel, inputs: Dict[str, Any], result: Any)
                Hooks can be sync or async functions
                Example:
                    async def my_post_hook(task, inputs, result):
                        # Custom result processing or logging
                        logger.info(f"Task {task.id} completed with result: {result}")
                    task_manager = TaskManager(db, post_hooks=[my_post_hook])
            executor_instances: Optional shared dictionary for storing executor instances (task_id -> executor)
                Used for cancellation support. If provided, executors created during execution are stored here
                so that cancel_task() can access them. Typically passed from TaskExecutor.
            use_demo: If True, executors return demo data instead of executing (default: False)
                This is an execution option, not a task input. It's passed as a parameter to TaskManager
                and used by TaskManager._execute_task_with_schemas() to determine whether to return demo data.
        """
        self.db = db
        self.is_async = isinstance(db, AsyncSession)
        self.root_task_id = root_task_id
        # Get task_model_class from config registry (supports custom TaskModel via decorators)
        task_model_class = get_task_model_class() or TaskModel
        self.task_repository = TaskRepository(db, task_model_class=task_model_class)
        self.streaming_callbacks = StreamingCallbacks(root_task_id=self.root_task_id)
        self.stream = False
        self.streaming_final = False
        # Use provided hooks or fall back to config registry
        # This allows hooks to be registered globally via decorators
        self.pre_hooks = pre_hooks if pre_hooks is not None else get_pre_hooks()
        self.post_hooks = post_hooks if post_hooks is not None else get_post_hooks()
        # Store executor instances for cancellation (task_id -> executor)
        # Use shared executor_instances dict from TaskExecutor if provided, otherwise create new one
        # This allows cancel_task() to access executors created during execution
        self._executor_instances: Dict[str, Any] = executor_instances if executor_instances is not None else {}
        # Track tasks that should be re-executed (even if they are completed or failed)
        # This allows re-executing failed tasks and ensures dependencies are also re-executed
        self._tasks_to_reexecute: set[str] = set()
        # Demo mode flag - if True, executors return demo data instead of executing
        self.use_demo = use_demo
    
    async def cancel_task(
        self,
        task_id: str,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel a task execution (called by external sources like CLI/API)
        
        This method:
        1. Checks if task is running
        2. If executor supports cancellation, calls executor.cancel() to get cancellation result
        3. Updates database with cancelled status and token_usage from cancellation result
        
        Args:
            task_id: Task ID to cancel
            error_message: Optional error message for cancellation
            
        Returns:
            Dictionary with cancellation result:
            {
                "status": "cancelled" | "failed",
                "message": str,
                "token_usage": Dict,  # Optional token usage from executor
            }
        """
        try:
            # Get task from database
            task = await self.task_repository.get_task_by_id(task_id)
            if not task:
                return {
                    "status": "failed",
                    "message": f"Task {task_id} not found",
                    "error": "Task not found"
                }
            
            # Check if task can be cancelled
            if task.status in ["completed", "failed", "cancelled"]:
                return {
                    "status": "failed",
                    "message": f"Task {task_id} is already {task.status}, cannot cancel",
                    "current_status": task.status
                }
            
            logger.info(f"Cancelling task {task_id} (current status: {task.status})")
            
            # If task is in_progress and executor supports cancellation, call executor.cancel()
            cancel_result = None
            token_usage = None
            result_data = None
            executor_cancelled = False  # Track if executor.cancel() was actually called
            
            if task.status == "in_progress":
                executor = self._executor_instances.get(task_id)
                if executor and hasattr(executor, 'cancel'):
                    try:
                        logger.info(f"Calling executor.cancel() for task {task_id}")
                        cancel_result = await executor.cancel()
                        executor_cancelled = True
                        logger.info(f"Executor {executor.__class__.__name__} cancel() returned: {cancel_result}")
                        
                        if cancel_result and cancel_result.get("status") == "cancelled":
                            token_usage = cancel_result.get("token_usage")
                            # Use result if available, otherwise use partial_result
                            result_data = cancel_result.get("result") or cancel_result.get("partial_result")
                    except Exception as e:
                        logger.warning(f"Failed to call executor.cancel() for task {task_id}: {str(e)}")
                        cancel_result = {
                            "status": "failed",
                            "message": f"Failed to cancel executor: {str(e)}",
                            "error": str(e)
                        }
            
            # Update database with cancelled status
            error_msg = error_message or (cancel_result.get("message") if cancel_result else "Cancelled by user")
            
            # Prepare update data - merge all fields in one update
            update_data = {
                "status": "cancelled",
                "error": error_msg,
                "completed_at": datetime.now(timezone.utc)
            }
            
            # If we have result data (from executor.cancel()), save it
            if result_data:
                update_data["result"] = result_data
            
            # If token_usage is available, merge it into result
            # If result_data exists, merge token_usage into it; otherwise create new dict
            if token_usage:
                if result_data and isinstance(result_data, dict):
                    # Merge token_usage into existing result
                    result_with_token = result_data.copy()
                    result_with_token["token_usage"] = token_usage
                    update_data["result"] = result_with_token
                else:
                    # Create new result dict with token_usage
                    update_data["result"] = {"token_usage": token_usage}
            
            # Update task status in one call (combines status, error, result, token_usage)
            await self.task_repository.update_task_status(
                task_id=task_id,
                **update_data
            )
            
            # Clear executor reference
            # Clear executor reference and task context to prevent memory leaks
            executor = self._executor_instances.pop(task_id, None)
            if executor and hasattr(executor, 'clear_task_context'):
                executor.clear_task_context()
                logger.debug(f"Cleared task context for task {task_id} during cancellation")
            
            # Build return result
            result = {
                "status": "cancelled",
                "message": error_msg,
            }
            
            if token_usage:
                result["token_usage"] = token_usage
            
            if result_data:
                result["result"] = result_data
            
            logger.info(f"Task {task_id} cancelled successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}", exc_info=True)
            return {
                "status": "failed",
                "message": f"Failed to cancel task {task_id}",
                "error": str(e)
            }

    
    async def distribute_task_tree(
        self,
        task_tree: TaskTreeNode,
        use_callback: bool = True
    ) -> TaskTreeNode:
        """
        Distribute task tree directly with proper multi-level priority execution
        
        Args:
            task_tree: Root task tree node
            use_callback: Whether to use callbacks
            
        Returns:
            Task tree node with execution results
        """
        logger.info(f"Distributing task tree with root task: {task_tree.task.id}")
        
        root_task = task_tree.task
        
        # Call on_tree_created hook
        await self._call_task_tree_hooks("on_tree_created", root_task, task_tree)
        
        # Call on_tree_started hook
        await self._call_task_tree_hooks("on_tree_started", root_task)
        
        try:
            # Execute task tree
            await self._execute_task_tree_recursive(task_tree, use_callback)
            
            # Check final status
            final_status = task_tree.calculate_status()
            
            # Call on_tree_completed hook
            if final_status == "completed":
                await self._call_task_tree_hooks("on_tree_completed", root_task, "completed")
            else:
                # Tree finished but not all tasks completed (some failed)
                await self._call_task_tree_hooks("on_tree_failed", root_task, f"Tree finished with status: {final_status}")
            
            return task_tree
        except Exception as e:
            # Call on_tree_failed hook
            await self._call_task_tree_hooks("on_tree_failed", root_task, str(e))
            raise
    
    async def distribute_task_tree_with_streaming(
        self,
        task_tree: TaskTreeNode,
        use_callback: bool = True
    ) -> None:
        """
        Distribute task tree with real-time streaming for progress updates
        
        Args:
            task_tree: Root task tree node
            use_callback: Whether to use callbacks
        """
        logger.info(f"Distributing task tree with streaming, root task: {task_tree.task.id}")
        
        # Enable streaming mode and set root task ID
        self.stream = True
        self.streaming_final = False
        self.root_task_id = task_tree.task.id
        
        root_task = task_tree.task
        
        # Call on_tree_created hook
        await self._call_task_tree_hooks("on_tree_created", root_task, task_tree)
        
        # Call on_tree_started hook
        await self._call_task_tree_hooks("on_tree_started", root_task)
        
        try:
            # Send initial status
            self.streaming_callbacks.progress(task_tree.task.id, 0.0, "Task tree execution started")
            
            # Save task IDs before execution to avoid accessing them after session rollback
            root_task_id = root_task.id
            task_tree_root_id = task_tree.task.id
            
            # Execute task tree with progress streaming
            await self._execute_task_tree_recursive(task_tree, use_callback)
            
            # Check final status
            final_progress = task_tree.calculate_progress()
            final_status = task_tree.calculate_status()
            
            # Ensure progress is a float
            if isinstance(final_progress, Decimal):
                final_progress = float(final_progress)
            
            # Send final status if all tasks are completed
            if final_status == "completed":
                self.streaming_callbacks.final(
                    task_tree_root_id,
                    final_status,
                    result={"progress": final_progress}
                )
                # Call on_tree_completed hook
                await self._call_task_tree_hooks("on_tree_completed", root_task, "completed")
            else:
                # Send progress update
                self.streaming_callbacks.progress(
                    task_tree_root_id,
                    final_progress,
                    f"Task tree execution {final_status}"
                )
                # Call on_tree_failed hook
                await self._call_task_tree_hooks("on_tree_failed", root_task, f"Tree finished with status: {final_status}")
                
        except Exception as e:
            logger.error(f"Error in distribute_task_tree_with_streaming: {str(e)}")
            # Use saved task ID to avoid accessing task after session rollback
            try:
                task_tree_root_id = task_tree.task.id if task_tree and task_tree.task else root_task_id
            except Exception:
                task_tree_root_id = root_task_id
            self.streaming_callbacks.task_failed(task_tree_root_id, str(e))
            # Call on_tree_failed hook
            await self._call_task_tree_hooks("on_tree_failed", root_task, str(e))
            raise
    
    async def _execute_task_tree_recursive(
        self,
        node: TaskTreeNode,
        use_callback: bool = True
    ) -> None:
        """
        Execute task tree recursively with proper dependency checking
        
        This method implements the re-execution logic:
        - Failed tasks are always re-executed
        - Completed tasks are re-executed if marked in `_tasks_to_reexecute`
        - Pending tasks execute normally
        - In-progress tasks are skipped unless marked for re-execution
        
        Args:
            node: Task tree node to execute
            use_callback: Whether to use callbacks
        """
        # Save task ID at the beginning to avoid accessing it after session rollback
        # Use SQLAlchemy inspect to safely get ID without triggering lazy loading
        from sqlalchemy import inspect as sa_inspect
        node_task_id_for_error_handling = None
        if node and node.task:
            try:
                # Try to get ID directly from the object's dict to avoid triggering SQLAlchemy lazy loading
                node_task_id_for_error_handling = node.task.__dict__.get('id') if hasattr(node.task, '__dict__') else None
                # If not in __dict__, try using inspect to get the identity
                if node_task_id_for_error_handling is None:
                    insp = sa_inspect(node.task)
                    if insp.persistent or insp.detached:
                        # Get identity key (primary key)
                        identity = insp.identity
                        if identity:
                            node_task_id_for_error_handling = identity[0] if identity else None
                # Last resort: try direct attribute access (may trigger lazy loading)
                if node_task_id_for_error_handling is None:
                    node_task_id_for_error_handling = node.task.id
            except Exception:
                # If all methods fail, set to None
                node_task_id_for_error_handling = None
        
        try:
            # Check if streaming has been marked as final
            if self.streaming_final:
                logger.info(f"Streaming marked as final, stopping task tree execution for {node.task.id}")
                return
            
            # Allow re-execution of failed tasks and pending tasks
            # Skip only completed and in_progress tasks (unless marked for re-execution)
            task_id = str(node.task.id)
            if node.task.status in ["completed", "in_progress"]:
                # Check if task is marked for re-execution
                if task_id not in self._tasks_to_reexecute:
                    logger.info(f"Task {node.task.id} already {node.task.status}, skipping distribution")
                    return
                else:
                    logger.info(f"Task {node.task.id} is {node.task.status} but marked for re-execution, will re-execute")
            elif node.task.status == "failed":
                # Failed tasks can always be re-executed
                logger.info(f"Task {node.task.id} is failed, will re-execute")
            
            # Note: Parent-child relationship is only for tree organization, not execution order
            # Only dependencies affect execution order - a task executes when its dependencies are satisfied
            # We process children first (for tree traversal), then check if task should execute based on dependencies
            
            # Group children by priority
            priority_groups = {}
            for child_node in node.children:
                priority = child_node.task.priority or 999
                if priority not in priority_groups:
                    priority_groups[priority] = []
                child_id = str(child_node.task.id)
                # Include pending tasks, failed tasks, and completed tasks marked for re-execution
                if child_node.task.status not in ["completed", "failed"]:
                    priority_groups[priority].append(child_node)
                    self._add_children_to_priority_groups(child_node, priority_groups)
                elif child_node.task.status == "failed":
                    # Failed tasks should be re-executed
                    priority_groups[priority].append(child_node)
                    self._add_children_to_priority_groups(child_node, priority_groups)
                elif child_node.task.status == "completed" and child_id in self._tasks_to_reexecute:
                    # Completed tasks marked for re-execution should be re-executed
                    priority_groups[priority].append(child_node)
                    self._add_children_to_priority_groups(child_node, priority_groups)
            
            if not priority_groups:
                # No children to execute - check if task should be executed based on dependencies
                # Note: Parent-child relationship is only for organization, not execution order
                # Task execution depends on dependencies, not children status
                deps_satisfied = await are_dependencies_satisfied(
                    node.task, self.task_repository, self._tasks_to_reexecute
                )
                if deps_satisfied and node.task.status != "completed":
                    logger.debug(f"All dependencies for task {node.task.id} are satisfied, executing task")
                    await self._execute_single_task(node.task, use_callback)
                else:
                    logger.debug(f"No children to execute for task {node.task.id}, and dependencies not satisfied or task already completed")
                return
            
            # Sort priorities in ascending order (lower numbers = higher priority)
            # Industry standard: smaller numbers execute first (higher priority)
            sorted_priorities = sorted(priority_groups.keys())
            logger.debug(f"Executing {len(node.children)} children for task {node.task.id} in {len(sorted_priorities)} priority groups")
            
            for priority in sorted_priorities:
                children_with_same_priority = priority_groups[priority]
                logger.debug(f"Processing {len(children_with_same_priority)} tasks with priority {priority}")
                
                # Check dependencies
                ready_tasks = []
                waiting_tasks = []
                
                for child_node in children_with_same_priority:
                    child_task = child_node.task
                    deps_satisfied = await are_dependencies_satisfied(
                        child_task, self.task_repository, self._tasks_to_reexecute
                    )
                    if deps_satisfied:
                        ready_tasks.append(child_node)
                    else:
                        waiting_tasks.append(child_node)
                
                # Execute ready tasks
                if ready_tasks:
                    if len(ready_tasks) == 1:
                        # Single task - execute directly
                        child_node = ready_tasks[0]
                        await self._execute_single_task(child_node.task, use_callback)
                        await self._execute_task_tree_recursive(child_node, use_callback)
                    else:
                        # Multiple tasks - execute in parallel
                        logger.debug(f"Executing {len(ready_tasks)} ready tasks in parallel with priority {priority}")
                        
                        async def execute_child_and_children(child_node):
                            await self._execute_single_task(child_node.task, use_callback)
                            await self._execute_task_tree_recursive(child_node, use_callback)
                        
                        parallel_tasks = [
                            execute_child_and_children(child_node)
                            for child_node in ready_tasks
                        ]
                        
                        await asyncio.gather(*parallel_tasks)
                        logger.debug(f"Completed parallel execution of {len(ready_tasks)} ready tasks")
                
                # Waiting tasks will be triggered by callbacks when dependencies are satisfied
                if waiting_tasks:
                    logger.debug(f"Leaving {len(waiting_tasks)} tasks waiting for dependencies")
            
            # After processing all children, check if task should be executed based on dependencies
            # Note: Parent-child relationship is only for tree organization, not execution order
            # Only dependencies affect execution order - if a task's dependencies are satisfied, it can execute
            # This handles both pending tasks and failed tasks that need re-execution
            # Tasks execute when their dependencies are satisfied, regardless of children status
            deps_satisfied = await are_dependencies_satisfied(
                node.task, self.task_repository, self._tasks_to_reexecute
            )
            if deps_satisfied and node.task.status != "completed":
                logger.debug(f"All dependencies for task {node.task.id} are satisfied, executing task")
                await self._execute_single_task(node.task, use_callback)
                    
        except Exception as e:
            # Use saved task ID to avoid accessing node.task.id after session rollback
            task_id = str(node_task_id_for_error_handling) if node_task_id_for_error_handling else "unknown"
            # Log business errors without stack trace, unexpected errors with stack trace
            if isinstance(e, BusinessError):
                logger.error(f"Business error in _execute_task_tree_recursive for task {task_id}: {str(e)}")
            else:
                logger.error(f"Error in _execute_task_tree_recursive for task {task_id}: {str(e)}", exc_info=True)
            try:
                # Update task status using repository (only if we have a valid task ID)
                if node_task_id_for_error_handling:
                    await self.task_repository.update_task_status(
                        task_id=node_task_id_for_error_handling,
                        status="failed",
                        error=str(e),
                        completed_at=datetime.now(timezone.utc)
                )
            except Exception as db_error:
                logger.error(f"Error updating task status in database: {str(db_error)}")
            raise
    
    def _add_children_to_priority_groups(
        self,
        node: TaskTreeNode,
        priority_groups: Dict[int, List[TaskTreeNode]]
    ):
        """Recursively add all children to priority groups"""
        for child_node in node.children:
            priority = child_node.task.priority or 999
            if priority not in priority_groups:
                priority_groups[priority] = []
            child_id = str(child_node.task.id)
            # Include pending tasks, failed tasks, and completed tasks marked for re-execution
            if child_node.task.status not in ["completed", "failed"]:
                priority_groups[priority].append(child_node)
                self._add_children_to_priority_groups(child_node, priority_groups)
            elif child_node.task.status == "failed":
                # Failed tasks should be re-executed
                priority_groups[priority].append(child_node)
                self._add_children_to_priority_groups(child_node, priority_groups)
            elif child_node.task.status == "completed" and child_id in self._tasks_to_reexecute:
                # Completed tasks marked for re-execution should be re-executed
                priority_groups[priority].append(child_node)
                self._add_children_to_priority_groups(child_node, priority_groups)
    
    async def _are_dependencies_satisfied(self, task: TaskModel) -> bool:
        """
        Check if all dependencies for a task are satisfied
        
        This is a wrapper around the dependency_resolver.are_dependencies_satisfied
        function that passes the necessary context from TaskManager.
        
        Args:
            task: Task to check dependencies for
            
        Returns:
            True if all dependencies are satisfied, False otherwise
        """
        return await are_dependencies_satisfied(
            task, self.task_repository, self._tasks_to_reexecute
        )
    
    async def _execute_single_task(
        self,
        task: TaskModel,
        use_callback: bool = True
    ):
        """
        Execute a single task
        
        Args:
            task: Task to execute
            use_callback: Whether to use callbacks
        """
        # Save task ID at the beginning to avoid accessing it after session rollback
        # Use SQLAlchemy inspect to safely get ID without triggering lazy loading
        from sqlalchemy import inspect as sa_inspect
        task_id_for_error_handling = None
        if task:
            try:
                # Try to get ID directly from the object's dict to avoid triggering SQLAlchemy lazy loading
                task_id_for_error_handling = task.__dict__.get('id') if hasattr(task, '__dict__') else None
                # If not in __dict__, try using inspect to get the identity
                if task_id_for_error_handling is None:
                    insp = sa_inspect(task)
                    if insp.persistent or insp.detached:
                        # Get identity key (primary key)
                        identity = insp.identity
                        if identity:
                            task_id_for_error_handling = identity[0] if identity else None
                # Last resort: try direct attribute access (may trigger lazy loading)
                if task_id_for_error_handling is None:
                    task_id_for_error_handling = task.id
            except Exception:
                # If all methods fail, set to None
                task_id_for_error_handling = None
        
        try:
            # Check if streaming has been marked as final
            if self.streaming_final:
                logger.info(f"Streaming marked as final, stopping single task execution for {task_id_for_error_handling or 'unknown'}")
                return
                
            # Check if task is already finished or cancelled
            # Allow re-execution of failed tasks if they are marked for re-execution
            # Use saved task_id_for_error_handling if available, otherwise try to get from task
            try:
                task_id = str(task_id_for_error_handling) if task_id_for_error_handling else str(task.id)
            except Exception:
                task_id = str(task_id_for_error_handling) if task_id_for_error_handling else "unknown"
            if task.status in ["completed", "cancelled"]:
                # Check if task is marked for re-execution
                if task_id not in self._tasks_to_reexecute:
                    logger.info(f"Task {task_id} already {task.status}, skipping execution")
                    return
                else:
                    logger.info(f"Task {task_id} is {task.status} but marked for re-execution, will re-execute")
            elif task.status == "failed":
                # Failed tasks can be re-executed if marked for re-execution
                if task_id in self._tasks_to_reexecute:
                    logger.info(f"Task {task_id} is failed and marked for re-execution, will re-execute")
                else:
                    # If not marked for re-execution, skip (shouldn't happen in normal flow)
                    logger.info(f"Task {task_id} is failed but not marked for re-execution, skipping execution")
                    return
            
            # Check if task is already in progress (may have been started by another process)
            if task.status == "in_progress":
                logger.info(f"Task {task_id} already in_progress, skipping execution")
                return
            
            # Check if task was cancelled before starting (double-check after potential race condition)
            # Refresh task from database to get latest status
            # Use saved task_id_for_error_handling to avoid accessing task.id after potential session rollback
            refresh_task_id = task_id_for_error_handling if task_id_for_error_handling else (task.id if task else None)
            if not refresh_task_id:
                raise ValueError("Task ID not available for refresh")
            task = await self.task_repository.get_task_by_id(refresh_task_id)
            if not task:
                raise ValueError(f"Task {refresh_task_id} not found")
            
            if task.status == "cancelled":
                logger.info(f"Task {task.id} was cancelled, skipping execution")
                return
            
            # Send task start status if streaming is enabled
            # Use saved task_id_for_error_handling for all task.id accesses to avoid session rollback issues
            current_task_id = task_id_for_error_handling if task_id_for_error_handling else (task.id if task else None)
            
            if self.stream:
                self.streaming_callbacks.task_start(current_task_id)
            
            # Update task status to in_progress using repository
            await self.task_repository.update_task_status(
                task_id=current_task_id,
                status="in_progress",
                error=None,
                started_at=datetime.now(timezone.utc)
            )
            # Refresh task object
            task = await self.task_repository.get_task_by_id(current_task_id)
            if not task:
                raise ValueError(f"Task {current_task_id} not found after status update")
            
            # Final check: if task was cancelled between status update and refresh
            if task.status == "cancelled":
                logger.info(f"Task {current_task_id} was cancelled after status update, stopping execution")
                return
            
            logger.info(f"Task {current_task_id} status updated to in_progress")
            
            # Resolve dependencies first (merge dependency results into inputs)
            resolved_inputs = await resolve_task_dependencies(task, self.task_repository)
            
            # Check cancellation before proceeding
            task = await self.task_repository.get_task_by_id(current_task_id)
            if not task:
                raise ValueError(f"Task {current_task_id} not found")
            if task.status == "cancelled":
                logger.info(f"Task {current_task_id} was cancelled during dependency resolution, stopping execution")
                return
            
            if resolved_inputs != (task.inputs or {}):
                # Update inputs using repository
                await self.task_repository.update_task_inputs(current_task_id, resolved_inputs)
                # Refresh task object
                task = await self.task_repository.get_task_by_id(current_task_id)
                if not task:
                    raise ValueError(f"Task {current_task_id} not found after input data update")
                
                # Check cancellation again
                if task.status == "cancelled":
                    logger.info(f"Task {current_task_id} was cancelled after input data update, stopping execution")
                    return
            
            # Execute pre-hooks (after dependency resolution, to allow user adjustment based on complete data)
            # Pre-hooks can access and modify task.inputs directly
            # Store inputs before pre-hooks to detect changes (deep copy for nested dicts)
            import copy
            inputs_before_pre_hooks = copy.deepcopy(task.inputs) if task.inputs else {}
            await self._execute_pre_hooks(task)
            
            # Update inputs if pre-hooks modified task.inputs
            # Use deep comparison to detect any changes (including nested dict modifications)
            inputs_after_pre_hooks = task.inputs or {}
            # Deep comparison to detect changes in nested structures
            if inputs_after_pre_hooks != inputs_before_pre_hooks:
                # Pre-hooks modified inputs, update database
                # Make a deep copy to ensure we're saving the current state
                inputs_to_save = copy.deepcopy(inputs_after_pre_hooks) if inputs_after_pre_hooks else {}
                logger.info(
                    f"Pre-hooks modified inputs for task {current_task_id}: "
                    f"before_keys={list(inputs_before_pre_hooks.keys())}, "
                    f"after_keys={list(inputs_after_pre_hooks.keys())}"
                )
                await self.task_repository.update_task_inputs(current_task_id, inputs_to_save)
                # Refresh task object to get latest state from database
                task = await self.task_repository.get_task_by_id(current_task_id)
                if not task:
                    raise ValueError(f"Task {current_task_id} not found after pre-hook inputs update")
                logger.info(f"Pre-hooks modified inputs for task {current_task_id}, updated in database")
            else:
                logger.debug(f"Pre-hooks did not modify inputs for task {current_task_id}")
            
            # Check cancellation before executing
            task = await self.task_repository.get_task_by_id(current_task_id)
            if not task:
                raise ValueError(f"Task {current_task_id} not found")
            if task.status == "cancelled":
                logger.info(f"Task {current_task_id} was cancelled before execution, stopping")
                return
            
            # Execute task using agent executor
            # Use task.inputs (which may have been modified by pre-hooks)
            final_inputs = task.inputs or {}
            logger.info(f"Task {current_task_id} execution - calling agent executor (name: {task.name})")
            
            # Execute task based on schemas
            # Note: For long-running executors, cancellation check should be done inside executor
            # TaskManager can only check before and after executor execution
            task_result = await self._execute_task_with_schemas(task, final_inputs)
            
            # Check cancellation after execution (in case it was cancelled during execution)
            # Note: If task was cancelled, cancel_task() was already called by external source,
            # so we just need to stop execution and preserve the cancelled status
            task = await self.task_repository.get_task_by_id(current_task_id)
            if task and task.status == "cancelled":
                logger.info(f"Task {current_task_id} was cancelled during execution, stopping")
                
                # Clear executor reference
                # Also clear task context to prevent memory leaks
                executor = self._executor_instances.pop(current_task_id, None)
                if executor and hasattr(executor, 'clear_task_context'):
                    executor.clear_task_context()
                    logger.debug(f"Cleared task context for task {current_task_id} after cancellation")
                
                # Don't update to completed, keep cancelled status
                if self.stream:
                    # StreamingCallbacks may not have task_cancelled method, use task_failed as fallback
                    if hasattr(self.streaming_callbacks, 'task_cancelled'):
                        self.streaming_callbacks.task_cancelled(current_task_id)
                    else:
                        self.streaming_callbacks.task_failed(current_task_id, "Task was cancelled")
                return
            
            # Clear executor reference after successful execution
            # Also clear task context to prevent memory leaks
            executor = self._executor_instances.pop(current_task_id, None)
            if executor and hasattr(executor, 'clear_task_context'):
                executor.clear_task_context()
                logger.debug(f"Cleared task context for task {current_task_id} after successful execution")
            
            # Update task status using repository
            # Clear error field when task completes successfully (for re-execution scenarios)
            await self.task_repository.update_task_status(
                task_id=current_task_id,
                status="completed",
                progress=1.0,
                result=task_result,
                error=None,  # Clear error when task completes successfully
                completed_at=datetime.now(timezone.utc)
            )
            # Refresh task object
            task = await self.task_repository.get_task_by_id(current_task_id)
            if not task:
                raise ValueError(f"Task {current_task_id} not found after completion update")
            
            if self.stream:
                self.streaming_callbacks.task_completed(current_task_id, result=task.result)
            
            # System-internal dependency task triggering
            # execute_after_task is always executed to trigger dependent tasks
            # This is independent of use_callback (which controls external URL notifications)
            # Post-hooks will be executed in execute_after_task BEFORE triggering dependent tasks
            # This ensures immediate response for notifications/logging without waiting for dependencies
            try:
                await self.execute_after_task(task)
            except Exception as e:
                logger.error(f"Error triggering dependent tasks for {current_task_id}: {str(e)}")
                # Don't fail the current task if dependency triggering fails
            
            # Note: use_callback is for external URL callback notifications (if configured)
            # It doesn't affect execute_after_task which handles internal dependency triggering
                
        except Exception as e:
            # Use saved task ID to avoid accessing task after session rollback
            task_id_str = str(task_id_for_error_handling) if task_id_for_error_handling else "unknown"
            # Log business errors without stack trace, unexpected errors with stack trace
            if isinstance(e, BusinessError):
                logger.error(f"Business error executing task {task_id_str}: {str(e)}")
            else:
                logger.error(f"Error executing task {task_id_str}: {str(e)}", exc_info=True)
            
            # Update task status using repository (only if we have a valid task ID)
            if task_id_for_error_handling:
                try:
                    await self.task_repository.update_task_status(
                        task_id=task_id_for_error_handling,
                        status="failed",
                        error=str(e),
                        completed_at=datetime.now(timezone.utc)
                    )
                except Exception as update_error:
                    # If update fails (e.g., session already rolled back), log but don't fail
                    logger.warning(f"Failed to update task status for {task_id_str}: {update_error}")
            
            if self.stream and task_id_for_error_handling:
                try:
                    self.streaming_callbacks.task_failed(task_id_for_error_handling, str(e))
                except Exception as callback_error:
                    # If callback fails (e.g., accessing task.id triggers session reload), log but don't fail
                    logger.warning(f"Failed to call task_failed callback for {task_id_str}: {callback_error}")
    
    async def _execute_pre_hooks(self, task: TaskModel) -> None:
        """
        Execute pre-execution hooks
        
        Args:
            task: Task to execute (hooks can access and modify task.inputs)
            
        Note:
            Pre-hooks are executed after dependency resolution, so task.inputs
            contains the complete resolved data including dependency results.
            Hooks can modify task.inputs directly.
        """
        if not self.pre_hooks:
            return
        
        logger.debug(f"Executing {len(self.pre_hooks)} pre-hooks for task {task.id}")
        
        for hook in self.pre_hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(task)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, task)
            except Exception as e:
                # Log error but don't fail the task execution
                logger.warning(
                    f"Pre-hook {hook.__name__} failed for task {task.id}: {str(e)}. "
                    f"Continuing with task execution."
                )
    
    async def _execute_post_hooks(
        self,
        task: TaskModel,
        inputs: Dict[str, Any],
        result: Any
    ) -> None:
        """
        Execute post-execution hooks
        
        Args:
            task: Task that was executed
            inputs: Input parameters used for execution
            result: Task execution result
        """
        if not self.post_hooks:
            return
        
        logger.debug(f"Executing {len(self.post_hooks)} post-hooks for task {task.id}")
        
        for hook in self.post_hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(task, inputs, result)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, task, inputs, result)
            except Exception as e:
                # Log error but don't fail the task execution
                logger.warning(
                    f"Post-hook {hook.__name__} failed for task {task.id}: {str(e)}. "
                    f"Task execution already completed."
                )
    
    async def _resolve_task_dependencies(self, task: TaskModel) -> Dict[str, Any]:
        """
        Resolve task dependencies by merging results from dependency tasks
        
        This is a wrapper around the dependency_resolver.resolve_task_dependencies
        function that passes the necessary context from TaskManager.
        
        Args:
            task: Task to resolve dependencies for
            
        Returns:
            Resolved input data dictionary
        """
        return await resolve_task_dependencies(task, self.task_repository)
    
    async def _get_completed_tasks_by_id(self, task: TaskModel) -> Dict[str, TaskModel]:
        """
        Get all completed tasks in the same task tree by id
        
        This is a wrapper around the dependency_resolver.get_completed_tasks_by_id
        function that passes the necessary context from TaskManager.
        
        Args:
            task: Task to get sibling tasks for
            
        Returns:
            Dictionary mapping task ids to completed TaskModel instances
        """
        return await get_completed_tasks_by_id(task, self.task_repository)
    
    async def _get_root_task(self, task: TaskModel) -> TaskModel:
        """Get root task of the task tree"""
        # Use repository method
        return await self.task_repository.get_root_task(task)
    
    async def _get_all_tasks_in_tree(self, root_task: TaskModel) -> List[TaskModel]:
        """
        Get all tasks in the task tree (recursive)
        
        Args:
            root_task: Root task of the tree
        
        Returns:
            List of all tasks in the tree
        """
        # Use repository method
        return await self.task_repository.get_all_tasks_in_tree(root_task)
    
    async def _call_task_tree_hooks(self, hook_type: str, root_task: TaskModel, *args):
        """
        Call task tree lifecycle hooks
        
        Args:
            hook_type: Hook type ("on_tree_created", "on_tree_started", "on_tree_completed", "on_tree_failed")
            root_task: Root task of the task tree
            *args: Additional arguments to pass to hooks
        """
        hooks = get_task_tree_hooks(hook_type)
        if not hooks:
            return
        
        logger.debug(f"Calling {len(hooks)} task tree hooks for '{hook_type}' on root task {root_task.id}")
        
        for hook in hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(root_task, *args)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, root_task, *args)
            except Exception as e:
                # Log error but don't fail the task tree execution
                logger.warning(
                    f"Task tree hook '{hook_type}' {hook.__name__ if hasattr(hook, '__name__') else str(hook)} "
                    f"failed for root task {root_task.id}: {str(e)}. Continuing with task tree execution."
                )
    
    async def execute_after_task(self, completed_task: TaskModel):
        """
        Execute after task completion - execute post-hooks and trigger dependent tasks
        
        Args:
            completed_task: Task that just completed
            
        Note:
            Post-hooks are executed FIRST (before triggering dependent tasks) to ensure
            immediate response for notifications, logging, etc. This allows:
            - Immediate notification of task completion
            - Fast logging and data export
            - Better user experience (no waiting for dependent tasks)
            
            If you need dependent task results in post-hooks, handle it in the
            dependent task's own post-hooks instead.
        """
        try:
            # Check if task is actually completed
            if completed_task.status != "completed":
                return
            
            # Execute post-hooks FIRST (before triggering dependent tasks)
            # This ensures immediate response and doesn't wait for dependent tasks
            refreshed_task = await self.task_repository.get_task_by_id(completed_task.id)
            if refreshed_task and refreshed_task.status == "completed":
                # Get the inputs that were used for execution
                # This should include pre-hook modifications since they were saved to DB
                # Use refreshed_task.inputs which contains the latest data from database
                logger.info(
                    f"Loading task {completed_task.id} from DB for post-hook: "
                    f"inputs_type={type(refreshed_task.inputs)}, "
                    f"inputs_keys={list(refreshed_task.inputs.keys()) if refreshed_task.inputs else []}, "
                    f"inputs_value={refreshed_task.inputs}"
                )
                inputs = refreshed_task.inputs or {}
                result = refreshed_task.result
                
                # Ensure we're passing the actual inputs dict (not a reference that might be stale)
                # Make a copy to ensure we're passing the current state
                # If inputs is already a dict, create a shallow copy; otherwise convert to dict
                if isinstance(inputs, dict):
                    inputs = dict(inputs)
                else:
                    # Handle case where inputs might be a JSON string or other type
                    inputs = dict(inputs) if inputs else {}
                
                logger.info(
                    f"Post-hook inputs for task {refreshed_task.id}: "
                    f"keys={list(inputs.keys())}, has_pre_hook_marker={inputs.get('_pre_hook_executed', False)}, "
                    f"inputs_type={type(inputs)}, inputs_value={inputs}"
                )
                
                await self._execute_post_hooks(refreshed_task, inputs, result)
            else:
                logger.warning(f"Task {completed_task.id} not found or not completed, skipping post-hooks")
            
            logger.info(f"🔍 Checking for dependent tasks after completion of {completed_task.id} (name: {completed_task.name})")
            
            # Get all tasks in the tree
            root_task = await self._get_root_task(completed_task)
            all_tasks = await self._get_all_tasks_in_tree(root_task)
            
            # Find tasks that are waiting and might have their dependencies satisfied
            waiting_tasks = [
                t for t in all_tasks 
                if t.status in ["pending", "in_progress"] and t.id != completed_task.id
            ]
            
            # Trigger dependent tasks if any
            if waiting_tasks:
                logger.info(f"Found {len(waiting_tasks)} waiting tasks to check for dependencies")
                
                # Check each waiting task to see if its dependencies are now satisfied
                triggered_tasks = []
                for task in waiting_tasks:
                    logger.debug(f"Checking dependencies for task {task.id} (name: {task.name})")
                    deps_satisfied = await are_dependencies_satisfied(
                        task, self.task_repository, self._tasks_to_reexecute
                    )
                    
                    if deps_satisfied:
                        logger.info(f"🚀 Task {task.id} (name: {task.name}) dependencies now satisfied, executing")
                        triggered_tasks.append(task)
                        try:
                            await self._execute_single_task(task, use_callback=True)
                        except Exception as e:
                            # Log business errors without stack trace, unexpected errors with stack trace
                            if isinstance(e, BusinessError):
                                logger.error(f"❌ Business error executing dependent task {task.id}: {str(e)}")
                            else:
                                logger.error(f"❌ Failed to execute dependent task {task.id}: {str(e)}", exc_info=True)
                            # Update task status using repository
                            await self.task_repository.update_task_status(
                                task_id=task.id,
                                status="failed",
                                error=str(e)
                            )
                    else:
                        logger.debug(f"Task {task.id} (name: {task.name}) dependencies not yet satisfied")
                
                if triggered_tasks:
                    logger.info(f"Successfully triggered {len(triggered_tasks)} dependent tasks")
                else:
                    logger.debug("No tasks were triggered by this completion")
            else:
                logger.debug("No waiting tasks found")
        except Exception as e:
            logger.error(f"Error in execute_after_task for {completed_task.id}: {str(e)}", exc_info=True)
    
    async def _execute_task_with_schemas(
        self,
        task: TaskModel,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute task based on schemas configuration
        
        Uses the executor registry to find and instantiate the appropriate executor
        based on task_type in schemas. Supports both built-in and third-party executors.
        
        Args:
            task: Task to execute
            inputs: Input parameters for task execution
            
        Returns:
            Task execution result
            
        Raises:
            ValueError: If task_type is not registered in executor registry
        """
        schemas = task.schemas or {}
        task_type = schemas.get("type")  # Optional: only used if method is not an executor id
        task_method = schemas.get("method", "command")
        
        # ============================================================
        # 1. get executor id from params (check this FIRST, before logging)
        # ============================================================
        params = task.params or {}
        executor_id = params.get("executor_id")
        
        # Log after we have executor_id info
        logger.info(f"Executing task {task.id} with type={task_type}, method={task_method}, executor_id={executor_id}")
        logger.debug(f"Task {task.id} params: {params}, executor_id from params: {executor_id}")

        # Get executor from unified extension registry
        registry = get_registry()
        
        # Strategy: Try to use method as executor id first, then fall back to type-based lookup
        # This allows:
        # 1. Direct id-based lookup: method="crewai_executor" (no type needed)
        # 2. Type-based lookup: type="stdio", method="command" (method is execution method, not id)
        extension_id = None
        extension = None
        
        # If executor_id is already set from params or schemas.method, use it
        if executor_id:
            extension = registry.get_by_id(executor_id)
            if extension and extension.category == ExtensionCategory.EXECUTOR:
                extension_id = executor_id
                logger.info(f"Using executor_id '{executor_id}' from params (task {task.id})")
        
        # If not found, try to use method as executor id
        if extension is None or (extension and extension.category != ExtensionCategory.EXECUTOR):
            if task_method:
                extension = registry.get_by_id(task_method)
                if extension and extension.category == ExtensionCategory.EXECUTOR:
                    extension_id = task_method
                    executor_id = task_method
                    logger.debug(f"Using method '{task_method}' as executor id (type not needed)")
        
        # If method is not an executor id, fall back to type-based lookup
        if extension is None or (extension and extension.category != ExtensionCategory.EXECUTOR):
            if not task_type:
                # If no type specified and method is not an executor id, use default
                task_type = "stdio"
                logger.debug("No type specified, defaulting to 'stdio'")
            extension = registry.get_by_type(ExtensionCategory.EXECUTOR, task_type)
            if extension:
                extension_id = extension.id
                executor_id = extension_id
                logger.debug(f"Using type '{task_type}' to find executor '{extension_id}'")
        
        if extension is None or extension.category != ExtensionCategory.EXECUTOR:
            # Task type not registered
            registered_extensions = registry.list_by_category(ExtensionCategory.EXECUTOR)
            error_msg = (
                f"Task executor not found. "
                f"type='{task_type}', method='{task_method}'. "
                f"Registered executor types: {[ext.type for ext in registry.get_all_by_category(ExtensionCategory.EXECUTOR) if ext.type]}. "
                f"Registered executor ids: {registry.list_by_category(ExtensionCategory.EXECUTOR)}. "
                f"Please register an executor for this task type using "
                f"register_extension(YourExecutorInstance, executor_class=YourExecutorClass)."
            )
            logger.error(error_msg)
            return {
                "error": error_msg,
                "task_id": task.id,
                "name": task.name,
                "task_type": task_type,
                "task_method": task_method,
                "registered_types": [ext.type for ext in registry.get_all_by_category(ExtensionCategory.EXECUTOR) if ext.type],
                "registered_ids": registry.list_by_category(ExtensionCategory.EXECUTOR),
                "inputs": inputs,
                "schemas": schemas
            }
        
        if not executor_id:
            executor_id = extension_id
        
        if not executor_id:
            error_msg = (
                f"Task {task.id}: executor_id is required in params. "
                f"Please specify params.executor_id (e.g., 'crewai_executor', 'command_executor')."
            )
            logger.error(error_msg)
            return {
                "error": error_msg,
                "task_id": task.id
            }
        
        # ============================================================
        # 2. extract executor initialization parameters from params
        # ============================================================
        # all fields in params except executor_id are initialization parameters
        init_params = params.copy()
        init_params.pop("executor_id", None)  # executor_id is already handled separately
        
        # Get input_schema from schemas to pass to executor
        input_schema = schemas.get("input_schema")
        if input_schema:
            init_params["inputs_schema"] = input_schema
        
        # Get model from schemas to pass to executor (for CrewAI executors)
        model = schemas.get("model")
        if model:
            init_params["model"] = model
        
        
        # ============================================================
        # 3. create executor instance
        # ============================================================
        # Create cancellation checker
        cached_cancelled = task.status == "cancelled"
        def cancellation_checker() -> bool:
            return cached_cancelled
        
        # Create executor: inputs as inputs parameter, other as **kwargs
        # Note: Input validation is now handled by executor itself (in BaseTask or executor.execute)
        # Pass task context to executor for full access to task information (including custom fields)
        # This allows executors to:
        # - Access all task fields (including custom TaskModel fields)
        # - Modify task context (e.g., update status, progress, custom fields)
        # - Share task object efficiently (lifecycle managed by TaskManager)
        executor = registry.create_executor_instance(
            extension_id=executor_id,
            inputs=inputs,  # inputs for execution (will be validated by executor)
            task=task,  # Pass task context (TaskModel instance) - supports custom TaskModel classes
            user_id=task.user_id,  # Also pass user_id for backward compatibility
            **init_params,  # initialization parameters (works, name, inputs_schema, etc.)
            cancellation_checker=cancellation_checker
        )
        
        if executor is None:
            error_msg = f"Failed to create executor instance '{executor_id}'"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "task_id": task.id,
                "executor_id": executor_id
            }
        
        # Store executor for cancellation support
        if hasattr(executor, 'cancel'):
            self._executor_instances[task.id] = executor
            logger.debug(f"Stored executor instance for task {task.id} (supports cancellation)")
        
        # ============================================================
        # 4. execute executor (with hooks)
        # ============================================================
        # Note: Input validation and any executor-specific input processing
        # should be handled by the executor itself (in BaseTask or executor.execute)
        # TaskManager only handles task orchestration and distribution
        
        # Check for demo mode (use instance variable instead of inputs)
        if self.use_demo:
            logger.info(f"Demo mode enabled for task {task.id} with executor {executor_id}")
            # Try to get custom demo result from executor if available
            demo_result = None
            if hasattr(executor, 'get_demo_result'):
                try:
                    demo_result = executor.get_demo_result(task, inputs)
                except Exception as e:
                    logger.warning(f"get_demo_result() failed for executor {executor_id}: {str(e)}. Using default demo data.")
            
            # Use default demo result if executor doesn't provide one
            if demo_result is None:
                demo_result = {"result": "Demo execution result", "demo_mode": True}
            
            # Ensure result format is consistent
            if isinstance(demo_result, dict):
                demo_result["demo_mode"] = True
                
                # Handle demo sleep time
                # Executor can specify _demo_sleep in get_demo_result() return value
                # Global scale factor is applied to executor's sleep time
                sleep_seconds = 0.0
                if "_demo_sleep" in demo_result:
                    # Executor-specific sleep time (remove from result)
                    executor_sleep = float(demo_result.pop("_demo_sleep"))
                    # Apply global scale factor
                    from aipartnerupflow.core.config import get_demo_sleep_scale
                    scale = get_demo_sleep_scale()
                    sleep_seconds = executor_sleep * scale
                    logger.debug(f"Demo mode: executor sleep={executor_sleep}s, scale={scale}, final sleep={sleep_seconds}s")
                
                # Sleep to simulate execution time if configured
                if sleep_seconds > 0:
                    import asyncio
                    await asyncio.sleep(sleep_seconds)
                
                return demo_result
            else:
                return {"result": demo_result, "demo_mode": True}
            

        # Get executor class to check for hooks
        executor_class = type(executor)
        
        # Call executor-specific pre_hook if available
        hook_result = None
        if hasattr(executor_class, '_executor_hooks'):
            pre_hook = executor_class._executor_hooks.get('pre_hook')
            if pre_hook:
                try:
                    logger.debug(f"Calling pre_hook for executor {executor_id} on task {task.id}")
                    if iscoroutinefunction(pre_hook):
                        hook_result = await pre_hook(executor, task, inputs)
                    else:
                        hook_result = await asyncio.to_thread(pre_hook, executor, task, inputs)
                    
                    # If hook returned a result, skip executor execution
                    if hook_result is not None:
                        logger.info(f"Pre_hook returned result for executor {executor_id}, skipping execution")
                        # Call post_hook if available
                        post_hook = executor_class._executor_hooks.get('post_hook')
                        if post_hook:
                            try:
                                if iscoroutinefunction(post_hook):
                                    await post_hook(executor, task, inputs, hook_result)
                                else:
                                    await asyncio.to_thread(post_hook, executor, task, inputs, hook_result)
                            except Exception as e:
                                logger.warning(f"Post_hook failed for executor {executor_id}: {str(e)}")
                        return hook_result
                except Exception as e:
                    logger.warning(f"Pre_hook failed for executor {executor_id}: {str(e)}. Continuing with execution.")
        
        try:
            result = await executor.execute(inputs)
            
            # Call executor-specific post_hook if available
            if hasattr(executor_class, '_executor_hooks'):
                post_hook = executor_class._executor_hooks.get('post_hook')
                if post_hook:
                    try:
                        logger.debug(f"Calling post_hook for executor {executor_id} on task {task.id}")
                        if iscoroutinefunction(post_hook):
                            await post_hook(executor, task, inputs, result)
                        else:
                            await asyncio.to_thread(post_hook, executor, task, inputs, result)
                    except Exception as e:
                        logger.warning(f"Post_hook failed for executor {executor_id}: {str(e)}")
            
            # Explicitly clear task context to prevent memory leaks
            # This is important for long-running executors and memory management
            if hasattr(executor, 'clear_task_context'):
                executor.clear_task_context()
                logger.debug(f"Cleared task context for executor {executor_id} on task {task.id}")
            
            return result
        except Exception as e:
            # Log business errors without stack trace, unexpected errors with stack trace
            if isinstance(e, BusinessError):
                logger.error(f"Business error executing task {task.id} with executor {executor.__class__.__name__}: {e}")
            else:
                logger.error(f"Error executing task {task.id} with executor {executor.__class__.__name__}: {e}", exc_info=True)
            # Explicitly clear task context on error to prevent memory leaks
            if hasattr(executor, 'clear_task_context'):
                executor.clear_task_context()
            # Clear executor reference on error
            self._executor_instances.pop(task.id, None)
            # Re-raise the exception to let TaskManager mark the task as failed
            raise
    
__all__ = [
    "TaskManager",
]

