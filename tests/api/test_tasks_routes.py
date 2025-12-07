"""
Test TaskRoutes.handle_task_execute functionality

Tests the four scenarios:
1. Regular POST (no webhook, no SSE)
2. Regular POST + webhook (no SSE)
3. SSE (no webhook)
4. SSE + webhook
"""

import pytest
import pytest_asyncio
import json
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from starlette.requests import Request
from starlette.responses import StreamingResponse

from aipartnerupflow.api.routes.tasks import TaskRoutes
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class
from aipartnerupflow.core.execution.task_tracker import TaskTracker


@pytest.fixture
def task_routes(use_test_db_session):
    """Create TaskRoutes instance for testing"""
    return TaskRoutes(
        task_model_class=get_task_model_class(),
        verify_token_func=None,  # No JWT for testing
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
async def sample_task(use_test_db_session):
    """Create a sample task in database for testing"""
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
    
    task_id = f"test-task-{uuid.uuid4().hex[:8]}"
    task = await task_repository.create_task(
        id=task_id,
        name="Test Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        schemas={
            "method": "system_info_executor"
        },
        inputs={}
    )
    
    return task_id


class TestHandleTaskExecute:
    """Test cases for handle_task_execute method"""
    
    @pytest.mark.asyncio
    async def test_regular_post_no_webhook(self, task_routes, mock_request, sample_task):
        """Test regular POST mode without webhook"""
        params = {
            "task_id": sample_task,
            "use_streaming": False
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskExecutor to avoid actual execution
        with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(return_value={
                "status": "started",
                "progress": 0.0,
                "root_task_id": sample_task
            })
            mock_executor_class.return_value = mock_executor
            
            # Mock TaskTracker
            with patch('aipartnerupflow.core.execution.task_tracker.TaskTracker') as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.is_task_running = Mock(return_value=False)
                mock_tracker_class.return_value = mock_tracker
                
                result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["protocol"] == "jsonrpc"
        assert result["root_task_id"] == sample_task
        assert result["task_id"] == sample_task
        assert result["status"] == "started"
        assert "streaming" not in result or result.get("streaming") is False
        assert "webhook_url" not in result
        
        # Note: execute_task_by_id is called via asyncio.create_task in background
        # We verify the response indicates correct mode instead of checking call args
    
    @pytest.mark.asyncio
    async def test_regular_post_with_webhook(self, task_routes, mock_request, sample_task):
        """Test regular POST mode with webhook callbacks"""
        webhook_url = "https://example.com/webhook"
        params = {
            "task_id": sample_task,
            "use_streaming": False,
            "webhook_config": {
                "url": webhook_url,
                "method": "POST",
                "timeout": 30.0,
                "max_retries": 3
            }
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskExecutor to avoid actual execution
        with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(return_value={
                "status": "started",
                "progress": 0.0,
                "root_task_id": sample_task
            })
            mock_executor_class.return_value = mock_executor
            
            # Mock TaskTracker
            with patch('aipartnerupflow.core.execution.task_tracker.TaskTracker') as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.is_task_running = Mock(return_value=False)
                mock_tracker_class.return_value = mock_tracker
                
                result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["protocol"] == "jsonrpc"
        assert result["root_task_id"] == sample_task
        assert result["task_id"] == sample_task
        assert result["status"] == "started"
        assert result["streaming"] is True  # Indicates webhook callbacks are active
        assert result["webhook_url"] == webhook_url
        assert "webhook" in result["message"].lower()
        
        # Verify execution was called with streaming enabled for webhook
        # Note: execute_task_tree is called via asyncio.create_task, so we check the call
        # The actual call happens in background, but we can verify the context was created
        from aipartnerupflow.api.routes.tasks import WebhookStreamingContext
        # The context is created before the async task, so we can't directly assert on it
        # But we can verify the response indicates webhook is configured
    
    @pytest.mark.asyncio
    async def test_sse_no_webhook(self, task_routes, mock_request, sample_task):
        """Test SSE mode without webhook"""
        params = {
            "task_id": sample_task,
            "use_streaming": True
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskExecutor to avoid actual execution
        with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(return_value={
                "status": "started",
                "progress": 0.0,
                "root_task_id": sample_task
            })
            mock_executor_class.return_value = mock_executor
            
            # Mock TaskTracker
            with patch('aipartnerupflow.core.execution.task_tracker.TaskTracker') as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.is_task_running = Mock(return_value=False)
                mock_tracker_class.return_value = mock_tracker
                
                # Mock get_task_streaming_events to return empty list initially
                with patch('aipartnerupflow.api.routes.tasks.get_task_streaming_events', new_callable=AsyncMock) as mock_get_events:
                    mock_get_events.return_value = []
                    
                    result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response is StreamingResponse
        assert isinstance(result, StreamingResponse)
        assert result.media_type == "text/event-stream"
        
        # Verify execution was called with streaming enabled
        # Note: execute_task_by_id is called via asyncio.create_task in background
        # The context is created before the async task, so we verify the response type
    
    @pytest.mark.asyncio
    async def test_sse_with_webhook(self, task_routes, mock_request, sample_task):
        """Test SSE mode with webhook callbacks"""
        webhook_url = "https://example.com/webhook"
        params = {
            "task_id": sample_task,
            "use_streaming": True,
            "webhook_config": {
                "url": webhook_url,
                "method": "POST",
                "timeout": 30.0,
                "max_retries": 3
            }
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskExecutor to avoid actual execution
        with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(return_value={
                "status": "started",
                "progress": 0.0,
                "root_task_id": sample_task
            })
            mock_executor_class.return_value = mock_executor
            
            # Mock TaskTracker
            with patch('aipartnerupflow.core.execution.task_tracker.TaskTracker') as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.is_task_running = Mock(return_value=False)
                mock_tracker_class.return_value = mock_tracker
                
                # Mock get_task_streaming_events to return empty list initially
                with patch('aipartnerupflow.api.routes.tasks.get_task_streaming_events', new_callable=AsyncMock) as mock_get_events:
                    mock_get_events.return_value = []
                    
                    result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response is StreamingResponse
        assert isinstance(result, StreamingResponse)
        assert result.media_type == "text/event-stream"
        
        # Verify execution was called with streaming enabled
        # Note: execute_task_by_id is called via asyncio.create_task in background
        # The context is created before the async task, so we verify the response type
    
    @pytest.mark.asyncio
    async def test_task_not_found(self, task_routes, mock_request):
        """Test error handling when task is not found"""
        params = {
            "task_id": "non-existent-task",
            "use_streaming": False
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError, match="not found"):
            await task_routes.handle_task_execute(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_task_already_running(self, task_routes, mock_request, sample_task):
        """Test handling when task is already running"""
        params = {
            "task_id": sample_task,
            "use_streaming": False
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskTracker to return True for is_task_running
        with patch('aipartnerupflow.core.execution.task_tracker.TaskTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.is_task_running = Mock(return_value=True)
            mock_tracker_class.return_value = mock_tracker
            
            result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response indicates task is already running
        assert isinstance(result, dict)
        assert result["success"] is False
        assert result["status"] == "already_running"
        assert sample_task in result["message"]
    
    @pytest.mark.asyncio
    async def test_missing_task_id(self, task_routes, mock_request):
        """Test error handling when task_id is missing"""
        params = {
            "use_streaming": False
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError, match="Either task_id or tasks array is required"):
            await task_routes.handle_task_execute(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_webhook_config_validation(self, task_routes, mock_request, sample_task):
        """Test webhook_config validation - missing url"""
        params = {
            "task_id": sample_task,
            "use_streaming": False,
            "webhook_config": {
                "method": "POST"
                # Missing required "url" field
            }
        }
        request_id = str(uuid.uuid4())
        
        # Import TaskTracker to patch its instance method
        from aipartnerupflow.core.execution.task_tracker import TaskTracker
        
        # Patch TaskTracker.is_task_running on the instance (not the class)
        # This avoids the singleton super() issue
        with patch.object(TaskTracker(), 'is_task_running', return_value=False):
            # Mock TaskExecutor to avoid actual execution, but allow code to continue
            # The error should occur when creating WebhookStreamingContext
            with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
                mock_executor = Mock()
                mock_executor.execute_task_by_id = AsyncMock()
                mock_executor_class.return_value = mock_executor
                
                with pytest.raises(ValueError, match="webhook_config.url is required"):
                    await task_routes.handle_task_execute(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_copy_execution_basic(self, task_routes, mock_request, sample_task):
        """Test copy_execution=True parameter"""
        params = {
            "task_id": sample_task,
            "copy_execution": True,
            "use_streaming": False
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskCreator.create_task_copy
        with patch('aipartnerupflow.api.routes.tasks.TaskCreator') as mock_creator_class:
            mock_creator = Mock()
            mock_copied_task = Mock()
            mock_copied_task.id = "copied-task-id"
            mock_copied_tree = Mock()
            mock_copied_tree.task = mock_copied_task
            mock_creator.create_task_copy = AsyncMock(return_value=mock_copied_tree)
            mock_creator_class.return_value = mock_creator
            
            # Mock _get_task_repository to return a mock repository
            with patch.object(task_routes, '_get_task_repository') as mock_get_repo:
                mock_repository = Mock(spec=TaskRepository)
                
                # Mock get_task_by_id: first call returns original task, second call returns copied task
                call_count = {"count": 0}
                async def get_task_side_effect(task_id):
                    call_count["count"] += 1
                    if task_id == sample_task:
                        # Return original task
                        task = Mock()
                        task.id = sample_task
                        task.user_id = "test_user"
                        return task
                    elif task_id == "copied-task-id":
                        # Return copied task
                        return mock_copied_task
                    return None
                
                mock_repository.get_task_by_id = AsyncMock(side_effect=get_task_side_effect)
                mock_repository.get_root_task = AsyncMock(return_value=mock_copied_task)
                mock_get_repo.return_value = mock_repository
                
                # Mock TaskExecutor
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
                    mock_executor = Mock()
                    mock_executor.execute_task_by_id = AsyncMock(return_value={
                        "status": "started",
                        "progress": 0.0,
                        "root_task_id": "copied-task-id"
                    })
                    mock_executor_class.return_value = mock_executor
                    
                    # Mock TaskTracker
                    with patch.object(TaskTracker(), 'is_task_running', return_value=False):
                        result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response includes original_task_id
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["protocol"] == "jsonrpc"
        assert result["root_task_id"] == "copied-task-id"
        assert result["task_id"] == "copied-task-id"
        assert result["original_task_id"] == sample_task
        assert result["status"] == "started"
        
        # Verify create_task_copy was called with correct parameters
        mock_creator.create_task_copy.assert_called_once()
        call_args = mock_creator.create_task_copy.call_args
        assert call_args[0][0].id == sample_task  # First positional arg is the task
        assert call_args[1]["children"] is False  # children defaults to False

    @pytest.mark.asyncio
    async def test_copy_execution_with_children(self, task_routes, mock_request, sample_task):
        """Test copy_execution=True with copy_children=True"""
        params = {
            "task_id": sample_task,
            "copy_execution": True,
            "copy_children": True,
            "use_streaming": False
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskCreator.create_task_copy
        with patch('aipartnerupflow.api.routes.tasks.TaskCreator') as mock_creator_class:
            mock_creator = Mock()
            mock_copied_task = Mock()
            mock_copied_task.id = "copied-task-id"
            mock_copied_tree = Mock()
            mock_copied_tree.task = mock_copied_task
            mock_creator.create_task_copy = AsyncMock(return_value=mock_copied_tree)
            mock_creator_class.return_value = mock_creator
            
            # Mock _get_task_repository to return a mock repository
            with patch.object(task_routes, '_get_task_repository') as mock_get_repo:
                mock_repository = Mock(spec=TaskRepository)
                async def get_task_side_effect(task_id):
                    if task_id == sample_task:
                        task = Mock()
                        task.id = sample_task
                        task.user_id = "test_user"
                        return task
                    elif task_id == "copied-task-id":
                        return mock_copied_task
                    return None
                mock_repository.get_task_by_id = AsyncMock(side_effect=get_task_side_effect)
                mock_repository.get_root_task = AsyncMock(return_value=mock_copied_task)
                mock_get_repo.return_value = mock_repository
                
                # Mock TaskExecutor
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
                    mock_executor = Mock()
                    mock_executor.execute_task_by_id = AsyncMock(return_value={
                        "status": "started",
                        "progress": 0.0,
                        "root_task_id": "copied-task-id"
                    })
                    mock_executor_class.return_value = mock_executor
                    
                    # Mock TaskTracker
                    with patch.object(TaskTracker(), 'is_task_running', return_value=False):
                        result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response includes original_task_id
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["original_task_id"] == sample_task
        
        # Verify create_task_copy was called with children=True
        mock_creator.create_task_copy.assert_called_once()
        call_args = mock_creator.create_task_copy.call_args
        assert call_args[1]["children"] is True

    @pytest.mark.asyncio
    async def test_copy_execution_with_streaming(self, task_routes, mock_request, sample_task):
        """Test copy_execution=True with use_streaming=True"""
        params = {
            "task_id": sample_task,
            "copy_execution": True,
            "use_streaming": True
        }
        request_id = str(uuid.uuid4())
        
        # Mock TaskCreator.create_task_copy
        with patch('aipartnerupflow.api.routes.tasks.TaskCreator') as mock_creator_class:
            mock_creator = Mock()
            mock_copied_task = Mock()
            mock_copied_task.id = "copied-task-id"
            mock_copied_tree = Mock()
            mock_copied_tree.task = mock_copied_task
            mock_creator.create_task_copy = AsyncMock(return_value=mock_copied_tree)
            mock_creator_class.return_value = mock_creator
            
            # Mock _get_task_repository to return a mock repository
            with patch.object(task_routes, '_get_task_repository') as mock_get_repo:
                mock_repository = Mock(spec=TaskRepository)
                async def get_task_side_effect(task_id):
                    if task_id == sample_task:
                        task = Mock()
                        task.id = sample_task
                        task.user_id = "test_user"
                        return task
                    elif task_id == "copied-task-id":
                        return mock_copied_task
                    return None
                mock_repository.get_task_by_id = AsyncMock(side_effect=get_task_side_effect)
                mock_repository.get_root_task = AsyncMock(return_value=mock_copied_task)
                mock_get_repo.return_value = mock_repository
                
                # Mock TaskExecutor
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor') as mock_executor_class:
                    mock_executor = Mock()
                    mock_executor.execute_task_by_id = AsyncMock(return_value={
                        "status": "started",
                        "progress": 0.0,
                        "root_task_id": "copied-task-id"
                    })
                    mock_executor_class.return_value = mock_executor
                    
                    # Mock TaskTracker
                    with patch.object(TaskTracker(), 'is_task_running', return_value=False):
                        result = await task_routes.handle_task_execute(params, mock_request, request_id)
        
        # Verify response is StreamingResponse
        assert isinstance(result, StreamingResponse)
        assert result.media_type == "text/event-stream"


class TestHandleTaskDelete:
    """Test cases for handle_task_delete method"""
    
    @pytest.mark.asyncio
    async def test_delete_pending_task_no_children(self, task_routes, mock_request, use_test_db_session):
        """Test deleting a pending task with no children"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a pending task (default status is pending)
        task = await task_repository.create_task(
            name="Task to Delete",
            user_id="test_user"
        )
        
        params = {"task_id": task.id}
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_delete(params, mock_request, request_id)
        
        # Verify deletion success
        assert result["success"] is True
        assert result["task_id"] == task.id
        assert result["deleted_count"] == 1
        assert result["children_deleted"] == 0
        
        # Verify task is physically deleted
        deleted_task = await task_repository.get_task_by_id(task.id)
        assert deleted_task is None
    
    @pytest.mark.asyncio
    async def test_delete_pending_task_with_pending_children(self, task_routes, mock_request, use_test_db_session):
        """Test deleting a pending task with all pending children"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create task tree: root -> child1, child2 -> grandchild (all pending by default)
        root = await task_repository.create_task(
            name="Root Task",
            user_id="test_user"
        )
        
        child1 = await task_repository.create_task(
            name="Child 1",
            user_id="test_user",
            parent_id=root.id
        )
        
        child2 = await task_repository.create_task(
            name="Child 2",
            user_id="test_user",
            parent_id=root.id
        )
        
        grandchild = await task_repository.create_task(
            name="Grandchild",
            user_id="test_user",
            parent_id=child1.id
        )
        
        params = {"task_id": root.id}
        request_id = str(uuid.uuid4())
        
        result = await task_routes.handle_task_delete(params, mock_request, request_id)
        
        # Verify deletion success
        assert result["success"] is True
        assert result["task_id"] == root.id
        assert result["deleted_count"] == 4  # root + child1 + child2 + grandchild
        assert result["children_deleted"] == 3
        
        # Verify all tasks are deleted
        assert await task_repository.get_task_by_id(root.id) is None
        assert await task_repository.get_task_by_id(child1.id) is None
        assert await task_repository.get_task_by_id(child2.id) is None
        assert await task_repository.get_task_by_id(grandchild.id) is None
    
    @pytest.mark.asyncio
    async def test_delete_fails_with_non_pending_children(self, task_routes, mock_request, use_test_db_session):
        """Test deletion fails when task has non-pending children"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create task tree with non-pending child
        root = await task_repository.create_task(
            name="Root Task",
            user_id="test_user"
        )
        
        child1 = await task_repository.create_task(
            name="Child 1",
            user_id="test_user",
            parent_id=root.id
        )
        
        child2 = await task_repository.create_task(
            name="Child 2",
            user_id="test_user",
            parent_id=root.id
        )
        
        # Update child2 to non-pending status
        await task_repository.update_task_status(child2.id, status="in_progress")
        
        params = {"task_id": root.id}
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_delete(params, mock_request, request_id)
        
        # Verify error message contains information about non-pending child
        error_msg = str(exc_info.value)
        assert "Cannot delete task" in error_msg
        assert "non-pending children" in error_msg
        assert child2.id in error_msg
        assert "in_progress" in error_msg
        
        # Verify tasks are not deleted
        assert await task_repository.get_task_by_id(root.id) is not None
        assert await task_repository.get_task_by_id(child1.id) is not None
        assert await task_repository.get_task_by_id(child2.id) is not None
    
    @pytest.mark.asyncio
    async def test_delete_fails_with_non_pending_task(self, task_routes, mock_request, use_test_db_session):
        """Test deletion fails when task itself is not pending"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task and update to non-pending status
        task = await task_repository.create_task(
            name="Task to Delete",
            user_id="test_user"
        )
        await task_repository.update_task_status(task.id, status="completed")
        
        params = {"task_id": task.id}
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_delete(params, mock_request, request_id)
        
        # Verify error message
        error_msg = str(exc_info.value)
        assert "Cannot delete task" in error_msg
        assert "task status is 'completed'" in error_msg
        assert "must be 'pending'" in error_msg
        
        # Verify task is not deleted
        assert await task_repository.get_task_by_id(task.id) is not None
    
    @pytest.mark.asyncio
    async def test_delete_fails_with_dependent_tasks(self, task_routes, mock_request, use_test_db_session):
        """Test deletion fails when other tasks depend on this task"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task that will be a dependency
        dep_task = await task_repository.create_task(
            name="Dependency Task",
            user_id="test_user"
        )
        
        # Create tasks that depend on dep_task
        dependent1 = await task_repository.create_task(
            name="Dependent Task 1",
            user_id="test_user",
            dependencies=[{"id": dep_task.id, "required": True}]
        )
        
        dependent2 = await task_repository.create_task(
            name="Dependent Task 2",
            user_id="test_user",
            dependencies=[{"id": dep_task.id, "required": False}]
        )
        
        params = {"task_id": dep_task.id}
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_delete(params, mock_request, request_id)
        
        # Verify error message contains information about dependent tasks
        error_msg = str(exc_info.value)
        assert "Cannot delete task" in error_msg
        assert "tasks depend on this task" in error_msg
        assert dependent1.id in error_msg
        assert dependent2.id in error_msg
        
        # Verify task is not deleted
        assert await task_repository.get_task_by_id(dep_task.id) is not None
    
    @pytest.mark.asyncio
    async def test_delete_fails_with_mixed_conditions(self, task_routes, mock_request, use_test_db_session):
        """Test deletion fails with both non-pending children and dependencies"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create task tree
        root = await task_repository.create_task(
            name="Root Task",
            user_id="test_user"
        )
        
        child1 = await task_repository.create_task(
            name="Child 1",
            user_id="test_user",
            parent_id=root.id
        )
        
        # Update child1 to non-pending status
        await task_repository.update_task_status(child1.id, status="completed")
        
        # Create a task that depends on root
        dependent = await task_repository.create_task(
            name="Dependent Task",
            user_id="test_user",
            dependencies=[{"id": root.id, "required": True}]
        )
        
        params = {"task_id": root.id}
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError) as exc_info:
            await task_routes.handle_task_delete(params, mock_request, request_id)
        
        # Verify error message contains both issues
        error_msg = str(exc_info.value)
        assert "Cannot delete task" in error_msg
        assert "non-pending children" in error_msg
        assert "tasks depend on this task" in error_msg
        assert child1.id in error_msg
        assert dependent.id in error_msg
        
        # Verify tasks are not deleted
        assert await task_repository.get_task_by_id(root.id) is not None
        assert await task_repository.get_task_by_id(child1.id) is not None
        assert await task_repository.get_task_by_id(dependent.id) is not None
    
    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, task_routes, mock_request):
        """Test deletion fails when task does not exist"""
        params = {"task_id": "non-existent-task"}
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError, match="not found"):
            await task_routes.handle_task_delete(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_delete_missing_task_id(self, task_routes, mock_request):
        """Test deletion fails when task_id is missing"""
        params = {}
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError, match="Task ID is required"):
            await task_routes.handle_task_delete(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_delete_with_permission_check(self, task_routes, use_test_db_session):
        """Test deletion respects permission checks"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task with a specific user_id
        task = await task_repository.create_task(
            name="Task to Delete",
            user_id="user1"
        )
        
        # Create a mock request with different user
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user_id = "user2"  # Different user
        mock_request.state.token_payload = None
        
        # Mock permission check to raise ValueError (permission denied)
        with patch.object(task_routes, '_check_permission', side_effect=ValueError("Permission denied")):
            params = {"task_id": task.id}
            request_id = str(uuid.uuid4())
            
            with pytest.raises(ValueError, match="Permission denied"):
                await task_routes.handle_task_delete(params, mock_request, request_id)
        
        # Verify task is not deleted
        assert await task_repository.get_task_by_id(task.id) is not None


class TestHandleTaskGenerate:
    """Test cases for handle_task_generate method"""
    
    @pytest.mark.asyncio
    async def test_generate_basic(self, task_routes, mock_request, use_test_db_session):
        """Test basic task generation without saving to database"""
        import os
        from unittest.mock import patch, AsyncMock, Mock
        
        # Mock environment variable for API key
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {
                "requirement": "Fetch data from API and process it",
                "user_id": "test_user"
            }
            request_id = str(uuid.uuid4())
            
            # Mock generate_executor execution
            mock_generated_tasks = [
                {
                    "name": "rest_executor",
                    "inputs": {"url": "https://api.example.com/data", "method": "GET"},
                    "priority": 1
                },
                {
                    "name": "command_executor",
                    "dependencies": [{"id": "task_1", "required": True}],
                    "inputs": {"command": "python process.py"},
                    "priority": 2
                }
            ]
            
            # Mock TaskRepository constructor
            mock_repository = Mock(spec=TaskRepository)
            mock_generate_task = Mock()
            mock_generate_task.id = "generate-task-id"
            mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
            
            mock_result_task = Mock()
            mock_result_task.id = "generate-task-id"
            mock_result_task.status = "completed"
            mock_result_task.result = {"tasks": mock_generated_tasks}
            mock_result_task.error = None
            mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
            
            # Mock TaskExecutor.execute_task_tree
            mock_executor = Mock()
            async def mock_execute_task_tree(*args, **kwargs):
                import asyncio
                await asyncio.sleep(0.01)
            mock_executor.execute_task_tree = mock_execute_task_tree
            
            with patch('aipartnerupflow.api.routes.tasks.TaskRepository', return_value=mock_repository):
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor', return_value=mock_executor):
                    result = await task_routes.handle_task_generate(params, mock_request, request_id)
            
            # Verify response
            assert isinstance(result, dict)
            assert "tasks" in result
            assert result["tasks"] == mock_generated_tasks
            assert result["count"] == 2
            assert "message" in result
            assert "Successfully generated" in result["message"]
            assert "root_task_id" not in result  # Not saved to DB
    
    @pytest.mark.asyncio
    async def test_generate_with_save(self, task_routes, mock_request, use_test_db_session):
        """Test task generation with save=True"""
        import os
        from unittest.mock import patch, AsyncMock, Mock
        
        # Mock environment variable for API key
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {
                "requirement": "Fetch data from API and process it",
                "user_id": "test_user",
                "save": True
            }
            request_id = str(uuid.uuid4())
            
            mock_generated_tasks = [
                {
                    "name": "rest_executor",
                    "inputs": {"url": "https://api.example.com/data", "method": "GET"},
                    "priority": 1
                }
            ]
            
            # Mock TaskRepository constructor
            mock_repository = Mock(spec=TaskRepository)
            mock_generate_task = Mock()
            mock_generate_task.id = "generate-task-id"
            mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
            
            mock_result_task = Mock()
            mock_result_task.id = "generate-task-id"
            mock_result_task.status = "completed"
            mock_result_task.result = {"tasks": mock_generated_tasks}
            mock_result_task.error = None
            mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
            
            # Mock TaskExecutor.execute_task_tree
            mock_executor = Mock()
            async def mock_execute_task_tree(*args, **kwargs):
                import asyncio
                await asyncio.sleep(0.01)
            mock_executor.execute_task_tree = mock_execute_task_tree
            
            # Mock TaskCreator.create_task_tree_from_array
            mock_creator = Mock()
            mock_root_task = Mock()
            mock_root_task.id = "root-task-id"
            mock_task_tree = Mock()
            mock_task_tree.task = mock_root_task
            mock_creator.create_task_tree_from_array = AsyncMock(return_value=mock_task_tree)
            
            with patch('aipartnerupflow.api.routes.tasks.TaskRepository', return_value=mock_repository):
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor', return_value=mock_executor):
                    with patch('aipartnerupflow.api.routes.tasks.TaskCreator', return_value=mock_creator):
                        result = await task_routes.handle_task_generate(params, mock_request, request_id)
            
            # Verify response includes root_task_id
            assert isinstance(result, dict)
            assert "tasks" in result
            assert result["count"] == 1
            assert "root_task_id" in result
            assert result["root_task_id"] == "root-task-id"
            assert "saved to database" in result["message"]
    
    @pytest.mark.asyncio
    async def test_generate_missing_requirement(self, task_routes, mock_request):
        """Test error handling when requirement is missing"""
        params = {
            "user_id": "test_user"
        }
        request_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError, match="Requirement is required"):
            await task_routes.handle_task_generate(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_generate_missing_api_key(self, task_routes, mock_request):
        """Test error handling when LLM API key is missing"""
        import os
        from unittest.mock import patch
        
        # Ensure no API key in environment
        with patch.dict(os.environ, {}, clear=True):
            params = {
                "requirement": "Fetch data from API",
                "user_id": "test_user"
            }
            request_id = str(uuid.uuid4())
            
            with pytest.raises(ValueError, match="LLM API key not found"):
                await task_routes.handle_task_generate(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_generate_with_llm_config(self, task_routes, mock_request, use_test_db_session):
        """Test task generation with LLM configuration parameters"""
        import os
        from unittest.mock import patch, AsyncMock, Mock
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {
                "requirement": "Fetch data from API",
                "user_id": "test_user",
                "llm_provider": "openai",
                "llm_model": "gpt-4o",
                "temperature": 0.8,
                "max_tokens": 5000
            }
            request_id = str(uuid.uuid4())
            
            mock_generated_tasks = [{"name": "rest_executor", "inputs": {}}]
            
            # Mock TaskRepository constructor
            mock_repository = Mock(spec=TaskRepository)
            mock_generate_task = Mock()
            mock_generate_task.id = "generate-task-id"
            mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
            
            mock_result_task = Mock()
            mock_result_task.id = "generate-task-id"
            mock_result_task.status = "completed"
            mock_result_task.result = {"tasks": mock_generated_tasks}
            mock_result_task.error = None
            mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
            
            # Mock TaskExecutor.execute_task_tree
            mock_executor = Mock()
            async def mock_execute_task_tree(*args, **kwargs):
                import asyncio
                await asyncio.sleep(0.01)
            mock_executor.execute_task_tree = mock_execute_task_tree
            
            with patch('aipartnerupflow.api.routes.tasks.TaskRepository', return_value=mock_repository):
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor', return_value=mock_executor):
                    result = await task_routes.handle_task_generate(params, mock_request, request_id)
            
            # Verify LLM config was passed to create_task
            create_call = mock_repository.create_task.call_args
            assert create_call is not None
            inputs = create_call[1]["inputs"]
            assert inputs["llm_provider"] == "openai"
            assert inputs["llm_model"] == "gpt-4o"
            assert inputs["temperature"] == 0.8
            assert inputs["max_tokens"] == 5000
    
    @pytest.mark.asyncio
    async def test_generate_failed_status(self, task_routes, mock_request, use_test_db_session):
        """Test error handling when generation task fails"""
        import os
        from unittest.mock import patch, AsyncMock, Mock
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {
                "requirement": "Fetch data from API",
                "user_id": "test_user"
            }
            request_id = str(uuid.uuid4())
            
            # Mock TaskRepository constructor
            mock_repository = Mock(spec=TaskRepository)
            mock_generate_task = Mock()
            mock_generate_task.id = "generate-task-id"
            mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
            
            mock_result_task = Mock()
            mock_result_task.id = "generate-task-id"
            mock_result_task.status = "failed"
            mock_result_task.error = "LLM API error"
            mock_result_task.result = None
            mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
            
            # Mock TaskExecutor.execute_task_tree
            mock_executor = Mock()
            async def mock_execute_task_tree(*args, **kwargs):
                import asyncio
                await asyncio.sleep(0.01)
            mock_executor.execute_task_tree = mock_execute_task_tree
            
            with patch('aipartnerupflow.api.routes.tasks.TaskRepository', return_value=mock_repository):
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor', return_value=mock_executor):
                    with pytest.raises(ValueError, match="Task generation failed"):
                        await task_routes.handle_task_generate(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_generate_no_tasks_generated(self, task_routes, mock_request, use_test_db_session):
        """Test error handling when no tasks are generated"""
        import os
        from unittest.mock import patch, AsyncMock, Mock
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {
                "requirement": "Fetch data from API",
                "user_id": "test_user"
            }
            request_id = str(uuid.uuid4())
            
            # Mock TaskRepository constructor
            mock_repository = Mock(spec=TaskRepository)
            mock_generate_task = Mock()
            mock_generate_task.id = "generate-task-id"
            mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
            
            mock_result_task = Mock()
            mock_result_task.id = "generate-task-id"
            mock_result_task.status = "completed"
            mock_result_task.result = {"tasks": []}  # Empty tasks array
            mock_result_task.error = None
            mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
            
            # Mock TaskExecutor.execute_task_tree
            mock_executor = Mock()
            async def mock_execute_task_tree(*args, **kwargs):
                import asyncio
                await asyncio.sleep(0.01)
            mock_executor.execute_task_tree = mock_execute_task_tree
            
            with patch('aipartnerupflow.api.routes.tasks.TaskRepository', return_value=mock_repository):
                with patch('aipartnerupflow.core.execution.task_executor.TaskExecutor', return_value=mock_executor):
                    with pytest.raises(ValueError, match="No tasks were generated"):
                        await task_routes.handle_task_generate(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_generate_with_permission_check(self, task_routes, use_test_db_session):
        """Test task generation respects permission checks"""
        import os
        from unittest.mock import patch, Mock
        
        # Create a mock request with user info
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user_id = "user2"
        mock_request.state.token_payload = None
        
        # Mock permission check to raise ValueError (permission denied)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch.object(task_routes, '_check_permission', side_effect=ValueError("Permission denied")):
                params = {
                    "requirement": "Fetch data from API",
                    "user_id": "user1"  # Different from authenticated user
                }
                request_id = str(uuid.uuid4())
                
                with pytest.raises(ValueError, match="Permission denied"):
                    await task_routes.handle_task_generate(params, mock_request, request_id)

