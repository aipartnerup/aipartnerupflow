"""
Test TaskRoutesAdapter

Tests for MCP adapter that bridges TaskRoutes with MCP protocol.
"""

import pytest
from unittest.mock import AsyncMock, patch
from aipartnerupflow.api.mcp.adapter import TaskRoutesAdapter


class TestTaskRoutesAdapter:
    """Test TaskRoutesAdapter functionality"""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter instance"""
        return TaskRoutesAdapter()
    
    @pytest.mark.asyncio
    async def test_execute_task_with_task_id(self, adapter):
        """Test executing task by task_id"""
        mock_result = {
            "success": True,
            "root_task_id": "test-root-id",
            "task_id": "test-task-id",
            "status": "started"
        }
        
        with patch.object(adapter.task_routes, 'handle_task_execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_result
            
            result = await adapter.execute_task({
                "task_id": "test-task-id",
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            assert call_args[0][0]["task_id"] == "test-task-id"
    
    @pytest.mark.asyncio
    async def test_execute_task_with_tasks_array(self, adapter):
        """Test executing task with tasks array"""
        mock_result = {
            "success": True,
            "root_task_id": "test-root-id"
        }
        
        with patch.object(adapter.task_routes, 'handle_task_execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_result
            
            result = await adapter.execute_task({
                "tasks": [{"name": "test-task", "schemas": {"method": "command_executor"}}],
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_task_single(self, adapter):
        """Test creating a single task"""
        mock_result = {"id": "test-task-id", "name": "test-task"}
        
        with patch.object(adapter.task_routes, 'handle_task_create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_result
            
            result = await adapter.create_task({
                "name": "test-task",
                "schemas": {"method": "command_executor"},
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_create.assert_called_once()
            # Should wrap single task in list
            call_args = mock_create.call_args
            assert isinstance(call_args[0][0], list)
            assert len(call_args[0][0]) == 1
    
    @pytest.mark.asyncio
    async def test_create_task_multiple(self, adapter):
        """Test creating multiple tasks"""
        mock_result = [{"id": "task-1"}, {"id": "task-2"}]
        
        with patch.object(adapter.task_routes, 'handle_task_create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_result
            
            result = await adapter.create_task({
                "tasks": [
                    {"name": "task-1"},
                    {"name": "task-2"}
                ],
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert isinstance(call_args[0][0], list)
            assert len(call_args[0][0]) == 2
    
    @pytest.mark.asyncio
    async def test_get_task(self, adapter):
        """Test getting a task"""
        mock_result = {"id": "test-task-id", "name": "test-task"}
        
        with patch.object(adapter.task_routes, 'handle_task_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_result
            
            result = await adapter.get_task({
                "task_id": "test-task-id",
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_task(self, adapter):
        """Test updating a task"""
        mock_result = {"id": "test-task-id", "name": "updated-task"}
        
        with patch.object(adapter.task_routes, 'handle_task_update', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_result
            
            result = await adapter.update_task({
                "task_id": "test-task-id",
                "name": "updated-task",
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_task(self, adapter):
        """Test deleting a task"""
        mock_result = {"success": True, "deleted": "test-task-id"}
        
        with patch.object(adapter.task_routes, 'handle_task_delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_result
            
            result = await adapter.delete_task({
                "task_id": "test-task-id",
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, adapter):
        """Test listing tasks"""
        mock_result = {
            "tasks": [{"id": "task-1"}, {"id": "task-2"}],
            "total": 2
        }
        
        with patch.object(adapter.task_routes, 'handle_tasks_list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_result
            
            result = await adapter.list_tasks({
                "status": "pending",
                "limit": 10,
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, adapter):
        """Test getting task status"""
        mock_result = {
            "task_id": "test-task-id",
            "status": "running",
            "progress": 0.5
        }
        
        with patch.object(adapter.task_routes, 'handle_running_tasks_status', new_callable=AsyncMock) as mock_status:
            mock_status.return_value = mock_result
            
            result = await adapter.get_task_status({
                "task_id": "test-task-id",
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, adapter):
        """Test canceling a task"""
        mock_result = {
            "success": True,
            "task_id": "test-task-id",
            "status": "cancelled"
        }
        
        with patch.object(adapter.task_routes, 'handle_task_cancel', new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = mock_result
            
            result = await adapter.cancel_task({
                "task_id": "test-task-id",
                "request_id": "test-request-id"
            })
            
            assert result == mock_result
            mock_cancel.assert_called_once()

