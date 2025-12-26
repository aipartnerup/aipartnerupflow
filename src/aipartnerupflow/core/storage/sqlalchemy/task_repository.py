"""
Task repository for task database operations

This module provides a TaskRepository class that encapsulates all database operations
for tasks. TaskManager should use TaskRepository instead of directly operating on db session.
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING, Type, TypeVar
from datetime import datetime
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
        
        # Check if task_model_class mapper has custom columns that might not exist in the database
        # This can happen if Base.metadata was polluted by custom TaskModel tests
        from sqlalchemy.inspection import inspect as sa_inspect
        custom_columns = {'project_id', 'priority_level', 'department'}
        has_custom_columns = False
        
        try:
            mapper = sa_inspect(task_model_class)
            if hasattr(mapper, 'columns'):
                mapper_columns = {col.key for col in mapper.columns}
                has_custom_columns = bool(custom_columns & mapper_columns)
        except Exception:
            pass
        
        # If mapper has custom columns and we're using default TaskModel, reload module to get clean one
        if has_custom_columns and task_model_class == TaskModel:
            import importlib
            import sys
            if 'aipartnerupflow.core.storage.sqlalchemy.models' in sys.modules:
                importlib.reload(sys.modules['aipartnerupflow.core.storage.sqlalchemy.models'])
            from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel as CleanTaskModel
            from sqlalchemy.orm import configure_mappers
            configure_mappers()
            self.task_model_class = CleanTaskModel
        else:
            self.task_model_class = task_model_class
    
    async def create_task(
        self,
        name: str,
        user_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        priority: int = 1,
        dependencies: Optional[List[Dict[str, Any]]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        schemas: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,  # Optional task ID (if not provided, TaskModel will auto-generate)
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
            inputs: Execution-time input parameters for executor.execute(inputs)
            schemas: Validation schemas (input_schema, output_schema)
            params: Executor initialization parameters (must include executor_id)
            id: Optional task ID. If not provided, TaskModel will auto-generate using default (UUID).
                If provided, will use the specified ID.
            **kwargs: User-defined custom fields (e.g., project_id="proj-123", department="engineering")
                These fields will be set on the task if they exist as columns in the TaskModel
                Example: create_task(..., project_id="proj-123", department="engineering")
            
        Returns:
            Created TaskModel instance (or custom TaskModel subclass if configured)
        """
        # Determine which TaskModel class to use (may be clean TaskModel if Base.metadata is polluted)
        # We need to check this early to get the correct available_columns
        task_model_to_check = self.task_model_class
        
        # Check if task_model_class's __table__ has custom columns that might not exist in the database
        # This can happen if Base.metadata was polluted by custom TaskModel tests
        # Note: We check __table__.columns instead of mapper.columns because __table__ references
        # Base.metadata.tables[TASK_TABLE_NAME], which gets polluted by extend_existing=True
        import importlib
        import sys
        from aipartnerupflow.core.storage.sqlalchemy.models import Base as ModelsBase, TASK_TABLE_NAME
        custom_columns = {'project_id', 'priority_level', 'department'}
        has_custom_columns = False
        use_clean_task_model = False
        clean_task_model = None
        
        try:
            # Check __table__.columns (which references Base.metadata) for custom columns
            if hasattr(self.task_model_class, '__table__'):
                table_columns = {c.name for c in self.task_model_class.__table__.columns}
                has_custom_columns = bool(custom_columns & table_columns)
            
            # Also check Base.metadata.tables directly
            if not has_custom_columns and TASK_TABLE_NAME in ModelsBase.metadata.tables:
                metadata_table_columns = {c.name for c in ModelsBase.metadata.tables[TASK_TABLE_NAME].columns}
                has_custom_columns = bool(custom_columns & metadata_table_columns)
            
            # If Base.metadata is polluted, reload module and use clean TaskModel
            # This is a defensive measure when Base.metadata is polluted by custom TaskModel tests
            if has_custom_columns and self.task_model_class == TaskModel:
                # Remove polluted table from Base.metadata first
                if TASK_TABLE_NAME in ModelsBase.metadata.tables:
                    ModelsBase.metadata.remove(ModelsBase.metadata.tables[TASK_TABLE_NAME])
                
                # Reload models module to get clean Base and TaskModel
                if 'aipartnerupflow.core.storage.sqlalchemy.models' in sys.modules:
                    importlib.reload(sys.modules['aipartnerupflow.core.storage.sqlalchemy.models'])
                
                from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel as CleanTaskModel, Base as CleanBase
                from sqlalchemy.orm import configure_mappers
                configure_mappers()
                
                # Force access to __table__ to ensure it's created with clean metadata
                _ = CleanTaskModel.__table__
                
                # Verify the table is clean (no custom columns)
                clean_table_columns = {c.name for c in CleanTaskModel.__table__.columns}
                if custom_columns & clean_table_columns:
                    # Still polluted, try to force clean by removing and recreating
                    if TASK_TABLE_NAME in CleanBase.metadata.tables:
                        CleanBase.metadata.remove(CleanBase.metadata.tables[TASK_TABLE_NAME])
                    # Force recreate by accessing __table__ again
                    _ = CleanTaskModel.__table__
                    configure_mappers()
                
                clean_task_model = CleanTaskModel
                use_clean_task_model = True
                task_model_to_check = clean_task_model
                # Update module-level TaskModel reference to ensure consistency
                import aipartnerupflow.core.storage.sqlalchemy.models as models_module
                models_module.TaskModel = CleanTaskModel
                # Also update this module's TaskModel reference
                import aipartnerupflow.core.storage.sqlalchemy.task_repository as repo_module
                repo_module.TaskModel = CleanTaskModel
                logger.debug(
                    f"Base.metadata was polluted with custom columns {custom_columns & table_columns if hasattr(self.task_model_class, '__table__') else set()}, "
                    f"using clean TaskModel to avoid database errors"
                )
        except Exception as e:
            logger.debug(f"Error checking for custom columns: {e}")
            pass
        
        # Core fields - only include fields that exist in the task_model_class table
        # This is important for custom TaskModel classes that may not have all standard fields
        # Get available columns from the task_model_class table (use task_model_to_check, not self.task_model_class)
        available_columns = set()
        if hasattr(task_model_to_check, '__table__'):
            available_columns = {c.name for c in task_model_to_check.__table__.columns}
        
        task_data = {}
        
        # Only add fields that exist in the table
        if 'name' in available_columns:
            task_data["name"] = name
        if 'user_id' in available_columns:
            task_data["user_id"] = user_id
        if 'parent_id' in available_columns:
            task_data["parent_id"] = parent_id
        if 'priority' in available_columns:
            task_data["priority"] = priority
        if 'dependencies' in available_columns:
            task_data["dependencies"] = dependencies or []
        if 'inputs' in available_columns:
            task_data["inputs"] = inputs or {}
        if 'schemas' in available_columns:
            task_data["schemas"] = schemas or {}
        if 'params' in available_columns:
            task_data["params"] = params or {}
        if 'status' in available_columns:
            task_data["status"] = "pending"
        if 'progress' in available_columns:
            task_data["progress"] = 0.0
        if 'has_children' in available_columns:
            task_data["has_children"] = False
        if 'original_task_id' in available_columns:
            task_data["original_task_id"] = None
        if 'has_copy' in available_columns:
            task_data["has_copy"] = False
        
        # Set id if provided (otherwise TaskModel will use its default)
        if id is not None and 'id' in available_columns:
            task_data["id"] = id
        
        # Add custom fields from kwargs if they exist as columns in the TaskModel
        # This allows users to pass custom fields like project_id, department, etc.
        # Note: 'id' should not be passed via kwargs, use the id parameter instead
        # Note: 'status' should not be overridden from kwargs for new tasks (always starts as 'pending')
        
        # Filter kwargs to only include valid columns
        for key, value in kwargs.items():
            if key == "id":
                logger.warning(
                    "id should be passed as a named parameter, not via kwargs. "
                    "Ignoring id from kwargs."
                )
                continue
            elif key == "status":
                # Status is always set to 'pending' for new tasks, ignore status from kwargs
                logger.debug(f"Ignoring status '{value}' from kwargs - new tasks always start as 'pending'")
                continue
            elif key in custom_columns and has_custom_columns and self.task_model_class == TaskModel:
                # Skip custom columns if mapper has them but they might not exist in the database
                # This prevents errors when Base.metadata is polluted (only for default TaskModel)
                logger.debug(f"Skipping custom column '{key}' to avoid potential database errors")
                continue
            elif key in available_columns:
                # Only add if the column actually exists in the table definition
                task_data[key] = value
            elif hasattr(self.task_model_class, key):
                # Fallback: check if it's a class attribute (but not a column)
                # This is less reliable, so log a warning
                logger.debug(f"Field '{key}' exists as class attribute but not as table column, skipping")
            else:
                logger.warning(
                    f"Custom field '{key}' ignored - not found in {self.task_model_class.__name__}. "
                    f"Available columns: {[c.name for c in self.task_model_class.__table__.columns]}"
                )
        
        # Use clean TaskModel if mapper is polluted (already determined above)
        task_model_to_use = clean_task_model if use_clean_task_model else self.task_model_class
        task = task_model_to_use(**task_data)
        
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
            # Check if task_model_class's __table__ or Base.metadata has custom columns
            # This can happen if Base.metadata was polluted by custom TaskModel tests
            from sqlalchemy.orm import configure_mappers
            from sqlalchemy import text
            from aipartnerupflow.core.storage.sqlalchemy.models import Base as ModelsBase, TASK_TABLE_NAME
            import importlib
            import sys
            
            custom_columns = {'project_id', 'priority_level', 'department'}
            has_custom_columns = False
            use_clean_task_model = False
            clean_task_model = None
            
            # Check __table__.columns (which references Base.metadata) for custom columns
            if hasattr(self.task_model_class, '__table__'):
                table_columns = {c.name for c in self.task_model_class.__table__.columns}
                has_custom_columns = bool(custom_columns & table_columns)
            
            # Also check Base.metadata.tables directly
            if not has_custom_columns and TASK_TABLE_NAME in ModelsBase.metadata.tables:
                metadata_table_columns = {c.name for c in ModelsBase.metadata.tables[TASK_TABLE_NAME].columns}
                has_custom_columns = bool(custom_columns & metadata_table_columns)
            
            # If Base.metadata is polluted, reload module and use clean TaskModel
            # Only do this if we're using the default TaskModel, not a custom one
            # Check by comparing class names and modules, not object identity (which may differ after reload)
            is_default_taskmodel = (
                self.task_model_class.__name__ == 'TaskModel' and
                hasattr(self.task_model_class, '__module__') and
                'aipartnerupflow.core.storage.sqlalchemy.models' in self.task_model_class.__module__
            )
            
            if has_custom_columns and is_default_taskmodel:
                # Remove polluted table from Base.metadata first
                if TASK_TABLE_NAME in ModelsBase.metadata.tables:
                    ModelsBase.metadata.remove(ModelsBase.metadata.tables[TASK_TABLE_NAME])
                
                # Reload models module to get clean Base and TaskModel
                if 'aipartnerupflow.core.storage.sqlalchemy.models' in sys.modules:
                    importlib.reload(sys.modules['aipartnerupflow.core.storage.sqlalchemy.models'])
                
                from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel as CleanTaskModel, Base as CleanBase
                from sqlalchemy.orm import configure_mappers
                configure_mappers()
                
                # Force access to __table__ to ensure it's created with clean metadata
                # This ensures the table definition is rebuilt from the class definition
                _ = CleanTaskModel.__table__
                
                # Verify the table is clean (no custom columns)
                clean_table_columns = {c.name for c in CleanTaskModel.__table__.columns}
                if custom_columns & clean_table_columns:
                    # Still polluted, try to force clean by removing and recreating
                    if TASK_TABLE_NAME in CleanBase.metadata.tables:
                        CleanBase.metadata.remove(CleanBase.metadata.tables[TASK_TABLE_NAME])
                    # Force recreate by accessing __table__ again
                    _ = CleanTaskModel.__table__
                    configure_mappers()
                
                clean_task_model = CleanTaskModel
                use_clean_task_model = True
                # Update module-level TaskModel reference to ensure consistency
                import aipartnerupflow.core.storage.sqlalchemy.models as models_module
                models_module.TaskModel = CleanTaskModel
                # Also update this module's TaskModel reference
                import aipartnerupflow.core.storage.sqlalchemy.task_repository as repo_module
                repo_module.TaskModel = CleanTaskModel
                logger.debug("Base.metadata was polluted in get_task_by_id, using clean TaskModel")
            elif has_custom_columns:
                # Base.metadata is polluted but we're using a custom TaskModel
                # Don't reload, just use the custom TaskModel as-is
                # The custom TaskModel should handle the pollution correctly
                logger.debug(f"Base.metadata is polluted but using custom TaskModel {self.task_model_class.__name__}, not reloading")
            
            # Use clean TaskModel if Base.metadata is polluted
            task_model_to_use = clean_task_model if use_clean_task_model else self.task_model_class
            
            # Update self.task_model_class if we're using clean TaskModel
            if use_clean_task_model:
                self.task_model_class = clean_task_model
            
            # If still has custom columns (shouldn't happen after reload), use select with explicit columns
            # But first check if instance already exists in session to avoid conflicts
            if has_custom_columns and not use_clean_task_model:
                # First try to get from session/identity map
                if self.is_async:
                    # For async, try normal query first
                    task = await self.db.get(self.task_model_class, task_id)
                    if task:
                        await self.db.refresh(task)
                        return task
                else:
                    # For sync, try normal query first
                    task = self.db.get(self.task_model_class, task_id)
                    if task:
                        self.db.refresh(task)
                        return task
                
                # If not found, use raw SQL to select only standard columns
                # This avoids issues when mapper has columns that don't exist in the database
                standard_columns = [
                    'id', 'parent_id', 'user_id', 'name', 'status', 'priority',
                    'dependencies', 'inputs', 'params', 'result', 'error', 'schemas',
                    'progress', 'created_at', 'started_at', 'updated_at', 'completed_at',
                    'has_children', 'original_task_id', 'has_copy'
                ]
                columns_str = ', '.join(standard_columns)
                
                if self.is_async:
                    stmt = text(f"SELECT {columns_str} FROM {self.task_model_class.__tablename__} WHERE id = :task_id")
                    result = await self.db.execute(stmt, {"task_id": task_id})
                    row = result.fetchone()
                    if row:
                        # Convert row to TaskModel instance
                        # This is a fallback when mapper is polluted
                        task_dict = dict(zip(standard_columns, row))
                        task = self.task_model_class(**task_dict)
                        # Merge instead of add to avoid conflicts
                        task = await self.db.merge(task)
                        return task
                    return None
                else:
                    stmt = text(f"SELECT {columns_str} FROM {self.task_model_class.__tablename__} WHERE id = :task_id")
                    result = self.db.execute(stmt, {"task_id": task_id})
                    row = result.fetchone()
                    if row:
                        # Convert row to TaskModel instance
                        task_dict = dict(zip(standard_columns, row))
                        task = self.task_model_class(**task_dict)
                        # Merge instead of add to avoid conflicts
                        task = self.db.merge(task)
                        return task
                    return None
            else:
                # Normal path: use ORM query
                # Double-check that self.task_model_class.__table__ is clean before using db.get()
                # This is important because db.get() uses __table__ to generate SQL, and if __table__ is polluted,
                # it will try to query non-existent columns
                final_task_model = self.task_model_class
                if hasattr(final_task_model, '__table__'):
                    final_table_columns = {c.name for c in final_task_model.__table__.columns}
                    if custom_columns & final_table_columns:
                        # Still polluted even after reload, use raw SQL as fallback
                        logger.debug("TaskModel.__table__ still has custom columns after reload, using raw SQL fallback")
                        standard_columns = [
                            'id', 'parent_id', 'user_id', 'name', 'status', 'priority',
                            'dependencies', 'inputs', 'params', 'result', 'error', 'schemas',
                            'progress', 'created_at', 'started_at', 'updated_at', 'completed_at',
                            'has_children', 'original_task_id', 'has_copy'
                        ]
                        columns_str = ', '.join(standard_columns)
                        
                        if self.is_async:
                            stmt = text(f"SELECT {columns_str} FROM {final_task_model.__tablename__} WHERE id = :task_id")
                            result = await self.db.execute(stmt, {"task_id": task_id})
                            row = result.fetchone()
                            if row:
                                task_dict = dict(zip(standard_columns, row))
                                task = final_task_model(**task_dict)
                                task = await self.db.merge(task)
                                return task
                            return None
                        else:
                            stmt = text(f"SELECT {columns_str} FROM {final_task_model.__tablename__} WHERE id = :task_id")
                            result = self.db.execute(stmt, {"task_id": task_id})
                            row = result.fetchone()
                            if row:
                                task_dict = dict(zip(standard_columns, row))
                                task = final_task_model(**task_dict)
                                task = self.db.merge(task)
                                return task
                            return None
                
                # Use ORM query with clean TaskModel
                if self.is_async:
                    task = await self.db.get(final_task_model, task_id)
                    if task:
                        # Explicitly refresh to ensure we get the latest data from database
                        await self.db.refresh(task)
                else:
                    task = self.db.get(final_task_model, task_id)
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
            # Handle error field: if explicitly set to None and status is completed, clear it
            # This allows clearing error when task completes successfully after re-execution
            # Use a sentinel value to distinguish between "not provided" and "explicitly None"
            if error is not None:
                task.error = error
            elif status == "completed":
                # Clear error when task completes successfully (re-execution scenario)
                task.error = None
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
    
    async def update_task_inputs(self, task_id: str, inputs: Dict[str, Any]) -> bool:
        """
        Update task inputs
        
        Args:
            task_id: Task ID
            inputs: New input parameters
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.inputs = inputs
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
            
            # Verify the update was successful
            logger.debug(
                f"Updated inputs for task {task_id}: "
                f"keys={list(inputs.keys())}, saved_keys={list(task.inputs.keys()) if task.inputs else []}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating task inputs for {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def update_task_dependencies(self, task_id: str, dependencies: List[Dict[str, Any]]) -> bool:
        """
        Update task dependencies
        
        Args:
            task_id: Task ID
            dependencies: New dependencies list
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.dependencies = dependencies
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
            
            logger.debug(f"Updated dependencies for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task dependencies for {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def update_task_name(self, task_id: str, name: str) -> bool:
        """
        Update task name
        
        Args:
            task_id: Task ID
            name: New task name
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.name = name
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
            
            logger.debug(f"Updated name for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task name for {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def update_task_priority(self, task_id: str, priority: int) -> bool:
        """
        Update task priority
        
        Args:
            task_id: Task ID
            priority: New priority level
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.priority = priority
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
            
            logger.debug(f"Updated priority for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task priority for {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def update_task_params(self, task_id: str, params: Dict[str, Any]) -> bool:
        """
        Update task params
        
        Args:
            task_id: Task ID
            params: New executor parameters
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.params = params
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
            
            logger.debug(f"Updated params for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task params for {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False
    
    async def update_task_schemas(self, task_id: str, schemas: Dict[str, Any]) -> bool:
        """
        Update task schemas
        
        Args:
            task_id: Task ID
            schemas: New validation schemas
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            task.schemas = schemas
            
            if self.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
            
            logger.debug(f"Updated schemas for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task schemas for {task_id}: {str(e)}")
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
    
    async def query_tasks(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        parent_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> List[TaskModelType]:
        """
        Query tasks with filters and pagination
        
        Args:
            user_id: Optional user ID filter
            status: Optional status filter (e.g., "completed", "pending", "in_progress", "failed")
            parent_id: Optional parent ID filter. If None, no filter. If empty string "", filter for root tasks (parent_id is None)
            limit: Maximum number of tasks to return (default: 100)
            offset: Number of tasks to skip (default: 0)
            order_by: Field to order by (default: "created_at")
            order_desc: If True, order descending; if False, order ascending (default: True)
            
        Returns:
            List of TaskModel instances (or custom TaskModel subclass) matching the criteria
        """
        try:
            # Build query
            if self.is_async:
                stmt = select(self.task_model_class)
                
                # Apply filters
                if user_id is not None:
                    stmt = stmt.filter(self.task_model_class.user_id == user_id)
                
                if status is not None:
                    stmt = stmt.filter(self.task_model_class.status == status)
                
                # Apply parent_id filter
                if parent_id is not None:
                    if parent_id == "":
                        # Empty string means filter for root tasks (parent_id is None)
                        stmt = stmt.filter(self.task_model_class.parent_id.is_(None))
                    else:
                        # Specific parent_id
                        stmt = stmt.filter(self.task_model_class.parent_id == parent_id)
                
                # Apply ordering
                order_column = getattr(self.task_model_class, order_by, None)
                if order_column is not None:
                    if order_desc:
                        stmt = stmt.order_by(order_column.desc())
                    else:
                        stmt = stmt.order_by(order_column.asc())
                
                # Apply pagination
                stmt = stmt.offset(offset).limit(limit)
                result = await self.db.execute(stmt)
                tasks = result.scalars().all()
            else:
                stmt = self.db.query(self.task_model_class)
                
                # Apply filters
                if user_id is not None:
                    stmt = stmt.filter(self.task_model_class.user_id == user_id)
                
                if status is not None:
                    stmt = stmt.filter(self.task_model_class.status == status)
                
                # Apply parent_id filter
                if parent_id is not None:
                    if parent_id == "":
                        # Empty string means filter for root tasks (parent_id is None)
                        stmt = stmt.filter(self.task_model_class.parent_id.is_(None))
                    else:
                        # Specific parent_id
                        stmt = stmt.filter(self.task_model_class.parent_id == parent_id)
                
                # Apply ordering
                order_column = getattr(self.task_model_class, order_by, None)
                if order_column is not None:
                    if order_desc:
                        stmt = stmt.order_by(order_column.desc())
                    else:
                        stmt = stmt.order_by(order_column.asc())
                
                # Apply pagination
                tasks = stmt.offset(offset).limit(limit).all()
            
            return list(tasks)
            
        except Exception as e:
            logger.error(f"Error querying tasks: {str(e)}")
            return []
    
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
    
    async def get_all_children_recursive(self, task_id: str) -> List[TaskModelType]:
        """
        Get all children tasks recursively (including grandchildren, etc.)
        
        Args:
            task_id: Parent task ID
            
        Returns:
            List of all child TaskModel instances (or custom TaskModel subclass) recursively
        """
        all_children = []
        
        async def collect_children(parent_id: str):
            children = await self.get_child_tasks_by_parent_id(parent_id)
            for child in children:
                all_children.append(child)
                # Recursively collect grandchildren
                await collect_children(child.id)
        
        await collect_children(task_id)
        return all_children
    
    async def find_dependent_tasks(self, task_id: str) -> List[TaskModelType]:
        """
        Find all tasks that depend on the given task (reverse dependencies)
        
        This method searches for tasks that have the given task_id in their dependencies field.
        
        Args:
            task_id: Task ID to find dependents for
            
        Returns:
            List of TaskModel instances (or custom TaskModel subclass) that depend on the given task
        """
        try:
            # Get all tasks from the database
            # We need to check all tasks' dependencies field to find reverse dependencies
            if self.is_async:
                stmt = select(self.task_model_class)
                result = await self.db.execute(stmt)
                all_tasks = result.scalars().all()
            else:
                all_tasks = self.db.query(self.task_model_class).all()
            
            dependent_tasks = []
            for task in all_tasks:
                dependencies = task.dependencies or []
                if not dependencies:
                    continue
                
                # Check if this task depends on the given task_id
                for dep in dependencies:
                    dep_id = None
                    if isinstance(dep, dict):
                        dep_id = dep.get("id")
                    elif isinstance(dep, str):
                        dep_id = dep
                    
                    if dep_id == task_id:
                        dependent_tasks.append(task)
                        break  # Found dependency, no need to check other dependencies
            
            return dependent_tasks
            
        except Exception as e:
            logger.error(f"Error finding dependent tasks for {task_id}: {str(e)}")
            return []
    
    async def delete_task(self, task_id: str) -> bool:
        """
        Physically delete a task from the database
        
        Args:
            task_id: Task ID to delete
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
            if self.is_async:
                # For async session, use delete statement
                stmt = delete(self.task_model_class).where(self.task_model_class.id == task_id)
                await self.db.execute(stmt)
                await self.db.commit()
            else:
                # For sync session, mark for deletion
                self.db.delete(task)
                self.db.commit()
            
            logger.debug(f"Physically deleted task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {str(e)}")
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()
            return False


__all__ = [
    "TaskRepository",
]

