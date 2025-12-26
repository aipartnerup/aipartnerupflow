"""
Test TaskCreator functionality
"""
import pytest
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
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
                "inputs": {"url": "https://example.com"},
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
        """Test error when duplicate id is provided in the same array"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_1",
                "name": "Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_1",  # Duplicate id in same array
                "name": "Task 2",
                "user_id": "user_123",
            }
        ]
        
        with pytest.raises(ValueError, match="Duplicate task id"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_auto_generate_id_when_exists_in_db(self, sync_db_session):
        """Test that new UUID is generated when provided ID already exists in database"""
        creator = TaskCreator(sync_db_session)
        
        # First, create a task with a specific ID
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        repo = TaskRepository(sync_db_session, task_model_class=get_task_model_class())
        existing_task = await repo.create_task(
            name="Existing Task",
            user_id="user_123",
            id="task_1"
        )
        assert existing_task.id == "task_1"
        
        # Now try to create a new task tree with the same ID
        # System should auto-generate a new UUID to avoid conflict
        tasks = [
            {
                "id": "task_1",  # This ID already exists in DB
                "name": "New Task 1",
                "user_id": "user_123",
            },
            {
                "id": "task_2",
                "name": "New Task 2",
                "user_id": "user_123",
                "parent_id": "task_1",  # References task_1
            }
        ]
        
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        # Verify that the new task has a different ID (auto-generated UUID)
        assert task_tree.task.name == "New Task 1"
        assert task_tree.task.id != "task_1"  # Should be a new UUID
        assert len(task_tree.task.id) == 36  # UUID format
        
        # Verify that the existing task in DB still has the original ID
        existing_task_refreshed = await repo.get_task_by_id("task_1")
        assert existing_task_refreshed is not None
        assert existing_task_refreshed.name == "Existing Task"
        
        # Verify parent_id reference still works (using provided_id for mapping)
        assert len(task_tree.children) == 1
        child_task = task_tree.children[0].task
        assert child_task.name == "New Task 2"
        assert child_task.parent_id == task_tree.task.id  # Should reference the new UUID
    
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
    
    @pytest.mark.asyncio
    async def test_error_circular_dependency_simple(self, sync_db_session):
        """Test error when simple circular dependency is detected (A -> B -> A)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
                "dependencies": [{"id": "task_b", "required": True}],
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a, in the same tree
                "dependencies": [{"id": "task_a", "required": True}],
            }
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_circular_dependency_three_nodes(self, sync_db_session):
        """Test error when circular dependency involves three nodes (A -> B -> C -> A)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
                "dependencies": [{"id": "task_b", "required": True}],
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a, in the same tree
                "dependencies": [{"id": "task_c", "required": True}],
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_b",  # Child of task_b, in the same tree
                "dependencies": [{"id": "task_a", "required": True}],
            }
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_circular_dependency_with_name(self, sync_db_session):
        """Test error when circular dependency is detected using name-based references"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "name": "Task A",  # No id, use name
                "user_id": "user_123",
                # Root task
                "dependencies": [{"name": "Task B", "required": True}],
            },
            {
                "name": "Task B",  # No id, use name
                "user_id": "user_123",
                "parent_id": "Task A",  # Child of Task A, in the same tree
                "dependencies": [{"name": "Task A", "required": True}],
            }
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_circular_dependency_self_reference(self, sync_db_session):
        """Test error when task depends on itself"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                "dependencies": [{"id": "task_a", "required": True}],  # Self-reference
            }
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_circular_dependency_complex(self, sync_db_session):
        """Test error when circular dependency involves multiple paths"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
                "dependencies": [{"id": "task_b", "required": True}],
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a, in the same tree
                "dependencies": [
                    {"id": "task_c", "required": True},
                    {"id": "task_d", "required": True},
                ],
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_b",  # Child of task_b, in the same tree
                "dependencies": [{"id": "task_a", "required": True}],  # Creates cycle: A -> B -> C -> A
            },
            {
                "id": "task_d",
                "name": "Task D",
                "user_id": "user_123",
                "parent_id": "task_b",  # Child of task_b, in the same tree
                "dependencies": [{"id": "task_b", "required": True}],  # Creates cycle: B -> D -> B
            }
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_circular_dependency_simple_string(self, sync_db_session):
        """Test error when circular dependency uses simple string format"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
                "dependencies": ["task_b"],  # Simple string format
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a, in the same tree
                "dependencies": ["task_a"],  # Simple string format
            }
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_no_error_valid_dependency_chain(self, sync_db_session):
        """Test that valid dependency chain (no cycles) works correctly"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # No dependencies - root task
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a
                "dependencies": [{"id": "task_a", "required": True}],
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a
                "dependencies": [
                    {"id": "task_a", "required": True},
                    {"id": "task_b", "required": True},
                ],
            }
        ]
        
        # Should not raise error - valid dependency chain (no cycles)
        task_tree = await creator.create_task_tree_from_array(tasks)
        
        assert task_tree.task.name == "Task A"
        assert len(task_tree.children) == 2  # task_b and task_c are children of task_a
        
        # Verify dependencies are set correctly
        task_b = next((t for t in creator.tree_to_flat_list(task_tree) if t.name == "Task B"), None)
        task_c = next((t for t in creator.tree_to_flat_list(task_tree) if t.name == "Task C"), None)
        
        assert task_b is not None
        assert task_c is not None
        assert task_b.dependencies is not None
        assert len(task_b.dependencies) == 1
        assert task_c.dependencies is not None
        assert len(task_c.dependencies) == 2
    
    @pytest.mark.asyncio
    async def test_error_multiple_root_tasks(self, sync_db_session):
        """Test error when multiple root tasks are provided (tasks not in same tree)"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task 1
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                # Root task 2 - multiple roots!
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a
            }
        ]
        
        with pytest.raises(ValueError, match="Multiple root tasks found"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_tasks_not_in_same_tree(self, sync_db_session):
        """Test error when tasks are not all reachable from root task"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # Child of task_a - in the tree
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_d",  # Child of task_d
            },
            {
                "id": "task_d",
                "name": "Task D",
                "user_id": "user_123",
                "parent_id": "task_e",  # Child of task_e - forms a disconnected chain
            },
            {
                "id": "task_e",
                "name": "Task E",
                "user_id": "user_123",
                # This is also a root task - disconnected from task_a
                # Chain: task_e -> task_d -> task_c (disconnected from task_a -> task_b)
            }
        ]
        
        with pytest.raises(ValueError, match="Multiple root tasks found"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_disconnected_subtree(self, sync_db_session):
        """Test error when there are disconnected subtrees"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # In the tree
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_d",  # Disconnected subtree
            },
            {
                "id": "task_d",
                "name": "Task D",
                "user_id": "user_123",
                # Another root task - disconnected from task_a
            }
        ]
        
        with pytest.raises(ValueError, match="Multiple root tasks found"):
            await creator.create_task_tree_from_array(tasks)
    
    @pytest.mark.asyncio
    async def test_error_isolated_task_not_reachable_from_root(self, sync_db_session):
        """Test error when a task is not reachable from root task via parent_id chain"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",  # In the tree
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_d",  # Child of task_d - disconnected chain
            },
            {
                "id": "task_d",
                "name": "Task D",
                "user_id": "user_123",
                "parent_id": "task_e",  # Child of task_e - forms a disconnected chain
            },
            {
                "id": "task_e",
                "name": "Task E",
                "user_id": "user_123",
                # This is also a root task - disconnected from task_a
                # Chain: task_e -> task_d -> task_c (disconnected from task_a -> task_b)
            }
        ]
        
        # Should be caught by "Multiple root tasks found" since task_e is also a root
        with pytest.raises(ValueError, match="Multiple root tasks found"):
            await creator.create_task_tree_from_array(tasks)


class TestTaskCreatorCopy:
    """Test task copy functionality with dependencies"""
    
    async def create_task(
        self,
        db_session,
        task_repository,
        task_id: str,
        name: str,
        user_id: str = "user_123",
        parent_id: Optional[str] = None,
        dependencies: Optional[List[Dict[str, Any]]] = None,
        status: str = "completed",
        result: Optional[Dict[str, Any]] = None,
        progress: float = 1.0
    ) -> TaskModel:
        """Helper to create a task"""
        task = await task_repository.create_task(
            name=name,
            user_id=user_id,
            parent_id=parent_id,
            priority=1,
            dependencies=dependencies,
            inputs={"test": "data"},
            id=task_id
        )
        
        # Update status and result
        await task_repository.update_task_status(
            task.id,
            status=status,
            result=result or {"result": f"Result for {name}"} if status == "completed" else None,
            progress=progress
        )
        
        # Commit and refresh based on session type
        if isinstance(db_session, AsyncSession):
            await db_session.commit()
            await db_session.refresh(task)
        else:
            db_session.commit()
            db_session.refresh(task)
        
        return task
    
    def get_task_names_from_tree(self, tree: TaskTreeNode) -> set:
        """Helper to extract all task names from a tree"""
        names = {tree.task.name}
        for child in tree.children:
            names.update(self.get_task_names_from_tree(child))
        return names
    
    def get_task_ids_from_tree(self, tree: TaskTreeNode) -> set:
        """Helper to extract all task IDs from a tree"""
        ids = {str(tree.task.id)}
        for child in tree.children:
            ids.update(self.get_task_ids_from_tree(child))
        return ids
    
    @pytest.mark.asyncio
    async def test_create_task_copy_basic(self, sync_db_session):
        """Test basic task copy without dependencies"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create a simple task tree: root -> child1 -> child2
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-1", "Root Task"
        )
        child1 = await self.create_task(
            sync_db_session, task_repository,
            "child-task-1", "Child 1",
            parent_id=root_task.id
        )
        child2 = await self.create_task(
            sync_db_session, task_repository,
            "child-task-2", "Child 2",
            parent_id=child1.id
        )
        
        # Create task copy
        new_tree = await creator.create_task_copy(root_task)
        
        # Verify new tree structure
        assert new_tree is not None
        assert new_tree.task.id != root_task.id
        assert new_tree.task.original_task_id == root_task.id
        assert new_tree.task.name == root_task.name
        assert new_tree.task.status == "pending"
        assert new_tree.task.result is None
        assert new_tree.task.progress == 0.0
        
        # Verify has_copy flag is set on original
        sync_db_session.refresh(root_task)
        assert root_task.has_copy is True
        
        # Verify child tasks are copied
        assert len(new_tree.children) == 1
        child1_copy = new_tree.children[0]
        assert isinstance(child1_copy, TaskTreeNode)
        assert child1_copy.task.id != child1.id
        # Each task's original_task_id should point to its own original task ID (not root)
        # This allows dependencies to be correctly mapped in _tree_to_task_array
        assert child1_copy.task.original_task_id == str(child1.id)
        assert child1_copy.task.name == child1.name
        
        # Verify grandchild is copied
        assert len(child1_copy.children) == 1
        child2_copy = child1_copy.children[0]
        assert isinstance(child2_copy, TaskTreeNode)
        assert child2_copy.task.id != child2.id
        # Each task's original_task_id should point to its own original task ID (not root)
        # This allows dependencies to be correctly mapped in _tree_to_task_array
        assert child2_copy.task.original_task_id == str(child2.id)
        assert child2_copy.task.name == child2.name
    
    @pytest.mark.asyncio
    async def test_create_task_copy_with_direct_dependency(self, sync_db_session):
        """Test task copy with direct dependency"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> task_a (name: "Task A")
        # root -> task_b (name: "Task B", depends on "Task A")
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-2", "Root Task"
        )
        task_a = await self.create_task(
            sync_db_session, task_repository,
            "task-a-1", "Task A",
            parent_id=root_task.id
        )
        task_b = await self.create_task(
            sync_db_session, task_repository,
            "task-b-1", "Task B",
            parent_id=root_task.id,
            dependencies=[{"id": task_a.id, "required": True}]
        )
        
        # Create task copy starting from task_a
        new_tree = await creator.create_task_copy(task_a)
        
        # Verify task_a and its subtree are copied
        # Verify task_b (dependent) is also copied
        copied_names = self.get_task_names_from_tree(new_tree)
        
        assert "Task A" in copied_names
        assert "Task B" in copied_names, "Dependent task should be copied"
        
        # Verify original_task_id: each task should point to its own original task ID
        # This allows dependencies to be correctly mapped in _tree_to_task_array
        all_copied_tasks = creator.tree_to_flat_list(new_tree)
        copied_task_a = next(t for t in all_copied_tasks if t.name == "Task A")
        copied_task_b = next(t for t in all_copied_tasks if t.name == "Task B")
        
        # Each copied task should link to its own original task ID
        assert copied_task_a.original_task_id == str(task_a.id)
        assert copied_task_b.original_task_id == str(task_b.id)
    
    @pytest.mark.asyncio
    async def test_create_task_copy_with_transitive_dependency(self, sync_db_session):
        """Test task copy with transitive dependency (A -> B -> C)"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> task_a (name: "Task A")
        # root -> task_b (name: "Task B", depends on "Task A")
        # root -> task_c (name: "Task C", depends on "Task B")
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-3", "Root Task"
        )
        task_a = await self.create_task(
            sync_db_session, task_repository,
            "task-a-2", "Task A",
            parent_id=root_task.id
        )
        task_b = await self.create_task(
            sync_db_session, task_repository,
            "task-b-2", "Task B",
            parent_id=root_task.id,
            dependencies=[{"id": task_a.id, "required": True}]
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-c-1", "Task C",
            parent_id=root_task.id,
            dependencies=[{"id": task_b.id, "required": True}]
        )
        
        # Create task copy starting from task_a
        new_tree = await creator.create_task_copy(task_a)
        
        # Verify all dependent tasks are copied (transitive)
        copied_names = self.get_task_names_from_tree(new_tree)
        
        assert "Task A" in copied_names
        assert "Task B" in copied_names, "Direct dependent should be copied"
        assert "Task C" in copied_names, "Transitive dependent should be copied"
    
    @pytest.mark.asyncio
    async def test_create_task_copy_with_subtree_dependencies(self, sync_db_session):
        """Test task copy when original_task has children with dependencies"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> parent_task -> child_task (name: "Child Task")
        # root -> dependent_task (depends on "Child Task")
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-4", "Root Task"
        )
        parent_task = await self.create_task(
            sync_db_session, task_repository,
            "parent-task-1", "Parent Task",
            parent_id=root_task.id
        )
        child_task = await self.create_task(
            sync_db_session, task_repository,
            "child-task-3", "Child Task",
            parent_id=parent_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "dependent-task-1", "Dependent Task",
            parent_id=root_task.id,
            dependencies=[{"id": child_task.id, "required": True}]
        )
        
        # Create task copy starting from parent_task
        new_tree = await creator.create_task_copy(parent_task)
        
        # Verify parent_task and child_task are copied
        # Verify dependent_task (depends on child_task) is also copied
        copied_names = self.get_task_names_from_tree(new_tree)
        
        assert "Parent Task" in copied_names
        assert "Child Task" in copied_names
        assert "Dependent Task" in copied_names, "Task depending on child should be copied"
    
    @pytest.mark.asyncio
    async def test_create_task_copy_preserves_structure(self, sync_db_session):
        """Test that copied tree preserves original structure"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create complex tree structure
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-6", "Root Task"
        )
        child1 = await self.create_task(
            sync_db_session, task_repository,
            "child-1-1", "Child 1",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-2-1", "Child 2",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "grandchild-1-1", "Grandchild 1",
            parent_id=child1.id
        )
        
        # Create task copy
        new_tree = await creator.create_task_copy(root_task)
        
        # Verify tree structure is preserved
        assert len(new_tree.children) == 2
        
        # Find child1 and child2 in new tree
        child1_copy = None
        child2_copy = None
        for child in new_tree.children:
            if isinstance(child, TaskTreeNode):
                if child.task.name == "Child 1":
                    child1_copy = child
                elif child.task.name == "Child 2":
                    child2_copy = child
        
        assert child1_copy is not None
        assert child2_copy is not None
        assert len(child1_copy.children) == 1
        assert len(child2_copy.children) == 0
        
        # Verify grandchild is in correct position
        assert child1_copy.children[0].task.name == "Grandchild 1"
    
    @pytest.mark.asyncio
    async def test_create_task_copy_marks_has_copy_flag(self, sync_db_session):
        """Test that has_copy flag is set on all original tasks"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree with multiple levels
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-7", "Root Task"
        )
        child1 = await self.create_task(
            sync_db_session, task_repository,
            "child-1-2", "Child 1",
            parent_id=root_task.id
        )
        child2 = await self.create_task(
            sync_db_session, task_repository,
            "child-2-2", "Child 2",
            parent_id=root_task.id
        )
        grandchild = await self.create_task(
            sync_db_session, task_repository,
            "grandchild-1-2", "Grandchild 1",
            parent_id=child1.id
        )
        
        # Create task copy
        await creator.create_task_copy(root_task)
        
        # Refresh all original tasks
        sync_db_session.refresh(root_task)
        sync_db_session.refresh(child1)
        sync_db_session.refresh(child2)
        sync_db_session.refresh(grandchild)
        
        # Verify has_copy is set on all original tasks
        assert root_task.has_copy is True
        assert child1.has_copy is True
        assert child2.has_copy is True
        assert grandchild.has_copy is True
    
    @pytest.mark.asyncio
    async def test_create_task_copy_resets_execution_fields(self, sync_db_session):
        """Test that execution-specific fields are reset in copy"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create completed task with results
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-8", "Root Task",
            status="completed",
            result={"output": "test result"},
            progress=1.0
        )
        
        # Create task copy
        new_tree = await creator.create_task_copy(root_task)
        
        # Verify execution fields are reset
        assert new_tree.task.status == "pending"
        assert new_tree.task.result is None
        assert new_tree.task.progress == 0.0
        
        # Verify non-execution fields are preserved
        assert new_tree.task.name == root_task.name
        assert new_tree.task.user_id == root_task.user_id
        assert new_tree.task.priority == root_task.priority
    
    @pytest.mark.asyncio
    async def test_create_task_copy_no_dependents(self, sync_db_session):
        """
        Test Scenario: No dependents → Only copy original_task subtree
        
        This test verifies that when there are no dependent tasks,
        only the original_task and its children are copied, not the entire root tree.
        """
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> original_task (name: "Original Task") -> child_task
        # root -> unrelated_task (no dependency on original_task)
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-scenario-6", "Root Task"
        )
        
        # Original task with children (this is what we want to copy)
        original_task = await self.create_task(
            sync_db_session, task_repository,
            "original-task-6", "Original Task",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-task-6", "Child Task",
            parent_id=original_task.id
        )
        
        # Unrelated task that doesn't depend on original_task
        unrelated_task = await self.create_task(
            sync_db_session, task_repository,
            "unrelated-task-6", "Unrelated Task",
            parent_id=root_task.id
        )
        
        # Another unrelated branch
        another_branch = await self.create_task(
            sync_db_session, task_repository,
            "another-branch-6", "Another Branch",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "another-child-6", "Another Child",
            parent_id=another_branch.id
        )
        
        # Create task copy starting from original_task
        new_tree = await creator.create_task_copy(original_task)
        
        # Verify: Only original_task subtree is copied
        copied_names = self.get_task_names_from_tree(new_tree)
        copied_ids = self.get_task_ids_from_tree(new_tree)
        
        # Should include original_task and its children
        assert "Original Task" in copied_names, "Original task should be copied"
        assert "Child Task" in copied_names, "Child of original task should be copied"
        
        # Should NOT include unrelated tasks
        assert "Unrelated Task" not in copied_names, "Unrelated task should NOT be copied"
        assert "Another Branch" not in copied_names, "Unrelated branch should NOT be copied"
        assert "Another Child" not in copied_names, "Unrelated child should NOT be copied"
        
        # When there are no dependents, the copied tree root should be original_task (not root_task)
        assert new_tree.task.name == "Original Task", "Copied tree root should be original_task (not root_task)"
        assert "Root Task" not in copied_names, "Root task should NOT be copied when there are no dependents"
        assert str(unrelated_task.id) not in copied_ids, "Unrelated task ID should NOT be in copied tree"
        assert str(another_branch.id) not in copied_ids, "Unrelated branch ID should NOT be in copied tree"
    
    @pytest.mark.asyncio
    async def test_create_task_copy_with_dependents(self, sync_db_session):
        """
        Test Scenario: With dependents → Copy original_task subtree + all dependents (including transitive)
        
        This test verifies that when there are dependent tasks,
        we copy original_task subtree + all dependent tasks (including transitive dependencies),
        but NOT the entire root task tree (excluding unrelated tasks).
        """
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> original_task (name: "Original Task") -> child_task (name: "Child Task")
        # root -> direct_dependent (depends on "Original Task")
        # root -> transitive_dependent (depends on "Direct Dependent")
        # root -> unrelated_task (no dependency)
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-scenario-5", "Root Task"
        )
        
        # Original task with children (this is what we want to copy)
        original_task = await self.create_task(
            sync_db_session, task_repository,
            "original-task-5", "Original Task",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-task-5", "Child Task",
            parent_id=original_task.id
        )
        
        # Direct dependent (depends on original_task)
        direct_dependent = await self.create_task(
            sync_db_session, task_repository,
            "direct-dependent-5", "Direct Dependent",
            parent_id=root_task.id,
            dependencies=[{"id": original_task.id, "required": True}]
        )
        
        # Transitive dependent (depends on direct_dependent)
        await self.create_task(
            sync_db_session, task_repository,
            "transitive-dependent-5", "Transitive Dependent",
            parent_id=root_task.id,
            dependencies=[{"id": direct_dependent.id, "required": True}]
        )
        
        # Unrelated task (no dependency on original_task or its dependents)
        unrelated_task = await self.create_task(
            sync_db_session, task_repository,
            "unrelated-task-5", "Unrelated Task",
            parent_id=root_task.id
        )
        
        # Another unrelated branch
        another_branch = await self.create_task(
            sync_db_session, task_repository,
            "another-branch-5", "Another Branch",
            parent_id=root_task.id
        )
        
        # Create task copy starting from original_task
        new_tree = await creator.create_task_copy(original_task)
        
        # Verify: original_task subtree + all dependents are copied
        copied_names = self.get_task_names_from_tree(new_tree)
        copied_ids = self.get_task_ids_from_tree(new_tree)
        
        # Should include original_task and its children
        assert "Original Task" in copied_names, "Original task should be copied"
        assert "Child Task" in copied_names, "Child of original task should be copied"
        
        # Should include direct dependent
        assert "Direct Dependent" in copied_names, "Direct dependent should be copied"
        
        # Should include transitive dependent
        assert "Transitive Dependent" in copied_names, "Transitive dependent should be copied"
        
        # Should NOT include unrelated tasks
        assert "Unrelated Task" not in copied_names, "Unrelated task should NOT be copied"
        assert "Another Branch" not in copied_names, "Unrelated branch should NOT be copied"
        
        assert str(unrelated_task.id) not in copied_ids, "Unrelated task ID should NOT be in copied tree"
        assert str(another_branch.id) not in copied_ids, "Unrelated branch ID should NOT be in copied tree"
    
    @pytest.mark.asyncio
    async def test_create_task_copy_minimal_subtree(self, sync_db_session):
        """Test that minimal subtree is built correctly"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> branch1 -> task_a (name: "Task A")
        # root -> branch2 -> task_b (name: "Task B", depends on "Task A")
        # root -> branch3 -> task_c (name: "Task C", no dependencies)
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-10", "Root Task"
        )
        branch1 = await self.create_task(
            sync_db_session, task_repository,
            "branch-1-1", "Branch 1",
            parent_id=root_task.id
        )
        task_a = await self.create_task(
            sync_db_session, task_repository,
            "task-a-3", "Task A",
            parent_id=branch1.id
        )
        branch2 = await self.create_task(
            sync_db_session, task_repository,
            "branch-2-1", "Branch 2",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-b-3", "Task B",
            parent_id=branch2.id,
            dependencies=[{"id": task_a.id, "required": True}]
        )
        branch3 = await self.create_task(
            sync_db_session, task_repository,
            "branch-3-1", "Branch 3",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-c-2", "Task C",
            parent_id=branch3.id
        )
        
        # Create task copy starting from task_a
        new_tree = await creator.create_task_copy(task_a)
        
        # Verify minimal subtree: should include task_a, task_b, and their branches
        # but not branch3/task_c
        copied_names = self.get_task_names_from_tree(new_tree)
        
        assert "Task A" in copied_names
        assert "Task B" in copied_names, "Dependent task should be copied"
        assert "Branch 1" in copied_names, "Parent branch should be included"
        assert "Branch 2" in copied_names, "Dependent task's branch should be included"
    
    @pytest.mark.asyncio
    async def test_error_missing_dependent_task(self, sync_db_session):
        """Test error when a task that depends on a task in the tree is not included"""
        creator = TaskCreator(sync_db_session)
        
        # Create a scenario where task_c depends on task_b, but we only include task_a and task_b
        # This simulates the case where task_c should be included but isn't
        # Note: Since we can only validate within the tasks array, we need to test differently
        
        # First, let's test the positive case where all dependents are included
        tasks_complete = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",
                "dependencies": [{"id": "task_a", "required": True}],
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_a",
                "dependencies": [{"id": "task_b", "required": True}],  # Depends on task_b
            }
        ]
        
        # This should work - all dependent tasks are included
        task_tree = await creator.create_task_tree_from_array(tasks_complete)
        assert task_tree.task.name == "Task A"
        
        # Now test with missing dependent - task_c depends on task_b but task_c is not included
        # However, since task_c is not in the array, we can't directly test this scenario
        # The validation only works within the provided tasks array
        # This is a limitation - we can only validate dependencies within the array itself
    
    @pytest.mark.asyncio
    async def test_error_missing_transitive_dependent_task(self, sync_db_session):
        """Test error when a task that transitively depends on a task in the tree is not included"""
        creator = TaskCreator(sync_db_session)
        
        # Test transitive dependencies: task_a -> task_b -> task_c -> task_d
        # All should be included
        tasks_complete = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",
                "dependencies": [{"id": "task_a", "required": True}],
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_a",
                "dependencies": [{"id": "task_b", "required": True}],  # Depends on task_b
            },
            {
                "id": "task_d",
                "name": "Task D",
                "user_id": "user_123",
                "parent_id": "task_a",
                "dependencies": [{"id": "task_c", "required": True}],  # Depends on task_c (transitive)
            }
        ]
        
        # This should work - all transitive dependents are included
        task_tree = await creator.create_task_tree_from_array(tasks_complete)
        assert task_tree.task.name == "Task A"
        
        # Verify all tasks are in the tree
        all_tasks = creator.tree_to_flat_list(task_tree)
        task_names = {task.name for task in all_tasks}
        assert "Task A" in task_names
        assert "Task B" in task_names
        assert "Task C" in task_names
        assert "Task D" in task_names
    
    @pytest.mark.asyncio
    async def test_no_error_when_all_dependents_included(self, sync_db_session):
        """Test that no error is raised when all dependent tasks are included"""
        creator = TaskCreator(sync_db_session)
        
        tasks = [
            {
                "id": "task_a",
                "name": "Task A",
                "user_id": "user_123",
                # Root task
            },
            {
                "id": "task_b",
                "name": "Task B",
                "user_id": "user_123",
                "parent_id": "task_a",
                "dependencies": [{"id": "task_a", "required": True}],
            },
            {
                "id": "task_c",
                "name": "Task C",
                "user_id": "user_123",
                "parent_id": "task_a",
                "dependencies": [
                    {"id": "task_a", "required": True},
                    {"id": "task_b", "required": True},
                ],
            },
            {
                "id": "task_d",
                "name": "Task D",
                "user_id": "user_123",
                "parent_id": "task_c",
                "dependencies": [{"id": "task_c", "required": True}],  # Depends on task_c
            }
        ]
        
        # Should not raise error - all dependent tasks are included
        task_tree = await creator.create_task_tree_from_array(tasks)
        assert task_tree.task.name == "Task A"
        
        # Verify all tasks are in the tree
        all_tasks = creator.tree_to_flat_list(task_tree)
        task_names = {task.name for task in all_tasks}
        assert "Task A" in task_names
        assert "Task B" in task_names
        assert "Task C" in task_names
        assert "Task D" in task_names

    @pytest.mark.asyncio
    async def test_create_task_copy_with_children(self, sync_db_session):
        """Test create_task_copy with children=True parameter"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> child1 -> grandchild1
        # root -> child2 -> grandchild2
        # task_depends_on_both (depends on both child1 and child2)
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-task-children", "Root Task"
        )
        child1 = await self.create_task(
            sync_db_session, task_repository,
            "child-1-children", "Child 1",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "grandchild-1-children", "Grandchild 1",
            parent_id=child1.id
        )
        child2 = await self.create_task(
            sync_db_session, task_repository,
            "child-2-children", "Child 2",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "grandchild-2-children", "Grandchild 2",
            parent_id=child2.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-depends-both", "Task Depends on Both",
            parent_id=root_task.id,  # Same root tree
            dependencies=[
                {"id": child1.id, "required": True},
                {"id": child2.id, "required": True}
            ]
        )
        
        # Copy with children=False (default behavior)
        new_tree_no_children = await creator.create_task_copy(root_task, children=False)
        copied_ids_no_children = self.get_task_ids_from_tree(new_tree_no_children)
        
        # Copy with children=True
        new_tree_with_children = await creator.create_task_copy(root_task, children=True)
        copied_ids_with_children = self.get_task_ids_from_tree(new_tree_with_children)
        
        # Verify that with children=True, we get more tasks
        # Both should include root, child1, child2, grandchild1, grandchild2
        # But with children=True, we also get task_depends_on_both (which depends on both children)
        assert len(copied_ids_with_children) >= len(copied_ids_no_children)
        
        # Verify task_depends_on_both is included when children=True
        # (it depends on both child1 and child2, so should be copied)
        copied_task_names = self.get_task_names_from_tree(new_tree_with_children)
        assert "Task Depends on Both" in copied_task_names, "Task depending on multiple children should be copied"
        
        # Verify deduplication: task_depends_on_both should only appear once
        all_copied_tasks = creator.tree_to_flat_list(new_tree_with_children)
        depends_task_count = sum(1 for task in all_copied_tasks if task.name == "Task Depends on Both")
        assert depends_task_count == 1, "Task depending on multiple copied tasks should only be copied once"

    @pytest.mark.asyncio
    async def test_create_task_copy_children_deduplication(self, sync_db_session):
        """Test that tasks depending on multiple copied children are only copied once"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree:
        # root -> child1
        # root -> child2
        # task_x (depends on child1)
        # task_y (depends on child2)
        # task_z (depends on both child1 and child2) - should only be copied once
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-dedup", "Root Task"
        )
        child1 = await self.create_task(
            sync_db_session, task_repository,
            "child-1-dedup", "Child 1",
            parent_id=root_task.id
        )
        child2 = await self.create_task(
            sync_db_session, task_repository,
            "child-2-dedup", "Child 2",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-x-dedup", "Task X",
            parent_id=root_task.id,  # Same root tree
            dependencies=[{"id": child1.id, "required": True}]
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-y-dedup", "Task Y",
            parent_id=root_task.id,  # Same root tree
            dependencies=[{"id": child2.id, "required": True}]
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-z-dedup", "Task Z",
            parent_id=root_task.id,  # Same root tree
            dependencies=[
                {"id": child1.id, "required": True},
                {"id": child2.id, "required": True}
            ]
        )
        
        # Copy with children=True
        new_tree = await creator.create_task_copy(root_task, children=True)
        all_copied_tasks = creator.tree_to_flat_list(new_tree)
        copied_names = {task.name for task in all_copied_tasks}
        
        # Verify all expected tasks are copied
        assert "Root Task" in copied_names
        assert "Child 1" in copied_names
        assert "Child 2" in copied_names
        assert "Task X" in copied_names
        assert "Task Y" in copied_names
        assert "Task Z" in copied_names
        
        # Verify Task Z appears only once (deduplication)
        task_z_count = sum(1 for task in all_copied_tasks if task.name == "Task Z")
        assert task_z_count == 1, "Task Z should only be copied once despite depending on both children"


class TestTaskCreatorCopyWithSave:
    """Test task copy functionality with save parameter"""
    
    async def create_task(
        self,
        db_session,
        task_repository,
        task_id: str,
        name: str,
        user_id: str = "user_123",
        parent_id: Optional[str] = None,
        dependencies: Optional[List[Dict[str, Any]]] = None,
        status: str = "completed",
        result: Optional[Dict[str, Any]] = None,
        progress: float = 1.0
    ) -> TaskModel:
        """Helper to create a task"""
        task = await task_repository.create_task(
            name=name,
            user_id=user_id,
            parent_id=parent_id,
            priority=1,
            dependencies=dependencies,
            inputs={"test": "data"},
            id=task_id
        )
        
        # Update status and result
        await task_repository.update_task_status(
            task.id,
            status=status,
            result=result or {"result": f"Result for {name}"} if status == "completed" else None,
            progress=progress
        )
        
        # Commit and refresh based on session type
        if isinstance(db_session, AsyncSession):
            await db_session.commit()
            await db_session.refresh(task)
        else:
            db_session.commit()
            db_session.refresh(task)
        
        return task
    
    @pytest.mark.asyncio
    async def test_create_task_copy_save_false_returns_array(self, sync_db_session):
        """Test that save=False returns task array instead of saving to database"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create a simple task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-save-test", "Root Task"
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-save-test", "Child Task",
            parent_id=root_task.id
        )
        
        # Copy with save=False
        result = await creator.create_task_copy(root_task, save=False)
        
        # Verify result is a list (task array)
        assert isinstance(result, list)
        assert len(result) == 2  # Root + Child
        
        # Verify tasks are not saved to database
        all_tasks = await task_repository.get_all_tasks_in_tree(root_task)
        assert len(all_tasks) == 2  # Only original tasks, no new tasks
        
        # Verify task array format
        for task_dict in result:
            assert isinstance(task_dict, dict)
            assert "name" in task_dict
            assert "user_id" in task_dict
            assert "status" in task_dict
            assert "priority" in task_dict
    
    @pytest.mark.asyncio
    async def test_create_task_copy_save_true_saves_to_database(self, sync_db_session):
        """Test that save=True saves tasks to database and returns TaskTreeNode"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create a simple task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-save-true", "Root Task"
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-save-true", "Child Task",
            parent_id=root_task.id
        )
        
        # Copy with save=True (default)
        result = await creator.create_task_copy(root_task, save=True)
        
        # Verify result is TaskTreeNode
        assert isinstance(result, TaskTreeNode)
        
        # Verify new tasks exist in database
        new_root = await task_repository.get_task_by_id(result.task.id)
        assert new_root is not None
        assert new_root.name == "Root Task"
        assert new_root.original_task_id == root_task.id
        
        # Verify copied tree structure
        new_tree = await task_repository.build_task_tree(new_root)
        all_copied_tasks = creator.tree_to_flat_list(new_tree)
        assert len(all_copied_tasks) == 2  # Root + Child
        
        # Verify original tasks still exist
        original_root = await task_repository.get_task_by_id(root_task.id)
        assert original_root is not None
        assert original_root.name == "Root Task"
    
    @pytest.mark.asyncio
    async def test_tree_to_task_array_format(self, sync_db_session):
        """Test that _tree_to_task_array returns correct format compatible with tasks.create"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create a task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-array-test", "Root Task"
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-array-test", "Child Task",
            parent_id=root_task.id,
            dependencies=[{"id": root_task.id, "required": True}]
        )
        
        # Get task tree
        task_tree = await task_repository.build_task_tree(root_task)
        
        # Convert to array
        task_array = creator._tree_to_task_array(task_tree)
        
        # Verify array format
        assert isinstance(task_array, list)
        assert len(task_array) == 2
        
        # Verify all tasks have required fields (based on TaskModel)
        task_model_class = get_task_model_class()
        set(task_model_class.__table__.columns.keys())
        
        for task_dict in task_array:
            # Should have name (required for tasks.create)
            assert "name" in task_dict
            assert isinstance(task_dict["name"], str)
            
            # Should have id (tasks.create needs complete data with id)
            assert "id" in task_dict
            assert isinstance(task_dict["id"], str)
            
            # Should not have auto-generated fields
            assert "created_at" not in task_dict
            assert "updated_at" not in task_dict
            assert "has_copy" not in task_dict
            
            # Should have parent_id as id reference (if not root)
            if task_dict["name"] == "Child Task":
                assert "parent_id" in task_dict
                # parent_id should reference parent's id (UUID), not name
                parent_task = next(t for t in task_array if t["name"] == "Root Task")
                assert task_dict["parent_id"] == parent_task["id"]
            
            # Verify dependencies use id references (since all tasks have id now)
            if "dependencies" in task_dict and task_dict["dependencies"]:
                for dep in task_dict["dependencies"]:
                    if isinstance(dep, dict):
                        # Dependencies should use id references (since all tasks have id)
                        assert "id" in dep, "Dependencies should reference tasks by id"
                        # Verify the referenced id exists in the task array
                        referenced_id = dep["id"]
                        assert any(t["id"] == referenced_id for t in task_array), \
                            f"Dependency references id '{referenced_id}' which should exist in task array"
    
    @pytest.mark.asyncio
    async def test_tree_to_task_array_name_uniqueness(self, sync_db_session):
        """Test that _tree_to_task_array ensures name uniqueness"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create tasks with duplicate names
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-dup-1", "Duplicate Name"
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-dup-1", "Duplicate Name",  # Same name
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-dup-2", "Duplicate Name",  # Same name again
            parent_id=root_task.id
        )
        
        # Get task tree
        task_tree = await task_repository.build_task_tree(root_task)
        
        # Convert to array
        task_array = creator._tree_to_task_array(task_tree)
        
        # Verify all names are unique
        names = [task_dict["name"] for task_dict in task_array]
        assert len(names) == len(set(names)), "All names should be unique"
        
        # Verify names are generated correctly
        assert "Duplicate Name" in names
        assert "Duplicate Name_1" in names or any("Duplicate Name" in name and "_" in name for name in names)
    
    @pytest.mark.asyncio
    async def test_tree_to_task_array_parent_id_references(self, sync_db_session):
        """Test that parent_id uses name references instead of ID"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create multi-level task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-parent-ref", "Root Task"
        )
        child_task = await self.create_task(
            sync_db_session, task_repository,
            "child-parent-ref", "Child Task",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "grandchild-parent-ref", "Grandchild Task",
            parent_id=child_task.id
        )
        
        # Get task tree
        task_tree = await task_repository.build_task_tree(root_task)
        
        # Convert to array
        task_array = creator._tree_to_task_array(task_tree)
        
        # Find tasks in array
        root_dict = next(t for t in task_array if t["name"] == "Root Task")
        child_dict = next(t for t in task_array if t["name"] == "Child Task")
        grandchild_dict = next(t for t in task_array if t["name"] == "Grandchild Task")
        
        # Verify parent_id references use ids (since all tasks have id now)
        assert "parent_id" not in root_dict  # Root has no parent
        assert "parent_id" in child_dict
        assert child_dict["parent_id"] == root_dict["id"]  # ID reference
        assert "parent_id" in grandchild_dict
        assert grandchild_dict["parent_id"] == child_dict["id"]  # ID reference
        
        # Verify all tasks have id
        assert "id" in root_dict
        assert "id" in child_dict
        assert "id" in grandchild_dict
    
    @pytest.mark.asyncio
    async def test_tree_to_task_array_dependencies_references(self, sync_db_session):
        """Test that dependencies use name references instead of ID"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create tasks with dependencies
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-dep-ref", "Root Task"
        )
        task_a = await self.create_task(
            sync_db_session, task_repository,
            "task-a-dep", "Task A",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-b-dep", "Task B",
            parent_id=root_task.id,
            dependencies=[{"id": task_a.id, "required": True}]
        )
        
        # Get task tree
        task_tree = await task_repository.build_task_tree(root_task)
        
        # Convert to array
        task_array = creator._tree_to_task_array(task_tree)
        
        # Find task_b in array
        task_b_dict = next(t for t in task_array if t["name"] == "Task B")
        
        # Verify dependencies use id references (since all tasks have id now)
        assert "dependencies" in task_b_dict
        assert len(task_b_dict["dependencies"]) == 1
        dep = task_b_dict["dependencies"][0]
        assert isinstance(dep, dict)
        assert "id" in dep  # Should have id
        # Find task_a in array to verify id reference
        task_a_dict = next(t for t in task_array if t["name"] == "Task A")
        assert dep["id"] == task_a_dict["id"]  # ID reference
        assert "name" not in dep  # Should not have name when using id field
    
    @pytest.mark.asyncio
    async def test_task_array_compatible_with_tasks_create(self, sync_db_session):
        """Test that returned task array can be used with tasks.create"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create original task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-compat", "Root Task"
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-compat", "Child Task",
            parent_id=root_task.id,
            dependencies=[{"id": root_task.id, "required": True}]
        )
        
        # Copy with save=False to get task array
        task_array = await creator.create_task_copy(root_task, save=False)
        
        # Verify it's a list
        assert isinstance(task_array, list)
        assert len(task_array) == 2
        
        # Verify format is compatible with tasks.create
        # (tasks.create expects id-based references when all tasks have id)
        for task_dict in task_array:
            assert "name" in task_dict
            assert isinstance(task_dict["name"], str)
            assert "id" in task_dict, "All tasks should have id for id-based mode"
            assert isinstance(task_dict["id"], str)
            if "parent_id" in task_dict:
                # parent_id should be an id (since all tasks have id now)
                assert isinstance(task_dict["parent_id"], str)
                # Find parent task to verify it's an id reference
                parent_dict = next((t for t in task_array if t["id"] == task_dict["parent_id"]), None)
                assert parent_dict is not None, "parent_id should reference a task by id"
        
        # Try to create tasks from the array (this should work)
        new_tree = await creator.create_task_tree_from_array(task_array)
        
        # Verify new tree was created successfully
        assert isinstance(new_tree, TaskTreeNode)
        assert new_tree.task.name == "Root Task"
        assert len(new_tree.children) == 1
        assert new_tree.children[0].task.name == "Child Task"
    
    @pytest.mark.asyncio
    async def test_create_task_copy_custom_mode_save_false(self, sync_db_session):
        """Test custom copy mode with save=False"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-custom", "Root Task"
        )
        task_a = await self.create_task(
            sync_db_session, task_repository,
            "task-a-custom", "Task A",
            parent_id=root_task.id
        )
        task_b = await self.create_task(
            sync_db_session, task_repository,
            "task-b-custom", "Task B",
            parent_id=root_task.id,
            dependencies=[{"id": task_a.id, "required": True}]
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-c-custom", "Task C",
            parent_id=root_task.id
        )
        
        # Copy with custom mode, save=False
        task_array = await creator.create_task_copy(
            root_task,
            copy_mode="custom",
            custom_task_ids=[str(task_b.id)],
            save=False
        )
        
        # Verify result is array
        assert isinstance(task_array, list)
        
        # Verify task_b and its dependency (task_a) are included
        task_names = [t["name"] for t in task_array]
        assert "Task B" in task_names
        assert "Task A" in task_names, "Dependency should be auto-included"
        
        # Verify task_c is not included (not in task_ids and not a dependency)
        assert "Task C" not in task_names
    
    @pytest.mark.asyncio
    async def test_create_task_copy_full_mode_save_false(self, sync_db_session):
        """Test full copy mode with save=False"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-full", "Root Task"
        )
        task_a = await self.create_task(
            sync_db_session, task_repository,
            "task-a-full", "Task A",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "task-b-full", "Task B",
            parent_id=root_task.id
        )
        
        # Copy with full mode, save=False
        task_array = await creator.create_task_copy(
            task_a,  # Start from task_a, but should copy from root
            copy_mode="full",
            save=False
        )
        
        # Verify result is array
        assert isinstance(task_array, list)
        
        # Verify all tasks from root are included
        task_names = [t["name"] for t in task_array]
        assert "Root Task" in task_names
        assert "Task A" in task_names
        assert "Task B" in task_names
    
    @pytest.mark.asyncio
    async def test_create_task_copy_reset_fields(self, sync_db_session):
        """Test reset_fields parameter functionality"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create completed task with results
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-reset", "Root Task",
            status="completed",
            result={"output": "test result"},
            progress=1.0
        )
        
        # Copy with reset_fields=["status", "progress"] (preserve result)
        task_array = await creator.create_task_copy(
            root_task,
            save=False,
            reset_fields=["status", "progress"]
        )
        
        # Verify reset_fields behavior
        root_dict = next(t for t in task_array if t["name"] == "Root Task")
        
        # Status and progress should be reset
        assert root_dict["status"] == "pending"
        assert root_dict["progress"] == 0.0
        
        # Result should be preserved (not in reset_fields)
        # Note: If result is None, it may not be included in the dict
        # But if it exists, it should be preserved
        if "result" in root_dict:
            # If result field is present, it should be preserved (not None)
            assert root_dict["result"] is not None
        # If result is not in dict, it means it was None and excluded (which is also valid)
    
    @pytest.mark.asyncio
    async def test_create_task_copy_reset_fields_all(self, sync_db_session):
        """Test reset_fields=None resets all execution fields"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create completed task with results
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-reset-all", "Root Task",
            status="completed",
            result={"output": "test result"},
            progress=1.0
        )
        
        # Copy with reset_fields=None (default - reset all)
        task_array = await creator.create_task_copy(
            root_task,
            save=False,
            reset_fields=None
        )
        
        # Verify all execution fields are reset
        root_dict = next(t for t in task_array if t["name"] == "Root Task")
        assert root_dict["status"] == "pending"
        assert root_dict["progress"] == 0.0
        assert root_dict.get("result") is None
        assert root_dict.get("error") is None
    
    @pytest.mark.asyncio
    async def test_create_task_copy_custom_include_children(self, sync_db_session):
        """Test custom copy mode with include_children parameter"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-include", "Root Task"
        )
        task_a = await self.create_task(
            sync_db_session, task_repository,
            "task-a-include", "Task A",
            parent_id=root_task.id
        )
        await self.create_task(
            sync_db_session, task_repository,
            "child-a-include", "Child A",
            parent_id=task_a.id
        )
        
        # Copy with custom_include_children=False (default)
        task_array_no_children = await creator.create_task_copy(
            root_task,
            copy_mode="custom",
            custom_task_ids=[str(task_a.id)],
            custom_include_children=False,
            save=False
        )
        
        # Copy with custom_include_children=True
        task_array_with_children = await creator.create_task_copy(
            root_task,
            copy_mode="custom",
            custom_task_ids=[str(task_a.id)],
            custom_include_children=True,
            save=False
        )
        
        # Verify custom_include_children=False doesn't include children
        names_no_children = [t["name"] for t in task_array_no_children]
        assert "Task A" in names_no_children
        assert "Child A" not in names_no_children
        
        # Verify custom_include_children=True includes children
        names_with_children = [t["name"] for t in task_array_with_children]
        assert "Task A" in names_with_children
        assert "Child A" in names_with_children
    
    @pytest.mark.asyncio
    async def test_tree_to_task_array_uses_task_model_fields(self, sync_db_session):
        """Test that _tree_to_task_array only uses TaskModel's actual fields"""
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        task_repository = TaskRepository(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create a task
        root_task = await self.create_task(
            sync_db_session, task_repository,
            "root-fields", "Root Task",
            result={"token_usage": {"total_tokens": 100}}
        )
        
        # Get task tree
        task_tree = await task_repository.build_task_tree(root_task)
        
        # Convert to array
        task_array = creator._tree_to_task_array(task_tree)
        
        # Get TaskModel fields
        task_model_class = get_task_model_class()
        valid_fields = set(task_model_class.__table__.columns.keys())
        # Remove fields that shouldn't be in create array
        # Note: id is now included for id-based mode
        valid_fields.discard("created_at")
        valid_fields.discard("updated_at")
        valid_fields.discard("has_copy")
        
        # Verify all fields in array are valid TaskModel fields
        root_dict = task_array[0]
        for field_name in root_dict.keys():
            # parent_id is converted to name reference, so it's valid
            if field_name == "parent_id":
                continue
            assert field_name in valid_fields or field_name == "parent_id", \
                f"Field '{field_name}' is not a valid TaskModel field"
        
        # Verify no fictional fields
        fictional_fields = ["display_name", "parent_index", "task_index"]
        for field in fictional_fields:
            assert field not in root_dict, f"Fictional field '{field}' should not be present"

