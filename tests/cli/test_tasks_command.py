"""
Test CLI tasks command functionality

Tests the core business scenarios for task management via CLI.
"""

import pytest
import pytest_asyncio
import json
import uuid
import asyncio
from typer.testing import CliRunner
from aipartnerupflow.cli.main import app
from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.storage import get_default_session, set_default_session, reset_default_session
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class

runner = CliRunner()


@pytest.fixture
def use_test_db_session(sync_db_session):
    """Fixture to set and reset default session for CLI tests"""
    set_default_session(sync_db_session)
    yield sync_db_session
    reset_default_session()


@pytest_asyncio.fixture
async def sample_task(use_test_db_session):
    """Create a sample task in database for testing"""
    
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
    
    task_id = f"test-task-{uuid.uuid4()}"
    task = await task_repository.create_task(
        id=task_id,
        name="Test Task",
        user_id="test_user",
        status="in_progress",
        priority=1,
        has_children=False,
        progress=0.5
    )
    
    # Start tracking to simulate running task
    task_executor = TaskExecutor()
    await task_executor.start_task_tracking(task_id)
    
    yield task_id
    
    # Cleanup
    await task_executor.stop_task_tracking(task_id)


class TestTasksListCommand:
    """Test cases for tasks list command"""
    
    @pytest.mark.asyncio
    async def test_tasks_list_no_running_tasks(self, use_test_db_session):
        """Test listing tasks when no tasks are running"""
        result = runner.invoke(app, ["tasks", "list"])
        
        assert result.exit_code == 0
        assert "No running tasks found" in result.stdout or "[]" in result.stdout
    
    @pytest.mark.asyncio
    async def test_tasks_list_with_running_tasks(self, use_test_db_session, sample_task):
        """Test listing running tasks"""
        result = runner.invoke(app, ["tasks", "list"])
        
        assert result.exit_code == 0
        # Should contain task information
        output = result.stdout
        assert "task_id" in output or sample_task in output
    
    @pytest.mark.asyncio
    async def test_tasks_list_with_user_filter(self, use_test_db_session, sample_task):
        """Test listing tasks with user_id filter"""
        result = runner.invoke(app, [
            "tasks", "list",
            "--user-id", "test_user"
        ])
        
        assert result.exit_code == 0


class TestTasksStatusCommand:
    """Test cases for tasks status command"""
    
    @pytest.mark.asyncio
    async def test_tasks_status_single_task(self, use_test_db_session, sample_task):
        """Test checking status of a single task"""
        result = runner.invoke(app, [
            "tasks", "status", sample_task
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        assert sample_task in output
        assert "status" in output
    
    @pytest.mark.asyncio
    async def test_tasks_status_multiple_tasks(self, use_test_db_session):
        """Test checking status of multiple tasks"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task_executor = TaskExecutor()
        
        # Create multiple tasks
        task_ids = []
        for i in range(2):
            task_id = f"status-test-{uuid.uuid4()}"
            await task_repository.create_task(
                id=task_id,
                name=f"Status Test Task {i}",
                user_id="test_user",
                status="in_progress",
                priority=1,
                has_children=False,
                progress=0.0
            )
            await task_executor.start_task_tracking(task_id)
            task_ids.append(task_id)
        
        try:
            result = runner.invoke(app, [
                "tasks", "status", *task_ids
            ])
            
            assert result.exit_code == 0
            output = result.stdout
            for task_id in task_ids:
                assert task_id in output
        finally:
            # Cleanup
            for task_id in task_ids:
                await task_executor.stop_task_tracking(task_id)
    
    @pytest.mark.asyncio
    async def test_tasks_status_not_found(self, use_test_db_session):
        """Test checking status of non-existent task"""
        result = runner.invoke(app, [
            "tasks", "status", "non-existent-task-id"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        assert "not_found" in output or "Unknown" in output


class TestTasksCountCommand:
    """Test cases for tasks count command"""
    
    @pytest.mark.asyncio
    async def test_tasks_count_no_running_tasks(self, use_test_db_session):
        """Test counting tasks when no tasks are running"""
        result = runner.invoke(app, ["tasks", "count"])
        
        assert result.exit_code == 0
        output = result.stdout
        assert "count" in output
        # Parse JSON output
        count_data = json.loads(output)
        assert count_data["count"] == 0
    
    @pytest.mark.asyncio
    async def test_tasks_count_with_running_tasks(self, use_test_db_session, sample_task):
        """Test counting running tasks"""
        result = runner.invoke(app, ["tasks", "count"])
        
        assert result.exit_code == 0
        output = result.stdout
        count_data = json.loads(output)
        assert count_data["count"] >= 1
    
    @pytest.mark.asyncio
    async def test_tasks_count_with_user_filter(self, use_test_db_session, sample_task):
        """Test counting tasks with user_id filter"""
        result = runner.invoke(app, [
            "tasks", "count",
            "--user-id", "test_user"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        count_data = json.loads(output)
        assert "count" in count_data
        assert count_data.get("user_id") == "test_user"


class TestTasksCancelCommand:
    """Test cases for tasks cancel command"""
    
    @pytest.mark.asyncio
    async def test_tasks_cancel_single_task(self, use_test_db_session):
        """Test cancelling a single task"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task_executor = TaskExecutor()
        
        # Create a task in in_progress status
        task_id = f"cancel-test-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Cancel Test Task",
            user_id="test_user",
            status="in_progress",
            priority=1,
            has_children=False,
            progress=0.5
        )
        await task_executor.start_task_tracking(task_id)
        
        try:
            result = runner.invoke(app, [
                "tasks", "cancel", task_id
            ])
            
            assert result.exit_code == 0
            output = result.stdout
            assert "cancelled" in output.lower() or task_id in output
            
            # Verify task status was updated
            task = await task_repository.get_task_by_id(task_id)
            assert task.status == "cancelled"
        finally:
            # Cleanup
            await task_executor.stop_task_tracking(task_id)
    
    @pytest.mark.asyncio
    async def test_tasks_cancel_multiple_tasks(self, use_test_db_session):
        """Test cancelling multiple tasks"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task_executor = TaskExecutor()
        
        # Create multiple tasks
        task_ids = []
        for i in range(2):
            task_id = f"cancel-multi-{uuid.uuid4()}"
            await task_repository.create_task(
                id=task_id,
                name=f"Cancel Multi Task {i}",
                user_id="test_user",
                status="in_progress",
                priority=1,
                has_children=False,
                progress=0.0
            )
            await task_executor.start_task_tracking(task_id)
            task_ids.append(task_id)
        
        try:
            result = runner.invoke(app, [
                "tasks", "cancel", *task_ids
            ])
            
            assert result.exit_code == 0
            output = result.stdout
            
            # Verify all tasks were cancelled
            for task_id in task_ids:
                assert task_id in output
                task = await task_repository.get_task_by_id(task_id)
                assert task.status == "cancelled"
        finally:
            # Cleanup
            for task_id in task_ids:
                await task_executor.stop_task_tracking(task_id)
    
    @pytest.mark.asyncio
    async def test_tasks_cancel_force(self, use_test_db_session):
        """Test force cancelling a task"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task_executor = TaskExecutor()
        
        task_id = f"cancel-force-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Force Cancel Test Task",
            user_id="test_user",
            status="in_progress",
            priority=1,
            has_children=False,
            progress=0.0
        )
        await task_executor.start_task_tracking(task_id)
        
        try:
            result = runner.invoke(app, [
                "tasks", "cancel", task_id,
                "--force"
            ])
            
            assert result.exit_code == 0
            output = result.stdout
            assert "cancelled" in output.lower() or task_id in output
            
            # Verify task was cancelled
            task = await task_repository.get_task_by_id(task_id)
            assert task.status == "cancelled"
        finally:
            await task_executor.stop_task_tracking(task_id)
    
    @pytest.mark.asyncio
    async def test_tasks_cancel_already_completed(self, use_test_db_session):
        """Test cancelling an already completed task"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        task_id = f"cancel-completed-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Completed Task",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        result = runner.invoke(app, [
            "tasks", "cancel", task_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        # Should indicate task is already finished
        assert "already" in output.lower() or "completed" in output.lower() or "failed" in output.lower()
    
    @pytest.mark.asyncio
    async def test_tasks_cancel_not_found(self, use_test_db_session):
        """Test cancelling a non-existent task"""
        result = runner.invoke(app, [
            "tasks", "cancel", "non-existent-task-id"
        ])
        
        assert result.exit_code == 1  # Should fail for not found
        output = result.stdout
        assert "not_found" in output.lower() or "error" in output.lower()

