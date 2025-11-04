"""
Test AgentExecutor functionality
"""
import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, DataPart

from aipartnerupflow.api.agent_executor import AIPartnerUpFlowAgentExecutor


class TestAgentExecutor:
    """Test cases for AIPartnerUpFlowAgentExecutor"""
    
    @pytest.fixture
    def executor(self):
        """Create AIPartnerUpFlowAgentExecutor instance"""
        return AIPartnerUpFlowAgentExecutor()
    
    @pytest.fixture
    def mock_event_queue(self):
        """Create mock event queue"""
        event_queue = AsyncMock(spec=EventQueue)
        event_queue.enqueue_event = AsyncMock()
        return event_queue
    
    def _create_request_context(self, tasks: list, metadata: dict = None) -> RequestContext:
        """Helper to create RequestContext with tasks array"""
        if metadata is None:
            metadata = {}
        
        # Create message with DataPart containing tasks
        message = Mock(spec=Message)
        message.parts = []
        
        # Option 1: Wrapped format (tasks array in first part)
        if len(tasks) == 1:
            data_part = Mock()
            data_part.root = DataPart(data={"tasks": tasks})
            message.parts.append(data_part)
        else:
            # Option 2: Direct format (each part is a task)
            for task in tasks:
                data_part = Mock()
                data_part.root = DataPart(data=task)
                message.parts.append(data_part)
        
        context = Mock(spec=RequestContext)
        context.task_id = str(uuid.uuid4())
        context.context_id = str(uuid.uuid4())
        context.metadata = metadata
        context.message = message
        context.configuration = {}
        
        return context
    
    @pytest.mark.asyncio
    async def test_extract_tasks_wrapped_format(self, executor):
        """Test extracting tasks from wrapped format"""
        tasks = [
            {
                "id": "task-1",
                "user_id": "test-user",
                "name": "Task 1",
                "status": "pending"
            },
            {
                "id": "task-2",
                "user_id": "test-user",
                "name": "Task 2",
                "status": "pending"
            }
        ]
        
        context = self._create_request_context(tasks)
        
        extracted = executor._extract_tasks_from_context(context)
        assert len(extracted) == 2
        assert extracted[0]["id"] == "task-1"
        assert extracted[1]["id"] == "task-2"
    
    @pytest.mark.asyncio
    async def test_extract_tasks_direct_format(self, executor):
        """Test extracting tasks from direct format"""
        tasks = [
            {
                "id": "task-1",
                "user_id": "test-user",
                "name": "Task 1"
            },
            {
                "id": "task-2",
                "user_id": "test-user",
                "name": "Task 2"
            }
        ]
        
        # Create context with direct format (multiple parts)
        message = Mock(spec=Message)
        message.parts = []
        for task in tasks:
            data_part = Mock()
            data_part.root = DataPart(data=task)
            message.parts.append(data_part)
        
        context = Mock(spec=RequestContext)
        context.message = message
        
        extracted = executor._extract_tasks_from_context(context)
        assert len(extracted) == 2
    
    @pytest.mark.asyncio
    async def test_extract_tasks_empty(self, executor):
        """Test extracting tasks with empty context"""
        message = Mock(spec=Message)
        message.parts = []
        
        context = Mock(spec=RequestContext)
        context.message = message
        
        with pytest.raises(ValueError, match="No tasks found"):
            executor._extract_tasks_from_context(context)
    
    @pytest.mark.asyncio
    async def test_build_task_tree_from_tasks(self, executor):
        """Test building task tree from tasks array"""
        tasks = [
            {
                "id": "root-task",
                "parent_id": None,
                "user_id": "test-user",
                "name": "Root Task",
                "dependencies": []
            },
            {
                "id": "child-1",
                "parent_id": "root-task",
                "user_id": "test-user",
                "name": "Child 1",
                "dependencies": []
            },
            {
                "id": "child-2",
                "parent_id": "root-task",
                "user_id": "test-user",
                "name": "Child 2",
                "dependencies": [{"id": "child-1", "required": True}]
            }
        ]
        
        # _build_task_tree_from_tasks doesn't need storage parameter
        task_tree = executor._build_task_tree_from_tasks(tasks)
        
        assert task_tree is not None
        assert task_tree.task.id == "root-task"
        assert len(task_tree.children) == 2
        assert task_tree.children[0].task.id == "child-1"
        assert task_tree.children[1].task.id == "child-2"
    
    @pytest.mark.asyncio
    async def test_should_use_streaming_mode(self, executor):
        """Test streaming mode detection"""
        # Test with stream metadata
        metadata = {"stream": True}
        context = Mock()
        context.metadata = metadata
        
        assert executor._should_use_streaming_mode(context) is True
        
        # Test without stream metadata
        metadata = {}
        context.metadata = metadata
        
        assert executor._should_use_streaming_mode(context) is False
    
    @pytest.mark.asyncio
    async def test_should_use_callback(self, executor):
        """Test callback detection"""
        # Test with push notification config (needs url attribute)
        context = Mock()
        push_config = Mock()
        push_config.url = "https://example.com/callback"
        context.configuration = Mock()
        context.configuration.push_notification_config = push_config
        
        assert executor._should_use_callback(context) is True
        
        # Test with metadata.use_callback (backward compatibility)
        context = Mock()
        context.configuration = None
        context.metadata = {"use_callback": True}
        
        assert executor._should_use_callback(context) is True
        
        # Test without push notification config
        context = Mock()
        context.configuration = None
        context.metadata = {}
        
        assert executor._should_use_callback(context) is False
    
    @pytest.mark.asyncio
    async def test_execute_simple_mode(self, executor, mock_event_queue):
        """Test simple mode execution"""
        tasks = [
            {
                "id": "task-1",
                "user_id": "test-user",
                "name": "Test Task",
                "status": "pending",
                "schemas": {
                    "type": "crew",
                    "method": "web_analyzer"
                }
            }
        ]
        
        context = self._create_request_context(tasks)
        
        # Mock TaskManager and get_default_session
        with patch('aipartnerupflow.api.agent_executor.TaskManager') as mock_manager_class, \
             patch('aipartnerupflow.api.agent_executor.get_default_session') as mock_storage:
            
            mock_storage.return_value = Mock()
            
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.distribute_task_tree = AsyncMock()
            mock_manager.distribute_task_tree.return_value = None
            
            # Mock task tree
            from aipartnerupflow.core.execution.task_manager import TaskTreeNode
            mock_task_node = Mock(spec=TaskTreeNode)
            mock_task_node.task = Mock()
            mock_task_node.task.id = "task-1"
            mock_task_node.task.status = "completed"
            mock_task_node.task.result = {"output": "result"}
            mock_task_node.children = []  # Add children attribute (empty list for leaf node)
            mock_task_node.calculate_status = Mock(return_value="completed")
            mock_task_node.calculate_progress = Mock(return_value=1.0)
            
            with patch.object(executor, '_build_task_tree_from_tasks', return_value=mock_task_node):
                result = await executor._execute_simple_mode(context, mock_event_queue)
                
                # Should have executed
                assert mock_manager.distribute_task_tree.called

