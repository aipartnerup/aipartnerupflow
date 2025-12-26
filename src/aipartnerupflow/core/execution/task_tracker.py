"""
Lightweight task tracker for in-memory task tracking
Separated from TaskExecutor to avoid blocking issues and improve performance
"""
from typing import Set, List, Dict, Any
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TaskTracker:
    """Lightweight task tracker - Singleton pattern for task tracking only"""
    
    _instance = None
    _initialized = False
    _lock = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskTracker, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not TaskTracker._initialized:
            # Simple in-memory task tracking - store context_ids (task IDs)
            self._running_tasks: Set[str] = set()
            TaskTracker._initialized = True
            logger.info("TaskTracker initialized")
    
    async def start_task_tracking(self, context_id: str) -> None:
        """Start tracking a task"""
        self._running_tasks.add(context_id)
        logger.info(f"Started tracking task: {context_id}")
    
    async def stop_task_tracking(self, context_id: str) -> None:
        """Stop tracking a task"""
        self._running_tasks.discard(context_id)
        logger.info(f"Stopped tracking task: {context_id}")
    
    def get_task_status(self, context_id: str) -> Dict[str, Any]:
        """Get task status by context_id (synchronous for system routes)"""
        # Use synchronous access for system routes to avoid blocking
        if context_id in self._running_tasks:
            return {
                "context_id": context_id,
                "status": "existent",
                "message": "Task is running"
            }
        else:
            return {
                "context_id": context_id,
                "status": "nonexistent",
                "message": "Task not found or not running"
            }
    
    def get_all_running_tasks(self) -> List[str]:
        """Get all running task context_ids (synchronous for system routes)"""
        return list(self._running_tasks)
    
    def get_running_tasks_count(self) -> int:
        """Get count of running tasks (synchronous for system routes)"""
        return len(self._running_tasks)
    
    def is_task_running(self, context_id: str) -> bool:
        """Check if a task is running (synchronous for system routes)"""
        return context_id in self._running_tasks

