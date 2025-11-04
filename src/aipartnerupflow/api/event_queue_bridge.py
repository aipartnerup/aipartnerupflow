"""
Bridge between A2A EventQueue and TaskManager StreamingCallbacks
"""

import asyncio
from typing import Dict, Any
from a2a.server.events import EventQueue
from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState
from a2a.utils import new_agent_parts_message, new_agent_text_message
from a2a.types import DataPart
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class EventQueueBridge:
    """
    Bridge that converts TaskManager progress updates to A2A TaskStatusUpdateEvents
    """
    
    def __init__(self, event_queue: EventQueue, context: Any):
        """
        Initialize bridge
        
        Args:
            event_queue: A2A EventQueue
            context: RequestContext from A2A
        """
        self.event_queue = event_queue
        self.context = context
        self._update_queue = asyncio.Queue()
        self._bridge_task = None
        
        # Start background task to process updates
        self._start_bridge_task()
    
    def _start_bridge_task(self):
        """Start background task to bridge updates"""
        async def bridge_worker():
            while True:
                try:
                    update_data = await self._update_queue.get()
                    
                    if update_data is None:  # Sentinel to stop
                        break
                    
                    # Convert to A2A TaskStatusUpdateEvent
                    event = self._convert_to_task_status_event(update_data)
                    await self.event_queue.enqueue_event(event)
                    
                    self._update_queue.task_done()
                except Exception as e:
                    logger.error(f"Error in bridge worker: {str(e)}")
        
        self._bridge_task = asyncio.create_task(bridge_worker())
    
    async def put(self, update_data: Dict[str, Any]):
        """
        Put progress update to bridge
        
        Args:
            update_data: Progress update data from TaskManager
        """
        await self._update_queue.put(update_data)
    
    def _convert_to_task_status_event(self, update_data: Dict[str, Any]) -> TaskStatusUpdateEvent:
        """
        Convert TaskManager progress update to A2A TaskStatusUpdateEvent
        
        Args:
            update_data: Progress update data
            
        Returns:
            TaskStatusUpdateEvent
        """
        task_id = update_data.get("task_id") or self.context.task_id
        update_type = update_data.get("type", "progress")
        status = update_data.get("status", "in_progress")
        
        # Map status to TaskState
        state_map = {
            "completed": TaskState.completed,
            "failed": TaskState.failed,
            "in_progress": TaskState.in_progress,
            "pending": TaskState.pending,
        }
        task_state = state_map.get(status, TaskState.in_progress)
        
        # Create message based on update type
        if update_type == "final":
            message = new_agent_parts_message([
                DataPart(data=update_data.get("result") or update_data)
            ])
        elif update_type == "task_failed":
            message = new_agent_text_message(update_data.get("error", "Task failed"))
        else:
            # Progress or other updates
            message = new_agent_parts_message([
                DataPart(data=update_data)
            ])
        
        return TaskStatusUpdateEvent(
            task_id=task_id,
            context_id=self.context.context_id or "unknown",
            status=TaskStatus(state=task_state, message=message),
            final=update_data.get("final", False)
        )
    
    async def close(self):
        """Close bridge and stop background task"""
        await self._update_queue.put(None)  # Sentinel to stop worker
        if self._bridge_task:
            await self._bridge_task

