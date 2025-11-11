"""
Task creation from tasks array

This module provides functionality to create task trees from tasks array (JSON format).
It is a core function that accepts a tasks array and builds a task tree structure.

External callers should provide tasks with resolved id and parent_id.
This module only validates that dependencies exist in the array and hierarchy is correct.

Usage:
    from aipartnerupflow.core.execution import TaskCreator
    
    creator = TaskCreator(db_session)
    tasks = [
        {
            "id": "task_1",  # Optional: if provided, used for references
            "name": "Task 1",  # Required: if no id, name must be unique and used for references
            "user_id": "user_123",
            "priority": 1,
            "input_data": {"url": "https://example.com"},
            "schemas": {"type": "stdio", "method": "system_info"},
        },
        {
            "id": "task_2",  # Optional: if provided, used for references
            "name": "Task 2",  # Required: if no id, name must be unique and used for references
            "user_id": "user_123",
            "parent_id": "task_1",  # If tasks have id: use id; if not: use name
            "dependencies": [{"id": "task_1", "required": True}],  # Can use id or name
        }
    ]
    task_tree = await creator.create_task_tree_from_array(tasks)
"""

from typing import List, Dict, Any, Optional, Union, Set
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from aipartnerupflow.core.execution.task_manager import TaskManager
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TaskCreator:
    """
    Task creation from tasks array
    
    This class provides functionality to create task trees from tasks array (JSON format).
    External callers should provide tasks with resolved id and parent_id.
    This module only validates that dependencies exist in the array and hierarchy is correct.
    
    Usage:
        from aipartnerupflow.core.execution import TaskCreator
        
        creator = TaskCreator(db_session)
        tasks = [
            {
                "id": "task_1",  # Optional: if provided, used for references
                "name": "Task 1",  # Required: if no id, name must be unique and used for references
                "user_id": "user_123",
                "priority": 1,
                "input_data": {"url": "https://example.com"},
                "schemas": {"type": "stdio", "method": "system_info"},
            },
            {
                "id": "task_2",  # Optional: if provided, used for references
                "name": "Task 2",  # Required: if no id, name must be unique and used for references
                "user_id": "user_123",
                "parent_id": "task_1",  # If tasks have id: use id; if not: use name
                "dependencies": [{"id": "task_1", "required": True}],  # Can use id or name
            }
        ]
        task_tree = await creator.create_task_tree_from_array(tasks)
    """
    
    def __init__(self, db: Session | AsyncSession):
        """
        Initialize TaskCreator
        
        Args:
            db: Database session (sync or async)
        """
        self.db = db
        self.task_manager = TaskManager(db)
    
    async def create_task_tree_from_array(
        self,
        tasks: List[Dict[str, Any]],
    ) -> TaskTreeNode:
        """
        Create task tree from tasks array
        
        Args:
            tasks: Array of task objects in JSON format. Each task must have:
                - id: Task ID (optional) - if provided, ALL tasks must have id and use id for references
                - name: Task name (required) - if id is not provided, ALL tasks must not have id, 
                    name must be unique and used for references
                - user_id: User ID (optional, can be None) - if not provided, will be None
                - priority: Priority level (optional, default: 1)
                - input_data: Input data (optional)
                - schemas: Task schemas (optional)
                - params: Task parameters (optional)
                - parent_id: Parent task ID or name (optional)
                    - If all tasks have id: use id value
                    - If all tasks don't have id: use name value (name must be unique)
                    - Mixed mode (some with id, some without) is not supported
                    - parent_id must reference a task within the same array, or be None for root tasks
                - dependencies: Dependencies list (optional)
                    - Each dependency must have "id" or "name" field pointing to a task in the array
                    - Will be validated to ensure the dependency exists and hierarchy is correct
                - Any other TaskModel fields
            
        Returns:
            TaskTreeNode: Root task node of the created task tree
            
        Raises:
            ValueError: If tasks array is empty, invalid, or dependencies are invalid
        """
        if not tasks:
            raise ValueError("Tasks array cannot be empty")
        
        logger.info(f"Creating task tree from {len(tasks)} tasks")
        
        # Step 1: Extract and validate task identifiers (id or name)
        # Rule: Either all tasks have id, or all tasks don't have id (use name)
        # Mixed mode is not supported for clarity and consistency
        provided_ids: Set[str] = set()
        provided_id_to_index: Dict[str, int] = {}  # provided_id -> index in array
        task_names: Set[str] = set()
        task_name_to_index: Dict[str, int] = {}  # task_name -> index in array
        
        # First pass: check if all tasks have id or all don't have id
        tasks_with_id = 0
        tasks_without_id = 0
        
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            if not task_name:
                raise ValueError(f"Task at index {index} must have a 'name' field")
            
            provided_id = task_data.get("id")
            if provided_id:
                tasks_with_id += 1
            else:
                tasks_without_id += 1
        
        # Validate: either all have id or all don't have id
        if tasks_with_id > 0 and tasks_without_id > 0:
            raise ValueError(
                "Mixed mode not supported: either all tasks must have 'id', or all tasks must not have 'id'. "
                f"Found {tasks_with_id} tasks with id and {tasks_without_id} tasks without id."
            )
        
        # Second pass: build identifier maps
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            if provided_id:
                # Task has id - validate uniqueness
                if provided_id in provided_ids:
                    raise ValueError(f"Duplicate task id '{provided_id}' at index {index}")
                provided_ids.add(provided_id)
                provided_id_to_index[provided_id] = index
            else:
                # Task has no id - must use name, and name must be unique
                if task_name in task_names:
                    raise ValueError(
                        f"Task at index {index} has no 'id' but name '{task_name}' is not unique. "
                        f"When using name-based references, all task names must be unique."
                    )
                task_names.add(task_name)
                task_name_to_index[task_name] = index
        
        # Step 2: Create all tasks first
        created_tasks: List[TaskModel] = []
        identifier_to_task: Dict[str, TaskModel] = {}  # id or name -> TaskModel
        
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            # user_id is optional (can be None) - get directly from task_data
            task_user_id = task_data.get("user_id")
            
            # Validate parent_id exists in the array (if provided)
            # parent_id can be either id (if tasks have id) or name (if tasks don't have id)
            # parent_id must reference a task within the same array, or be None for root tasks
            parent_id = task_data.get("parent_id")
            if parent_id:
                if parent_id not in provided_ids and parent_id not in task_names:
                    raise ValueError(
                        f"Task '{task_name}' at index {index} has parent_id '{parent_id}' "
                        f"which is not in the tasks array (not found as id or name). "
                        f"parent_id must reference a task within the same array."
                    )
            
            # Validate dependencies exist in the array
            dependencies = task_data.get("dependencies")
            if dependencies:
                self._validate_dependencies(
                    dependencies, task_name, index, provided_ids, provided_id_to_index,
                    task_names, task_name_to_index
                )
            
            # Create task (parent_id and dependencies will be set in step 3)
            # Pass id if provided (as optional parameter)
            logger.debug(f"Creating task: name={task_name}, provided_id={provided_id}")
            task = await self.task_manager.task_repository.create_task(
                name=task_name,
                user_id=task_user_id,
                parent_id=None,  # Will be set in step 3
                priority=task_data.get("priority", 1),
                dependencies=None,  # Will be set in step 3
                input_data=task_data.get("input_data"),
                schemas=task_data.get("schemas"),
                params=task_data.get("params"),
                id=provided_id  # Optional: if None, TaskModel will auto-generate
            )
            
            logger.debug(f"Task created: id={task.id}, name={task.name}, provided_id={provided_id}")
            
            # Verify the task was created with the correct ID
            if provided_id and task.id != provided_id:
                logger.error(
                    f"Task ID mismatch: expected {provided_id}, got {task.id}. "
                    f"This indicates an issue with ID assignment."
                )
                raise ValueError(
                    f"Task ID mismatch: expected {provided_id}, got {task.id}. "
                    f"Task was not created with the specified ID."
                )
            
            # Note: TaskRepository.create_task already commits and refreshes the task
            # No need to commit again here
            
            created_tasks.append(task)
            
            # Map identifier (id or name) to created task
            if provided_id:
                identifier_to_task[provided_id] = task
            else:
                # Use name as identifier when id is not provided
                identifier_to_task[task_name] = task
        
        # Step 3: Set parent_id and dependencies using actual task ids
        for index, (task_data, task) in enumerate(zip(tasks, created_tasks)):
            # Resolve parent_id (can be id or name, depending on whether tasks have id)
            # If tasks have id: parent_id should be an id
            # If tasks don't have id: parent_id should be a name (name must be unique)
            parent_id = task_data.get("parent_id")
            actual_parent_id = None
            
            if parent_id:
                # Find the actual task that corresponds to the parent_id (id or name)
                parent_task = identifier_to_task.get(parent_id)
                if parent_task:
                    actual_parent_id = parent_task.id
                    # Update parent's has_children flag
                    parent_task.has_children = True
                    # Update parent task in database
                    if self.task_manager.is_async:
                        await self.db.commit()
                        await self.db.refresh(parent_task)
                    else:
                        self.db.commit()
                        self.db.refresh(parent_task)
                else:
                    raise ValueError(
                        f"Task '{task.name}' at index {index} has parent_id '{parent_id}' "
                        f"which does not map to any created task"
                    )
            
            # Resolve dependencies to actual task ids
            # Whether user provides id or name, we convert to actual task id
            # If user provided id, use it; otherwise use system-generated UUID
            dependencies = task_data.get("dependencies")
            actual_dependencies = None
            if dependencies:
                actual_dependencies = []
                for dep in dependencies:
                    if isinstance(dep, dict):
                        # Support both "id" and "name" for dependency reference
                        # User can provide either id or name, we'll map it to actual task id
                        dep_ref = dep.get("id") or dep.get("name")
                        if dep_ref:
                            # Find the actual task that corresponds to the dependency reference (id or name)
                            dep_task = identifier_to_task.get(dep_ref)
                            if dep_task:
                                # Use actual task id (user-provided if provided, otherwise system-generated)
                                # Final structure is always: {"id": "actual_task_id", "required": bool, "type": str}
                                actual_dependencies.append({
                                    "id": dep_task.id,  # Use actual task id (user-provided or system-generated)
                                    "required": dep.get("required", True),
                                    "type": dep.get("type", "result"),
                                })
                            else:
                                raise ValueError(
                                    f"Task '{task.name}' at index {index} has dependency reference '{dep_ref}' "
                                    f"which does not map to any created task"
                                )
                        else:
                            raise ValueError(f"Task '{task.name}' dependency must have 'id' or 'name' field")
                    else:
                        # Simple string dependency (can be id or name)
                        dep_ref = str(dep)
                        dep_task = identifier_to_task.get(dep_ref)
                        if dep_task:
                            # Use actual task id (user-provided or system-generated)
                            actual_dependencies.append({
                                "id": dep_task.id,  # Use actual task id
                                "required": True,
                                "type": "result",
                            })
                        else:
                            raise ValueError(
                                f"Task '{task.name}' at index {index} has dependency '{dep_ref}' "
                                f"which does not map to any created task"
                            )
                
                actual_dependencies = actual_dependencies if actual_dependencies else None
            
            # Update task with parent_id and dependencies
            if actual_parent_id is not None or actual_dependencies is not None:
                task.parent_id = actual_parent_id
                task.dependencies = actual_dependencies
                # Update in database
                if self.task_manager.is_async:
                    await self.db.commit()
                    await self.db.refresh(task)
                else:
                    self.db.commit()
                    self.db.refresh(task)
        
        # Step 4: Build task tree structure
        # Find root task (task with no parent_id)
        root_task = None
        for task in created_tasks:
            if task.parent_id is None:
                root_task = task
                break
        
        if not root_task:
            raise ValueError(
                "No root task found (task with no parent_id). "
                "At least one task in the array must have parent_id=None or no parent_id field."
            )
        
        root_node = await self._build_task_tree(root_task, created_tasks)
        
        logger.info(f"Created task tree: root task {root_node.task.name} "
                    f"with {len(root_node.children)} direct children")
        return root_node
    
    def _validate_dependencies(
        self,
        dependencies: List[Any],
        task_name: str,
        task_index: int,
        provided_ids: Set[str],
        id_to_index: Dict[str, int],
        task_names: Set[str],
        name_to_index: Dict[str, int]
    ) -> None:
        """
        Validate dependencies exist in the array and hierarchy is correct
        
        Args:
            dependencies: Dependencies list from task data
            task_name: Name of the task (for error messages)
            task_index: Index of the task in the array
            provided_ids: Set of all provided task IDs
            id_to_index: Map of id -> index in array
            task_names: Set of all task names (for name-based references)
            name_to_index: Map of name -> index in array
            
        Raises:
            ValueError: If dependencies are invalid
        """
        for dep in dependencies:
            if isinstance(dep, dict):
                # Support both "id" and "name" for dependency reference
                dep_ref = dep.get("id") or dep.get("name")
                if not dep_ref:
                    raise ValueError(f"Task '{task_name}' dependency must have 'id' or 'name' field")
                
                # Validate dependency exists in the array (as id or name)
                dep_index = None
                if dep_ref in provided_ids:
                    dep_index = id_to_index.get(dep_ref)
                elif dep_ref in task_names:
                    dep_index = name_to_index.get(dep_ref)
                else:
                    raise ValueError(
                        f"Task '{task_name}' at index {task_index} has dependency reference '{dep_ref}' "
                        f"which is not in the tasks array (not found as id or name)"
                    )
                
                # Validate hierarchy: dependency should be at an earlier index (or same level)
                if dep_index is not None and dep_index >= task_index:
                    # This is allowed for same-level dependencies, but log a warning
                    logger.debug(
                        f"Task '{task_name}' at index {task_index} depends on task at index {dep_index}. "
                        f"This is allowed but may indicate a potential issue."
                    )
            else:
                # Simple string dependency (can be id or name)
                dep_ref = str(dep)
                if dep_ref not in provided_ids and dep_ref not in task_names:
                    raise ValueError(
                        f"Task '{task_name}' at index {task_index} has dependency '{dep_ref}' "
                        f"which is not in the tasks array (not found as id or name)"
                    )
    
    async def _build_task_tree(
        self,
        root_task: TaskModel,
        all_tasks: List[TaskModel]
    ) -> TaskTreeNode:
        """
        Build task tree structure from root task
        
        Args:
            root_task: Root task
            all_tasks: All created tasks
            
        Returns:
            TaskTreeNode: Root task node with children
        """
        # Create task node
        task_node = TaskTreeNode(task=root_task)
        
        # Find children (tasks with parent_id == root_task.id)
        children = [task for task in all_tasks if task.parent_id == root_task.id]
        
        # Recursively build children
        for child_task in children:
            child_node = await self._build_task_tree(child_task, all_tasks)
            task_node.add_child(child_node)
        
        return task_node
    
    def tree_to_flat_list(self, root_node: TaskTreeNode) -> List[TaskModel]:
        """
        Convert tree structure to flat list for database operations
        
        Args:
            root_node: Root task node
            
        Returns:
            List[TaskModel]: Flat list of all tasks in the tree
        """
        tasks = [root_node.task]
        
        def collect_children(node: TaskTreeNode):
            for child in node.children:
                tasks.append(child.task)
                collect_children(child)
        
        collect_children(root_node)
        return tasks


__all__ = [
    "TaskCreator",
]
