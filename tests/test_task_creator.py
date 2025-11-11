"""
Test TaskCreator functionality
"""
import pytest
from aipartnerupflow.core.execution.task_creator import TaskCreator
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel


class TestTaskCreator:
    """Test TaskCreator core functionality"""
    
    @pytest.mark.asyncio
    async def test_create_task_tree_with_id(self, sync_db_session):
        """Test creating task tree with id-based references"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
                "priority": 1,
                "input_data": {"url": "https://example.com"},
            },
            {
                "id": "task_2",
                "name": "Task 2",
                "user_id": "user_123",
                "parent_id": "task_1",
                "dependencies": [{"id": "task_1", "required": True}],
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        assert isinstance(task_tree, TaskTreeNode)
        assert task_tree.task.name == "Task 1"
        assert len(task_tree.children) == 1
        assert task_tree.children[0].task.name == "Task 2"
        
        # Verify parent_id is set correctly
        child_task = task_tree.children[0].task
        assert child_task.parent_id == task_tree.task.id
        
        # Verify dependencies are set correctly (using actual task ids)
        assert child_task.dependencies is not None
        assert len(child_task.dependencies) == 1
        assert child_task.dependencies[0]["id"] == task_tree.task.id
        assert child_task.dependencies[0]["required"] is True
    
    @pytest.mark.asyncio
    async def test_create_task_tree_with_name(self, sync_db_session):
        """Test creating task tree with name-based references (no id)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "name": "Task 1",  # No id, name must be unique
                "user_id": "user_123",
                "priority": 1,
            },
            {
                "name": "Task 2",  # No id, name must be unique
                "user_id": "user_123",
                "parent_id": "Task 1",  # Use name as parent_id
                "dependencies": [{"name": "Task 1", "required": True}],  # Use name in dependencies
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        assert isinstance(task_tree, TaskTreeNode)
        assert task_tree.task.name == "Task 1"
        assert len(task_tree.children) == 1
        assert task_tree.children[0].task.name == "Task 2"
        
        # Verify parent_id is set correctly (using actual task id)
        child_task = task_tree.children[0].task
        assert child_task.parent_id == task_tree.task.id
        
        # Verify dependencies are set correctly (using actual task ids)
        assert child_task.dependencies is not None
        assert len(child_task.dependencies) == 1
        assert child_task.dependencies[0]["id"] == task_tree.task.id
        assert child_task.dependencies[0]["required"] is True
    
    @pytest.mark.asyncio
    async def test_error_mixed_id_and_name(self, sync_db_session):
        """Test error when mixing tasks with id and without id"""
        creator = TaskCreator(sync_db_session)
        
        # Mixed mode: some tasks have id, some don't (not supported)
        tasks = [
            {
                "id": "task_1",  # Has id
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "name": "Task 2",  # No id - mixed mode not supported
                "user_id": "user_123",
            }
        ]
        
        with pytest.raises(ValueError, match="Mixed mode not supported"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_create_task_tree_multiple_levels(self, sync_db_session):
        """Test creating task tree with multiple levels"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "root",
                "name": "Root Task",
                "user_id": "user_123",
            },
            {
                "id": "child_1",
                "name": "Child 1",
                "user_id": "user_123",
                "parent_id": "root",
            },
            {
                "id": "child_2",
                "name": "Child 2",
                "user_id": "user_123",
                "parent_id": "root",
            },
            {
                "id": "grandchild",
                "name": "Grandchild",
                "user_id": "user_123",
                "parent_id": "child_1",
                "dependencies": [{"id": "child_2", "required": True}],
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        assert task_tree.task.name == "Root Task"
        assert len(task_tree.children) == 2
        
        # Find child_1
        child_1 = next((c for c in task_tree.children if c.task.name == "Child 1"), None)
        assert child_1 is not None
        assert len(child_1.children) == 1
        assert child_1.children[0].task.name == "Grandchild"
        
        # Verify grandchild's dependencies
        grandchild = child_1.children[0].task
        assert grandchild.dependencies is not None
        assert len(grandchild.dependencies) == 1
    
    @pytest.mark.asyncio
    async def test_create_task_tree_without_parent_id(self, sync_db_session):
        """Test creating task tree without parent_id (root task)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
                # No parent_id - this is a root task
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        # Root task should have no parent_id
        assert task_tree.task.parent_id is None
        assert task_tree.task.name == "Task 1"
    
    @pytest.mark.asyncio
    async def test_error_missing_name(self, sync_db_session):
        """Test error when task is missing name"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                # Missing name
                "user_id": "user_123",
            }
        ]
        
        with pytest.raises(ValueError, match="must have a 'name' field"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_create_task_tree_without_user_id(self, sync_db_session):
        """Test creating task tree without user_id (user_id is optional)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                # No user_id - should work
            },
            {
                "id": "task_2",
                "name": "Task 2",
                "parent_id": "task_1",
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        assert task_tree.task.name == "Task 1"
        assert task_tree.task.user_id is None
        assert len(task_tree.children) == 1
        assert task_tree.children[0].task.user_id is None
    
    @pytest.mark.asyncio
    async def test_error_duplicate_id(self, sync_db_session):
        """Test error when duplicate id is provided"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_1",  # Duplicate id
                "name": "Task 2",
                "user_id": "user_123",
            }
        ]
        
        with pytest.raises(ValueError, match="Duplicate task id"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_duplicate_name_without_id(self, sync_db_session):
        """Test error when duplicate name is provided (when no id)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "name": "Task 1",  # No id
                "user_id": "user_123",
            },
            {
                "name": "Task 1",  # Duplicate name (no id)
                "user_id": "user_123",
            }
        ]
        
        with pytest.raises(ValueError, match="name.*is not unique"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_invalid_parent_id(self, sync_db_session):
        """Test error when parent_id doesn't exist in array"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_2",
                "name": "Task 2",
                "user_id": "user_123",
                "parent_id": "nonexistent_task",  # Invalid parent_id
            }
        ]
        
        with pytest.raises(ValueError, match="parent_id.*not in the tasks array"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_invalid_dependency_id(self, sync_db_session):
        """Test error when dependency id doesn't exist in array"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_2",
                "name": "Task 2",
                "user_id": "user_123",
                "dependencies": [{"id": "nonexistent_task", "required": True}],
            }
        ]
        
        with pytest.raises(ValueError, match="dependency.*not in the tasks array"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_invalid_dependency_name(self, sync_db_session):
        """Test error when dependency name doesn't exist in array"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "name": "Task 1",  # No id
                "user_id": "user_123",
            },
            {
                "name": "Task 2",  # No id
                "user_id": "user_123",
                "dependencies": [{"name": "nonexistent_task", "required": True}],
            }
        ]
        
        with pytest.raises(ValueError, match="dependency.*not in the tasks array"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_dependency_missing_id_and_name(self, sync_db_session):
        """Test error when dependency has neither id nor name"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_2",
                "name": "Task 2",
                "user_id": "user_123",
                "dependencies": [{"required": True}],  # Missing id and name
            }
        ]
        
        with pytest.raises(ValueError, match="dependency must have 'id' or 'name' field"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_empty_tasks_array(self, sync_db_session):
        """Test error when tasks array is empty"""
        creator = TaskCreator(sync_db_session)
        
        with pytest.raises(ValueError, match="Tasks array cannot be empty"):
            await creator.create_task_tree_from_array([])
    
    @pytest.mark.asyncio
    async def test_dependencies_with_required_and_type(self, sync_db_session):
        """Test dependencies with required and type fields"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_2",
                "name": "Task 2",
                "user_id": "user_123",
                "parent_id": "task_1",  # Task 2 is a child of Task 1
                "dependencies": [
                    {
                        "id": "task_1",
                        "required": False,
                        "type": "result"
                    }
                ],
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        child_task = task_tree.children[0].task
        assert child_task.dependencies is not None
        assert len(child_task.dependencies) == 1
        assert child_task.dependencies[0]["required"] is False
        assert child_task.dependencies[0]["type"] == "result"
    
    @pytest.mark.asyncio
    async def test_simple_string_dependency(self, sync_db_session):
        """Test simple string dependency (backward compatibility)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_2",
                "name": "Task 2",
                "user_id": "user_123",
                "parent_id": "task_1",  # Task 2 is a child of Task 1
                "dependencies": ["task_1"],  # Simple string dependency
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        child_task = task_tree.children[0].task
        assert child_task.dependencies is not None
        assert len(child_task.dependencies) == 1
        assert child_task.dependencies[0]["id"] == task_tree.task.id
        assert child_task.dependencies[0]["required"] is True
    
    @pytest.mark.asyncio
    async def test_tree_to_flat_list(self, sync_db_session):
        """Test converting task tree to flat list"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "root",
                "name": "Root",
                "user_id": "user_123",
            },
            {
                "id": "child_1",
                "name": "Child 1",
                "user_id": "user_123",
                "parent_id": "root",
            },
            {
                "id": "child_2",
                "name": "Child 2",
                "user_id": "user_123",
                "parent_id": "root",
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        flat_list = creator.tree_to_flat_list(task_tree)
        
        assert len(flat_list) == 3
        assert all(isinstance(task, TaskModel) for task in flat_list)
        
        # Verify all tasks are in the list
        task_names = {task.name for task in flat_list}
        assert "Root" in task_names
        assert "Child 1" in task_names
        assert "Child 2" in task_names
    
    @pytest.mark.asyncio
    async def test_parent_has_children_flag(self, sync_db_session):
        """Test that parent task's has_children flag is set correctly"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "parent",
                "name": "Parent",
                "user_id": "user_123",
            },
            {
                "id": "child",
                "name": "Child",
                "user_id": "user_123",
                "parent_id": "parent",
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        # Refresh parent task from database to get updated has_children flag
        parent_task = await creator.task_manager.task_repository.get_task_by_id(task_tree.task.id)
        assert parent_task.has_children is True
    
    @pytest.mark.asyncio
    async def test_multiple_children_same_parent(self, sync_db_session):
        """Test multiple children with same parent"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "parent",
                "name": "Parent",
                "user_id": "user_123",
            },
            {
                "id": "child_1",
                "name": "Child 1",
                "user_id": "user_123",
                "parent_id": "parent",
            },
            {
                "id": "child_2",
                "name": "Child 2",
                "user_id": "user_123",
                "parent_id": "parent",
            },
            {
                "id": "child_3",
                "name": "Child 3",
                "user_id": "user_123",
                "parent_id": "parent",
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        assert len(task_tree.children) == 3
        assert all(child.task.parent_id == task_tree.task.id for child in task_tree.children)
    
    @pytest.mark.asyncio
    async def test_dependencies_use_actual_task_ids(self, sync_db_session):
        """Test that dependencies use actual task ids (user-provided or system-generated)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "user_id_1",  # User-provided id
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "user_id_2",  # User-provided id
                "name": "Task 2",
                "user_id": "user_123",
                "parent_id": "user_id_1",  # Task 2 is a child of Task 1
                "dependencies": [{"id": "user_id_1", "required": True}],
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        # Dependencies should use actual task id (user-provided id if provided, otherwise system-generated)
        child_task = task_tree.children[0].task
        assert child_task.dependencies is not None
        assert len(child_task.dependencies) == 1
        
        # The dependency id should be the actual task id
        # If user provided id, use it; otherwise use system-generated UUID
        actual_dep_id = child_task.dependencies[0]["id"]
        assert actual_dep_id == task_tree.task.id  # Actual task id
        # Since user provided id="user_id_1", the actual task id is "user_id_1"
        assert actual_dep_id == "user_id_1"  # User-provided id becomes the actual task id

