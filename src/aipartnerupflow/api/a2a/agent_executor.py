"""
Agent executor for A2A protocol that handles task tree execution
"""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, new_agent_parts_message
from a2a.types import DataPart, Task, Artifact, Part
from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List, Type
from datetime import datetime, timezone

from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.storage import get_default_session
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.config import get_task_model_class
from aipartnerupflow.api.a2a.event_queue_bridge import EventQueueBridge
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class AIPartnerUpFlowAgentExecutor(AgentExecutor):
    """
    Agent executor that integrates task tree execution functionality
    
    Receives tasks array and constructs TaskTreeNode internally,
    then executes using TaskManager.
    
    Supports custom TaskModel classes via task_model_class parameter.
    """

    def __init__(self):
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
        """
        # Initialize task executor which manages task execution and tracking
        self.task_executor = TaskExecutor()
        # Refresh config to ensure we pick up hooks registered via decorators
        # (important for tests where hooks may be registered after TaskExecutor singleton initialization)
        self.task_executor.refresh_config()
        self.task_model_class = get_task_model_class()
        
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
        Execute task tree from tasks array
        
        Args:
            context: Request context from A2A protocol
            event_queue: Event queue for streaming updates
            
        Returns:
            Result from simple mode execution, or None for streaming mode
        """
        logger.debug(f"Context configuration: {context.configuration}")
        logger.debug(f"Context metadata: {context.metadata}")
        
        # Check if streaming mode should be used
        use_streaming_mode = self._should_use_streaming_mode(context)
        
        if use_streaming_mode:
            # Streaming mode: push multiple status update events
            await self._execute_streaming_mode(context, event_queue)
            return None
        else:
            # Simple mode: return result directly
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
    
    def _should_use_callback(self, context: RequestContext) -> bool:
        """
        Check if callback mode should be used
        
        Callback mode is determined by configuration.push_notification_config
        
        Args:
            context: Request context
            
        Returns:
            True if callback mode should be used
        """
        if context.configuration and hasattr(context.configuration, "push_notification_config"):
            config = context.configuration.push_notification_config
            if config and hasattr(config, "url"):
                logger.debug("Using callback mode from configuration.push_notification_config")
                return True
        
        # Also check if metadata has use_callback flag (backward compatibility)
        if context.metadata and context.metadata.get("use_callback") is True:
            logger.debug("Using callback mode from metadata.use_callback")
            return True
        
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
            # Extract tasks array from context
            tasks = self._extract_tasks_from_context(context)
            if not tasks:
                raise ValueError("No tasks provided in request")
            
            # Log extracted tasks for debugging
            logger.debug(f"Extracted tasks with IDs: {[t.get('id') for t in tasks]}")
            
            # Generate context ID if not present
            context_id = context.context_id or str(uuid.uuid4())
            
            # Get database session
            db_session = get_default_session()
            
            # Execute tasks using TaskExecutor (handles building tree, saving, and execution)
            # Behavior controlled by global configuration (get_require_existing_tasks())
            # Default: require_existing_tasks=False (auto-create for convenience)
            # root_task_id=None means use the actual root task ID from the created task tree
            # Allow override via context metadata for testing scenarios
            require_existing_tasks = context.metadata.get("require_existing_tasks")
            if require_existing_tasks is None:
                require_existing_tasks = None  # Use global configuration
            
            execution_result = await self.task_executor.execute_tasks(
                tasks=tasks,
                root_task_id=None,  # Use actual root task ID from created task tree
                use_streaming=False,
                require_existing_tasks=require_existing_tasks,  # Allow override via metadata
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
            from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
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
            a2a_task = Task(
                id=task_id,  # Must match context.task_id
                context_id=context_id,
                kind="task",
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_text_message(task_status_message)
                ),
                artifacts=artifacts,
                metadata={
                    "root_task_id": actual_root_task_id,
                    "user_id": root_task_model.user_id
                } if root_task_model.user_id else {
                    "root_task_id": actual_root_task_id
                }
            )
            
            # Send result as TaskStatusUpdateEvent
            completed_status = TaskStatusUpdateEvent(
                task_id=task_id,  # Use context.task_id
                context_id=context_id,
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_parts_message([DataPart(data={
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
        
        logger.info(f"Starting streaming mode execution")
        logger.info(f"Task ID: {context.task_id}, Context ID: {context.context_id}")
        
        try:
            # Extract tasks array from context
            tasks = self._extract_tasks_from_context(context)
            if not tasks:
                raise ValueError("No tasks provided in request")
            
            logger.info(f"Received {len(tasks)} tasks to execute")
            
            # Get database session
            db_session = get_default_session()
            
            # Connect streaming callbacks to event queue
            # Bridge TaskManager's StreamingCallbacks to A2A EventQueue
            event_queue_bridge = EventQueueBridge(event_queue, context)
            
            # Execute tasks using TaskExecutor with streaming (handles building tree, saving, and execution)
            # Behavior controlled by global configuration (get_require_existing_tasks())
            # Default: require_existing_tasks=False (auto-create for convenience)
            # root_task_id=None means use the actual root task ID from the created task tree
            execution_result = await self.task_executor.execute_tasks(
                tasks=tasks,
                root_task_id=None,  # Use actual root task ID from created task tree
                use_streaming=True,
                streaming_callbacks_context=event_queue_bridge,
                require_existing_tasks=None,  # Use global configuration (default: False, auto-create)
                db_session=db_session
            )
            
            # Execution happens with streaming callbacks
            # Final status will be sent by TaskManager via streaming_callbacks
            logger.info("Task tree execution started with streaming")
            
            # Return initial response - actual result will come via streaming
            return {
                "status": "in_progress",
                "task_count": len(tasks),
                "root_task_id": execution_result["root_task_id"]
            }
            
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
    
    def _extract_data_from_parts(self, parts) -> Dict[str, Any]:
        """
        Extract structured data from DataPart in message parts (legacy method)
        
        Note: For tasks extraction, use _extract_tasks_from_context instead
        """
        if not parts:
            logger.warning("No parts found")
            return {}
        
        try:
            parts_len = len(parts)
            logger.debug(f"Processing {parts_len} parts")
        except (TypeError, AttributeError):
            logger.warning("Parts object doesn't support len(), treating as empty")
            return {}

        extracted_data = {}
        for i, part in enumerate(parts):
            part_data = self._extract_single_part_data(part)
            if part_data:
                if isinstance(part_data, dict):
                    extracted_data.update(part_data)
                else:
                    extracted_data["raw_data"] = part_data
        
        logger.debug(f"Final extracted_data: {extracted_data}")
        return extracted_data

    async def _send_error_update(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        error: str
    ):
        """Helper method to send error updates"""
        error_data = {
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

    def _create_json_response(self, result: Dict[str, Any]) -> Any:
        """Create a JSON response using DataPart"""
        try:
            data_part = DataPart(data=result)
            response_message = new_agent_parts_message([data_part])
            return response_message
        except Exception as e:
            logger.error(f"Failed to create DataPart response: {str(e)}")
            return new_agent_text_message(json.dumps(result, indent=2))

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """Cancel execution"""
        logger.info("Cancel requested")
        await event_queue.enqueue_event(
            new_agent_text_message("Cancel requested but not fully implemented")
        )

