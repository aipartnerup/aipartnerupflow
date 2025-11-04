"""
Agent executor for A2A protocol that handles task tree execution
"""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, new_agent_parts_message
from a2a.types import DataPart
from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List, Type
from datetime import datetime, timezone

from aipartnerupflow.core.execution.task_manager import TaskManager
from aipartnerupflow.core.types import TaskTreeNode, TaskPreHook, TaskPostHook
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage import get_default_session
from aipartnerupflow.api.event_queue_bridge import EventQueueBridge
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class AIPartnerUpFlowAgentExecutor(AgentExecutor):
    """
    Agent executor that integrates task tree execution functionality
    
    Receives tasks array and constructs TaskTreeNode internally,
    then executes using TaskManager.
    
    Supports custom TaskModel classes via task_model_class parameter.
    """

    def __init__(
        self,
        task_model_class: Optional[Type[TaskModel]] = None,
        pre_hooks: Optional[List[TaskPreHook]] = None,
        post_hooks: Optional[List[TaskPostHook]] = None
    ):
        """
        Initialize agent executor
        
        Args:
            task_model_class: Optional custom TaskModel class.
                             If provided, will be used when creating TaskManager.
                             If None, default TaskModel will be used.
            pre_hooks: Optional list of pre-execution hook functions.
                      Will be passed to TaskManager when created.
            post_hooks: Optional list of post-execution hook functions.
                       Will be passed to TaskManager when created.
        """
        self.task_model_class = task_model_class
        self.pre_hooks = pre_hooks
        self.post_hooks = post_hooks
        logger.info(
            f"Initialized AIPartnerUpFlowAgentExecutor "
            f"(TaskModel: {task_model_class.__name__ if task_model_class else 'TaskModel'}, "
            f"pre_hooks: {len(pre_hooks) if pre_hooks else 0}, "
            f"post_hooks: {len(post_hooks) if post_hooks else 0})"
        )

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
            
            # Generate task IDs if not present
            task_id = context.task_id or str(uuid.uuid4())
            context_id = context.context_id or str(uuid.uuid4())
            
            # Get database session
            db_session = get_default_session()
            
            logger.info(f"Creating task tree from {len(tasks)} tasks")
            
            # Build TaskTreeNode from tasks array
            task_tree = self._build_task_tree_from_tasks(tasks)
            
            # Save tasks to database first
            await self._save_tasks_to_database(task_tree, db_session)
            
            # Create TaskManager with hooks
            task_manager = TaskManager(
                db_session,
                root_task_id=task_id,
                pre_hooks=self.pre_hooks,
                post_hooks=self.post_hooks
            )
            
            # Execute task tree
            await task_manager.distribute_task_tree(task_tree, use_callback=True)
            
            # Execution completed
            # Get final status from task tree
            final_status = task_tree.calculate_status()
            final_progress = task_tree.calculate_progress()
            
            # Get root task result
            root_result = {
                "status": final_status,
                "progress": final_progress,
                "root_task_id": task_tree.task.id,
                "task_count": len(tasks)
            }
            
            # Send result as TaskStatusUpdateEvent
            completed_status = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=TaskState.completed if final_status == "completed" else TaskState.failed,
                    message=new_agent_parts_message([DataPart(data=root_result)])
                ),
                final=True
            )
            await event_queue.enqueue_event(completed_status)
            
            return root_result
            
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
            
            # Build TaskTreeNode from tasks array
            task_tree = self._build_task_tree_from_tasks(tasks)
            
            logger.info(f"Built task tree with root task: {task_tree.task.id}")
            
            # Save tasks to database first
            await self._save_tasks_to_database(task_tree, db_session)
            
            # Create TaskManager with streaming support and hooks
            task_manager = TaskManager(
                db_session,
                root_task_id=context.task_id,
                pre_hooks=self.pre_hooks,
                post_hooks=self.post_hooks
            )
            task_manager.stream = True
            
            # Connect streaming callbacks to event queue
            # Bridge TaskManager's StreamingCallbacks to A2A EventQueue
            event_queue_bridge = EventQueueBridge(event_queue, context)
            task_manager.streaming_callbacks.set_streaming_context(event_queue_bridge, context)
            
            # Execute task tree with streaming
            await task_manager.distribute_task_tree_with_streaming(task_tree, use_callback=True)
            
            # Execution happens with streaming callbacks
            # Final status will be sent by TaskManager via streaming_callbacks
            # Wait a bit for execution to complete (in real scenario, this would be managed differently)
            logger.info("Task tree execution started with streaming")
            
            # Return initial response - actual result will come via streaming
            return {
                "status": "in_progress",
                "task_count": len(tasks),
                "root_task_id": task_tree.task.id
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
            
            # Create TaskModel
            task_model = TaskModel(
                id=task_id,
                parent_id=parent_id,
                user_id=user_id,
                name=task_dict.get("name", "Unnamed Task"),
                status=task_dict.get("status", "pending"),
                priority=task_dict.get("priority", 1),
                has_children=task_dict.get("has_children", False),
                dependencies=task_dict.get("dependencies", []),
                progress=task_dict.get("progress", 0.0),
                input_data=task_dict.get("input_data", {}),
                params=task_dict.get("params", {}),
                schemas=task_dict.get("schemas", {}),
                result=task_dict.get("result"),
                error=task_dict.get("error"),
            )
            
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

    async def _save_tasks_to_database(
        self,
        task_tree: TaskTreeNode,
        db_session: Any
    ):
        """
        Save all tasks in the tree to database
        
        Args:
            task_tree: Root task tree node
            db_session: Database session
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        
        is_async = isinstance(db_session, AsyncSession)
        
        async def save_node_async(node: TaskTreeNode):
            """Recursively save tasks (async)"""
            # Check if task already exists
            existing = await db_session.get(TaskModel, node.task.id)
            
            if not existing:
                db_session.add(node.task)
            
            # Recursively save children
            for child in node.children:
                await save_node_async(child)
        
        def save_node_sync(node: TaskTreeNode):
            """Recursively save tasks (sync)"""
            # Check if task already exists
            from sqlalchemy import select
            result = db_session.execute(select(TaskModel).filter(TaskModel.id == node.task.id))
            existing = result.scalar_one_or_none()
            
            if not existing:
                db_session.add(node.task)
            
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

