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
            "inputs": {"url": "https://example.com"},
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
import copy
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from aipartnerupflow.core.execution.task_manager import TaskManager
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.core.config import get_task_model_class

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
                "inputs": {"url": "https://example.com"},
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
                - inputs: Execution-time input parameters (optional)
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
        
        # Step 2: Validate all tasks first (parent_id, dependencies)
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
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
        
        # Step 2.5: Detect circular dependencies before creating tasks
        self._detect_circular_dependencies(
            tasks, provided_ids, provided_id_to_index, task_names, task_name_to_index
        )
        
        # Step 2.6: Validate dependent task inclusion
        # Ensure all tasks that depend on tasks in the tree are also included
        self._validate_dependent_task_inclusion(
            tasks, provided_ids, task_names
        )
        
        # Step 3: Create all tasks
        created_tasks: List[TaskModel] = []
        identifier_to_task: Dict[str, TaskModel] = {}  # id or name -> TaskModel
        
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            # user_id is optional (can be None) - get directly from task_data
            task_user_id = task_data.get("user_id")
            
            # Check if provided_id already exists in database
            # If it exists, generate a new UUID to avoid primary key conflict
            actual_id = provided_id
            if provided_id:
                existing_task = await self.task_manager.task_repository.get_task_by_id(provided_id)
                if existing_task:
                    # ID already exists, generate new UUID
                    import uuid
                    actual_id = str(uuid.uuid4())
                    logger.warning(
                        f"Task ID '{provided_id}' already exists in database. "
                        f"Generating new ID '{actual_id}' to avoid conflict."
                    )
                    # Update the task_data to use the new ID for internal reference tracking
                    # Note: We'll still use provided_id for identifier_to_task mapping
                    # but create the task with actual_id
            
            # Create task (parent_id and dependencies will be set in step 4)
            # Use actual_id (may be different from provided_id if conflict detected)
            logger.debug(f"Creating task: name={task_name}, provided_id={provided_id}, actual_id={actual_id}")
            task = await self.task_manager.task_repository.create_task(
                name=task_name,
                user_id=task_user_id,
                parent_id=None,  # Will be set in step 4
                priority=task_data.get("priority", 1),
                dependencies=None,  # Will be set in step 4
                inputs=task_data.get("inputs"),
                schemas=task_data.get("schemas"),
                params=task_data.get("params"),
                id=actual_id  # Use actual_id (may be auto-generated if provided_id conflicts)
            )
            
            logger.debug(f"Task created: id={task.id}, name={task.name}, provided_id={provided_id}, actual_id={actual_id}")
            
            # Verify the task was created with the expected ID
            # If actual_id was generated due to conflict, task.id should match actual_id (not provided_id)
            expected_id = actual_id if actual_id else provided_id
            if expected_id and task.id != expected_id:
                logger.error(
                    f"Task ID mismatch: expected {expected_id}, got {task.id}. "
                    f"This indicates an issue with ID assignment."
                )
                raise ValueError(
                    f"Task ID mismatch: expected {expected_id}, got {task.id}. "
                    f"Task was not created with the expected ID."
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
        
        # Step 4: Set parent_id and dependencies using actual task ids
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
        
        # Step 5: Build task tree structure
        # Find root task (task with no parent_id)
        root_tasks = [task for task in created_tasks if task.parent_id is None]
        
        if not root_tasks:
            raise ValueError(
                "No root task found (task with no parent_id). "
                "At least one task in the array must have parent_id=None or no parent_id field."
            )
        
        if len(root_tasks) > 1:
            root_task_names = [task.name for task in root_tasks]
            raise ValueError(
                f"Multiple root tasks found: {root_task_names}. "
                f"All tasks must be in a single task tree. "
                f"Only one task should have parent_id=None or no parent_id field."
            )
        
        root_task = root_tasks[0]
        
        # Verify all tasks are reachable from the root task (in the same tree)
        # Build a set of all task IDs that are reachable from root
        reachable_task_ids: Set[str] = {root_task.id}
        
        def collect_reachable_tasks(task_id: str):
            """Recursively collect all tasks reachable from the given task via parent_id chain"""
            for task in created_tasks:
                if task.parent_id == task_id and task.id not in reachable_task_ids:
                    reachable_task_ids.add(task.id)
                    collect_reachable_tasks(task.id)
        
        collect_reachable_tasks(root_task.id)
        
        # Check if all tasks are reachable
        all_task_ids = {task.id for task in created_tasks}
        unreachable_task_ids = all_task_ids - reachable_task_ids
        
        if unreachable_task_ids:
            unreachable_task_names = [
                task.name for task in created_tasks 
                if task.id in unreachable_task_ids
            ]
            raise ValueError(
                f"Tasks not in the same tree: {unreachable_task_names}. "
                f"All tasks must be reachable from the root task via parent_id chain. "
                f"These tasks are not connected to the root task '{root_task.name}'."
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
    
    def _detect_circular_dependencies(
        self,
        tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        id_to_index: Dict[str, int],
        task_names: Set[str],
        name_to_index: Dict[str, int]
    ) -> None:
        """
        Detect circular dependencies in task array using DFS.
        
        Args:
            tasks: List of task dictionaries
            provided_ids: Set of all provided task IDs
            id_to_index: Map of id -> index in array
            task_names: Set of all task names
            name_to_index: Map of name -> index in array
            
        Raises:
            ValueError: If circular dependencies are detected
        """
        # Build dependency graph: identifier -> set of identifiers it depends on
        dependency_graph: Dict[str, Set[str]] = {}
        identifier_to_name: Dict[str, str] = {}  # identifier -> task name for error messages
        
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            # Use id if provided, otherwise use name as identifier
            identifier = provided_id if provided_id else task_name
            identifier_to_name[identifier] = task_name
            
            # Initialize empty set for this task
            dependency_graph[identifier] = set()
            
            # Collect all dependencies for this task
            dependencies = task_data.get("dependencies")
            if dependencies:
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_ref = dep.get("id") or dep.get("name")
                        if dep_ref:
                            dependency_graph[identifier].add(dep_ref)
                    else:
                        dep_ref = str(dep)
                        dependency_graph[identifier].add(dep_ref)
        
        # DFS to detect cycles
        # visited: all nodes we've visited (completely processed)
        # rec_stack: nodes in current recursion stack (path from root, indicates potential cycle)
        visited: Set[str] = set()
        
        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            """
            DFS to detect cycles.
            
            Args:
                node: Current node being visited
                path: Current path from root to this node
            
            Returns:
                Cycle path if cycle detected, None otherwise
            """
            if node in path:
                # Found a cycle - extract the cycle path
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]  # Complete the cycle
                return cycle
            
            if node in visited:
                # Already processed this node completely, no cycle from here
                return None
            
            # Mark as visited and add to current path
            visited.add(node)
            path.append(node)
            
            # Visit all dependencies
            # Only visit dependencies that exist in the graph (should have been validated already)
            node_deps = dependency_graph.get(node, set())
            for dep in node_deps:
                # Skip if dependency is not in the graph (shouldn't happen after validation, but be safe)
                if dep not in dependency_graph:
                    continue
                cycle = dfs(dep, path)
                if cycle:
                    return cycle
            
            # Remove from current path (backtrack)
            path.pop()
            return None
        
        # Check all nodes for cycles
        for identifier in dependency_graph.keys():
            if identifier not in visited:
                cycle_path = dfs(identifier, [])
                if cycle_path:
                    # Format cycle path with task names for better error message
                    cycle_names = [identifier_to_name.get(id, id) for id in cycle_path]
                    raise ValueError(
                        f"Circular dependency detected: {' -> '.join(cycle_names)}. "
                        f"Tasks cannot have circular dependencies as this would cause infinite loops."
                    )
    
    def _find_dependent_tasks(
        self,
        task_identifier: str,
        all_tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        task_names: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Find all tasks that depend on the specified task identifier.
        
        Args:
            task_identifier: Task identifier (id or name) to find dependents for
            all_tasks: All tasks in the array
            provided_ids: Set of all provided task IDs
            task_names: Set of all task names
            
        Returns:
            List of tasks that depend on the specified task identifier
        """
        dependent_tasks = []
        
        for task_data in all_tasks:
            dependencies = task_data.get("dependencies")
            if not dependencies:
                continue
            
            # Check if this task depends on the specified task_identifier
            for dep in dependencies:
                if isinstance(dep, dict):
                    dep_ref = dep.get("id") or dep.get("name")
                    if dep_ref == task_identifier:
                        dependent_tasks.append(task_data)
                        break
                else:
                    dep_ref = str(dep)
                    if dep_ref == task_identifier:
                        dependent_tasks.append(task_data)
                        break
        
        return dependent_tasks
    
    def _find_transitive_dependents(
        self,
        task_identifiers: Set[str],
        all_tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        task_names: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Find all tasks that depend on any of the specified task identifiers (including transitive).
        
        Args:
            task_identifiers: Set of task identifiers (id or name) to find dependents for
            all_tasks: All tasks in the array
            provided_ids: Set of all provided task IDs
            task_names: Set of all task names
            
        Returns:
            List of tasks that depend on any of the specified task identifiers (directly or transitively)
        """
        # Track all dependent tasks found (to avoid duplicates)
        found_dependents: Set[int] = set()  # Track by index to avoid duplicates
        dependent_tasks: List[Dict[str, Any]] = []
        
        # Start with the initial set of task identifiers
        current_identifiers = task_identifiers.copy()
        processed_identifiers: Set[str] = set()
        
        # Recursively find all transitive dependents
        while current_identifiers:
            next_identifiers: Set[str] = set()
            
            for identifier in current_identifiers:
                if identifier in processed_identifiers:
                    continue
                processed_identifiers.add(identifier)
                
                # Find direct dependents
                for index, task_data in enumerate(all_tasks):
                    if index in found_dependents:
                        continue
                    
                    dependencies = task_data.get("dependencies")
                    if not dependencies:
                        continue
                    
                    # Check if this task depends on the current identifier
                    depends_on_identifier = False
                    for dep in dependencies:
                        if isinstance(dep, dict):
                            dep_ref = dep.get("id") or dep.get("name")
                            if dep_ref == identifier:
                                depends_on_identifier = True
                                break
                        else:
                            dep_ref = str(dep)
                            if dep_ref == identifier:
                                depends_on_identifier = True
                                break
                    
                    if depends_on_identifier:
                        found_dependents.add(index)
                        dependent_tasks.append(task_data)
                        
                        # Add this task's identifier to next iteration
                        task_identifier = task_data.get("id") or task_data.get("name")
                        if task_identifier and task_identifier not in processed_identifiers:
                            next_identifiers.add(task_identifier)
            
            current_identifiers = next_identifiers
        
        return dependent_tasks
    
    def _validate_dependent_task_inclusion(
        self,
        tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        task_names: Set[str]
    ) -> None:
        """
        Validate that all tasks that depend on tasks in the tree are also included.
        
        Args:
            tasks: List of task dictionaries
            provided_ids: Set of all provided task IDs
            task_names: Set of all task names
            
        Raises:
            ValueError: If dependent tasks are missing
        """
        # Collect all task identifiers in the current tree
        tree_identifiers: Set[str] = set()
        for task_data in tasks:
            provided_id = task_data.get("id")
            task_name = task_data.get("name")
            if provided_id:
                tree_identifiers.add(provided_id)
            else:
                tree_identifiers.add(task_name)
        
        # Find all tasks that depend on tasks in the tree (including transitive)
        all_dependent_tasks = self._find_transitive_dependents(
            tree_identifiers, tasks, provided_ids, task_names
        )
        
        # Check if all dependent tasks are included in the tree
        included_identifiers = tree_identifiers.copy()
        missing_dependents = []
        
        for dep_task in all_dependent_tasks:
            dep_identifier = dep_task.get("id") or dep_task.get("name")
            if dep_identifier and dep_identifier not in included_identifiers:
                missing_dependents.append(dep_task)
        
        if missing_dependents:
            missing_names = [task.get("name", "Unknown") for task in missing_dependents]
            raise ValueError(
                f"Missing dependent tasks: {missing_names}. "
                f"All tasks that depend on tasks in the tree must be included. "
                f"These tasks depend on tasks in the tree but are not included in the tasks array."
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
    
    async def create_task_copy(
        self,
        original_task: TaskModel,
        children: bool = False,
        copy_mode: str = "minimal",
        custom_task_ids: Optional[List[str]] = None,
        custom_include_children: bool = False,
        reset_fields: Optional[List[str]] = None,
        save: bool = True
    ) -> Union[TaskTreeNode, List[Dict[str, Any]]]:
        """
        Create a copy of a task tree for re-execution.
        
        Preserves original task results while creating new execution instance.
        Automatically includes dependent tasks (tasks that depend on this task and its children,
        including transitive dependencies).
        
        Args:
            original_task: Original task to copy (can be root or any task in tree)
            children: If True, also copy each direct child task with its dependencies.
                     When copying children, tasks that depend on multiple copied tasks are
                     only copied once (deduplication by task ID).
            copy_mode: Copy mode - "minimal" (default), "full", or "custom"
                - "minimal": Copies minimal subtree (original_task + children + dependents)
                - "full": Copies complete tree from root, marks unrelated tasks as completed
                - "custom": Copies only specified custom_task_ids with auto-include dependencies
            custom_task_ids: List of task IDs to copy (required when copy_mode="custom")
            custom_include_children: If True, also include all children recursively (used when copy_mode="custom")
            reset_fields: Optional list of field names to reset.
                         If None, use default reset behavior.
                         Valid fields: "status", "progress", "result", "error",
                                      "started_at", "completed_at", "updated_at"
            save: If True, save to database and return TaskTreeNode.
                  If False, return task array (List[Dict]) without saving.
        
        Returns:
            TaskTreeNode with saved tasks if save=True,
            List[Dict[str, Any]] task array compatible with tasks.create if save=False
        """
        if copy_mode == "full":
            result = await self.create_task_copy_full(original_task, reset_fields, save)
        elif copy_mode == "custom":
            if not custom_task_ids:
                raise ValueError("custom_task_ids is required when copy_mode='custom'")
            result = await self.create_task_copy_custom(original_task, custom_task_ids, custom_include_children, reset_fields, save)
        else:
            result = await self.create_task_copy_minimal(original_task, children, reset_fields, save)
        
        # If not saving, convert TaskTreeNode to task array
        if not save and isinstance(result, TaskTreeNode):
            return self._tree_to_task_array(result)
        
        return result
    
    async def create_task_copy_minimal(
        self,
        original_task: TaskModel,
        children: bool = False,
        reset_fields: Optional[List[str]] = None,
        save: bool = True
    ) -> TaskTreeNode:
        """
        Create a copy of a task tree for re-execution (minimal mode).
        
        Preserves original task results while creating new execution instance.
        Automatically includes dependent tasks (tasks that depend on this task and its children,
        including transitive dependencies).
        
        Process:
        1. Get root task and all tasks in the tree for dependency lookup
        2. Build original_task's subtree (original_task + all its children)
        3. If children=True, also collect identifiers from each direct child's subtree
        4. Collect all task identifiers (id or name) from the subtree(s)
        5. Find all tasks that depend on these identifiers (including transitive dependencies)
           - Special handling for failed leaf nodes:
             * Check if original_subtree contains any failed leaf nodes
             * If failed leaf nodes exist: filter out pending dependent tasks
             * If no failed leaf nodes: copy all dependent tasks
        6. Collect all required task IDs (original_task subtree + filtered dependent tasks)
        7. Build minimal subtree containing all required tasks
        8. Copy entire tree structure
        9. Save copied tree to database
        10. Mark all original tasks as having copies
        
        Args:
            original_task: Original task to copy (can be root or any task in tree)
            children: If True, also copy each direct child task with its dependencies.
                     When copying children, tasks that depend on multiple copied tasks are
                     only copied once (deduplication by task ID).
            
        Returns:
            TaskTreeNode with copied task tree, all tasks linked to original via original_task_id
        """
        logger.info(f"Creating task copy (minimal mode) for original task {original_task.id}, children={children}")
        
        # Step 1: Get root task and all tasks in the tree for dependency lookup
        # Note: children=True only supports dependencies within the same root tree
        root_task = await self.task_manager.task_repository.get_root_task(original_task)
        all_tasks = await self.task_manager.task_repository.get_all_tasks_in_tree(root_task)
        
        # Step 2: Build original_task's subtree (original_task + all its children)
        original_subtree = await self.task_manager.task_repository.build_task_tree(original_task)
        
        # Step 3: Collect all task identifiers (id or name) from the subtree
        task_identifiers = self._collect_task_identifiers_from_tree(original_subtree)
        
        # If children=True, also collect identifiers from each direct child's subtree
        if children:
            for child_node in original_subtree.children:
                child_identifiers = self._collect_task_identifiers_from_tree(child_node)
                task_identifiers.update(child_identifiers)
                logger.info(f"Collected {len(child_identifiers)} task identifiers from child {child_node.task.id} subtree")
        
        logger.info(f"Collected {len(task_identifiers)} total task identifiers (original_task + {'children' if children else 'no children'}): {task_identifiers}")
        
        # Step 4: Find all tasks that depend on these identifiers (including transitive dependencies)
        dependent_tasks = []
        if task_identifiers:
            all_dependent_tasks = await self._find_dependent_tasks_for_identifiers(task_identifiers, all_tasks)
            
            # Check if original_subtree contains any failed leaf nodes
            def has_failed_leaf_nodes(node: TaskTreeNode) -> bool:
                """Check if tree contains any failed leaf nodes"""
                task_status = getattr(node.task, 'status', None)
                is_leaf = not node.children
                is_failed_leaf = (task_status == "failed" and is_leaf)
                
                if is_failed_leaf:
                    return True
                
                # Recursively check children
                for child in node.children:
                    if has_failed_leaf_nodes(child):
                        return True
                
                return False
            
            has_failed_leaves = has_failed_leaf_nodes(original_subtree)
            
            if has_failed_leaves:
                # For tasks containing failed leaf nodes, only copy dependents that are NOT pending
                for dep_task in all_dependent_tasks:
                    dep_status = getattr(dep_task, 'status', None)
                    if dep_status != "pending":
                        dependent_tasks.append(dep_task)
                
                if all_dependent_tasks:
                    pending_count = len(all_dependent_tasks) - len(dependent_tasks)
                    logger.info(f"Found {len(all_dependent_tasks)} dependent tasks for subtree with failed leaf nodes, "
                              f"filtering out {pending_count} pending tasks, keeping {len(dependent_tasks)} non-pending tasks")
            else:
                # For other cases (no failed leaf nodes), copy all dependents
                dependent_tasks = all_dependent_tasks
                if dependent_tasks:
                    logger.info(f"Found {len(dependent_tasks)} dependent tasks for original_task subtree")
        
        # Step 5: Collect all required task IDs
        required_task_ids = set()
        
        # Add all tasks from original_task subtree
        def collect_subtree_task_ids(node: TaskTreeNode):
            required_task_ids.add(str(node.task.id))
            for child in node.children:
                collect_subtree_task_ids(child)
        
        collect_subtree_task_ids(original_subtree)
        
        # Add all dependent tasks
        for dep_task in dependent_tasks:
            required_task_ids.add(str(dep_task.id))
        
        logger.info(f"Total {len(required_task_ids)} tasks to copy: {len(self.tree_to_flat_list(original_subtree))} from original_task subtree + {len(dependent_tasks)} dependent tasks")
        
        # Step 6: Build minimal subtree containing all required tasks
        # Note: children=True only supports dependencies within the same root tree
        if not dependent_tasks:
            # No dependents: use original_task subtree directly
            minimal_tree = original_subtree
            logger.info("No dependents found, using original_task subtree directly")
        else:
            # Has dependents: find minimal subtree that includes original_task + all dependents
            # All dependents should be in the same root tree (children=True only supports same root tree)
            root_tree = await self.task_manager.task_repository.build_task_tree(root_task)
            minimal_tree = await self._find_minimal_subtree(root_tree, required_task_ids)
            
            if not minimal_tree:
                # Fallback: use original_subtree
                logger.warning("Could not build minimal subtree with dependents, falling back to original_task subtree")
                minimal_tree = original_subtree
        
        root_original_task_id = minimal_tree.task.id
        
        # Step 7: Copy entire tree structure (all tasks pending for re-execution in minimal mode)
        new_tree = await self._copy_task_tree_recursive(
            minimal_tree, root_original_task_id, None, None, reset_fields, save=save
        )
        
        # If not saving, return tree (will be converted to array by create_task_copy)
        if not save:
            logger.info(f"Created task copy preview (minimal mode): {len(self.tree_to_flat_list(new_tree))} tasks, not saved to database")
            return new_tree
        
        # Step 8: Save copied tree to database
        await self._save_copied_task_tree(new_tree, None)
        
        # Step 9: Mark all original tasks as having copies
        await self._mark_original_tasks_has_copy(minimal_tree)
        if self.task_manager.is_async:
            await self.db.commit()
        else:
            self.db.commit()
        
        logger.info(f"Created task copy (minimal mode): root task {new_tree.task.id} (original: {root_original_task_id}, includes {len(dependent_tasks)} dependent tasks)")
        
        return new_tree
    
    def _collect_task_identifiers_from_tree(self, node: TaskTreeNode) -> Set[str]:
        """
        Collect all task identifiers (id or name) from a task tree.
        
        Args:
            node: Task tree node
            
        Returns:
            Set of task identifiers in the tree
        """
        identifiers = set()
        # Use id as identifier (primary)
        identifiers.add(str(node.task.id))
        # Also use name if available (for dependency matching)
        if node.task.name:
            identifiers.add(node.task.name)
        
        for child_node in node.children:
            identifiers.update(self._collect_task_identifiers_from_tree(child_node))
        
        return identifiers
    
    async def _find_dependent_tasks_for_identifiers(
        self,
        task_identifiers: Set[str],
        all_tasks: List[TaskModel]
    ) -> List[TaskModel]:
        """
        Find all tasks that depend on any of the specified task identifiers (including transitive dependencies).
        
        Args:
            task_identifiers: Set of task identifiers (id or name) to find dependents for
            all_tasks: All tasks in the same context
            
        Returns:
            List of tasks that depend on any of the specified identifiers (directly or transitively)
        """
        if not task_identifiers:
            return []
        
        # Find tasks that directly depend on any of these identifiers
        dependent_tasks = []
        for task in all_tasks:
            dependencies = getattr(task, 'dependencies', None)
            if dependencies and isinstance(dependencies, list):
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_id = dep.get("id")
                        dep_name = dep.get("name")
                        if dep_id in task_identifiers or dep_name in task_identifiers:
                            dependent_tasks.append(task)
                            break
                    else:
                        # Simple string dependency
                        dep_ref = str(dep)
                        if dep_ref in task_identifiers:
                            dependent_tasks.append(task)
                            break
        
        # Recursively find tasks that depend on the dependent tasks
        all_dependent_tasks = set(dependent_tasks)
        processed_identifiers = set(task_identifiers)
        
        async def find_transitive_dependents(current_dependent_tasks: List[TaskModel]):
            """Recursively find tasks that depend on current dependent tasks"""
            new_dependents = []
            for dep_task in current_dependent_tasks:
                dep_id = str(dep_task.id)
                dep_name = dep_task.name if dep_task.name else None
                dep_identifiers = {dep_id}
                if dep_name:
                    dep_identifiers.add(dep_name)
                
                # Only process if not already processed
                if not dep_identifiers.intersection(processed_identifiers):
                    processed_identifiers.update(dep_identifiers)
                    # Find tasks that depend on this dependent task
                    for task in all_tasks:
                        if task in all_dependent_tasks:
                            continue  # Already in the set
                        task_deps = getattr(task, 'dependencies', None)
                        if task_deps and isinstance(task_deps, list):
                            for dep in task_deps:
                                if isinstance(dep, dict):
                                    dep_id = dep.get("id")
                                    dep_name = dep.get("name")
                                    if dep_id in dep_identifiers or dep_name in dep_identifiers:
                                        new_dependents.append(task)
                                        all_dependent_tasks.add(task)
                                        break
                                else:
                                    dep_ref = str(dep)
                                    if dep_ref in dep_identifiers:
                                        new_dependents.append(task)
                                        all_dependent_tasks.add(task)
                                        break
            
            if new_dependents:
                await find_transitive_dependents(new_dependents)
        
        await find_transitive_dependents(dependent_tasks)
        
        return list(all_dependent_tasks)
    
    async def _find_dependency_tasks_for_identifiers(
        self,
        task_identifiers: Set[str],
        all_tasks: List[TaskModel]
    ) -> List[TaskModel]:
        """
        Find all tasks that the specified task identifiers depend on (upstream dependencies, including transitive).
        
        Args:
            task_identifiers: Set of task identifiers (id or name) to find dependencies for
            all_tasks: All tasks in the same context
            
        Returns:
            List of tasks that the specified identifiers depend on (directly or transitively)
        """
        if not task_identifiers:
            return []
        
        # Build a map of task identifier to task for quick lookup
        tasks_by_identifier: Dict[str, TaskModel] = {}
        for task in all_tasks:
            task_id = str(task.id)
            tasks_by_identifier[task_id] = task
            if task.name:
                tasks_by_identifier[task.name] = task
        
        # Find tasks that directly depend on any of these identifiers (these are the upstream dependencies)
        dependency_tasks = []
        processed_identifiers = set(task_identifiers)
        identifiers_to_process = set(task_identifiers)
        
        async def find_transitive_dependencies(current_identifiers: Set[str]):
            """Recursively find tasks that current identifiers depend on"""
            new_dependency_identifiers = set()
            
            # For each task with an identifier in current_identifiers, find its dependencies
            for task in all_tasks:
                task_id = str(task.id)
                task_name = task.name if task.name else None
                
                # Check if this task is in current_identifiers
                if task_id not in current_identifiers and task_name not in current_identifiers:
                    continue
                
                # Get dependencies for this task
                dependencies = getattr(task, 'dependencies', None)
                if dependencies and isinstance(dependencies, list):
                    for dep in dependencies:
                        if isinstance(dep, dict):
                            dep_id = dep.get("id")
                            dep_name = dep.get("name")
                            dep_identifier = dep_id or dep_name
                        else:
                            dep_identifier = str(dep)
                        
                        if dep_identifier and dep_identifier not in processed_identifiers:
                            # Found a new dependency identifier
                            processed_identifiers.add(dep_identifier)
                            new_dependency_identifiers.add(dep_identifier)
                            
                            # If this dependency identifier corresponds to a task, add it to dependency_tasks
                            if dep_identifier in tasks_by_identifier:
                                dep_task = tasks_by_identifier[dep_identifier]
                                if dep_task not in dependency_tasks:
                                    dependency_tasks.append(dep_task)
            
            # Recursively process new dependency identifiers
            if new_dependency_identifiers:
                await find_transitive_dependencies(new_dependency_identifiers)
        
        await find_transitive_dependencies(identifiers_to_process)
        
        return dependency_tasks
    
    async def _find_minimal_subtree(
        self,
        root_tree: TaskTreeNode,
        required_task_ids: Set[str]
    ) -> Optional[TaskTreeNode]:
        """
        Find minimal subtree that contains all required tasks.
        Returns None if not all required tasks are found in the tree.
        
        Args:
            root_tree: Root task tree to search in
            required_task_ids: Set of task IDs that must be included
            
        Returns:
            Minimal TaskTreeNode containing all required tasks, or None
        """
        def collect_task_ids(node: TaskTreeNode) -> Set[str]:
            """Collect all task IDs in the tree"""
            task_ids = {str(node.task.id)}
            for child in node.children:
                task_ids.update(collect_task_ids(child))
            return task_ids
        
        # Check if all required tasks are in the tree
        all_task_ids = collect_task_ids(root_tree)
        if not required_task_ids.issubset(all_task_ids):
            return None
        
        def build_minimal_subtree(node: TaskTreeNode) -> Optional[TaskTreeNode]:
            """Build minimal subtree containing required tasks"""
            # Collect task IDs in this subtree
            subtree_task_ids = collect_task_ids(node)
            
            # Check if this subtree contains any required tasks
            if not subtree_task_ids.intersection(required_task_ids):
                return None
            
            # If this node is required or has required descendants, include it
            new_node = TaskTreeNode(task=node.task)
            
            for child in node.children:
                child_subtree = build_minimal_subtree(child)
                if child_subtree:
                    new_node.add_child(child_subtree)
            
            return new_node
        
        return build_minimal_subtree(root_tree)
    
    async def create_task_copy_custom(
        self,
        original_task: TaskModel,
        custom_task_ids: List[str],
        custom_include_children: bool = False,
        reset_fields: Optional[List[str]] = None,
        save: bool = True
    ) -> TaskTreeNode:
        """
        Create a copy of specified tasks for re-execution (custom mode).
        
        Copies only specified task_ids, automatically includes missing dependencies,
        and optionally includes children based on include_children parameter.
        
        Process:
        1. Get root task and build complete tree from root
        2. Validate all task_ids exist in the tree
        3. Automatically include missing dependencies recursively
        4. Optionally include children if include_children=True
        5. Build minimal subtree containing all required tasks
        6. Copy filtered tree (all tasks marked as pending)
        7. Mark all original tasks as having copies
        
        Args:
            original_task: Original task to copy (used to find root task)
            task_ids: List of task IDs to copy (required)
            include_children: If True, also include all children recursively
            reset_fields: Optional list of field names to reset.
            
        Returns:
            TaskTreeNode with copied task tree, all tasks linked to original via original_task_id
            
        Raises:
            ValueError: If any task_id is not found in the tree
        """
        logger.info(f"Creating task copy (custom mode) for custom_task_ids: {custom_task_ids}, custom_include_children={custom_include_children}")
        
        # Step 1: Get root task and build complete tree from root
        root_task = await self.task_manager.task_repository.get_root_task(original_task)
        root_tree = await self.task_manager.task_repository.build_task_tree(root_task)
        all_tasks = await self.task_manager.task_repository.get_all_tasks_in_tree(root_task)
        
        # Step 2: Validate all custom_task_ids exist in the tree
        all_task_ids = {str(task.id) for task in all_tasks}
        missing_ids = set(custom_task_ids) - all_task_ids
        if missing_ids:
            raise ValueError(f"Task IDs not found in tree: {missing_ids}")
        
        # Step 3: Collect required task IDs (custom_task_ids + dependencies + optional children)
        required_task_ids = set(custom_task_ids)
        
        # Collect task identifiers for dependency resolution
        task_identifiers = set()
        tasks_by_id: Dict[str, TaskModel] = {}
        for task in all_tasks:
            task_id = str(task.id)
            tasks_by_id[task_id] = task
            if task_id in custom_task_ids:
                task_identifiers.add(task_id)
                if task.name:
                    task_identifiers.add(task.name)
        
        # Automatically include missing dependencies recursively
        if task_identifiers:
            dependency_tasks = await self._find_dependency_tasks_for_identifiers(task_identifiers, all_tasks)
            for dep_task in dependency_tasks:
                required_task_ids.add(str(dep_task.id))
            if dependency_tasks:
                logger.info(f"Found {len(dependency_tasks)} upstream dependency tasks: {[t.id for t in dependency_tasks]}")
        
        # Optionally include children if custom_include_children=True
        if custom_include_children:
            def collect_children_ids(node: TaskTreeNode, target_ids: Set[str], collected: Set[str]):
                """Recursively collect children IDs for tasks in target_ids"""
                task_id = str(node.task.id)
                if task_id in target_ids and task_id not in collected:
                    collected.add(task_id)
                    for child in node.children:
                        required_task_ids.add(str(child.task.id))
                        collect_children_ids(child, target_ids, collected)
            
            collected = set()
            def traverse_tree(node: TaskTreeNode):
                collect_children_ids(node, set(custom_task_ids), collected)
                for child in node.children:
                    traverse_tree(child)
            
            traverse_tree(root_tree)
            logger.info(f"Included children: {len(required_task_ids) - len(set(custom_task_ids)) - len(dependency_tasks)} additional tasks")
        
        # Step 4: Build minimal subtree containing all required tasks
        minimal_tree = await self._find_minimal_subtree(root_tree, required_task_ids)
        if not minimal_tree:
            raise ValueError(f"Could not build minimal subtree containing all required tasks: {required_task_ids}")
        
        root_original_task_id = minimal_tree.task.id
        
        # Step 5: Copy filtered tree (all tasks marked as pending in custom mode)
        new_tree = await self._copy_task_tree_recursive(
            minimal_tree,
            root_original_task_id,
            None,
            None,  # All tasks are pending in custom mode
            reset_fields,
            save=save
        )
        
        # If not saving, return tree (will be converted to array by create_task_copy)
        if not save:
            logger.info(f"Created task copy preview (custom mode): {len(required_task_ids)} tasks, not saved to database")
            return new_tree
        
        # Step 6: Save copied tree to database
        await self._save_copied_task_tree(new_tree, None)
        
        # Step 7: Mark all original tasks as having copies
        await self._mark_original_tasks_has_copy(minimal_tree)
        
        # Step 8: Commit all changes
        if self.task_manager.is_async:
            await self.db.commit()
        else:
            self.db.commit()
        
        logger.info(f"Created task copy (custom mode): root task {new_tree.task.id} (original: {root_original_task_id}), "
                   f"{len(required_task_ids)} tasks copied")
        
        return new_tree
    
    async def create_task_copy_full(
        self,
        original_task: TaskModel,
        reset_fields: Optional[List[str]] = None,
        save: bool = True
    ) -> TaskTreeNode:
        """
        Create a copy of the complete task tree from root for re-execution (full mode).
        
        Always copies the full tree from root, analyzing dependencies to determine which tasks need re-execution.
        
        Process:
        1. Get root task and build complete tree from root
        2. Identify tasks that need re-execution:
           - Specified task + all its children
           - All upstream dependencies (tasks these depend on, recursively)
           - All downstream dependencies (tasks that depend on these, recursively)
        3. Copy complete tree from root
        4. Mark tasks appropriately:
           - Tasks in re-execution set → pending, reset all execution fields
           - Unrelated successful tasks → completed, preserve token_usage and result
        5. Mark all original tasks as having copies (has_copy=True)
        
        Args:
            original_task: Original task to copy (can be root or any task in tree)
            
        Returns:
            TaskTreeNode with copied task tree, all tasks linked to original via original_task_id
        """
        logger.info(f"Creating task copy (full mode) for original task {original_task.id} (always copying full tree from root)")
        
        # Step 1: Get root task and all tasks in the tree
        root_task = await self.task_manager.task_repository.get_root_task(original_task)
        all_tasks = await self.task_manager.task_repository.get_all_tasks_in_tree(root_task)
        
        # Step 2: Build complete tree from root
        root_tree = await self.task_manager.task_repository.build_task_tree(root_task)
        
        # Step 3: Build original_task's subtree (original_task + all its children)
        original_subtree = await self.task_manager.task_repository.build_task_tree(original_task)
        
        # Step 4: Collect all task identifiers (id or name) from the subtree
        task_identifiers = self._collect_task_identifiers_from_tree(original_subtree)
        logger.info(f"Collected {len(task_identifiers)} task identifiers from original_task subtree: {task_identifiers}")
        
        # Step 5: Find all tasks that need re-execution
        # This includes:
        # - Original task + all its children
        # - All upstream dependencies (tasks these codes depend on)
        # - All downstream dependencies (tasks that depend on these codes)
        tasks_to_re_execute_ids = set()
        
        # Add original task and all its children
        def collect_subtree_task_ids(node: TaskTreeNode):
            tasks_to_re_execute_ids.add(str(node.task.id))
            for child in node.children:
                collect_subtree_task_ids(child)
        
        collect_subtree_task_ids(original_subtree)
        
        # Find upstream dependencies (tasks that original_task subtree depends on)
        if task_identifiers:
            dependency_tasks = await self._find_dependency_tasks_for_identifiers(task_identifiers, all_tasks)
            for dep_task in dependency_tasks:
                tasks_to_re_execute_ids.add(str(dep_task.id))
            if dependency_tasks:
                logger.info(f"Found {len(dependency_tasks)} upstream dependency tasks: {[t.id for t in dependency_tasks]}")
        
        # Find downstream dependencies (tasks that depend on original_task subtree)
        if task_identifiers:
            dependent_tasks = await self._find_dependent_tasks_for_identifiers(task_identifiers, all_tasks)
            for dep_task in dependent_tasks:
                tasks_to_re_execute_ids.add(str(dep_task.id))
            if dependent_tasks:
                logger.info(f"Found {len(dependent_tasks)} downstream dependency tasks: {[t.id for t in dependent_tasks]}")
        
        logger.info(f"Total {len(tasks_to_re_execute_ids)} tasks need re-execution out of {len(all_tasks)} total tasks")
        
        # Step 6: Copy complete tree from root
        root_original_task_id = str(root_task.id)
        new_tree = await self._copy_task_tree_recursive(
            root_tree,
            root_original_task_id,
            None,
            tasks_to_re_execute_ids,
            reset_fields,
            save=save
        )
        
        # If not saving, return tree (will be converted to array by create_task_copy)
        if not save:
            logger.info(f"Created task copy preview (full mode): {len(all_tasks)} tasks, not saved to database")
            return new_tree
        
        # Step 7: Save copied tree to database
        await self._save_copied_task_tree(new_tree, None)
        
        # Step 8: Mark all original tasks as having copies
        await self._mark_original_tasks_has_copy(root_tree)
        
        # Step 9: Commit all changes
        if self.task_manager.is_async:
            await self.db.commit()
        else:
            self.db.commit()
        
        logger.info(f"Created task copy (full mode): root task {new_tree.task.id} (original: {root_task.id}), "
                   f"{len(tasks_to_re_execute_ids)} tasks marked for re-execution")
        
        return new_tree
    
    async def _copy_task_tree_recursive(
        self,
        original_node: TaskTreeNode,
        root_original_task_id: str,
        parent_id: Optional[str] = None,
        tasks_to_re_execute_ids: Optional[Set[str]] = None,
        reset_fields: Optional[List[str]] = None,
        save: bool = True
    ) -> TaskTreeNode:
        """
        Recursively copy task tree structure.
        
        Args:
            original_node: Original task tree node to copy
            root_original_task_id: Root task ID for original_task_id linkage
            parent_id: Parent task ID (will be set after saving)
            tasks_to_re_execute_ids: Optional set of task IDs that need re-execution.
                                   If provided, tasks in this set will be marked as pending,
                                   others will be marked as completed with preserved token_usage.
            reset_fields: Optional list of field names to reset.
                         If None, use default reset behavior.
            save: If True, save to database. If False, create in-memory instances only.
            
        Returns:
            New TaskTreeNode with copied task tree
        """
        # Determine if this task should be re-executed
        should_re_execute = True
        if tasks_to_re_execute_ids is not None:
            task_id = str(original_node.task.id)
            should_re_execute = task_id in tasks_to_re_execute_ids
        
        # Create new task from original with appropriate status
        if should_re_execute:
            new_task = await self._create_task_copy_from_original(
                original_node.task,
                root_original_task_id,
                parent_id,
                reset_fields,
                save=save
            )
        else:
            new_task = await self._create_task_copy_with_status(
                original_node.task,
                root_original_task_id,
                should_re_execute=False,
                parent_id=parent_id,
                reset_fields=reset_fields,
                save=save
            )
        
        # Create new task node
        new_node = TaskTreeNode(task=new_task)
        
        # Recursively copy children
        for child_node in original_node.children:
            child_new_node = await self._copy_task_tree_recursive(
                child_node,
                root_original_task_id,
                None,  # parent_id will be set after saving
                tasks_to_re_execute_ids,
                reset_fields,
                save=save
            )
            new_node.add_child(child_new_node)
        
        return new_node
    
    def _reset_task_fields(self, task: TaskModel, reset_fields: Optional[List[str]]):
        """
        Resets specified fields of a task to their default "pending" state values.
        If reset_fields is None, all default resettable fields are reset.
        
        Args:
            task: TaskModel instance to reset
            reset_fields: Optional list of field names to reset.
                         If None, all default resettable fields are reset.
                         Valid fields: "status", "progress", "result", "error",
                                      "started_at", "completed_at", "updated_at"
        """
        default_reset_fields = ["status", "progress", "result", "error", "started_at", "completed_at", "updated_at"]
        fields_to_reset = set(reset_fields) if reset_fields is not None else set(default_reset_fields)
        
        if "status" in fields_to_reset:
            task.status = "pending"
        if "progress" in fields_to_reset:
            task.progress = 0.0
        if "result" in fields_to_reset:
            task.result = None
        if "error" in fields_to_reset:
            task.error = None
        if "started_at" in fields_to_reset:
            task.started_at = None
        if "completed_at" in fields_to_reset:
            task.completed_at = None
        if "updated_at" in fields_to_reset:
            task.updated_at = datetime.now(timezone.utc)
    
    async def _create_task_copy_from_original(
        self,
        original_task: TaskModel,
        root_original_task_id: str,
        parent_id: Optional[str] = None,
        reset_fields: Optional[List[str]] = None,
        save: bool = True
    ) -> TaskModel:
        """
        Create a new task instance copied from original task (for re-execution).
        
        Args:
            original_task: Original task to copy from
            root_original_task_id: Root task ID for original_task_id linkage
            parent_id: Parent task ID (will be set after saving)
            reset_fields: Optional list of field names to reset.
            save: If True, save to database. If False, create in-memory instance only.
            
        Returns:
            New TaskModel instance ready for execution (status="pending")
        """
        return await self._create_task_copy_with_status(
            original_task,
            root_original_task_id,
            should_re_execute=True,
            parent_id=parent_id,
            reset_fields=reset_fields,
            save=save
        )
    
    async def _create_task_copy_with_status(
        self,
        original_task: TaskModel,
        root_original_task_id: str,
        should_re_execute: bool,
        parent_id: Optional[str] = None,
        reset_fields: Optional[List[str]] = None,
        save: bool = True
    ) -> TaskModel:
        """
        Create a new task instance copied from original task with appropriate status.
        
        Args:
            original_task: Original task to copy from
            root_original_task_id: Root task ID for original_task_id linkage
            should_re_execute: If True, task will be pending for re-execution.
                             If False, preserve completed status and token_usage.
            parent_id: Parent task ID (will be set after saving)
            reset_fields: Optional list of field names to reset.
                         If None, use default reset behavior.
                         Valid fields: "status", "progress", "result", "error",
                                      "started_at", "completed_at", "updated_at"
            save: If True, save to database. If False, create in-memory instance only.
            
        Returns:
            New TaskModel instance with appropriate status
        """
        # Safely get values from SQLAlchemy columns
        schemas_value = getattr(original_task, 'schemas', None)
        dependencies_value = getattr(original_task, 'dependencies', None)
        inputs_value = getattr(original_task, 'inputs', None)
        params_value = getattr(original_task, 'params', None)
        result_value = getattr(original_task, 'result', None)
        
        # Get current time for new task timestamps
        datetime.now(timezone.utc)
        
        # Get TaskModel class
        task_model_class = get_task_model_class()
        
        if should_re_execute:
            # Task needs re-execution: reset to pending, clear all execution results
            # Use original_task.id as original_task_id (not root_original_task_id) so dependencies can be correctly mapped
            # Explicitly generate UUID for task.id to ensure uniqueness and clear task tree relationships
            task_id = str(uuid.uuid4())
            if save:
                task = await self.task_manager.task_repository.create_task(
                    id=task_id,
                    name=original_task.name,
                    user_id=original_task.user_id,
                    parent_id=parent_id,
                    priority=original_task.priority,
                    dependencies=copy.deepcopy(dependencies_value) if dependencies_value else None,
                    inputs=copy.deepcopy(inputs_value) if inputs_value else None,
                    schemas=copy.deepcopy(schemas_value) if schemas_value else None,
                    params=copy.deepcopy(params_value) if params_value else None,
                    original_task_id=str(original_task.id),
                )
            else:
                # Create in-memory TaskModel instance without saving to database
                task = task_model_class(
                    id=task_id,
                    name=original_task.name,
                    user_id=original_task.user_id,
                    parent_id=parent_id,
                    priority=original_task.priority,
                    dependencies=copy.deepcopy(dependencies_value) if dependencies_value else None,
                    inputs=copy.deepcopy(inputs_value) if inputs_value else None,
                    schemas=copy.deepcopy(schemas_value) if schemas_value else None,
                    params=copy.deepcopy(params_value) if params_value else None,
                    original_task_id=str(original_task.id),
                )
            # Apply field reset logic
            self._reset_task_fields(task, reset_fields)
            return task
        else:
            # Unrelated successful task: preserve completed status and token_usage
            # Get token_usage from result.token_usage (direct access, no hooks)
            token_usage = None
            if isinstance(result_value, dict):
                token_usage = result_value.get('token_usage')
            
            # Preserve result with token_usage if available
            preserved_result = None
            if result_value:
                preserved_result = copy.deepcopy(result_value)
                # Ensure token_usage is in result if we have it
                if token_usage and isinstance(preserved_result, dict):
                    preserved_result['token_usage'] = token_usage
            
            # Create task with completed status
            # Use original_task.id as original_task_id (not root_original_task_id) so dependencies can be correctly mapped
            # Explicitly generate UUID for task.id to ensure uniqueness and clear task tree relationships
            task_id = str(uuid.uuid4())
            if save:
                task = await self.task_manager.task_repository.create_task(
                    id=task_id,
                    name=original_task.name,
                    user_id=original_task.user_id,
                    parent_id=parent_id,
                    priority=original_task.priority,
                    dependencies=copy.deepcopy(dependencies_value) if dependencies_value else None,
                    inputs=copy.deepcopy(inputs_value) if inputs_value else None,
                    schemas=copy.deepcopy(schemas_value) if schemas_value else None,
                    params=copy.deepcopy(params_value) if params_value else None,
                    original_task_id=str(original_task.id),
                )
            else:
                # Create in-memory TaskModel instance without saving to database
                task = task_model_class(
                    id=task_id,
                    name=original_task.name,
                    user_id=original_task.user_id,
                    parent_id=parent_id,
                    priority=original_task.priority,
                    dependencies=copy.deepcopy(dependencies_value) if dependencies_value else None,
                    inputs=copy.deepcopy(inputs_value) if inputs_value else None,
                    schemas=copy.deepcopy(schemas_value) if schemas_value else None,
                    params=copy.deepcopy(params_value) if params_value else None,
                    original_task_id=str(original_task.id),
                )
            
            # Set status and preserve result/token_usage (unless reset_fields specifies otherwise)
            if reset_fields is None:
                # Default: preserve completed status
                task.status = "completed"
                task.progress = 1.0
                task.result = preserved_result
                
                # Preserve timestamps if available
                if hasattr(original_task, 'started_at') and original_task.started_at:
                    task.started_at = original_task.started_at
                if hasattr(original_task, 'completed_at') and original_task.completed_at:
                    task.completed_at = original_task.completed_at
            else:
                # Only reset specified fields, preserve others
                if "status" not in reset_fields:
                    task.status = "completed"
                if "progress" not in reset_fields:
                    task.progress = 1.0
                if "result" not in reset_fields:
                    task.result = preserved_result
                if "started_at" not in reset_fields:
                    if hasattr(original_task, 'started_at') and original_task.started_at:
                        task.started_at = original_task.started_at
                if "completed_at" not in reset_fields:
                    if hasattr(original_task, 'completed_at') and original_task.completed_at:
                        task.completed_at = original_task.completed_at
                # Apply reset_fields for fields that should be reset
                self._reset_task_fields(task, reset_fields)
            
            # Update in database only if saving
            if save:
                if self.task_manager.is_async:
                    await self.db.commit()
                    await self.db.refresh(task)
                else:
                    self.db.commit()
                    self.db.refresh(task)
            
            return task
    
    async def _save_copied_task_tree(self, node: TaskTreeNode, parent_id: Optional[str] = None):
        """
        Update parent_id and dependencies references for copied task tree.
        Tasks are already saved by create_task, we need to update parent_id and dependencies
        to reference tasks within the new copied tree (not the original tree).
        
        IMPORTANT: To avoid db session cache issues, we:
        1. First, ensure all tasks are flushed/committed so IDs are available
        2. Build the ID mapping after all tasks are saved
        3. Update dependencies and parent_id
        4. Commit and refresh to ensure changes are persisted
        
        Args:
            node: Task tree node to update
            parent_id: Parent task ID
        """
        # Step 1: First, ensure all tasks in the tree are flushed to database
        # This ensures all task IDs are available and avoids cache issues
        # Tasks are already added to session by create_task, we just need to flush
        # Flush to database (but don't commit yet) to ensure all IDs are generated
        if self.task_manager.is_async:
            await self.db.flush()
        else:
            self.db.flush()
        
        # Step 2: Refresh all tasks to ensure we have latest data from database after flush
        # This avoids cache issues where we might read stale data
        async def refresh_all_tasks(current_node: TaskTreeNode):
            """Refresh all tasks to get latest data from database"""
            task = current_node.task
            if self.task_manager.is_async:
                await self.db.refresh(task)
            else:
                self.db.refresh(task)
            for child in current_node.children:
                await refresh_all_tasks(child)
        
        await refresh_all_tasks(node)
        
        # Step 3: Build mapping: original_task_id -> new task id for all tasks in the tree
        # After flush and refresh, all task IDs should be available and up-to-date
        def build_original_to_new_id_mapping(current_node: TaskTreeNode, mapping: Dict[str, str]):
            """Build mapping from original_task_id to new task id"""
            task = current_node.task
            if task.original_task_id:
                original_id = str(task.original_task_id)
                new_id = str(task.id)
                mapping[original_id] = new_id
            for child in current_node.children:
                build_original_to_new_id_mapping(child, mapping)
        
        original_to_new_id: Dict[str, str] = {}
        build_original_to_new_id_mapping(node, original_to_new_id)
        
        # Step 4: Update dependencies to reference new task IDs
        def update_dependencies(current_node: TaskTreeNode, id_mapping: Dict[str, str]):
            """Update dependencies to reference new task IDs within the copied tree"""
            task = current_node.task
            
            dependencies = getattr(task, 'dependencies', None)
            if dependencies and isinstance(dependencies, list):
                updated_deps = []
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_copy = dep.copy()
                        # Convert dependency id from original task ID to new task ID
                        if "id" in dep_copy:
                            dep_id = str(dep_copy["id"])
                            if dep_id in id_mapping:
                                # Map to new task ID in the copied tree
                                dep_copy["id"] = id_mapping[dep_id]
                            else:
                                # If not found in mapping, this dependency references a task outside the copied tree
                                # This should not happen if the copy logic is correct, but we'll keep it as-is
                                # and log a warning
                                logger.warning(
                                    f"Task {task.id} has dependency {dep_id} that is not in the copied tree. "
                                    f"Keeping original reference."
                                )
                        updated_deps.append(dep_copy)
                    else:
                        # String or other format - try to convert
                        dep_str = str(dep)
                        if dep_str in id_mapping:
                            updated_deps.append({"id": id_mapping[dep_str]})
                        else:
                            # Keep original if not found
                            updated_deps.append(dep)
                task.dependencies = updated_deps
            # Recursively update children
            for child in current_node.children:
                update_dependencies(child, id_mapping)
        
        # Update all dependencies in the tree
        update_dependencies(node, original_to_new_id)
        
        # Step 5: Update parent_id
        task = node.task
        if parent_id is not None:
            task.parent_id = parent_id
        
        # Step 6: Save task with updated dependencies and parent_id
        if self.task_manager.is_async:
            await self.db.commit()
            await self.db.refresh(task)
        else:
            self.db.commit()
            self.db.refresh(task)
        
        # Recursively update children
        for child_node in node.children:
            await self._save_copied_task_tree(child_node, task.id)
    
    async def _mark_original_tasks_has_copy(self, node: TaskTreeNode):
        """
        Recursively mark all original tasks as having copies.
        
        Args:
            node: Task tree node to mark
        """
        node.task.has_copy = True
        if self.task_manager.is_async:
            await self.db.commit()
            await self.db.refresh(node.task)
        else:
            self.db.commit()
            self.db.refresh(node.task)
        
        # Recursively mark children
        for child_node in node.children:
            await self._mark_original_tasks_has_copy(child_node)
    
    def _tree_to_task_array(self, node: TaskTreeNode) -> List[Dict[str, Any]]:
        """
        Convert TaskTreeNode to flat task array compatible with tasks.create API.
        
        Uses TaskModel's actual fields via get_task_model_class().
        Since tasks are not saved yet, uses name-based references instead of id.
        Ensures all names are unique.
        
        Args:
            node: Task tree node
            
        Returns:
            List of task dictionaries compatible with tasks.create format
        """
        # Get TaskModel class (may be custom)
        task_model_class = get_task_model_class()
        
        # Get all column names from TaskModel
        task_columns = set(task_model_class.__table__.columns.keys())
        
        tasks = []
        name_counter = {}  # Track name usage for uniqueness
        task_to_name = {}  # task object id -> unique name
        
        # First pass: assign unique names to all tasks
        def assign_names(current_node: TaskTreeNode):
            task = current_node.task
            original_name = task.name
            
            # Generate unique name if needed
            if original_name not in name_counter:
                name_counter[original_name] = 0
                unique_name = original_name
            else:
                name_counter[original_name] += 1
                unique_name = f"{original_name}_{name_counter[original_name]}"
            
            task_to_name[id(task)] = unique_name
            
            # Recursively process children
            for child in current_node.children:
                assign_names(child)
        
        assign_names(node)
        
        # Build mappings for dependencies conversion
        # Map original task.id and original_task_id to new generated id and name
        task_id_to_new_id: Dict[str, str] = {}  # original task.id -> new generated id
        task_id_to_name: Dict[str, str] = {}  # original task.id -> name (for name-based refs)
        
        # First pass: map all task.id to their names
        def build_id_mappings(current_node: TaskTreeNode):
            task = current_node.task
            task_id_to_name[str(task.id)] = task_to_name[id(task)]
            for child in current_node.children:
                build_id_mappings(child)
        build_id_mappings(node)
        
        # Second pass: map original_task_id to name (for name-based refs fallback)
        # This allows dependencies that reference original task IDs to be converted correctly
        def map_original_task_ids(current_node: TaskTreeNode):
            task = current_node.task
            if task.original_task_id:
                original_id = str(task.original_task_id)
                # Only map if not already in the mapping (avoid overwriting existing mappings)
                # This ensures that if original_task_id matches another task's id in the tree,
                # we use that task's name, not the current task's name
                if original_id not in task_id_to_name:
                    task_id_to_name[original_id] = task_to_name[id(task)]
            for child in current_node.children:
                map_original_task_ids(child)
        map_original_task_ids(node)
        
        # Third pass: pre-generate all new IDs for all tasks (needed for dependency conversion)
        def pre_generate_ids(current_node: TaskTreeNode):
            task = current_node.task
            task_id_str = str(task.id)
            # Check if this task.id has already been mapped (should not happen in a valid tree)
            if task_id_str in task_id_to_new_id:
                # This should not happen, but if it does, reuse the existing mapping
                # This ensures we don't create duplicate IDs
                return
            new_task_id = str(uuid.uuid4())
            # Map task.id to new id
            task_id_to_new_id[task_id_str] = new_task_id
            # Also map original_task_id to new id (if exists) for dependency conversion
            # This ensures dependencies that reference original_task_id can be converted correctly
            if task.original_task_id:
                original_id = str(task.original_task_id)
                # Only map if not already mapped (avoid overwriting if multiple tasks have same original_task_id)
                if original_id not in task_id_to_new_id:
                    task_id_to_new_id[original_id] = new_task_id
            
            # IMPORTANT: Dependencies in the copied task may reference original task IDs
            # We need to map those original IDs to the new IDs of the copied tasks
            # Iterate through all tasks in the tree to build a complete mapping
            dependencies = getattr(task, 'dependencies', None)
            if dependencies:
                for dep in dependencies:
                    if isinstance(dep, dict) and "id" in dep:
                        dep_id = str(dep["id"])
                        # If this dependency ID is not yet mapped, we need to find which copied task
                        # corresponds to this original dependency ID
                        if dep_id not in task_id_to_new_id:
                            # Find the task in the tree that has this ID as its original_task_id
                            # or as its task.id (if it's a direct reference)
                            # This will be handled by iterating through all tasks
                            pass  # Will be handled in a separate pass
            for child in current_node.children:
                pre_generate_ids(child)
        pre_generate_ids(node)
        
        # Fourth pass: map dependency IDs that reference original task IDs
        # Dependencies in copied tasks may reference original task IDs from the original tree
        # We need to map those original IDs to the new IDs of the corresponding copied tasks
        # Strategy: For each dependency ID that's not yet mapped, find the task in the new tree
        # that corresponds to that original ID (by checking original_task_id or task.id)
        def find_task_by_original_id(current_node: TaskTreeNode, target_original_id: str) -> Optional[TaskTreeNode]:
            """Find a task in the tree that corresponds to the given original task ID"""
            task = current_node.task
            # Check if this task's original_task_id matches, or if task.id matches (for direct references)
            if (task.original_task_id and str(task.original_task_id) == target_original_id) or \
               str(task.id) == target_original_id:
                return current_node
            # Recursively check children
            for child in current_node.children:
                result = find_task_by_original_id(child, target_original_id)
                if result:
                    return result
            return None
        
        def map_dependency_ids(current_node: TaskTreeNode):
            """Map all dependency IDs in the tree to new task IDs"""
            task = current_node.task
            dependencies = getattr(task, 'dependencies', None)
            if dependencies:
                for dep in dependencies:
                    if isinstance(dep, dict) and "id" in dep:
                        dep_id = str(dep["id"])
                        # If this dependency ID is not yet mapped, find the corresponding task in the new tree
                        if dep_id not in task_id_to_new_id:
                            found_node = find_task_by_original_id(node, dep_id)
                            if found_node:
                                # Map the dependency ID to the new ID of the found task
                                found_new_id = task_id_to_new_id[str(found_node.task.id)]
                                task_id_to_new_id[dep_id] = found_new_id
                            # If not found, it will raise an error during conversion (which is correct)
            for child in current_node.children:
                map_dependency_ids(child)
        map_dependency_ids(node)
        
        # Fourth pass: build task array with id and name-based references
        def collect_tasks(current_node: TaskTreeNode, parent_name: Optional[str] = None, parent_id: Optional[str] = None):
            task = current_node.task
            unique_name = task_to_name[id(task)]
            
            # Build task dict using TaskModel's actual fields
            task_dict: Dict[str, Any] = {}
            
            # Get pre-generated UUID for this task (for save=False, tasks.create needs complete data)
            new_task_id = task_id_to_new_id[str(task.id)]
            task_dict["id"] = new_task_id
            
            # Handle parent_id separately (before the loop, since we skip it in the loop)
            # Use parent id (since all tasks have id now)
            # parent_id parameter is the new generated id of the parent task
            if parent_id is not None:
                task_dict["parent_id"] = parent_id
            # else: don't set parent_id (root task) - this is correct
            
            # Get all TaskModel fields and their values
            for column_name in task_columns:
                # Skip id (already set above), parent_id (handled separately above), created_at, updated_at, has_copy (these are auto-generated or not needed for create)
                if column_name in ("id", "parent_id", "created_at", "updated_at", "has_copy"):
                    continue
                
                # Get value from task
                value = getattr(task, column_name, None)
                
                # Handle special cases
                if column_name == "name":
                    # Use unique name
                    task_dict["name"] = unique_name
                elif column_name == "progress":
                    # Convert Numeric to float
                    task_dict["progress"] = float(value) if value is not None else 0.0
                elif column_name == "dependencies" and value is not None:
                    # Convert dependencies: replace original id references with new generated id
                    # Since all tasks have id now, dependencies must use id references
                    if isinstance(value, list):
                        converted_deps = []
                        for dep in value:
                            if isinstance(dep, dict):
                                dep_copy = dep.copy()
                                # Convert id to new generated id (required for id-based mode)
                                if "id" in dep_copy:
                                    dep_id = str(dep_copy["id"])
                                    if dep_id in task_id_to_new_id:
                                        # Use new generated id
                                        dep_copy["id"] = task_id_to_new_id[dep_id]
                                    else:
                                        # If not found, this is an error - dependency must be in the tree
                                        raise ValueError(
                                            f"Dependency id '{dep_id}' not found in task tree. "
                                            f"All dependencies must reference tasks within the copied tree."
                                        )
                                # If dependency has "name" but no "id", try to find it by name
                                elif "name" in dep_copy:
                                    dep_name = dep_copy["name"]
                                    # Find task with this name and use its new id
                                    found = False
                                    for orig_id, new_id in task_id_to_new_id.items():
                                        if task_id_to_name.get(orig_id) == dep_name:
                                            dep_copy["id"] = new_id
                                            del dep_copy["name"]
                                            found = True
                                            break
                                    if not found:
                                        raise ValueError(
                                            f"Dependency name '{dep_name}' not found in task tree. "
                                            f"All dependencies must reference tasks within the copied tree."
                                        )
                                converted_deps.append(dep_copy)
                            else:
                                # String or other format - try to convert
                                dep_str = str(dep)
                                if dep_str in task_id_to_new_id:
                                    converted_deps.append({"id": task_id_to_new_id[dep_str]})
                                else:
                                    # Try to find by name
                                    found = False
                                    for orig_id, new_id in task_id_to_new_id.items():
                                        if task_id_to_name.get(orig_id) == dep_str:
                                            converted_deps.append({"id": new_id})
                                            found = True
                                            break
                                    if not found:
                                        raise ValueError(
                                            f"Dependency '{dep_str}' not found in task tree. "
                                            f"All dependencies must reference tasks within the copied tree."
                                        )
                        task_dict["dependencies"] = converted_deps
                    else:
                        task_dict["dependencies"] = value
                elif value is not None:
                    # Include non-None values
                    task_dict[column_name] = value
            
            tasks.append(task_dict)
            
            # Recursively collect children
            for child in current_node.children:
                collect_tasks(child, unique_name, new_task_id)
        
        collect_tasks(node, None, None)  # Root task has no parent
        return tasks


__all__ = [
    "TaskCreator",
]
