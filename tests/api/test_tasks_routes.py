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

