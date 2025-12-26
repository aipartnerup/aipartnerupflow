"""
Test cases for handle_task_update critical field validation

Tests the validation logic for critical fields (parent_id, user_id, dependencies)
and ensures other fields can be updated freely.
"""

import pytest
import pytest_asyncio
import uuid
from unittest.mock import Mock
from starlette.requests import Request

from aipartnerupflow.api.routes.tasks import TaskRoutes
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class


@pytest.fixture
def task_routes(use_test_db_session):
    """Create TaskRoutes instance for testing"""
    return TaskRoutes(
        task_model_class=get_task_model_class(),
        verify_token_func=None,
        verify_permission_func=None
    )


@pytest.fixture
def mock_request():
    """Create a mock Request object"""
    request = Mock(spec=Request)
    request.state = Mock()
    request.state.user_id = None
    request.state.token_payload = None
    return request


@pytest_asyncio.fixture
async def pending_task(use_test_db_session):
    """Create a pending task for testing"""
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
    
    task_id = f"pending-task-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=task_id,
        name="Pending Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        inputs={},
        dependencies=[]
    )
    
    return task_id


@pytest_asyncio.fixture
async def completed_task(use_test_db_session):
    """Create a completed task for testing"""
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
    
    task_id = f"completed-task-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=task_id,
        name="Completed Task",
        user_id="test_user",
        priority=1,
        has_children=False,
        progress=1.0,
        inputs={},
        dependencies=[]
    )
    # Update status to completed (create_task always creates pending tasks)
    await task_repository.update_task_status(
        task_id=task_id,
        status="completed",
        progress=1.0
    )
    
    return task_id


@pytest_asyncio.fixture
async def in_progress_task(use_test_db_session):
    """Create an in_progress task for testing"""
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
    
    task_id = f"inprogress-task-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=task_id,
        name="In Progress Task",
        user_id="test_user",
        priority=1,
        has_children=False,
        progress=0.5,
        inputs={},
        dependencies=[]
    )
    # Update status to in_progress (create_task always creates pending tasks)
    await task_repository.update_task_status(
        task_id=task_id,
        status="in_progress",
        progress=0.5
    )
    
    return task_id


@pytest_asyncio.fixture
async def task_tree_with_dependencies(use_test_db_session):
    """Create a task tree with dependencies for testing"""
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
    
    # Create root task
    root_id = f"root-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=root_id,
        name="Root Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=True,
        progress=0.0,
        inputs={},
        dependencies=[]
    )
    
    # Create child task 1
    child1_id = f"child1-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=child1_id,
        name="Child Task 1",
        user_id="test_user",
        parent_id=root_id,
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        inputs={},
        dependencies=[{"id": root_id, "required": True}]
    )
    
    # Create child task 2
    child2_id = f"child2-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=child2_id,
        name="Child Task 2",
        user_id="test_user",
        parent_id=root_id,
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        inputs={},
        dependencies=[{"id": root_id, "required": True}]
    )
    
    return {
        "root_id": root_id,
        "child1_id": child1_id,
        "child2_id": child2_id
    }


class TestCriticalFieldValidation:
    """Test critical field validation (parent_id, user_id, dependencies)"""
    
    @pytest.mark.asyncio
    async def test_update_parent_id_always_rejected(self, task_routes, mock_request, pending_task):
        """Test that parent_id update is always rejected"""
        params = {
            "task_id": pending_task,
            "parent_id": "new-parent-id"
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Cannot update 'parent_id'" in str(exc_info.value)
        assert "task hierarchy is fixed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_user_id_always_rejected(self, task_routes, mock_request, pending_task):
        """Test that user_id update is always rejected"""
        params = {
            "task_id": pending_task,
            "user_id": "new-user-id"
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Cannot update 'user_id'" in str(exc_info.value)
        assert "task ownership is fixed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_dependencies_non_pending_rejected(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test that dependencies update is rejected for non-pending tasks"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create root task
        root_id = f"root-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=root_id,
            name="Root Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            inputs={},
            dependencies=[]
        )
        
        # Create completed task in same tree
        completed_id = f"completed-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=completed_id,
            name="Completed Task",
            user_id="test_user",
            parent_id=root_id,
            priority=1,
            has_children=False,
            progress=1.0,
            inputs={},
            dependencies=[]
        )
        # Update status to completed (create_task always creates pending tasks)
        await task_repository.update_task_status(
            task_id=completed_id,
            status="completed",
            progress=1.0
        )
        
        # Try to update dependencies for completed task
        params = {
            "task_id": completed_id,
            "dependencies": [{"id": root_id, "required": True}]
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Cannot update 'dependencies'" in str(exc_info.value)
        assert "task status is 'completed'" in str(exc_info.value)
        assert "must be 'pending'" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_dependencies_in_progress_rejected(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test that dependencies update is rejected for in_progress tasks"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create root task
        root_id = f"root-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=root_id,
            name="Root Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            inputs={},
            dependencies=[]
        )
        
        # Create in_progress task in same tree
        in_progress_id = f"inprogress-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=in_progress_id,
            name="In Progress Task",
            user_id="test_user",
            parent_id=root_id,
            priority=1,
            has_children=False,
            progress=0.5,
            inputs={},
            dependencies=[]
        )
        # Update status to in_progress (create_task always creates pending tasks)
        await task_repository.update_task_status(
            task_id=in_progress_id,
            status="in_progress",
            progress=0.5
        )
        
        # Try to update dependencies for in_progress task
        params = {
            "task_id": in_progress_id,
            "dependencies": [{"id": root_id, "required": True}]
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Cannot update 'dependencies'" in str(exc_info.value)
        assert "task status is 'in_progress'" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_dependencies_invalid_reference(
        self, task_routes, mock_request, pending_task
    ):
        """Test that dependencies update is rejected for invalid dependency references"""
        params = {
            "task_id": pending_task,
            "dependencies": [{"id": "non-existent-task-id", "required": True}]
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Dependency reference 'non-existent-task-id' not found in task tree" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_dependencies_circular_dependency(
        self, task_routes, mock_request, task_tree_with_dependencies, use_test_db_session
    ):
        """Test that circular dependencies are detected and rejected"""
        # Try to create a circular dependency: child1 depends on child2, child2 depends on child1
        params = {
            "task_id": task_tree_with_dependencies["child1_id"],
            "dependencies": [{"id": task_tree_with_dependencies["child2_id"], "required": True}]
        }
        request_id = str(uuid.uuid4())
        
        # First, update child2 to depend on child1
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        child2 = await task_repository.get_task_by_id(task_tree_with_dependencies["child2_id"])
        child2.dependencies = [{"id": task_tree_with_dependencies["child1_id"], "required": True}]
        if task_repository.is_async:
            await use_test_db_session.commit()
        else:
            use_test_db_session.commit()
        
        # Now try to update child1 to depend on child2 (creates cycle)
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Circular dependency detected" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_dependencies_valid_update(
        self, task_routes, mock_request, task_tree_with_dependencies
    ):
        """Test that valid dependencies update succeeds for pending task"""
        params = {
            "task_id": task_tree_with_dependencies["child1_id"],
            "dependencies": [
                {"id": task_tree_with_dependencies["root_id"], "required": True},
                {"id": task_tree_with_dependencies["child2_id"], "required": False}
            ]
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert "dependencies" in result
        assert len(result["dependencies"]) == 2
    
    @pytest.mark.asyncio
    async def test_update_dependencies_not_list_rejected(
        self, task_routes, mock_request, pending_task
    ):
        """Test that dependencies must be a list"""
        params = {
            "task_id": pending_task,
            "dependencies": "not-a-list"
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "must be a list" in str(exc_info.value)


class TestOtherFieldsUpdate:
    """Test that other fields can be updated freely without status restrictions"""
    
    @pytest.mark.asyncio
    async def test_update_inputs_from_any_status(
        self, task_routes, mock_request, completed_task
    ):
        """Test that inputs can be updated from completed status"""
        params = {
            "task_id": completed_task,
            "inputs": {"new_key": "new_value"}
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["inputs"]["new_key"] == "new_value"
    
    @pytest.mark.asyncio
    async def test_update_name_from_any_status(
        self, task_routes, mock_request, completed_task
    ):
        """Test that name can be updated from completed status"""
        params = {
            "task_id": completed_task,
            "name": "New Task Name"
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["name"] == "New Task Name"
    
    @pytest.mark.asyncio
    async def test_update_priority_from_any_status(
        self, task_routes, mock_request, completed_task
    ):
        """Test that priority can be updated from completed status"""
        params = {
            "task_id": completed_task,
            "priority": 5
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["priority"] == 5
    
    @pytest.mark.asyncio
    async def test_update_params_from_any_status(
        self, task_routes, mock_request, completed_task
    ):
        """Test that params can be updated from completed status"""
        params = {
            "task_id": completed_task,
            "params": {"executor_id": "new_executor"}
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["params"]["executor_id"] == "new_executor"
    
    @pytest.mark.asyncio
    async def test_update_schemas_from_any_status(
        self, task_routes, mock_request, completed_task
    ):
        """Test that schemas can be updated from completed status"""
        params = {
            "task_id": completed_task,
            "schemas": {"input_schema": {"type": "object"}}
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert "input_schema" in result["schemas"]
    
    @pytest.mark.asyncio
    async def test_update_status_from_any_status(
        self, task_routes, mock_request, completed_task
    ):
        """Test that status can be updated from completed status"""
        params = {
            "task_id": completed_task,
            "status": "pending"
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_update_result_from_any_status(
        self, task_routes, mock_request, pending_task
    ):
        """Test that result can be updated from pending status"""
        params = {
            "task_id": pending_task,
            "result": {"output": "test_result"}
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["result"]["output"] == "test_result"
    
    @pytest.mark.asyncio
    async def test_update_error_from_any_status(
        self, task_routes, mock_request, pending_task
    ):
        """Test that error can be updated from pending status"""
        params = {
            "task_id": pending_task,
            "error": "Test error message"
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["error"] == "Test error message"
    
    @pytest.mark.asyncio
    async def test_update_progress_from_any_status(
        self, task_routes, mock_request, pending_task
    ):
        """Test that progress can be updated from pending status"""
        params = {
            "task_id": pending_task,
            "progress": 0.75
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert float(result["progress"]) == 0.75


class TestMultipleFieldsUpdate:
    """Test updating multiple fields at once"""
    
    @pytest.mark.asyncio
    async def test_update_multiple_fields_success(
        self, task_routes, mock_request, pending_task
    ):
        """Test updating multiple non-critical fields succeeds"""
        params = {
            "task_id": pending_task,
            "name": "Updated Name",
            "priority": 3,
            "inputs": {"key": "value"}
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["name"] == "Updated Name"
        assert result["priority"] == 3
        assert result["inputs"]["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_update_with_critical_field_error(
        self, task_routes, mock_request, pending_task
    ):
        """Test that critical field errors are reported even when other fields are valid"""
        params = {
            "task_id": pending_task,
            "name": "Updated Name",
            "parent_id": "new-parent",  # This should fail
            "priority": 3
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Cannot update 'parent_id'" in str(exc_info.value)
        # Verify that the error message includes the critical field error
    
    @pytest.mark.asyncio
    async def test_update_multiple_critical_fields_errors(
        self, task_routes, mock_request, pending_task
    ):
        """Test that all critical field errors are reported"""
        params = {
            "task_id": pending_task,
            "parent_id": "new-parent",  # Should fail
            "user_id": "new-user",  # Should fail
            "name": "Updated Name"  # Should succeed (but update won't happen due to errors)
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        error_message = str(exc_info.value)
        assert "Cannot update 'parent_id'" in error_message
        assert "Cannot update 'user_id'" in error_message


class TestDependencyUpdateEdgeCases:
    """Test edge cases for dependency updates"""
    
    @pytest.mark.asyncio
    async def test_update_dependencies_empty_list(
        self, task_routes, mock_request, task_tree_with_dependencies
    ):
        """Test that empty dependencies list is valid"""
        params = {
            "task_id": task_tree_with_dependencies["child1_id"],
            "dependencies": []
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert result["dependencies"] == []
    
    @pytest.mark.asyncio
    async def test_update_dependencies_self_reference(
        self, task_routes, mock_request, task_tree_with_dependencies
    ):
        """Test that self-reference in dependencies creates circular dependency"""
        params = {
            "task_id": task_tree_with_dependencies["child1_id"],
            "dependencies": [{"id": task_tree_with_dependencies["child1_id"], "required": True}]
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert "Circular dependency detected" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_dependencies_string_format(
        self, task_routes, mock_request, task_tree_with_dependencies
    ):
        """Test that dependencies can be specified as string IDs"""
        params = {
            "task_id": task_tree_with_dependencies["child1_id"],
            "dependencies": [task_tree_with_dependencies["root_id"]]
        }
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_update(params, mock_request, request_id)
        
        assert result is not None
        assert len(result["dependencies"]) == 1

