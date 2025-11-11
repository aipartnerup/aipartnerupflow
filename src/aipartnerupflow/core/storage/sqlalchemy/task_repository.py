"""
Task repository for task database operations

This module provides a TaskRepository class that encapsulates all database operations
for tasks. TaskManager should use TaskRepository instead of directly operating on db session.

This is similar to aisee_orchestrator's TaskRepository pattern.
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING, Type, TypeVar
from datetime import datetime, timezone
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.utils.logger import get_logger

if TYPE_CHECKING:
    from aipartnerupflow.core.types import TaskTreeNode

logger = get_logger(__name__)

# Type variable for TaskModel subclasses
TaskModelType = TypeVar("TaskModelType", bound=TaskModel)


class TaskRepository:
    """
    Task repository for database operations
    
    Provides methods for:
    - Creating, updating, and deleting tasks
    - Building task trees
    - Querying tasks by various criteria
    - Managing task hierarchies
    
    TaskManager should use this repository instead of directly operating on db session.
    
    Supports custom TaskModel classes via task_model_class parameter.
    Users can pass their custom TaskModel subclass to support custom fields.
    
    Example:
        # Use default TaskModel
        repo = TaskRepository(db)
        
        # Use custom TaskModel with additional fields
        repo = TaskRepository(db, task_model_class=MyTaskModel)
        task = await repo.create_task(..., project_id="proj-123")  # Custom field
    """
    
    def __init__(
        self,
        db: Union[Session, AsyncSession],
        task_model_class: Type[TaskModelType] = TaskModel
    ):
        """
        Initialize TaskRepository
        
        Args:
            db: Database session (sync or async)
            task_model_class: Custom TaskModel class (default: TaskModel)
                Users can pass their custom TaskModel subclass that inherits TaskModel
                to add custom fields (e.g., project_id, department, etc.)
                Example: TaskRepository(db, task_model_class=MyTaskModel)
        """
        self.db = db
        self.is_async = isinstance(db, AsyncSession)
        self.task_model_class = task_model_class
    
    async def create_task(
        self,
        name: str,
        user_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        priority: int = 1,
        dependencies: Optional[List[Dict[str, Any]]] = None,
        input_data: Optional[Dict[str, Any]] = None,
        schemas: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs  # User-defined custom fields (e.g., project_id, department, etc.)
    ) -> TaskModelType:
        """
        Create a new task
        
        Args:
            name: Task name
            user_id: User ID (optional, for multi-user scenarios)
            parent_id: Parent task ID
            priority: Priority level (0=urgent/highest, 1=high, 2=normal, 3=low/lowest). ASC order: smaller numbers execute first.
            dependencies: Task dependencies: [{"id": "uuid", "required": true}]
            input_data: Input data for the task
            schemas: Task schemas
            params: Task parameters
            **kwargs: User-defined custom fields (e.g., project_id="proj-123", department="engineering")
                These fields will be set on the task if they exist as columns in the TaskModel
                Example: create_task(..., project_id="proj-123", department="engineering")
            
        Returns:
            Created TaskModel instance (or custom TaskModel subclass if configured)
        """
        # Core fields
        task_data = {
            "name": name,
            "user_id": user_id,
            "parent_id": parent_id,
            "priority": priority,
            "dependencies": dependencies or [],
            "input_data": input_data or {},
            "schemas": schemas or {},
            "params": params or {},
            "status": "pending",
            "progress": 0.0,
            "has_children": False,
        }
        
        # Add custom fields from kwargs if they exist as columns in the TaskModel
        # This allows users to pass custom fields like project_id, department, etc.
        for key, value in kwargs.items():
            if hasattr(self.task_model_class, key) or key in self.task_model_class.__table__.columns:
                task_data[key] = value
            else:
                logger.warning(
                    f"Custom field '{key}' ignored - not found in {self.task_model_class.__name__}. "
                    f"Available columns: {[c.name for c in self.task_model_class.__table__.columns]}"
                )
        
        task = self.task_model_class(**task_data)
        
        self.db.add(task)
        
        try:
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
        except Exception as e:
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            logger.error(f"Error creating task: {str(e)}")
            raise
        
        return task
    
    async def get_task_by_id(self, task_id: str) -> Optional[TaskModelType]:
        """
        Get a task by ID
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskModel instance (or custom TaskModel subclass) or None if not found
        """
        try:
            if self.is_async:
                task = await self.db.get(self.task_model_class, task_id)
                if task:
                    # Explicitly refresh to ensure we get the latest data from database
                    await self.db.refresh(task)
            else:
                task = self.db.get(self.task_model_class, task_id)
                if task:
                    # Explicitly refresh to ensure we get the latest data from database
                    self.db.refresh(task)
            return task
        except Exception as e:
            logger.error(f"Error getting task by ID {task_id}: {str(e)}")
            return None
    
    async def get_child_tasks_by_parent_id(self, parent_id: str) -> List[TaskModelType]:
        """
        Get child tasks by parent ID
        
        Args:
            parent_id: Parent task ID
            
        Returns:
            List of child TaskModel instances (or custom TaskModel subclass), ordered by priority
        """
        try:
            if self.is_async:
                stmt = select(self.task_model_class).filter(
                    self.task_model_class.parent_id == parent_id
                ).order_by(self.task_model_class.priority.asc())
                result = await self.db.execute(stmt)
                children = result.scalars().all()
            else:
                children = self.db.query(self.task_model_class).filter(
                    self.task_model_class.parent_id == parent_id
                ).order_by(self.task_model_class.priority.asc()).all()
            return children
        except Exception as e:
            logger.error(f"Error getting child tasks for parent {parent_id}: {str(e)}")
            return []
    
    async def get_root_task(self, task: TaskModelType) -> TaskModelType:
        """
        Get root task (traverse up the tree until parent_id is None)
        
        Args:
            task: Starting task
            
        Returns:
            Root TaskModel instance (or custom TaskModel subclass)
        """
        current_task = task
        
        # Traverse up to find root
        while current_task.parent_id:
            parent = await self.get_task_by_id(current_task.parent_id)
            if not parent:
                break
            current_task = parent
        
        return current_task
    
    async def get_all_tasks_in_tree(self, root_task: TaskModelType) -> List[TaskModelType]:
        """
        Get all tasks in the task tree (recursive)
        
        Args:
            root_task: Root task of the tree
            
        Returns:
            List of all tasks in the tree (or custom TaskModel subclass)
        """
        all_tasks = [root_task]
        
        # Get all child tasks recursively
        async def get_children(parent_id: str):
            children = await self.get_child_tasks_by_parent_id(parent_id)
            for child in children:
                all_tasks.append(child)
                await get_children(child.id)
        
        await get_children(root_task.id)
        return all_tasks
    
    async def build_task_tree(self, task: TaskModelType) -> "TaskTreeNode":
        """
        Build TaskTreeNode for a task with its children (recursive)
        
        Args:
            task: Root task (or custom TaskModel subclass)
            
        Returns:
            TaskTreeNode instance with all children recursively built
        """
        # Lazy import to avoid circular dependency
        from aipartnerupflow.core.types import TaskTreeNode
        
        # Get all child tasks
        child_tasks = await self.get_child_tasks_by_parent_id(task.id)
        
        # Create the main task node
        task_node = TaskTreeNode(task=task)
        
        # Add child tasks recursively
        for child_task in child_tasks:
            child_node = await self.build_task_tree(child_task)
            task_node.add_child(child_node)
        
        return task_node
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> bool:
        """
        Update task status and related fields
        
        Args:
            task_id: Task ID
            status: New status
            error: Error message (if any)
            result: Task result
            progress: Task progress (0.0 to 1.0)
            started_at: Task start time
            completed_at: Task completion time
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.status = status
            if error is not None:
                task.error = error
            if result is not None:
                task.result = result
            if progress is not None:
                task.progress = progress
            if started_at is not None:
                task.started_at = started_at
            if completed_at is not None:
                task.completed_at = completed_at
            
            if self.is_async:
                await self.db.commit()
            else:
                self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating task status for {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def update_task_input_data(self, task_id: str, input_data: Dict[str, Any]) -> bool:
        """
        Update task input data
        
        Args:
            task_id: Task ID
            input_data: New input data
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.input_data = input_data
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
            
            # Verify the update was successful
            logger.debug(
                f"Updated input_data for task {task_id}: "
                f"keys={list(input_data.keys())}, saved_keys={list(task.input_data.keys()) if task.input_data else []}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating task input data for {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def get_completed_tasks_by_ids(self, task_ids: List[str]) -> Dict[str, TaskModelType]:
        """
        Get completed tasks by a list of IDs
        
        Args:
            task_ids: List of task IDs
            
        Returns:
            Dictionary mapping task_id to TaskModel (or custom TaskModel subclass) for completed tasks
        """
        if not task_ids:
            return {}
        
        try:
            if self.is_async:
                stmt = select(self.task_model_class).filter(
                    self.task_model_class.id.in_(task_ids),
                    self.task_model_class.status == "completed"
                )
                result = await self.db.execute(stmt)
                tasks = result.scalars().all()
            else:
                tasks = self.db.query(self.task_model_class).filter(
                    self.task_model_class.id.in_(task_ids),
                    self.task_model_class.status == "completed"
                ).all()
            
            return {task.id: task for task in tasks}
            
        except Exception as e:
            logger.error(f"Error getting completed tasks by IDs: {str(e)}")
            return {}
    
    async def save_task_hierarchy_to_database(self, task_tree: "TaskTreeNode") -> bool:
        """
        Save complete task hierarchy to database from TaskTreeNode
        
        Args:
            task_tree: Root task node of the task tree
            
        Returns:
            True if successful, False otherwise
            
        Note: Tasks should already be created via create_task(),
        so this method mainly ensures the hierarchy is properly saved.
        """
        # Import here to avoid circular dependency
        from aipartnerupflow.core.types import TaskTreeNode
        
        try:
            # Save root task first
            root_task = task_tree.task
            self.db.add(root_task)
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(root_task)
            else:
                self.db.commit()
                self.db.refresh(root_task)
            
            # Recursively save children with proper parent_id
            await self._save_children_recursive(task_tree)
            
            logger.info(f"Saved task tree: root task {root_task.id} with {len(task_tree.children)} direct children")
            return True
            
        except Exception as e:
            logger.error(f"Error saving task hierarchy to database: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def _save_children_recursive(self, parent_node: "TaskTreeNode"):
        """Recursively save children tasks with proper parent_id"""
        for child_node in parent_node.children:
            child_task = child_node.task
            # Set parent_id to the parent task's actual ID
            child_task.parent_id = parent_node.task.id
            self.db.add(child_task)
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(child_task)
            else:
                self.db.commit()
                self.db.refresh(child_task)
            
            # Recursively save grandchildren
            if child_node.children:
                await self._save_children_recursive(child_node)


__all__ = [
    "TaskRepository",
]

