"""
Task executor for AIPartnerUpFlow that manages task tree execution
"""
import uuid
import copy
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aipartnerupflow.core.execution.task_manager import TaskManager
from aipartnerupflow.core.execution.task_tracker import TaskTracker
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.storage import create_pooled_session
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.config import (
    get_task_model_class,
    get_pre_hooks,
    get_post_hooks,
    get_use_task_creator,
    get_require_existing_tasks,
)
from aipartnerupflow.core.utils.logger import get_logger

# Auto-import extensions to register extensions and tools when TaskExecutor is imported
# This ensures extensions and tools are available when TaskExecutor is used
# (extensions/__init__.py auto-imports tools, so tools will be registered automatically)
try:
    import aipartnerupflow.extensions  # noqa: F401
except ImportError:
    # Extensions may not be installed, that's okay
    pass
except Exception:
    # Other errors (syntax errors, etc.) should not break import
    pass

logger = get_logger(__name__)


class TaskExecutor:
    """
    Task executor - Singleton pattern for task execution and tracking
    
    This is a singleton to ensure resource efficiency and shared state.
    Hooks and task model are read from the config registry at initialization time.
    
    Design rationale:
    - Singleton: Saves memory, shared TaskTracker state
    - Static hooks: Hooks are registered at application startup (module import time)
    - Performance: Hooks are cached, no registry lookup on each execution
    - Production reality: Hooks don't change at runtime (even in multi-user scenarios,
      hooks handle user logic internally, but the hook list itself is static)
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskExecutor, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not TaskExecutor._initialized:
            # TaskTracker is singleton for shared state (running tasks)
            self.task_tracker = TaskTracker()
            # Read configuration from registry at initialization (static hooks)
            # In production, hooks are registered at application startup
            self.task_model_class = get_task_model_class()
            self.pre_hooks = get_pre_hooks()
            self.post_hooks = get_post_hooks()
            # Store executor instances for cancellation (task_id -> executor)
            # This allows cancel_task() to access executors created during execution
            self._executor_instances: Dict[str, Any] = {}
            TaskExecutor._initialized = True
            logger.info(
                f"Initialized TaskExecutor "
                f"(TaskModel: {self.task_model_class.__name__}, "
                f"pre_hooks: {len(self.pre_hooks)}, "
                f"post_hooks: {len(self.post_hooks)})"
            )
    
    def refresh_config(self):
        """
        Refresh configuration from registry (for testing scenarios)
        
        In production, hooks are registered at startup before TaskExecutor creation,
        so this method is not needed. It's provided for testing scenarios where
        hooks are registered after TaskExecutor initialization.
        """
        self.task_model_class = get_task_model_class()
        self.pre_hooks = get_pre_hooks()
        self.post_hooks = get_post_hooks()
        logger.debug(
            f"Refreshed TaskExecutor config "
            f"(TaskModel: {self.task_model_class.__name__}, "
            f"pre_hooks: {len(self.pre_hooks)}, "
            f"post_hooks: {len(self.post_hooks)})"
        )

    def _mark_tasks_for_reexecution(self, task_tree: TaskTreeNode) -> set[str]:
        """
        Mark tasks in the task tree that need re-execution
        
        Only marks tasks that are:
        - failed: Always need re-execution
        - completed: Need re-execution when their dependent tasks are re-executed
        
        Does NOT mark pending tasks (newly created tasks should execute normally).
        
        Args:
            task_tree: Root TaskTreeNode to mark
            
        Returns:
            Set of task IDs marked for re-execution
        """
        tasks_to_reexecute = set()
        
        def collect_task_ids(node: TaskTreeNode):
            """Recursively collect task IDs that need re-execution"""
            task_status = node.task.status
            task_id = str(node.task.id)
            task_name = getattr(node.task, 'name', 'unknown')
            
            # Only mark failed or completed tasks for re-execution
            # Pending tasks should execute normally without re-execution marker
            if task_status == "failed":
                tasks_to_reexecute.add(task_id)
                logger.debug(f"Marked failed task {task_id} ({task_name}) for re-execution")
            elif task_status == "completed":
                # Mark completed tasks for re-execution to ensure dependencies are re-executed
                # when a dependent task is re-executed
                tasks_to_reexecute.add(task_id)
                logger.debug(f"Marked completed task {task_id} ({task_name}) for re-execution")
            elif task_status == "pending":
                # Pending tasks should NOT be marked for re-execution
                logger.debug(f"Skipping pending task {task_id} ({task_name}) - will execute normally")
            else:
                # in_progress or other statuses
                logger.debug(f"Skipping task {task_id} ({task_name}) with status {task_status} - will execute normally")
            
            for child in node.children:
                collect_task_ids(child)
        
        collect_task_ids(task_tree)
        if tasks_to_reexecute:
            logger.info(f"Marked {len(tasks_to_reexecute)} tasks for re-execution: {list(tasks_to_reexecute)}")
        else:
            logger.debug("No tasks marked for re-execution (all tasks are pending or in_progress)")
        return tasks_to_reexecute
    
    async def execute_task_tree(
        self,
        task_tree: TaskTreeNode,
        root_task_id: str,
        use_streaming: bool = False,
        streaming_callbacks_context: Optional[Any] = None,
        use_demo: bool = False,
        db_session: Optional[Union[Session, AsyncSession]] = None
    ) -> Dict[str, Any]:
        """
        Execute a task tree
        
        Args:
            task_tree: Root TaskTreeNode to execute
            root_task_id: Root task ID
            use_streaming: Whether to use streaming mode
            streaming_callbacks_context: Context for streaming callbacks (if use_streaming is True)
            db_session: Optional database session (defaults to get_default_session())
            use_demo: If True, executors return demo data instead of executing (default: False)
                     This is an execution option, not a task input. It's passed to TaskManager
                     and used to determine whether to return demo data.
            
        Returns:
            Execution result dictionary
        """
        if db_session is None:
            async with create_pooled_session() as session:
                return await self.execute_task_tree(
                    task_tree=task_tree,
                    root_task_id=root_task_id,
                    use_streaming=use_streaming,
                    streaming_callbacks_context=streaming_callbacks_context,
                    use_demo=use_demo,
                    db_session=session,
                )
        
        # Start task tracking
        await self.start_task_tracking(root_task_id)
        
        try:
            # Mark all tasks in the tree for re-execution
            # This ensures failed tasks and their dependencies are re-executed
            tasks_to_reexecute = self._mark_tasks_for_reexecution(task_tree)
            
            # Create TaskManager with hooks (cached at initialization)
            # In production, hooks are registered at application startup before TaskExecutor creation
            # Pass shared executor_instances so TaskManager can store executors for cancellation
            task_manager = TaskManager(
                db_session,
                root_task_id=root_task_id,
                pre_hooks=self.pre_hooks,
                post_hooks=self.post_hooks,
                executor_instances=self._executor_instances,  # Pass shared executor instances
                use_demo=use_demo  # Pass use_demo flag
            )
            
            # Set tasks to re-execute in TaskManager
            task_manager._tasks_to_reexecute = tasks_to_reexecute
            
            if use_streaming and streaming_callbacks_context:
                task_manager.stream = True
                # Set streaming context - streaming_callbacks_context is EventQueueBridge
                # which has put() method that StreamingCallbacks can use
                task_manager.streaming_callbacks.set_streaming_context(
                    streaming_callbacks_context,  # EventQueueBridge acts as event_queue
                    None  # context will be set by the caller if needed
                )
                # Execute with streaming
                await task_manager.distribute_task_tree_with_streaming(
                    task_tree, 
                    use_callback=True
                )
            else:
                # Execute without streaming
                await task_manager.distribute_task_tree(task_tree, use_callback=True)
            
            # Reload task tree from database to get updated status
            from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            updated_root_task = await task_repository.get_task_by_id(task_tree.task.id)
            
            if updated_root_task:
                final_status = updated_root_task.status
                # Safely convert progress to float
                try:
                    if updated_root_task.progress is not None:
                        if isinstance(updated_root_task.progress, (int, float)):
                            final_progress = float(updated_root_task.progress)
                        elif isinstance(updated_root_task.progress, str):
                            final_progress = float(updated_root_task.progress)
                        else:
                            final_progress = task_tree.calculate_progress()
                    else:
                        final_progress = 0.0
                except (ValueError, TypeError):
                    final_progress = task_tree.calculate_progress()
                # Include root task result if available
                root_result = updated_root_task.result
            else:
                final_status = task_tree.calculate_status()
                final_progress = task_tree.calculate_progress()
                root_result = None
            
            result = {
                "status": final_status,
                "progress": final_progress,
                "root_task_id": task_tree.task.id
            }
            
            # Include root task result if available
            if root_result is not None:
                result["result"] = root_result
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing task tree: {str(e)}", exc_info=True)
            raise
        finally:
            # Stop task tracking
            await self.stop_task_tracking(root_task_id)

    async def start_task_tracking(self, context_id: str) -> None:
        """Start tracking a task"""
        await self.task_tracker.start_task_tracking(context_id)

    async def stop_task_tracking(self, context_id: str) -> None:
        """Stop tracking a task"""
        await self.task_tracker.stop_task_tracking(context_id)

    def get_task_status(self, context_id: str) -> Dict[str, Any]:
        """Get task status by context_id"""
        return self.task_tracker.get_task_status(context_id)
    
    def get_all_running_tasks(self) -> List[str]:
        """Get all running task context_ids"""
        return self.task_tracker.get_all_running_tasks()
    
    def get_running_tasks_count(self) -> int:
        """Get count of running tasks"""
        return self.task_tracker.get_running_tasks_count()
    
    def is_task_running(self, context_id: str) -> bool:
        """Check if a task is running"""
        return self.task_tracker.is_task_running(context_id)
    
    async def cancel_task(
        self,
        task_id: str,
        error_message: Optional[str] = None,
        db_session: Optional[Union[Session, AsyncSession]] = None
    ) -> Dict[str, Any]:
        """
        Cancel a task execution
        
        This method:
        1. Creates a TaskManager instance
        2. Calls TaskManager.cancel_task() to handle cancellation
        3. Stops task tracking
        
        Args:
            task_id: Task ID to cancel
            error_message: Optional error message for cancellation
            db_session: Optional database session (defaults to get_default_session())
            
        Returns:
            Dictionary with cancellation result from TaskManager
        """
        if db_session is None:
            async with create_pooled_session() as session:
                return await self.cancel_task(
                    task_id=task_id, error_message=error_message, db_session=session
                )
        
        # Create TaskManager instance with shared executor_instances
        # This allows cancel_task() to access executors created during execution
        task_manager = TaskManager(
            db_session,
            root_task_id=task_id,
            pre_hooks=self.pre_hooks,
            post_hooks=self.post_hooks,
            executor_instances=self._executor_instances  # Pass shared executor instances
        )
        
        # Call TaskManager.cancel_task()
        result = await task_manager.cancel_task(task_id, error_message)
        
        # Stop task tracking if task was running
        if self.is_task_running(task_id):
            await self.stop_task_tracking(task_id)
        
        return result

    def _build_task_tree_from_tasks(
        self,
        tasks: List[Dict[str, Any]]
    ) -> TaskTreeNode:
        """
        Build TaskTreeNode from tasks array
        
        Args:
            tasks: List of task dictionaries
            
        Returns:
            Root TaskTreeNode
        """
        if not tasks:
            raise ValueError("Tasks array is empty")
        
        # Create TaskModel instances from task dictionaries
        task_models = []
        task_dict_map = {}  # Map task_id to task dict for building tree
        
        for task_dict in tasks:
            # Extract task data
            task_id = task_dict.get("id") or str(uuid.uuid4())
            parent_id = task_dict.get("parent_id")
            user_id = task_dict.get("user_id")
            if not user_id:
                raise ValueError(f"Task {task_id} missing required user_id")
            
            # Create TaskModel using configured class (supports custom TaskModel)
            # Only set fields that are explicitly provided in task_dict
            # This ensures that None values mean "don't update" in _save_tasks_to_database
            task_data = {
                "id": task_id,
                "parent_id": parent_id,
                "user_id": user_id,
                "name": task_dict.get("name", "Unnamed Task"),  # Required field, has default
                "status": task_dict.get("status", "pending"),  # Required field, has default
                "priority": task_dict.get("priority", 1),  # Required field, has default
                "has_children": task_dict.get("has_children", False),  # Required field, has default
                "progress": task_dict.get("progress", 0.0),  # Required field, has default
            }
            
            # Optional fields: only set if explicitly provided in task_dict
            # This allows None values to mean "don't update" in _save_tasks_to_database
            if "dependencies" in task_dict:
                task_data["dependencies"] = task_dict["dependencies"]
            if "inputs" in task_dict:
                task_data["inputs"] = task_dict["inputs"]
            if "params" in task_dict:
                task_data["params"] = task_dict["params"]
            if "schemas" in task_dict:
                task_data["schemas"] = task_dict["schemas"]
            if "result" in task_dict:
                task_data["result"] = task_dict["result"]
            if "error" in task_dict:
                task_data["error"] = task_dict["error"]
            
            # Add any custom fields from task_dict (e.g., project_id)
            # These will be set if they exist as columns in the TaskModel
            # Check both class attributes and table columns for custom fields
            for key, value in task_dict.items():
                if key not in task_data:
                    # Check if field exists as class attribute or table column
                    has_attr = hasattr(self.task_model_class, key)
                    has_column = hasattr(self.task_model_class, '__table__') and key in self.task_model_class.__table__.columns
                    if has_attr or has_column:
                        task_data[key] = value
            
            task_model = self.task_model_class(**task_data)
            
            task_models.append(task_model)
            task_dict_map[task_id] = {"model": task_model, "dict": task_dict}
        
        # Build tree structure
        # Find root task (no parent_id)
        root_task_model = None
        for task_model in task_models:
            if not task_model.parent_id:
                root_task_model = task_model
                break
        
        if not root_task_model:
            raise ValueError("No root task found (task without parent_id)")
        
        # Build tree recursively
        def build_node(task_id: str) -> TaskTreeNode:
            """Recursively build tree node"""
            task_info = task_dict_map.get(task_id)
            if not task_info:
                raise ValueError(f"Task {task_id} not found in tasks array")
            
            node = TaskTreeNode(task_info["model"])
            
            # Find and add children
            for other_task_id, other_info in task_dict_map.items():
                if other_info["dict"].get("parent_id") == task_id:
                    child_node = build_node(other_task_id)
                    node.add_child(child_node)
            
            return node
        
        root_node = build_node(root_task_model.id)
        logger.info(f"Built task tree: root {root_task_model.id} with {len(root_node.children)} direct children")
        
        return root_node

    async def _save_tasks_to_database(
        self,
        task_tree: TaskTreeNode,
        db_session: Union[Session, AsyncSession]
    ):
        """
        Save all tasks in the tree to database
        
        This method handles both new task creation and existing task updates.
        For existing tasks, it intelligently merges data:
        - Only updates fields that are explicitly provided (not None)
        - Deep merges inputs instead of overwriting
        - Preserves existing custom fields if not in update data
        - Uses task_model_class to dynamically determine fields (no hardcoded field lists)
        
        Args:
            task_tree: Root task tree node
            db_session: Database session
        """
        is_async = isinstance(db_session, AsyncSession)
        
        # Get all column names from the model class (supports custom TaskModel)
        # This avoids hardcoding field names and makes the code maintainable
        model_columns = set(self.task_model_class.__table__.columns.keys())
        
        # Fields that should never be updated (read-only or auto-managed)
        readonly_fields = {'id', 'created_at', 'updated_at'}
        
        def should_update_field(key: str, value: Any, existing_value: Any) -> bool:
            """
            Determine if a field should be updated
            
            Principle: Only update fields that are explicitly provided (not None).
            If a field is None in tasks dict, it means "don't update this field".
            
            Args:
                key: Field name
                value: New value from node.task
                existing_value: Existing value in database
                
            Returns:
                True if field should be updated, False otherwise
            """
            # Skip readonly fields
            if key in readonly_fields:
                return False
            
            # Skip non-model fields (internal attributes)
            if key.startswith('_') or key not in model_columns:
                return False
            
            # Only update if value is explicitly provided (not None)
            # This preserves existing fields if not in update data
            # Applies to all fields uniformly - no special cases for execution state
            return value is not None
        
        def merge_inputs(existing: dict, new: dict, task_id: str) -> dict:
            """
            Deep merge new inputs into existing inputs
            
            This preserves pre-hook modifications while allowing updates to specific fields.
            
            Principle:
            - If new is None: means "not provided" - preserve existing unchanged
            - If new is empty dict ({}): means user explicitly wants to clear inputs - update to {}
              This could happen if pre-hooks filtered out all invalid fields
            - If new has content: merge it into existing (preserving existing keys, updating new keys)
            - This allows updating only specific fields in inputs without overwriting the entire dict
            
            Args:
                existing: Existing inputs from database (may contain pre-hook modifications)
                new: New inputs from node.task (from tasks dict)
                task_id: Task ID for logging purposes
                
            Returns:
                Merged inputs dictionary
            """
            # None means not provided - preserve existing
            if new is None:
                return existing
            
            # Empty dict means user explicitly wants to clear inputs
            # This could happen if pre-hooks filtered out all invalid fields
            # Log a warning but allow it (executor should handle validation)
            if not new:
                logger.warning(
                    f"Task {task_id}: inputs is empty dict - this may cause execution failure. "
                    f"Consider validating inputs before execution."
                )
                return {}
            
            # No existing data - use new
            if not existing:
                return copy.deepcopy(new)
            
            # Deep merge: existing data is preserved, new data overwrites specific keys
            # This allows updating only specific fields in inputs
            # Example: existing={'resource': 'cpu', '_pre_hook_executed': True}, new={'resource': 'memory'}
            # Result: {'resource': 'memory', '_pre_hook_executed': True}
            merged = copy.deepcopy(existing)
            merged.update(copy.deepcopy(new))
            return merged
        
        async def save_node_async(node: TaskTreeNode):
            """Recursively save tasks (async)"""
            # Check if task already exists
            existing = await db_session.get(self.task_model_class, node.task.id)
            
            if not existing:
                # New task: add directly
                db_session.add(node.task)
            else:
                # Existing task: update fields intelligently
                for key, value in node.task.__dict__.items():
                    if not hasattr(existing, key):
                        continue
                    
                    if not should_update_field(key, value, getattr(existing, key, None)):
                        continue
                    
                    # Special handling for inputs: deep merge instead of overwrite
                    # This preserves pre-hook modifications
                    if key == 'inputs':
                        existing_value = existing.inputs or {}
                        new_value = value  # Keep original value (could be None or {})
                        merged_value = merge_inputs(existing_value, new_value, existing.id)
                        setattr(existing, key, merged_value)
                    else:
                        # For other fields: direct update
                        setattr(existing, key, value)
            
            # Recursively save children
            for child in node.children:
                await save_node_async(child)
        
        def save_node_sync(node: TaskTreeNode):
            """Recursively save tasks (sync)"""
            # Check if task already exists
            result = db_session.execute(select(self.task_model_class).filter(self.task_model_class.id == node.task.id))
            existing = result.scalar_one_or_none()
            
            if not existing:
                # New task: add directly
                db_session.add(node.task)
            else:
                # Existing task: update fields intelligently
                for key, value in node.task.__dict__.items():
                    if not hasattr(existing, key):
                        continue
                    
                    if not should_update_field(key, value, getattr(existing, key, None)):
                        continue
                    
                    # Special handling for inputs: deep merge instead of overwrite
                    # This preserves pre-hook modifications
                    if key == 'inputs':
                        existing_value = existing.inputs or {}
                        new_value = value  # Keep original value (could be None or {})
                        merged_value = merge_inputs(existing_value, new_value, existing.id)
                        setattr(existing, key, merged_value)
                    else:
                        # For other fields: direct update
                        setattr(existing, key, value)
            
            # Recursively save children
            for child in node.children:
                save_node_sync(child)
        
        # Save all tasks
        if is_async:
            await save_node_async(task_tree)
            await db_session.commit()
        else:
            save_node_sync(task_tree)
            db_session.commit()
        
        logger.info(f"Saved task tree to database: root {task_tree.task.id}")

    async def execute_tasks(
        self,
        tasks: List[Dict[str, Any]],
        root_task_id: Optional[str] = None,
        use_streaming: bool = False,
        streaming_callbacks_context: Optional[Any] = None,
        require_existing_tasks: Optional[bool] = None,
        use_demo: bool = False,
        db_session: Optional[Union[Session, AsyncSession]] = None
    ) -> Dict[str, Any]:
        """
        Execute tasks from a list of task dictionaries
        
        This method supports two modes:
        
        1. **Auto-Create and Execute (require_existing_tasks=False, default)**:
           - Creates tasks if they don't exist in database (more convenient)
           - Uses TaskCreator for rigorous task creation (configurable via get_use_task_creator())
           - Validates dependencies and hierarchy
           - Recommended for most use cases
        
        2. **Execute Existing Only (require_existing_tasks=True)**:
           - Only executes tasks that already exist in database
           - Loads task tree from database
           - Tasks should be a list of task IDs or task dictionaries with existing IDs
           - Suitable when tasks are pre-created via API (e.g., frontend interaction workflow)
        
        The behavior is controlled by:
        - `require_existing_tasks` parameter (takes precedence)
        - Global configuration `get_require_existing_tasks()` (used if parameter is None)
        - Default: False (auto-create for convenience)
        
        The use of TaskCreator is controlled by global configuration (get_use_task_creator()).
        By default, TaskCreator is used for rigorous validation. This can be configured via:
            from aipartnerupflow.core.config import set_use_task_creator
            set_use_task_creator(True)  # Use TaskCreator (default, recommended)
            set_use_task_creator(False) # Use quick create mode (not recommended)
        
        Args:
            tasks: List of task dictionaries or task IDs (if require_existing_tasks=True)
            root_task_id: Optional root task ID for tracking (defaults to root task's ID)
            use_streaming: Whether to use streaming mode
            streaming_callbacks_context: Context for streaming callbacks (if use_streaming is True)
            require_existing_tasks: If True, only execute existing tasks. If False, create if not exist (default).
                                  If None, uses global configuration get_require_existing_tasks().
            db_session: Optional database session (defaults to get_default_session())
            
        Returns:
            Execution result dictionary with status, progress, and root_task_id
        """
        if not tasks:
            raise ValueError("No tasks provided")
        
        # Get database session
        if db_session is None:
            async with create_pooled_session() as session:
                return await self.execute_tasks(
                    tasks=tasks,
                    root_task_id=root_task_id,
                    use_streaming=use_streaming,
                    streaming_callbacks_context=streaming_callbacks_context,
                    require_existing_tasks=require_existing_tasks,
                    use_demo=use_demo,
                    db_session=session,
                )
        
        # Determine whether to require existing tasks
        # Parameter takes precedence, then global config, then default to False
        if require_existing_tasks is None:
            require_existing_tasks = get_require_existing_tasks()
        
        # Check if tasks already exist in database
        if require_existing_tasks:
            # Only execute existing tasks
            task_tree = await self._load_existing_task_tree(tasks, db_session)
        else:
            # Create tasks if they don't exist (auto-create mode)
            # Use configuration to determine whether to use TaskCreator
            use_task_creator = get_use_task_creator()
            
            if use_task_creator:
                # Use TaskCreator for rigorous task creation (recommended)
                from aipartnerupflow.core.execution.task_creator import TaskCreator
                task_creator = TaskCreator(db_session)
                logger.debug(f"Creating task tree from {len(tasks)} tasks with IDs: {[t.get('id') for t in tasks]}")
                task_tree = await task_creator.create_task_tree_from_array(tasks)
                logger.info(f"Created task tree using TaskCreator: root {task_tree.task.id}")
                logger.debug(f"Root task details: id={task_tree.task.id}, name={task_tree.task.name}")
            else:
                # Use quick create mode (not recommended, may have issues)
                logger.warning(
                    "Using quick create mode (use_task_creator=False). "
                    "This mode may have issues. Consider using TaskCreator (default) for rigorous validation."
                )
                logger.info(f"Creating task tree from {len(tasks)} tasks (quick mode)")
                task_tree = self._build_task_tree_from_tasks(tasks)
                # Save tasks to database
                await self._save_tasks_to_database(task_tree, db_session)
        
        # Use root task ID if not provided
        if root_task_id is None:
            root_task_id = task_tree.task.id
        
        # Execute task tree
        execution_result = await self.execute_task_tree(
            task_tree=task_tree,
            root_task_id=root_task_id,
            use_streaming=use_streaming,
            streaming_callbacks_context=streaming_callbacks_context,
            use_demo=use_demo,
            db_session=db_session
        )
        
        return execution_result

    async def _load_existing_task_tree(
        self,
        tasks: List[Union[str, Dict[str, Any]]],
        db_session: Union[Session, AsyncSession]
    ) -> TaskTreeNode:
        """
        Load existing task tree from database
        
        Args:
            tasks: List of task IDs (strings) or task dictionaries with 'id' field
            db_session: Database session
            
        Returns:
            Root TaskTreeNode
        """
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        # Extract task IDs
        task_ids = []
        for task in tasks:
            if isinstance(task, str):
                task_ids.append(task)
            elif isinstance(task, dict):
                task_id = task.get("id")
                if not task_id:
                    raise ValueError("Task dictionary must have 'id' field when create_if_not_exists=False")
                task_ids.append(task_id)
            else:
                raise ValueError(f"Invalid task format: {task}")
        
        if not task_ids:
            raise ValueError("No valid task IDs provided")
        
        # Load tasks from database
        task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
        loaded_tasks = []
        for task_id in task_ids:
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found in database")
            loaded_tasks.append(task)
        
        # Find root task (no parent_id)
        root_task = None
        for task in loaded_tasks:
            if not task.parent_id:
                root_task = task
                break
        
        if not root_task:
            raise ValueError("No root task found (task without parent_id)")
        
        # Build task tree recursively
        def build_node(task: TaskModel) -> TaskTreeNode:
            """Recursively build tree node"""
            node = TaskTreeNode(task)
            # Find children
            for child_task in loaded_tasks:
                if child_task.parent_id == task.id:
                    child_node = build_node(child_task)
                    node.add_child(child_node)
            return node
        
        root_node = build_node(root_task)
        logger.info(f"Loaded existing task tree: root {root_task.id} with {len(root_node.children)} direct children")
        
        return root_node
    
    async def _collect_all_dependencies(
        self,
        task_id: str,
        task_repository,
        collected: set,
        processed: set,
        all_tasks_in_tree: List
    ) -> set:
        """
        Recursively collect all dependencies (including transitive dependencies) for a task
        
        Args:
            task_id: Task ID to collect dependencies for
            task_repository: TaskRepository instance
            collected: Set of already collected dependency task IDs (output)
            processed: Set of already processed task IDs (to avoid cycles)
            all_tasks_in_tree: List of all tasks in the tree (for lookup)
            
        Returns:
            Set of task IDs that are dependencies (including transitive)
            Note: The target task itself is NOT included in the result
        """
        # Avoid processing the same task twice (cycle detection)
        if task_id in processed:
            return collected
        
        # Find the task in the tree
        task = None
        for t in all_tasks_in_tree:
            if t.id == task_id:
                task = t
                break
        
        if not task:
            return collected
        
        # Mark as processed to avoid cycles
        processed.add(task_id)
        
        # Get dependencies from task
        dependencies = task.dependencies or []
        if not dependencies:
            return collected
        
        # Process each dependency
        for dep in dependencies:
            dep_id = None
            if isinstance(dep, dict):
                dep_id = dep.get("id")
            elif isinstance(dep, str):
                dep_id = dep
            
            if dep_id and dep_id not in collected:
                # Add dependency to collected set
                collected.add(dep_id)
                # Recursively collect dependencies of this dependency
                collected = await self._collect_all_dependencies(
                    dep_id, task_repository, collected, processed, all_tasks_in_tree
                )
        
        return collected
    
    def _build_subtree_with_dependencies(
        self,
        target_task_id: str,
        full_tree: TaskTreeNode,
        required_task_ids: set
    ) -> Optional[TaskTreeNode]:
        """
        Build a subtree containing the target task and all its dependencies
        
        This method builds a minimal subtree that includes:
        - The target task
        - All dependency tasks (including transitive dependencies)
        - All ancestor nodes needed to maintain tree structure
        
        Args:
            target_task_id: ID of the target task to execute
            full_tree: TaskTreeNode of the full tree
            required_task_ids: Set of task IDs that must be included (target + dependencies)
            
        Returns:
            TaskTreeNode containing target task and dependencies, or None if not found
        """
        def find_node(node: TaskTreeNode, task_id: str) -> Optional[TaskTreeNode]:
            """Find a node by task ID in the tree"""
            if node.task.id == task_id:
                return node
            for child in node.children:
                found = find_node(child, task_id)
                if found:
                    return found
            return None
        
        def collect_ancestors(node: TaskTreeNode, task_id: str, ancestors: set) -> bool:
            """Collect all ancestor nodes of a task"""
            if node.task.id == task_id:
                return True
            for child in node.children:
                if collect_ancestors(child, task_id, ancestors):
                    ancestors.add(node.task.id)
                    return True
            return False
        
        def build_subtree(node: TaskTreeNode, required_ids: set, ancestor_ids: set) -> Optional[TaskTreeNode]:
            """Build subtree containing required tasks and their ancestors"""
            # Check if this node is required or is an ancestor of a required task
            is_required = node.task.id in required_ids
            is_ancestor = node.task.id in ancestor_ids
            
            if not is_required and not is_ancestor:
                # Check if any descendant is required
                def check_descendants(n: TaskTreeNode) -> bool:
                    if n.task.id in required_ids or n.task.id in ancestor_ids:
                        return True
                    for child in n.children:
                        if check_descendants(child):
                            return True
                    return False
                
                if not check_descendants(node):
                    return None
            
            # Create new node for this task
            new_node = TaskTreeNode(node.task)
            
            # Process children
            for child in node.children:
                child_subtree = build_subtree(child, required_ids, ancestor_ids)
                if child_subtree:
                    new_node.add_child(child_subtree)
            
            return new_node
        
        # Find target task node
        target_node = find_node(full_tree, target_task_id)
        if not target_node:
            return None
        
        # Collect all ancestor nodes for required tasks
        ancestor_ids = set()
        for req_id in required_task_ids:
            collect_ancestors(full_tree, req_id, ancestor_ids)
        
        # Build subtree including required tasks and their ancestors
        return build_subtree(full_tree, required_task_ids, ancestor_ids)
    
    async def execute_task_by_id(
        self,
        task_id: str,
        use_streaming: bool = False,
        streaming_callbacks_context: Optional[Any] = None,
        use_demo: bool = False,
        db_session: Optional[Union[Session, AsyncSession]] = None
    ) -> Dict[str, Any]:
        """
        Execute a task by ID with automatic dependency handling
        
        This method supports executing both root tasks and child tasks:
        - Root task: Executes the entire task tree
        - Child task: Executes the task and all its dependencies (including transitive dependencies)
        
        Args:
            task_id: Task ID to execute
            use_streaming: Whether to use streaming mode
            streaming_callbacks_context: Context for streaming callbacks (if use_streaming is True)
            db_session: Optional database session (defaults to get_default_session())
            use_demo: If True, executors return demo data instead of executing (default: False)
                     This is an execution option, not a task input. It's passed to TaskManager
                     and used to determine whether to return demo data.
            
        Returns:
            Execution result dictionary with status, progress, and root_task_id
        """
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        # Get database session
        if db_session is None:
            async with create_pooled_session() as session:
                return await self.execute_task_by_id(
                    task_id=task_id,
                    use_streaming=use_streaming,
                    streaming_callbacks_context=streaming_callbacks_context,
                    use_demo=use_demo,
                    db_session=session,
                )
        
        # Create repository
        task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
        
        # Get task
        task = await task_repository.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Get root task ID (traverse up to find root)
        root_task = await task_repository.get_root_task(task)
        root_task_id = root_task.id
        
        # Check if the task is a root task (no parent_id)
        is_root_task = task.parent_id is None
        
        # Build full task tree starting from root task
        full_task_tree = await task_repository.build_task_tree(root_task)
        
        # Determine which tasks to execute
        if is_root_task:
            # If it's a root task, execute the entire tree
            task_tree = full_task_tree
            logger.info(f"Executing root task {task_id}: full tree will be executed")
        else:
            # If it's a child task, collect all dependencies (including transitive)
            # Get all tasks in the tree for dependency lookup
            all_tasks_in_tree = await task_repository.get_all_tasks_in_tree(root_task)
            
            # Collect all dependencies recursively (excluding the target task itself)
            dependency_ids = await self._collect_all_dependencies(
                task_id, task_repository, set(), set(), all_tasks_in_tree
            )
            # Add the target task itself and all its dependencies
            required_task_ids = dependency_ids.copy()
            required_task_ids.add(task_id)
            
            logger.info(
                f"Executing child task {task_id}: will execute task and {len(required_task_ids) - 1} dependencies"
            )
            
            # Build subtree containing target task and all dependencies
            task_tree = self._build_subtree_with_dependencies(
                task_id, full_task_tree, required_task_ids
            )
            
            if not task_tree:
                raise ValueError(f"Could not build subtree for task {task_id}")
        
        # Execute task tree using existing method
        execution_result = await self.execute_task_tree(
            task_tree=task_tree,
            root_task_id=root_task_id,
            use_streaming=use_streaming,
            streaming_callbacks_context=streaming_callbacks_context,
            use_demo=use_demo,
            db_session=db_session
        )
        
        return execution_result

