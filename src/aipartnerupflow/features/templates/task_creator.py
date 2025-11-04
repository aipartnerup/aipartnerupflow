"""
Task creation from templates

This module provides functionality to create task trees from predefined templates.
It integrates with TaskPlanner to retrieve templates and TaskManager to create task trees.

Installation: pip install aipartnerupflow[templates]
"""

from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from aipartnerupflow.features.templates.task_planner import (
    TaskPlanner,
    TaskTemplate,
    TaskTemplateTreeNode
)
from aipartnerupflow.core.execution.task_manager import TaskManager
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TaskCreator:
    """
    Task creation from templates
    
    This class provides functionality to create task trees from predefined templates.
    It combines TaskPlanner (template management) with TaskManager (task execution).
    
    Usage:
        from aipartnerupflow.features.templates import TaskCreator
        
        creator = TaskCreator(db_session)
        task_tree = await creator.create_task_tree_from_template(
            user_id="user_123",
            template_id="my_template",
            input_data={"url": "https://example.com"}
        )
    """
    
    def __init__(self, db: Session | AsyncSession):
        """
        Initialize TaskCreator
        
        Args:
            db: Database session (sync or async)
        """
        self.db = db
        self.task_planner = TaskPlanner(db)
        self.task_manager = TaskManager(db)
    
    async def create_task_tree_from_template(
        self,
        user_id: str,
        template_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        parent_task_id: Optional[str] = None,
    ) -> TaskTreeNode:
        """
        Create task hierarchy as a tree structure from a specific task template
        
        Args:
            user_id: User ID for the tasks
            template_id: Template ID to use
            input_data: Optional input data to override template defaults
            parent_task_id: Optional parent task ID (for nested templates)
            
        Returns:
            TaskTreeNode: Root task node of the created task tree
            
        Raises:
            ValueError: If template not found
        """
        logger.info(f"Creating task tree from template {template_id} for user {user_id}")
        
        # Get task template plan
        template_tree = self.task_planner.get_task_template_plan(template_id)
        if not template_tree:
            raise ValueError(f"Task template plan not found for template ID: {template_id}")
        
        # Create task tree from template tree recursively
        root_node = await self._create_task_from_template_node(
            template_tree, user_id, input_data or {}, parent_task_id
        )
        
        logger.info(f"Created task tree from template: root task {root_node.task.name} "
                    f"with {len(root_node.children)} direct children")
        return root_node
    
    async def _create_task_from_template_node(
        self,
        template_node: TaskTemplateTreeNode,
        user_id: str,
        input_data: Dict[str, Any],
        parent_task_id: Optional[str] = None,
    ) -> TaskTreeNode:
        """
        Recursively create task from template node
        
        Args:
            template_node: Template node to create task from
            user_id: User ID for the task
            input_data: Input data (may be overridden by template defaults)
            parent_task_id: Parent task ID (for nested templates)
            
        Returns:
            TaskTreeNode: Created task node
        """
        template = template_node.task
        
        # Prepare input data from template and provided input_data
        task_input_data = self._prepare_task_input_data(template, input_data)
        
        # Get model from template schemas if specified
        model_value = None
        if template.schemas and 'model' in template.schemas:
            model_value = template.schemas['model']
        
        # Convert template dependencies to TaskModel format
        # Template dependencies use "code" or "name", TaskModel uses "id"
        dependencies = []
        if template.dependencies:
            # Convert template dependency format to TaskModel dependency format
            # Template: [{"name": "code_web_analyzer", "type": "result", "required": True}]
            # TaskModel: [{"id": "task-uuid", "required": True}]
            # Note: Actual task IDs will be resolved during task tree building
            for dep in template.dependencies:
                # Store dependency info in a format that can be resolved later
                dependencies.append({
                    "code": dep.get("name") or dep.get("code"),
                    "type": dep.get("type", "result"),
                    "required": dep.get("required", True)
                })
        
        # Create task using TaskManager
        task = await self.task_manager.create_task(
            name=template.name,
            user_id=user_id,
            parent_id=parent_task_id,
            priority=template.priority or 1,
            dependencies=dependencies if dependencies else None,
            input_data=task_input_data,
            schemas=template.schemas,
        )
        
        # Create task tree node
        task_node = TaskTreeNode(task=task)
        
        # Recursively create children
        for child_template_node in template_node.children:
            child_task_node = await self._create_task_from_template_node(
                child_template_node, user_id, input_data, task.id
            )
            task_node.add_child(child_task_node)
        
        return task_node
    
    def _prepare_task_input_data(
        self,
        template: "TaskTemplate",
        provided_input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare input data for a task based on template schemas and provided data
        
        Args:
            template: Task template
            provided_input_data: Input data provided by user
            
        Returns:
            Dict[str, Any]: Prepared input data
        """
        input_data = {}
        
        # Get input schemas from template
        schemas = template.schemas or {}
        input_schema = schemas.get("input_schema", {})
        
        # Process each field in input_schema
        if input_schema:
            for key, field_schema in input_schema.items():
                if isinstance(field_schema, dict):
                    field_type = field_schema.get("type", "string")
                    default_value = field_schema.get("default", None)
                    required = field_schema.get("required", False)
                    
                    # Use provided value if available, otherwise use default
                    if key in provided_input_data:
                        input_data[key] = provided_input_data[key]
                    elif default_value is not None:
                        input_data[key] = default_value
                    elif required:
                        # For required fields without default, use None or empty
                        if field_type == "array":
                            input_data[key] = []
                        elif field_type == "object":
                            input_data[key] = {}
                        elif field_type == "number" or field_type == "integer":
                            input_data[key] = 0
                        elif field_type == "boolean":
                            input_data[key] = False
                        else:
                            input_data[key] = None
                else:
                    # Direct value (not a schema definition)
                    input_data[key] = provided_input_data.get(key, field_schema)
        
        # Also check for input_data in schemas (for default values)
        input_data_from_schemas = schemas.get("input_data", {})
        if input_data_from_schemas:
            # Merge with priority: provided > schema defaults
            for key, value in input_data_from_schemas.items():
                if key not in input_data:
                    input_data[key] = value
        
        return input_data
    
    def save_task_hierarchy_to_database(
        self,
        task_tree: TaskTreeNode
    ) -> bool:
        """
        Save complete task hierarchy to database from TaskTreeNode
        
        Args:
            task_tree: Root task node of the task tree
            
        Returns:
            bool: True if successful, False otherwise
            
        Note: Tasks should already be created via TaskManager.create_task(),
        so this method mainly ensures the hierarchy is properly saved.
        """
        try:
            if self.task_manager.is_async:
                # For async, tasks are already saved via create_task
                return True
            else:
                # For sync, commit if needed
                self.db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving task hierarchy to database: {e}", exc_info=True)
            if self.db:
                self.db.rollback()
            return False
    
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

