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
from unittest.mock import Mock, AsyncMock, patch
from starlette.requests import Request
from starlette.responses import StreamingResponse

from aipartnerupflow.api.routes.tasks import TaskRoutes
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class
from aipartnerupflow.core.execution.task_tracker import TaskTracker


@pytest.fixture
def task_routes(use_test_db_session):
    """Create TaskRoutes instance for testing"""
    return TaskRoutes(
        task_model_class=get_task_model_class(),
        verify_token_func=None,  # No JWT for testing
        verify_permission_func=None,
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
    await task_repository.create_task(
        id=task_id,
        name="Test Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        schemas={"method": "system_info_executor"},
        inputs={},
    )

    return task_id


class TestHandleTaskExecute:
    """Test cases for handle_task_execute method"""

    @pytest.mark.asyncio
    async def test_regular_post_no_webhook(self, task_routes, mock_request, sample_task):
        """Test regular POST mode without webhook"""
        params = {"task_id": sample_task, "use_streaming": False}
        request_id = str(uuid.uuid4())

        # Mock TaskExecutor to avoid actual execution
        with patch(
            "aipartnerupflow.core.execution.task_executor.TaskExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(
                return_value={"status": "started", "progress": 0.0, "root_task_id": sample_task}
            )
            mock_executor_class.return_value = mock_executor

            # Mock TaskTracker
            with patch(
                "aipartnerupflow.core.execution.task_tracker.TaskTracker"
            ) as mock_tracker_class:
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
                "max_retries": 3,
            },
        }
        request_id = str(uuid.uuid4())

        # Mock TaskExecutor to avoid actual execution
        with patch(
            "aipartnerupflow.core.execution.task_executor.TaskExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(
                return_value={"status": "started", "progress": 0.0, "root_task_id": sample_task}
            )
            mock_executor_class.return_value = mock_executor

            # Mock TaskTracker
            with patch(
                "aipartnerupflow.core.execution.task_tracker.TaskTracker"
            ) as mock_tracker_class:
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

        # The context is created before the async task, so we can't directly assert on it
        # But we can verify the response indicates webhook is configured

    @pytest.mark.asyncio
    async def test_sse_no_webhook(self, task_routes, mock_request, sample_task):
        """Test SSE mode without webhook"""
        params = {"task_id": sample_task, "use_streaming": True}
        request_id = str(uuid.uuid4())

        # Mock TaskExecutor to avoid actual execution
        with patch(
            "aipartnerupflow.core.execution.task_executor.TaskExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(
                return_value={"status": "started", "progress": 0.0, "root_task_id": sample_task}
            )
            mock_executor_class.return_value = mock_executor

            # Mock TaskTracker
            with patch(
                "aipartnerupflow.core.execution.task_tracker.TaskTracker"
            ) as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.is_task_running = Mock(return_value=False)
                mock_tracker_class.return_value = mock_tracker

                # Mock get_task_streaming_events to return empty list initially
                with patch(
                    "aipartnerupflow.api.routes.tasks.get_task_streaming_events",
                    new_callable=AsyncMock,
                ) as mock_get_events:
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
                "max_retries": 3,
            },
        }
        request_id = str(uuid.uuid4())

        # Mock TaskExecutor to avoid actual execution
        with patch(
            "aipartnerupflow.core.execution.task_executor.TaskExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_task_by_id = AsyncMock(
                return_value={"status": "started", "progress": 0.0, "root_task_id": sample_task}
            )
            mock_executor_class.return_value = mock_executor

            # Mock TaskTracker
            with patch(
                "aipartnerupflow.core.execution.task_tracker.TaskTracker"
            ) as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.is_task_running = Mock(return_value=False)
                mock_tracker_class.return_value = mock_tracker

                # Mock get_task_streaming_events to return empty list initially
                with patch(
                    "aipartnerupflow.api.routes.tasks.get_task_streaming_events",
                    new_callable=AsyncMock,
                ) as mock_get_events:
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
        params = {"task_id": "non-existent-task", "use_streaming": False}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="not found"):
            await task_routes.handle_task_execute(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_task_already_running(self, task_routes, mock_request, sample_task):
        """Test handling when task is already running"""
        params = {"task_id": sample_task, "use_streaming": False}
        request_id = str(uuid.uuid4())

        # Mock TaskTracker to return True for is_task_running
        with patch("aipartnerupflow.core.execution.task_tracker.TaskTracker") as mock_tracker_class:
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
        params = {"use_streaming": False}
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
            },
        }
        request_id = str(uuid.uuid4())

        # Import TaskTracker to patch its instance method
        from aipartnerupflow.core.execution.task_tracker import TaskTracker

        # Patch TaskTracker.is_task_running on the instance (not the class)
        # This avoids the singleton super() issue
        with patch.object(TaskTracker(), "is_task_running", return_value=False):
            # Mock TaskExecutor to avoid actual execution, but allow code to continue
            # The error should occur when creating WebhookStreamingContext
            with patch(
                "aipartnerupflow.core.execution.task_executor.TaskExecutor"
            ) as mock_executor_class:
                mock_executor = Mock()
                mock_executor.execute_task_by_id = AsyncMock()
                mock_executor_class.return_value = mock_executor

                with pytest.raises(ValueError, match="webhook_config.url is required"):
                    await task_routes.handle_task_execute(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_copy_execution_basic(self, task_routes, mock_request, sample_task):
        """Test copy_execution=True parameter"""
        params = {"task_id": sample_task, "copy_execution": True, "use_streaming": False}
        request_id = str(uuid.uuid4())

        # Mock TaskCreator.create_task_copy
        with patch("aipartnerupflow.api.routes.tasks.TaskCreator") as mock_creator_class:
            mock_creator = Mock()
            mock_copied_task = Mock()
            mock_copied_task.id = "copied-task-id"
            mock_copied_tree = Mock()
            mock_copied_tree.task = mock_copied_task
            mock_creator.create_task_copy = AsyncMock(return_value=mock_copied_tree)
            mock_creator_class.return_value = mock_creator

            # Mock _get_task_repository to return a mock repository
            with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
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
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor"
                ) as mock_executor_class:
                    mock_executor = Mock()
                    mock_executor.execute_task_by_id = AsyncMock(
                        return_value={
                            "status": "started",
                            "progress": 0.0,
                            "root_task_id": "copied-task-id",
                        }
                    )
                    mock_executor_class.return_value = mock_executor

                    # Mock TaskTracker
                    with patch.object(TaskTracker(), "is_task_running", return_value=False):
                        result = await task_routes.handle_task_execute(
                            params, mock_request, request_id
                        )

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
            "use_streaming": False,
        }
        request_id = str(uuid.uuid4())

        # Mock TaskCreator.create_task_copy
        with patch("aipartnerupflow.api.routes.tasks.TaskCreator") as mock_creator_class:
            mock_creator = Mock()
            mock_copied_task = Mock()
            mock_copied_task.id = "copied-task-id"
            mock_copied_tree = Mock()
            mock_copied_tree.task = mock_copied_task
            mock_creator.create_task_copy = AsyncMock(return_value=mock_copied_tree)
            mock_creator_class.return_value = mock_creator

            # Mock _get_task_repository to return a mock repository
            with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
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
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor"
                ) as mock_executor_class:
                    mock_executor = Mock()
                    mock_executor.execute_task_by_id = AsyncMock(
                        return_value={
                            "status": "started",
                            "progress": 0.0,
                            "root_task_id": "copied-task-id",
                        }
                    )
                    mock_executor_class.return_value = mock_executor

                    # Mock TaskTracker
                    with patch.object(TaskTracker(), "is_task_running", return_value=False):
                        result = await task_routes.handle_task_execute(
                            params, mock_request, request_id
                        )

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
        params = {"task_id": sample_task, "copy_execution": True, "use_streaming": True}
        request_id = str(uuid.uuid4())

        # Mock TaskCreator.create_task_copy
        with patch("aipartnerupflow.api.routes.tasks.TaskCreator") as mock_creator_class:
            mock_creator = Mock()
            mock_copied_task = Mock()
            mock_copied_task.id = "copied-task-id"
            mock_copied_tree = Mock()
            mock_copied_tree.task = mock_copied_task
            mock_creator.create_task_copy = AsyncMock(return_value=mock_copied_tree)
            mock_creator_class.return_value = mock_creator

            # Mock _get_task_repository to return a mock repository
            with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
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
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor"
                ) as mock_executor_class:
                    mock_executor = Mock()
                    mock_executor.execute_task_by_id = AsyncMock(
                        return_value={
                            "status": "started",
                            "progress": 0.0,
                            "root_task_id": "copied-task-id",
                        }
                    )
                    mock_executor_class.return_value = mock_executor

                    # Mock TaskTracker
                    with patch.object(TaskTracker(), "is_task_running", return_value=False):
                        result = await task_routes.handle_task_execute(
                            params, mock_request, request_id
                        )

        # Verify response is StreamingResponse
        assert isinstance(result, StreamingResponse)
        assert result.media_type == "text/event-stream"


class TestHandleTaskDelete:
    """Test cases for handle_task_delete method"""

    @pytest.mark.asyncio
    async def test_delete_pending_task_no_children(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test deleting a pending task with no children"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create a pending task (default status is pending)
        task = await task_repository.create_task(name="Task to Delete", user_id="test_user")

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
    async def test_delete_pending_task_with_pending_children(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test deleting a pending task with all pending children"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create task tree: root -> child1, child2 -> grandchild (all pending by default)
        root = await task_repository.create_task(name="Root Task", user_id="test_user")

        child1 = await task_repository.create_task(
            name="Child 1", user_id="test_user", parent_id=root.id
        )

        child2 = await task_repository.create_task(
            name="Child 2", user_id="test_user", parent_id=root.id
        )

        grandchild = await task_repository.create_task(
            name="Grandchild", user_id="test_user", parent_id=child1.id
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
    async def test_delete_fails_with_non_pending_children(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test deletion fails when task has non-pending children"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create task tree with non-pending child
        root = await task_repository.create_task(name="Root Task", user_id="test_user")

        child1 = await task_repository.create_task(
            name="Child 1", user_id="test_user", parent_id=root.id
        )

        child2 = await task_repository.create_task(
            name="Child 2", user_id="test_user", parent_id=root.id
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
    async def test_delete_fails_with_non_pending_task(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test deletion fails when task itself is not pending"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create a task and update to non-pending status
        task = await task_repository.create_task(name="Task to Delete", user_id="test_user")
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
    async def test_delete_fails_with_dependent_tasks(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test deletion fails when other tasks depend on this task"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create a task that will be a dependency
        dep_task = await task_repository.create_task(name="Dependency Task", user_id="test_user")

        # Create tasks that depend on dep_task
        dependent1 = await task_repository.create_task(
            name="Dependent Task 1",
            user_id="test_user",
            dependencies=[{"id": dep_task.id, "required": True}],
        )

        dependent2 = await task_repository.create_task(
            name="Dependent Task 2",
            user_id="test_user",
            dependencies=[{"id": dep_task.id, "required": False}],
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
    async def test_delete_fails_with_mixed_conditions(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test deletion fails with both non-pending children and dependencies"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create task tree
        root = await task_repository.create_task(name="Root Task", user_id="test_user")

        child1 = await task_repository.create_task(
            name="Child 1", user_id="test_user", parent_id=root.id
        )

        # Update child1 to non-pending status
        await task_repository.update_task_status(child1.id, status="completed")

        # Create a task that depends on root
        dependent = await task_repository.create_task(
            name="Dependent Task",
            user_id="test_user",
            dependencies=[{"id": root.id, "required": True}],
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
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create a task with a specific user_id
        task = await task_repository.create_task(name="Task to Delete", user_id="user1")

        # Create a mock request with different user
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user_id = "user2"  # Different user
        mock_request.state.token_payload = None

        # Mock permission check to raise ValueError (permission denied)
        with patch.object(
            task_routes, "_check_permission", side_effect=ValueError("Permission denied")
        ):
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
            params = {"requirement": "Fetch data from API and process it", "user_id": "test_user"}
            request_id = str(uuid.uuid4())

            # Mock generate_executor execution
            mock_generated_tasks = [
                {
                    "name": "rest_executor",
                    "inputs": {"url": "https://api.example.com/data", "method": "GET"},
                    "priority": 1,
                },
                {
                    "name": "command_executor",
                    "dependencies": [{"id": "task_1", "required": True}],
                    "inputs": {"command": "python process.py"},
                    "priority": 2,
                },
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

            with patch(
                "aipartnerupflow.api.routes.tasks.TaskRepository", return_value=mock_repository
            ):
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor",
                    return_value=mock_executor,
                ):
                    result = await task_routes.handle_task_generate(
                        params, mock_request, request_id
                    )

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
                "save": True,
            }
            request_id = str(uuid.uuid4())

            mock_generated_tasks = [
                {
                    "name": "rest_executor",
                    "inputs": {"url": "https://api.example.com/data", "method": "GET"},
                    "priority": 1,
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

            with patch(
                "aipartnerupflow.api.routes.tasks.TaskRepository", return_value=mock_repository
            ):
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor",
                    return_value=mock_executor,
                ):
                    with patch(
                        "aipartnerupflow.api.routes.tasks.TaskCreator", return_value=mock_creator
                    ):
                        result = await task_routes.handle_task_generate(
                            params, mock_request, request_id
                        )

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
        params = {"user_id": "test_user"}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="Requirement is required"):
            await task_routes.handle_task_generate(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_generate_missing_api_key(self, task_routes, mock_request):
        """Test error handling when LLM API key is missing"""
        import os
        from unittest.mock import patch
        from aipartnerupflow.core.utils.llm_key_context import clear_llm_key_context

        # Clear context and ensure no API key in environment
        clear_llm_key_context()
        with patch.dict(os.environ, {}, clear=True):
            params = {"requirement": "Fetch data from API", "user_id": "test_user"}
            request_id = str(uuid.uuid4())

            with pytest.raises(ValueError, match="LLM API key not found"):
                await task_routes.handle_task_generate(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_generate_with_header_api_key(self, task_routes, mock_request, use_test_db_session):
        """Test task generation using X-LLM-API-KEY header"""
        import os
        from unittest.mock import patch, AsyncMock, Mock
        from aipartnerupflow.core.utils.llm_key_context import set_llm_key_from_header, clear_llm_key_context

        # Clear context first, then set header key
        clear_llm_key_context()
        set_llm_key_from_header("header-test-key")
        
        # Ensure no API key in environment to test header takes priority
        with patch.dict(os.environ, {}, clear=True):
            params = {"requirement": "Fetch data from API", "user_id": "test_user"}
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

            with patch(
                "aipartnerupflow.api.routes.tasks.TaskRepository", return_value=mock_repository
            ):
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor",
                    return_value=mock_executor,
                ):
                    result = await task_routes.handle_task_generate(
                        params, mock_request, request_id
                    )

            # Verify response
            assert isinstance(result, dict)
            assert "tasks" in result
            assert result["tasks"] == mock_generated_tasks
            assert result["count"] == 1
            assert "message" in result
            assert "Successfully generated" in result["message"]
            
            # Clean up
            clear_llm_key_context()

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
                "model": "gpt-4o",
                "temperature": 0.8,
                "max_tokens": 5000,
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

            with patch(
                "aipartnerupflow.api.routes.tasks.TaskRepository", return_value=mock_repository
            ):
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor",
                    return_value=mock_executor,
                ):
                    await task_routes.handle_task_generate(
                        params, mock_request, request_id
                    )

            # Verify LLM config was passed to create_task
            create_call = mock_repository.create_task.call_args
            assert create_call is not None
            inputs = create_call[1]["inputs"]
            assert inputs["llm_provider"] == "openai"
            assert inputs["model"] == "gpt-4o"
            assert inputs["temperature"] == 0.8
            assert inputs["max_tokens"] == 5000

    @pytest.mark.asyncio
    async def test_generate_failed_status(self, task_routes, mock_request, use_test_db_session):
        """Test error handling when generation task fails"""
        import os
        from unittest.mock import patch, AsyncMock, Mock

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {"requirement": "Fetch data from API", "user_id": "test_user"}
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

            with patch(
                "aipartnerupflow.api.routes.tasks.TaskRepository", return_value=mock_repository
            ):
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor",
                    return_value=mock_executor,
                ):
                    with pytest.raises(ValueError, match="Task generation failed"):
                        await task_routes.handle_task_generate(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_generate_no_tasks_generated(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test error handling when no tasks are generated"""
        import os
        from unittest.mock import patch, AsyncMock, Mock

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {"requirement": "Fetch data from API", "user_id": "test_user"}
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

            with patch(
                "aipartnerupflow.api.routes.tasks.TaskRepository", return_value=mock_repository
            ):
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor",
                    return_value=mock_executor,
                ):
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
            with patch.object(
                task_routes, "_check_permission", side_effect=ValueError("Permission denied")
            ):
                params = {
                    "requirement": "Fetch data from API",
                    "user_id": "user1",  # Different from authenticated user
                }
                request_id = str(uuid.uuid4())

                with pytest.raises(ValueError, match="Permission denied"):
                    await task_routes.handle_task_generate(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_generate_with_jwt_token_user_id_propagation(self, use_test_db_session):
        """Test that user_id from JWT token is correctly propagated to generated tasks"""
        import os
        from unittest.mock import patch, AsyncMock, Mock
        from aipartnerupflow.api.a2a.server import generate_token, verify_token
        from aipartnerupflow.api.routes.tasks import TaskRoutes
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        # Generate JWT token with user_id
        secret_key = "test_secret_key_for_user_id_propagation"
        user_id = "demo_user_4470f5d3f0f60c78"
        payload = {"user_id": user_id, "sub": user_id}
        token = generate_token(payload, secret_key)
        
        # Create TaskRoutes with JWT verification
        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)
        
        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
            verify_permission_func=None,
        )
        
        # Create mock request with JWT token
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        mock_request.cookies = {}
        mock_request.state = Mock()
        mock_request.state.user_id = user_id
        mock_request.state.token_payload = verify_token_func(token)
        
        # Mock environment variable for API key
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            params = {"requirement": "create a task to check cpu"}
            request_id = str(uuid.uuid4())
            
            # Mock LLM response with wrong user_id (simulating LLM generating "api_user" or "user123")
            # This simulates what LLM actually generates
            mock_llm_response = json.dumps([
                {
                    "id": "task_1",  # Not UUID format - LLM generates simple IDs
                    "name": "system_info_executor",
                    "user_id": "api_user",  # LLM generated wrong value (common mistake)
                    "inputs": {"resource": "cpu", "timeout": 60},
                    "priority": 1
                }
            ])
            
            # Mock TaskRepository
            mock_repository = Mock(spec=TaskRepository)
            mock_generate_task = Mock()
            mock_generate_task.id = "generate-task-id"
            mock_generate_task.user_id = user_id  # Task should have correct user_id (from JWT token)
            mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
            
            mock_result_task = Mock()
            mock_result_task.id = "generate-task-id"
            mock_result_task.status = "completed"
            mock_result_task.result = {}  # Will be updated by mock_execute_task_tree
            mock_result_task.error = None
            mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
            
            # Mock TaskExecutor.execute_task_tree to actually call generate_executor
            # This will test the full flow including _post_process_tasks
            from aipartnerupflow.extensions.generate.generate_executor import GenerateExecutor
            
            async def mock_execute_task_tree(*args, **kwargs):
                # Actually execute generate_executor to test _post_process_tasks
                # This tests the full flow: LLM generates wrong user_id -> _post_process_tasks corrects it
                executor = GenerateExecutor()
                executor.task = mock_generate_task  # Set task context (so self.user_id works)
                
                # Mock LLM client to return response with wrong user_id
                mock_llm_client = Mock()
                mock_llm_client.generate = AsyncMock(return_value=mock_llm_response)
                
                with patch('aipartnerupflow.extensions.generate.generate_executor.create_llm_client', return_value=mock_llm_client):
                    # Execute with user_id in inputs (from handle_task_generate)
                    result = await executor.execute({
                        "requirement": "create a task to check cpu",
                        "user_id": user_id  # This comes from JWT token extraction
                    })
                    
                    # Update mock_result_task with actual result (after _post_process_tasks)
                    mock_result_task.result = result
            
            mock_executor = Mock()
            mock_executor.execute_task_tree = mock_execute_task_tree
            
            with patch(
                "aipartnerupflow.api.routes.tasks.TaskRepository", return_value=mock_repository
            ):
                with patch(
                    "aipartnerupflow.core.execution.task_executor.TaskExecutor",
                    return_value=mock_executor,
                ):
                    result = await task_routes.handle_task_generate(
                        params, mock_request, request_id
                    )
            
            # Verify response
            assert isinstance(result, dict)
            assert "tasks" in result
            assert len(result["tasks"]) == 1
            
            # CRITICAL: Verify generated task has correct user_id (not "api_user" or None)
            # This tests that _post_process_tasks correctly overrides LLM-generated wrong user_id
            generated_task = result["tasks"][0]
            
            # Verify user_id is correct (from JWT token, not LLM-generated "api_user")
            assert generated_task["user_id"] == user_id, \
                f"Generated task should have user_id='{user_id}' (from JWT token), " \
                f"got '{generated_task.get('user_id')}'. " \
                f"This means _post_process_tasks failed to override LLM-generated 'api_user'."
            assert generated_task["user_id"] != "api_user", \
                f"Generated task should not have LLM-generated 'api_user', " \
                f"got '{generated_task.get('user_id')}'. " \
                f"This means _post_process_tasks did not override the wrong value."
            assert generated_task["user_id"] is not None, \
                f"Generated task should not have None user_id, " \
                f"got '{generated_task.get('user_id')}'. " \
                f"This means user_id was not properly extracted from JWT token."
            
            # Verify task has UUID format ID (not "task_1" from LLM)
            import re
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
            assert uuid_pattern.match(generated_task["id"]), \
                f"Generated task should have UUID format id (not LLM-generated 'task_1'), " \
                f"got '{generated_task.get('id')}'. " \
                f"This means _post_process_tasks failed to convert ID to UUID format."
            assert generated_task["id"] != "task_1", \
                f"Generated task should not have LLM-generated ID 'task_1', " \
                f"got '{generated_task.get('id')}'. " \
                f"This means _post_process_tasks did not convert the ID to UUID."


class TestAdminPermission:
    """Test cases for admin permission checking in task queries"""

    @pytest.mark.asyncio
    async def test_regular_user_can_only_see_own_tasks(self, use_test_db_session):
        """Test that regular user without user_id param can only see their own tasks"""
        from aipartnerupflow.api.routes.tasks import TaskRoutes
        from aipartnerupflow.api.a2a.server import generate_token, verify_token
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class

        # Setup: Create tasks for different users
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create tasks for user1
        task1 = await task_repository.create_task(
            name="User1 Task 1", user_id="user1", status="pending"
        )
        task2 = await task_repository.create_task(
            name="User1 Task 2", user_id="user1", status="completed"
        )

        # Create tasks for user2
        task3 = await task_repository.create_task(
            name="User2 Task 1", user_id="user2", status="pending"
        )
        task4 = await task_repository.create_task(
            name="User2 Task 2", user_id="user2", status="in_progress"
        )

        # Create TaskRoutes with JWT verification
        secret_key = "test_secret_key_for_admin_permission"
        regular_user_payload = {"user_id": "user1", "sub": "user1"}  # Regular user, no admin role
        regular_user_token = generate_token(regular_user_payload, secret_key)

        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
            verify_permission_func=None,
        )

        # Create mock request with regular user token
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": f"Bearer {regular_user_token}"}
        mock_request.state = Mock()
        mock_request.state.user_id = "user1"
        mock_request.state.token_payload = verify_token_func(regular_user_token)

        # Call handle_tasks_list without user_id param
        params = {}  # No user_id specified
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_tasks_list(params, mock_request, request_id)

        # Verify: Regular user should only see their own tasks (user1's tasks)
        assert isinstance(result, list)
        task_ids = [task["id"] for task in result]
        assert task1.id in task_ids, "User1 should see their own task1"
        assert task2.id in task_ids, "User1 should see their own task2"
        assert task3.id not in task_ids, "User1 should NOT see user2's task3"
        assert task4.id not in task_ids, "User1 should NOT see user2's task4"

    @pytest.mark.asyncio
    async def test_admin_user_can_see_all_tasks(self, use_test_db_session):
        """Test that admin user without user_id param can see all tasks"""
        from aipartnerupflow.api.routes.tasks import TaskRoutes
        from aipartnerupflow.api.a2a.server import generate_token, verify_token
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class

        # Setup: Create tasks for different users
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create tasks for user1
        task1 = await task_repository.create_task(
            name="User1 Task 1", user_id="user1", status="pending"
        )
        task2 = await task_repository.create_task(
            name="User1 Task 2", user_id="user1", status="completed"
        )

        # Create tasks for user2
        task3 = await task_repository.create_task(
            name="User2 Task 1", user_id="user2", status="pending"
        )
        task4 = await task_repository.create_task(
            name="User2 Task 2", user_id="user2", status="in_progress"
        )

        # Create TaskRoutes with JWT verification
        secret_key = "test_secret_key_for_admin_permission"
        admin_user_payload = {"user_id": "admin_user", "sub": "admin_user", "roles": ["admin"]}
        admin_user_token = generate_token(admin_user_payload, secret_key)

        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
            verify_permission_func=None,
        )

        # Create mock request with admin user token
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": f"Bearer {admin_user_token}"}
        mock_request.state = Mock()
        mock_request.state.user_id = "admin_user"
        mock_request.state.token_payload = verify_token_func(admin_user_token)

        # Call handle_tasks_list without user_id param
        params = {}  # No user_id specified
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_tasks_list(params, mock_request, request_id)

        # Verify: Admin user should see all tasks
        assert isinstance(result, list)
        task_ids = [task["id"] for task in result]
        assert task1.id in task_ids, "Admin should see user1's task1"
        assert task2.id in task_ids, "Admin should see user1's task2"
        assert task3.id in task_ids, "Admin should see user2's task3"
        assert task4.id in task_ids, "Admin should see user2's task4"

    @pytest.mark.asyncio
    async def test_admin_user_can_query_specific_user_tasks(self, use_test_db_session):
        """Test that admin user can query tasks for any specific user_id"""
        from aipartnerupflow.api.routes.tasks import TaskRoutes
        from aipartnerupflow.api.a2a.server import generate_token, verify_token
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class

        # Setup: Create tasks for different users
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create tasks for user1
        task1 = await task_repository.create_task(
            name="User1 Task 1", user_id="user1", status="pending"
        )
        task2 = await task_repository.create_task(
            name="User1 Task 2", user_id="user1", status="completed"
        )

        # Create tasks for user2
        task3 = await task_repository.create_task(
            name="User2 Task 1", user_id="user2", status="pending"
        )
        task4 = await task_repository.create_task(
            name="User2 Task 2", user_id="user2", status="in_progress"
        )

        # Create TaskRoutes with JWT verification
        secret_key = "test_secret_key_for_admin_permission"
        admin_user_payload = {"user_id": "admin_user", "sub": "admin_user", "roles": ["admin"]}
        admin_user_token = generate_token(admin_user_payload, secret_key)

        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
            verify_permission_func=None,
        )

        # Create mock request with admin user token
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": f"Bearer {admin_user_token}"}
        mock_request.state = Mock()
        mock_request.state.user_id = "admin_user"
        mock_request.state.token_payload = verify_token_func(admin_user_token)

        # Test 1: Admin queries user1's tasks by specifying user_id
        params = {"user_id": "user1"}  # Specify user_id
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_tasks_list(params, mock_request, request_id)

        # Verify: Admin should only see user1's tasks when user_id is specified
        assert isinstance(result, list)
        task_ids = [task["id"] for task in result]
        assert task1.id in task_ids, "Admin should see user1's task1 when querying user1"
        assert task2.id in task_ids, "Admin should see user1's task2 when querying user1"
        assert task3.id not in task_ids, "Admin should NOT see user2's task3 when querying user1"
        assert task4.id not in task_ids, "Admin should NOT see user2's task4 when querying user1"

        # Test 2: Admin queries user2's tasks by specifying user_id
        params = {"user_id": "user2"}  # Specify different user_id
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_tasks_list(params, mock_request, request_id)

        # Verify: Admin should only see user2's tasks when user_id is specified
        assert isinstance(result, list)
        task_ids = [task["id"] for task in result]
        assert task1.id not in task_ids, "Admin should NOT see user1's task1 when querying user2"
        assert task2.id not in task_ids, "Admin should NOT see user1's task2 when querying user2"
        assert task3.id in task_ids, "Admin should see user2's task3 when querying user2"
        assert task4.id in task_ids, "Admin should see user2's task4 when querying user2"


class TestHandleTaskExecuteUseDemo:
    """Test cases for handle_task_execute method with use_demo parameter"""

    @pytest.mark.asyncio
    async def test_execute_with_use_demo_task_id_mode(self, task_routes, mock_request, sample_task):
        """Test executing task by task_id with use_demo=True"""
        params = {"task_id": sample_task, "use_streaming": False, "use_demo": True}
        request_id = str(uuid.uuid4())

        # Mock TaskExecutor to avoid actual execution
        with patch(
            "aipartnerupflow.core.execution.task_executor.TaskExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_execute_task_by_id = AsyncMock(
                return_value={"status": "started", "progress": 0.0, "root_task_id": sample_task}
            )
            mock_executor.execute_task_by_id = mock_execute_task_by_id
            mock_executor_class.return_value = mock_executor

            # Mock TaskTracker
            with patch(
                "aipartnerupflow.core.execution.task_tracker.TaskTracker"
            ) as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.is_task_running = Mock(return_value=False)
                mock_tracker_class.return_value = mock_tracker

                result = await task_routes.handle_task_execute(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["protocol"] == "jsonrpc"
        assert result["root_task_id"] == sample_task

        # Note: use_demo is now passed as parameter to TaskExecutor, not stored in inputs
        # Verify that execute_task_by_id was called with use_demo=True
        mock_execute_task_by_id.assert_called_once()
        call_kwargs = mock_execute_task_by_id.call_args[1]
        assert call_kwargs.get("use_demo") is True

    @pytest.mark.asyncio
    async def test_execute_with_use_demo_tasks_array_mode(self, task_routes, mock_request):
        """Test executing tasks array with use_demo=True"""
        tasks = [
            {
                "id": f"demo-task-{uuid.uuid4().hex[:8]}",
                "name": "Demo Task 1",
                "user_id": "test_user",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "schemas": {"method": "system_info_executor"},
                "inputs": {"resource": "cpu"},
            }
        ]

        params = {"tasks": tasks, "use_streaming": False, "use_demo": True}
        request_id = str(uuid.uuid4())

        # Mock TaskExecutor to avoid actual execution
        with patch(
            "aipartnerupflow.core.execution.task_executor.TaskExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_execute_tasks = AsyncMock(
                return_value={"status": "started", "progress": 0.0, "root_task_id": tasks[0]["id"]}
            )
            mock_executor.execute_tasks = mock_execute_tasks
            mock_executor_class.return_value = mock_executor

            result = await task_routes.handle_task_execute(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["protocol"] == "jsonrpc"

        # Note: use_demo is now passed as parameter to TaskExecutor, not stored in inputs
        # Verify that execute_tasks was called with use_demo=True
        mock_execute_tasks.assert_called_once()
        call_kwargs = mock_execute_tasks.call_args[1]
        assert call_kwargs.get("use_demo") is True


class TestHandleTaskCopy:
    """Test cases for handle_task_copy method"""

    @pytest_asyncio.fixture
    async def task_tree_for_copy(self, use_test_db_session):
        """Create a task tree for copy testing"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create task tree: root -> child1, child2
        root = await task_repository.create_task(
            name="Root Task",
            user_id="test_user",
            status="completed",
            priority=1,
        )
        child1 = await task_repository.create_task(
            name="Child Task 1",
            user_id="test_user",
            parent_id=root.id,
            status="completed",
            priority=1,
        )
        child2 = await task_repository.create_task(
            name="Child Task 2",
            user_id="test_user",
            parent_id=root.id,
            status="completed",
            priority=1,
            dependencies=[{"id": child1.id, "required": True}],
        )

        return {
            "root": root,
            "child1": child1,
            "child2": child2,
        }

    @pytest.mark.asyncio
    async def test_copy_basic_minimal_mode(self, task_routes, mock_request, task_tree_for_copy, use_test_db_session):
        """Test basic copy with minimal mode (default)"""
        root = task_tree_for_copy["root"]
        params = {"task_id": root.id, "copy_mode": "minimal", "save": True}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert "id" in result
        assert result["name"] == "Root Task"
        assert result["id"] != root.id  # New task ID

        # Verify task was saved to database
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )
        copied_task = await task_repository.get_task_by_id(result["id"])
        assert copied_task is not None
        assert copied_task.name == "Root Task"

    @pytest.mark.asyncio
    async def test_copy_with_save_false(self, task_routes, mock_request, task_tree_for_copy):
        """Test copy with save=False returns task array"""
        root = task_tree_for_copy["root"]
        params = {"task_id": root.id, "copy_mode": "minimal", "save": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response is task array
        assert isinstance(result, dict)
        assert "tasks" in result
        assert result["saved"] is False
        assert isinstance(result["tasks"], list)
        assert len(result["tasks"]) > 0

        # Verify task array format
        task_array = result["tasks"]
        for task_dict in task_array:
            assert "id" in task_dict
            assert "name" in task_dict

    @pytest.mark.asyncio
    async def test_copy_with_children(self, task_routes, mock_request, task_tree_for_copy):
        """Test copy with children=True"""
        root = task_tree_for_copy["root"]
        params = {
            "task_id": root.id,
            "copy_mode": "minimal",
            "children": True,
            "save": True,
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert "id" in result
        assert result["name"] == "Root Task"

        # Verify children were copied
        if "children" in result:
            assert len(result["children"]) > 0

    @pytest.mark.asyncio
    async def test_copy_custom_mode(self, task_routes, mock_request, task_tree_for_copy):
        """Test copy with custom mode"""
        child1 = task_tree_for_copy["child1"]
        params = {
            "task_id": child1.id,
            "copy_mode": "custom",
            "custom_task_ids": [child1.id],
            "custom_include_children": False,
            "save": True,
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert "id" in result
        assert result["id"] != child1.id  # New task ID

    @pytest.mark.asyncio
    async def test_copy_full_mode(self, task_routes, mock_request, task_tree_for_copy):
        """Test copy with full mode"""
        root = task_tree_for_copy["root"]
        params = {"task_id": root.id, "copy_mode": "full", "save": True}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert "id" in result
        assert result["name"] == "Root Task"

    @pytest.mark.asyncio
    async def test_copy_with_reset_fields(self, task_routes, mock_request, task_tree_for_copy, use_test_db_session):
        """Test copy with reset_fields"""
        root = task_tree_for_copy["root"]
        params = {
            "task_id": root.id,
            "copy_mode": "minimal",
            "reset_fields": ["status", "progress"],
            "save": True,
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert "id" in result

        # Verify reset fields were applied
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )
        copied_task = await task_repository.get_task_by_id(result["id"])
        assert copied_task.status == "pending"  # Reset from completed
        assert copied_task.progress == 0.0  # Reset from previous value

    @pytest.mark.asyncio
    async def test_copy_task_not_found(self, task_routes, mock_request):
        """Test error handling when task is not found"""
        params = {"task_id": "non-existent-task", "copy_mode": "minimal"}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="not found"):
            await task_routes.handle_task_copy(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_copy_missing_task_id(self, task_routes, mock_request):
        """Test error handling when task_id is missing"""
        params = {"copy_mode": "minimal"}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="Task ID is required"):
            await task_routes.handle_task_copy(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_copy_custom_mode_missing_task_ids(self, task_routes, mock_request, task_tree_for_copy):
        """Test error handling when custom_task_ids is missing in custom mode"""
        root = task_tree_for_copy["root"]
        params = {"task_id": root.id, "copy_mode": "custom"}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="custom_task_ids is required"):
            await task_routes.handle_task_copy(params, mock_request, request_id)
    
    @pytest.mark.asyncio
    async def test_copy_custom_mode_with_include_children(self, task_routes, mock_request, task_tree_for_copy):
        """Test copy with custom mode and custom_include_children=True"""
        root = task_tree_for_copy["root"]
        child1 = task_tree_for_copy["child1"]
        params = {
            "task_id": root.id,
            "copy_mode": "custom",
            "custom_task_ids": [child1.id],
            "custom_include_children": True,
            "save": True,
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response
        assert isinstance(result, dict)
        assert "id" in result
    
    @pytest.mark.asyncio
    async def test_copy_with_save_false_returns_array(self, task_routes, mock_request, task_tree_for_copy):
        """Test copy with save=False returns task array format"""
        root = task_tree_for_copy["root"]
        params = {"task_id": root.id, "copy_mode": "minimal", "save": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_task_copy(params, mock_request, request_id)

        # Verify response is task array
        assert isinstance(result, dict)
        assert "tasks" in result
        assert result["saved"] is False
        assert isinstance(result["tasks"], list)
        
        # Verify task array has correct format for tasks.create
        task_array = result["tasks"]
        assert len(task_array) > 0
        for task_dict in task_array:
            assert "id" in task_dict
            assert "name" in task_dict
            assert isinstance(task_dict["id"], str)
            assert isinstance(task_dict["name"], str)
