"""
Agent executor for A2A protocol that handles task tree execution
"""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, new_agent_parts_message
from a2a.types import DataPart, Task, Artifact, Part
from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState
import uuid
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable
from datetime import datetime, timezone

from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.execution.task_creator import TaskCreator
from aipartnerupflow.core.storage import get_default_session
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class
from aipartnerupflow.api.a2a.event_queue_bridge import EventQueueBridge
from aipartnerupflow.api.a2a.task_routes_adapter import TaskRoutesAdapter
from aipartnerupflow.api.routes.tasks import TaskRoutes
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class AIPartnerUpFlowAgentExecutor(AgentExecutor):
    """
    Agent executor that integrates task tree execution functionality
    
    Receives tasks array and constructs TaskTreeNode internally,
    then executes using TaskManager.
    
    Supports custom TaskModel classes via task_model_class parameter.
    """

    def __init__(self, task_routes: Optional[TaskRoutes] = None, verify_token_func: Optional["Callable[[str], Optional[dict]]"] = None):
        """
        Initialize agent executor
        
        Configuration (task_model_class, hooks) is automatically retrieved from
        the global config registry. Use decorators to register hooks before initialization.
        
        Example:
            from aipartnerupflow import register_pre_hook, set_task_model_class
            
            @register_pre_hook
            async def my_hook(task):
                ...
            
            set_task_model_class(MyTaskModel)
            executor = AIPartnerUpFlowAgentExecutor()  # Configuration from registry
        
        Args:
            task_routes: Optional TaskRoutes instance. If None, will be created automatically.
            verify_token_func: Optional JWT verification function for permission checking.
        """
        # Initialize task executor which manages task execution and tracking
        self.task_executor = TaskExecutor()
        # Refresh config to ensure we pick up hooks registered via decorators
        # (important for tests where hooks may be registered after TaskExecutor singleton initialization)
        self.task_executor.refresh_config()
        self.task_model_class = get_task_model_class()
        
        # Initialize TaskRoutes adapter for task management operations
        # If task_routes is not provided, create it with default configuration
        if task_routes is None:
            # Create TaskRoutes with default configuration
            # Note: verify_token_func and verify_permission_func will be None
            # Permission checking will be handled at the middleware level
            task_routes = TaskRoutes(
                task_model_class=self.task_model_class,
                verify_token_func=verify_token_func,
                verify_permission_func=None
            )
        
        self.task_routes_adapter = TaskRoutesAdapter(
            task_routes=task_routes,
            verify_token_func=verify_token_func
        )
        
        logger.info(
            f"Initialized AIPartnerUpFlowAgentExecutor "
            f"(TaskModel: {self.task_model_class.__name__})"
        )
    
    @property
    def pre_hooks(self):
        """Get pre-hooks from task executor"""
        return self.task_executor.pre_hooks
    
    @property
    def post_hooks(self):
        """Get post-hooks from task executor"""
        return self.task_executor.post_hooks

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> Any:
        """
        Execute task management operation or task tree execution
        
        This method routes to different handlers based on the method/skill_id:
        - If method is "tasks.execute" or skill_id is "tasks.execute" (or "execute_task_tree" for backward compatibility): Execute task tree (original behavior)
        - Otherwise: Route to appropriate TaskRoutes handler via adapter
        
        Args:
            context: Request context from A2A protocol
            event_queue: Event queue for streaming updates
            
        Returns:
            Result from handler (Task object, List[Task], or dict) or None for streaming mode
        """
        logger.debug(f"Context configuration: {context.configuration}")
        logger.debug(f"Context metadata: {context.metadata}")
        
        # Extract method from context
        method = self.task_routes_adapter.extract_method(context)
        
        # If method is tasks.execute or skill_id is tasks.execute (or execute_task_tree for backward compatibility), use original execution logic
        skill_id = context.metadata.get("skill_id") if context.metadata else None
        if method == "tasks.execute" or skill_id == "tasks.execute" or skill_id == "execute_task_tree":
            # Original task execution behavior
            use_streaming_mode = self._should_use_streaming_mode(context)
            
            if use_streaming_mode:
                # Streaming mode: push multiple status update events
                await self._execute_streaming_mode(context, event_queue)
                return None
            else:
                # Simple mode: return result directly
                return await self._execute_simple_mode(context, event_queue)
        
        # For other methods, route to TaskRoutes handlers via adapter
        if method:
            return await self._execute_task_management_method(context, event_queue, method)
        
        # If no method specified, default to task execution (backward compatibility)
        logger.warning("No method specified in context, defaulting to task execution")
        use_streaming_mode = self._should_use_streaming_mode(context)
        
        if use_streaming_mode:
            await self._execute_streaming_mode(context, event_queue)
            return None
        else:
            return await self._execute_simple_mode(context, event_queue)

    def _should_use_streaming_mode(self, context: RequestContext) -> bool:
        """
        Check if streaming mode should be used
        
        Streaming mode is determined by metadata.stream flag
        
        Args:
            context: Request context
            
        Returns:
            True if streaming mode should be used
        """
        # Check metadata.stream (only configuration, not task data)
        if context.metadata and context.metadata.get("stream") is True:
            logger.debug("Using streaming mode from metadata.stream")
            return True
        
        # Default to simple mode
        logger.debug("Using simple mode")
        return False
    
    async def _execute_simple_mode(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> Any:
        """
        Simple mode: return result directly, no intermediate status updates
        
        Args:
            context: Request context
            event_queue: Event queue
        """
        try:
            # Get database session
            db_session = get_default_session()
            
            # Check if copy_execution is enabled via metadata
            copy_execution = context.metadata.get("copy_execution", False) if context.metadata else False
            copy_children = context.metadata.get("copy_children", False) if context.metadata else False
            original_task_id = None
            
            if copy_execution:
                # If copy_execution is True, check if task_id is provided in metadata
                task_id = context.metadata.get("task_id") if context.metadata else None
                if not task_id:
                    raise ValueError("task_id is required in metadata when copy_execution=True")
                
                # Get the original task from database
                task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
                original_task = await task_repository.get_task_by_id(task_id)
                if not original_task:
                    raise ValueError(f"Task {task_id} not found")
                
                original_task_id = task_id
                
                # Copy the task (and children if copy_children=True)
                logger.info(f"Copying task {task_id} before execution (copy_children={copy_children})")
                task_creator = TaskCreator(db_session)
                copied_tree = await task_creator.create_task_copy(original_task, children=copy_children)
                logger.info(f"Task copied: original={original_task_id}, copy={copied_tree.task.id}")
                
                # Convert copied tree to tasks array format
                tasks = self._tree_node_to_tasks_array(copied_tree)
            else:
                # Extract tasks array from context
                tasks = self._extract_tasks_from_context(context)
                if not tasks:
                    raise ValueError("No tasks provided in request")
            
            # Log extracted tasks for debugging
            logger.debug(f"Extracted tasks with IDs: {[t.get('id') for t in tasks]}")
            
            # Generate context ID if not present
            context_id = context.context_id or str(uuid.uuid4())
            
            # Execute tasks using TaskExecutor (handles building tree, saving, and execution)
            # Behavior controlled by global configuration (get_require_existing_tasks())
            # Default: require_existing_tasks=False (auto-create for convenience)
            # root_task_id=None means use the actual root task ID from the created task tree
            # Allow override via context metadata for testing scenarios
            require_existing_tasks = context.metadata.get("require_existing_tasks") if context.metadata else None
            if require_existing_tasks is None:
                require_existing_tasks = None  # Use global configuration
            
            # Extract use_demo from metadata, message.metadata, or configuration
            use_demo = False
            if context.metadata:
                use_demo = context.metadata.get("use_demo", False)
            # Also check message.metadata if available (A2A protocol supports metadata in message)
            if not use_demo and context.message and hasattr(context.message, "metadata"):
                message_metadata = context.message.metadata
                if isinstance(message_metadata, dict):
                    use_demo = message_metadata.get("use_demo", False)
            if not use_demo and context.configuration:
                try:
                    config_dict = context.configuration.model_dump(exclude_none=True) if hasattr(context.configuration, 'model_dump') else context.configuration.dict(exclude_none=True)
                    use_demo = config_dict.get("use_demo", False)
                except (AttributeError, TypeError):
                    pass
            
            execution_result = await self.task_executor.execute_tasks(
                tasks=tasks,
                root_task_id=None,  # Use actual root task ID from created task tree
                use_streaming=False,
                require_existing_tasks=require_existing_tasks,  # Allow override via metadata
                use_demo=use_demo,
                db_session=db_session
            )
            
            logger.debug(f"Execution result root_task_id: {execution_result.get('root_task_id')}")
            
            # Get root task result - use actual root task ID from execution result
            final_status = execution_result["status"]
            actual_root_task_id = execution_result["root_task_id"]
            
            # A2A protocol requires Task object with id matching context.task_id
            # Use context.task_id if available, otherwise use actual_root_task_id
            task_id = context.task_id or actual_root_task_id
            context_id = context.context_id or actual_root_task_id
            
            # Get root task from database to create Task object
            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            root_task_model = await task_repository.get_task_by_id(actual_root_task_id)
            
            if not root_task_model:
                raise ValueError(f"Root task {actual_root_task_id} not found after execution")
            
            # Create A2A Task object with matching task_id
            # Map TaskModel to A2A Task format
            task_state = TaskState.completed if final_status == "completed" else TaskState.failed
            task_status_message = f"Task execution {final_status}"
            
            # Create artifacts from execution result
            # Artifact requires artifact_id and parts (list of Part)
            artifacts = [
                Artifact(
                    artifact_id=str(uuid.uuid4()),
                    parts=[
                        Part(
                            root=DataPart(
                                kind="data",
                                data={
                                    "status": final_status,
                                    "progress": float(execution_result["progress"]),
                                    "root_task_id": actual_root_task_id,
                                    "task_count": len(tasks),
                                    "result": root_task_model.result
                                }
                            )
                        )
                    ]
                )
            ]
            
            # Create Task object with matching task_id
            # Add protocol identifier to metadata for easy identification
            metadata = {
                "protocol": "a2a",
                "root_task_id": actual_root_task_id,
            }
            if root_task_model.user_id:
                metadata["user_id"] = root_task_model.user_id
            if original_task_id:
                metadata["original_task_id"] = original_task_id
            
            a2a_task = Task(
                id=task_id,  # Must match context.task_id
                context_id=context_id,
                kind="task",
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_text_message(task_status_message)
                ),
                artifacts=artifacts,
                metadata=metadata
            )
            
            # Send result as TaskStatusUpdateEvent
            completed_status = TaskStatusUpdateEvent(
                task_id=task_id,  # Use context.task_id
                context_id=context_id,
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_parts_message([DataPart(data={
                        "protocol": "a2a",
                        "status": final_status,
                        "progress": execution_result["progress"],
                        "root_task_id": actual_root_task_id,
                        "task_count": len(tasks)
                    })])
                ),
                final=True
            )
            await event_queue.enqueue_event(completed_status)
            
            return a2a_task
            
        except Exception as e:
            logger.error(f"Error in simple mode execution: {str(e)}", exc_info=True)
            
            task_id = context.task_id or str(uuid.uuid4())
            context_id = context.context_id or str(uuid.uuid4())
            
            # Send error as TaskStatusUpdateEvent
            error_status = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=new_agent_text_message(f"Error: {str(e)}")
                ),
                final=True
            )
            await event_queue.enqueue_event(error_status)
            raise

    async def _execute_streaming_mode(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> Any:
        """
        Streaming mode: push multiple status update events with real-time task progress
        
        Args:
            context: Request context
            event_queue: Event queue
        """
        if not context.task_id or not context.context_id:
            raise ValueError("Task ID and Context ID are required for streaming mode")
        
        logger.info("Starting streaming mode execution")
        logger.info(f"Task ID: {context.task_id}, Context ID: {context.context_id}")
        
        try:
            # Get database session
            db_session = get_default_session()
            
            # Check if copy_execution is enabled via metadata
            copy_execution = context.metadata.get("copy_execution", False) if context.metadata else False
            copy_children = context.metadata.get("copy_children", False) if context.metadata else False
            original_task_id = None
            
            if copy_execution:
                # If copy_execution is True, check if task_id is provided in metadata
                task_id = context.metadata.get("task_id") if context.metadata else None
                if not task_id:
                    raise ValueError("task_id is required in metadata when copy_execution=True")
                
                # Get the original task from database
                task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
                original_task = await task_repository.get_task_by_id(task_id)
                if not original_task:
                    raise ValueError(f"Task {task_id} not found")
                
                original_task_id = task_id
                
                # Copy the task (and children if copy_children=True)
                logger.info(f"Copying task {task_id} before execution (copy_children={copy_children})")
                task_creator = TaskCreator(db_session)
                copied_tree = await task_creator.create_task_copy(original_task, children=copy_children)
                logger.info(f"Task copied: original={original_task_id}, copy={copied_tree.task.id}")
                
                # Convert copied tree to tasks array format
                tasks = self._tree_node_to_tasks_array(copied_tree)
            else:
                # Extract tasks array from context
                tasks = self._extract_tasks_from_context(context)
                if not tasks:
                    raise ValueError("No tasks provided in request")
            
            logger.info(f"Received {len(tasks)} tasks to execute")
            
            # Connect streaming callbacks to event queue
            # Bridge TaskManager's StreamingCallbacks to A2A EventQueue
            # Pass original_task_id to bridge if copy_execution was used
            event_queue_bridge = EventQueueBridge(event_queue, context)
            if original_task_id:
                # Store original_task_id in bridge for inclusion in events
                event_queue_bridge.original_task_id = original_task_id
            
            # Execute tasks using TaskExecutor with streaming (handles building tree, saving, and execution)
            # Behavior controlled by global configuration (get_require_existing_tasks())
            # Default: require_existing_tasks=False (auto-create for convenience)
            # root_task_id=None means use the actual root task ID from the created task tree
            # Extract use_demo from metadata, message.metadata, or configuration
            use_demo = False
            if context.metadata:
                use_demo = context.metadata.get("use_demo", False)
            # Also check message.metadata if available (A2A protocol supports metadata in message)
            if not use_demo and context.message and hasattr(context.message, "metadata"):
                message_metadata = context.message.metadata
                if isinstance(message_metadata, dict):
                    use_demo = message_metadata.get("use_demo", False)
            if not use_demo and context.configuration:
                try:
                    config_dict = context.configuration.model_dump(exclude_none=True) if hasattr(context.configuration, 'model_dump') else context.configuration.dict(exclude_none=True)
                    use_demo = config_dict.get("use_demo", False)
                except (AttributeError, TypeError):
                    pass
            
            execution_result = await self.task_executor.execute_tasks(
                tasks=tasks,
                root_task_id=None,  # Use actual root task ID from created task tree
                use_streaming=True,
                streaming_callbacks_context=event_queue_bridge,
                require_existing_tasks=None,  # Use global configuration (default: False, auto-create)
                use_demo=use_demo,
                db_session=db_session
            )
            
            # Execution happens with streaming callbacks
            # Final status will be sent by TaskManager via streaming_callbacks
            logger.info("Task tree execution started with streaming")
            
            # Return initial response - actual result will come via streaming
            result = {
                "status": "in_progress",
                "task_count": len(tasks),
                "root_task_id": execution_result["root_task_id"]
            }
            if original_task_id:
                result["original_task_id"] = original_task_id
            return result
            
        except Exception as e:
            logger.error(f"Error in streaming mode execution: {str(e)}", exc_info=True)
            await self._send_error_update(event_queue, context, str(e))
            raise

    def _extract_tasks_from_context(self, context: RequestContext) -> List[Dict[str, Any]]:
        """
        Extract tasks array from request context
        
        Tasks should be in context.message.parts as an array of DataPart objects,
        where each part contains a task object.
        
        Args:
            context: Request context
            
        Returns:
            List of task dictionaries
        """
        tasks = []
        
        # Extract tasks directly from message parts
        # parts is an array, each part should contain a task
        if context.message and hasattr(context.message, "parts"):
            parts = context.message.parts
            
            # Try to extract tasks array from parts
            # Method 1: Check if parts[0] contains a "tasks" array
            if parts and len(parts) > 0:
                first_part_data = self._extract_single_part_data(parts[0])
                
                # Check if first part contains "tasks" key (wrapped format)
                if isinstance(first_part_data, dict) and "tasks" in first_part_data:
                    tasks = first_part_data["tasks"]
                    if not isinstance(tasks, list):
                        raise ValueError("Tasks must be a list")
                else:
                    # Method 2: Each part is a task (direct format)
                    # Extract each part as a task
                    for i, part in enumerate(parts):
                        task_data = self._extract_single_part_data(part)
                        if task_data:
                            if isinstance(task_data, dict):
                                tasks.append(task_data)
                            else:
                                logger.warning(f"Part {i} does not contain a valid task object")
        
        if not tasks:
            raise ValueError("No tasks found in context.message.parts")
        
        logger.info(f"Extracted {len(tasks)} tasks from context.message.parts")
        return tasks

    def _tree_node_to_tasks_array(self, root_node) -> List[Dict[str, Any]]:
        """
        Convert TaskTreeNode to tasks array format for execution
        
        Args:
            root_node: Root TaskTreeNode
            
        Returns:
            List of task dictionaries in tasks array format
        """
        from aipartnerupflow.core.types import TaskTreeNode
        
        tasks = []
        
        def collect_tasks(node: TaskTreeNode):
            """Recursively collect tasks from tree"""
            # Convert TaskModel to dict
            task_dict = node.task.to_dict()
            
            # Set parent_id if node has parent
            # Note: In TaskTreeNode, parent is not directly stored, but we can infer from tree structure
            # For now, we'll rely on the task's parent_id field which should be set during copy
            
            # Add to tasks array
            tasks.append(task_dict)
            
            # Recursively process children
            for child in node.children:
                collect_tasks(child)
        
        collect_tasks(root_node)
        return tasks
    
    def _extract_single_part_data(self, part) -> Any:
        """
        Extract data from a single part
        
        Args:
            part: Single A2A part object
            
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

    async def _send_error_update(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        error: str
    ):
        """Helper method to send error updates"""
        error_data = {
            "protocol": "a2a",
            "status": "failed",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        status_update = TaskStatusUpdateEvent(
            task_id=context.task_id or "unknown",
            context_id=context.context_id or "unknown",
            status=TaskStatus(
                state=TaskState.failed,
                message=new_agent_parts_message([DataPart(data=error_data)])
            ),
            final=True
        )
        await event_queue.enqueue_event(status_update)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """
        Cancel task execution
        
        This method:
        1. Extracts task ID from RequestContext
        2. Calls TaskExecutor.cancel_task() to cancel the task
        3. Sends TaskStatusUpdateEvent via EventQueue with cancellation status
        
        Args:
            context: Request context from A2A protocol
            event_queue: Event queue for streaming updates
        """
        try:
            # Step 1: Extract task ID from context
            # Priority: context.task_id > context.context_id > metadata.task_id > metadata.context_id
            task_id = None
            if context.task_id:
                task_id = context.task_id
                logger.debug(f"Using context.task_id: {task_id}")
            elif context.context_id:
                task_id = context.context_id
                logger.debug(f"Using context.context_id: {task_id}")
            elif context.metadata:
                task_id = context.metadata.get("task_id") or context.metadata.get("context_id")
                if task_id:
                    logger.debug(f"Using metadata task_id/context_id: {task_id}")
            
            if not task_id:
                error_msg = "Task ID not found in context. Provide task_id or context_id in context or metadata."
                logger.error(error_msg)
                await self._send_cancel_error(event_queue, context, error_msg)
                return
            
            # Step 2: Extract optional parameters from metadata
            metadata = context.metadata or {}
            error_message = metadata.get("error_message")
            # Note: force parameter is not used by TaskExecutor.cancel_task(), 
            # but we can log it for reference
            force = metadata.get("force", False)
            if force:
                logger.info(f"Force cancellation requested for task {task_id}")
            
            # Step 3: Get database session and call TaskExecutor.cancel_task()
            db_session = get_default_session()
            logger.info(f"Cancelling task {task_id}")
            
            cancel_result = await self.task_executor.cancel_task(
                task_id=task_id,
                error_message=error_message,
                db_session=db_session
            )
            
            # Step 4: Create TaskStatusUpdateEvent based on cancellation result
            # Map status: "cancelled" -> TaskState.canceled, "failed" -> TaskState.failed
            result_status = cancel_result.get("status", "failed")
            task_state = TaskState.canceled if result_status == "cancelled" else TaskState.failed
            
            # Build event data
            event_data = {
                "protocol": "a2a",
                "status": result_status,
                "message": cancel_result.get("message", "Cancellation completed"),
            }
            
            # Add optional fields if available
            if "token_usage" in cancel_result and cancel_result["token_usage"]:
                event_data["token_usage"] = cancel_result["token_usage"]
            
            if "result" in cancel_result and cancel_result["result"]:
                event_data["result"] = cancel_result["result"]
            
            if "error" in cancel_result and cancel_result["error"]:
                event_data["error"] = cancel_result["error"]
            
            # Add timestamp
            event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Step 5: Create and send TaskStatusUpdateEvent
            status_update = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context.context_id or task_id,
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_parts_message([DataPart(data=event_data)])
                ),
                final=True
            )
            
            await event_queue.enqueue_event(status_update)
            logger.info(f"Task {task_id} cancellation completed with status: {result_status}")
            
        except Exception as e:
            logger.error(f"Error cancelling task: {str(e)}", exc_info=True)
            await self._send_cancel_error(event_queue, context, f"Failed to cancel task: {str(e)}")
    
    async def _send_cancel_error(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        error: str
    ):
        """
        Helper method to send cancellation error updates
        
        Args:
            event_queue: Event queue
            context: Request context
            error: Error message
        """
        # Try to extract task_id for error event
        task_id = context.task_id or context.context_id
        if not task_id and context.metadata:
            task_id = context.metadata.get("task_id") or context.metadata.get("context_id")
        task_id = task_id or "unknown"
        
        error_data = {
            "protocol": "a2a",
            "status": "failed",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        status_update = TaskStatusUpdateEvent(
            task_id=task_id,
            context_id=context.context_id or task_id,
            status=TaskStatus(
                state=TaskState.failed,
                message=new_agent_parts_message([DataPart(data=error_data)])
            ),
            final=True
        )
        await event_queue.enqueue_event(status_update)
    
    async def _execute_task_management_method(
        self,
        context: RequestContext,
        event_queue: EventQueue,
        method: str
    ) -> Any:
        """
        Execute a task management method via TaskRoutes adapter
        
        Args:
            context: Request context from A2A protocol
            event_queue: Event queue for streaming updates
            method: Method name (e.g., "tasks.create", "tasks.get")
            
        Returns:
            Result in A2A protocol format (Task, List[Task], or dict)
        """
        try:
            request_id = str(uuid.uuid4())
            
            # Extract parameters from context
            params = self.task_routes_adapter.extract_params(context, method)
            
            logger.info(f"Executing task management method: {method} with params: {params}")
            
            # Call handler via adapter
            result = await self.task_routes_adapter.call_handler(
                method=method,
                params=params,
                context=context,
                request_id=request_id
            )
            
            # Convert result to A2A protocol format
            a2a_result = self.task_routes_adapter.convert_result_to_a2a_format(
                result=result,
                method=method,
                context=context
            )
            
            # Send result as TaskStatusUpdateEvent if it's a Task or list of Tasks
            if isinstance(a2a_result, Task):
                # Single task result
                status_update = TaskStatusUpdateEvent(
                    task_id=a2a_result.id,
                    context_id=a2a_result.context_id,
                    status=a2a_result.status,
                    final=True
                )
                await event_queue.enqueue_event(status_update)
            elif isinstance(a2a_result, list) and a2a_result and isinstance(a2a_result[0], Task):
                # List of tasks - send status update for each
                for task in a2a_result:
                    status_update = TaskStatusUpdateEvent(
                        task_id=task.id,
                        context_id=task.context_id,
                        status=task.status,
                        final=True
                    )
                    await event_queue.enqueue_event(status_update)
            elif isinstance(a2a_result, dict):
                # Dictionary result - send as status update
                task_id = a2a_result.get("task_id") or context.task_id or context.context_id
                context_id = a2a_result.get("context_id") or context.context_id or task_id
                
                status_update = TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.completed,
                        message=new_agent_parts_message([DataPart(data=a2a_result)])
                    ),
                    final=True
                )
                await event_queue.enqueue_event(status_update)
            
            return a2a_result
            
        except Exception as e:
            logger.error(f"Error executing task management method {method}: {str(e)}", exc_info=True)
            await self._send_error_update(event_queue, context, f"Error in {method}: {str(e)}")
            raise

