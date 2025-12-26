"""
Test CLI run command functionality

Tests the core business scenarios for executing tasks via CLI.
"""

import pytest
import json
import uuid
import tempfile
from pathlib import Path
from typer.testing import CliRunner
from aipartnerupflow.cli.main import app
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class

runner = CliRunner()


@pytest.fixture
def temp_tasks_file():
    """Create a temporary tasks JSON file"""
    tasks = [
        {
            "id": "test-task-1",
            "name": "Test Task 1",
            "user_id": "test_user",
            "schemas": {
                "method": "system_info_executor"
            },
            "inputs": {
                "resource": "cpu"
            },
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "progress": 0.0
        }
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(tasks, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestRunCommand:
    """Test cases for run flow command"""
    
    @pytest.mark.asyncio
    async def test_run_flow_with_tasks_array(self, use_test_db_session):
        """Test executing tasks using --tasks option (standard mode)"""
        tasks_json = json.dumps([
            {
                "id": "test-task-1",
                "name": "Test Task 1",
                "user_id": "test_user",
                "schemas": {
                    "method": "system_info_executor"
                },
                "inputs": {
                    "resource": "cpu"
                },
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "progress": 0.0
            }
        ])
        
        result = runner.invoke(app, [
            "run", "flow",
            "--tasks", tasks_json
        ])
        
        assert result.exit_code == 0
        assert "status" in result.stdout or "root_task_id" in result.stdout
        
        # Verify task was created in database
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task = await task_repository.get_task_by_id("test-task-1")
        assert task is not None
        assert task.name == "Test Task 1"
    
    @pytest.mark.asyncio
    async def test_run_flow_with_tasks_file(self, use_test_db_session, temp_tasks_file):
        """Test executing tasks using --tasks-file option"""
        
        result = runner.invoke(app, [
            "run", "flow",
            "--tasks-file", str(temp_tasks_file)
        ])
        
        assert result.exit_code == 0
        
        # Verify task was created
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task = await task_repository.get_task_by_id("test-task-1")
        assert task is not None
    
    @pytest.mark.asyncio
    async def test_run_flow_legacy_mode(self, use_test_db_session):
        """Test executing task using legacy mode (executor_id + inputs)"""
        
        result = runner.invoke(app, [
            "run", "flow", "system_info_executor",
            "--inputs", '{"resource": "cpu"}'
        ])
        
        assert result.exit_code == 0
        assert "status" in result.stdout or "root_task_id" in result.stdout
    
    @pytest.mark.asyncio
    async def test_run_flow_background_mode(self, use_test_db_session):
        """Test executing tasks in background mode"""
        
        tasks_json = json.dumps([
            {
                "id": f"bg-task-{uuid.uuid4()}",
                "name": "Background Task",
                "user_id": "test_user",
                "schemas": {
                    "method": "system_info_executor"
                },
                "inputs": {
                    "resource": "cpu"
                },
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "progress": 0.0
            }
        ])
        
        result = runner.invoke(app, [
            "run", "flow",
            "--tasks", tasks_json,
            "--background"
        ])
        
        assert result.exit_code == 0
        assert "Task(s) started in background" in result.stdout or "Task ID:" in result.stdout
    
    @pytest.mark.asyncio
    async def test_run_flow_multiple_unrelated_tasks(self, use_test_db_session):
        """Test executing multiple unrelated tasks (multiple root tasks)"""
        
        tasks_json = json.dumps([
            {
                "id": "root-task-1",
                "name": "Root Task 1",
                "user_id": "test_user",
                "schemas": {
                    "method": "system_info_executor"
                },
                "inputs": {
                    "resource": "cpu"
                },
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "progress": 0.0
            },
            {
                "id": "root-task-2",
                "name": "Root Task 2",
                "user_id": "test_user",
                "schemas": {
                    "method": "system_info_executor"
                },
                "inputs": {
                    "resource": "memory"
                },
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "progress": 0.0
            }
        ])
        
        result = runner.invoke(app, [
            "run", "flow",
            "--tasks", tasks_json
        ])
        
        assert result.exit_code == 0
        assert "unrelated task groups" in result.stdout or "task_groups" in result.stdout
        
        # Verify both tasks were created
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task1 = await task_repository.get_task_by_id("root-task-1")
        task2 = await task_repository.get_task_by_id("root-task-2")
        assert task1 is not None
        assert task2 is not None
    
    @pytest.mark.asyncio
    async def test_run_flow_task_tree(self, use_test_db_session):
        """Test executing task tree (parent-child relationship)"""
        
        tasks_json = json.dumps([
            {
                "id": "root-task",
                "name": "Root Task",
                "user_id": "test_user",
                "schemas": {
                    "method": "system_info_executor"
                },
                "inputs": {
                    "resource": "cpu"
                },
                "status": "pending",
                "priority": 1,
                "has_children": True,
                "progress": 0.0
            },
            {
                "id": "child-task",
                "name": "Child Task",
                "parent_id": "root-task",
                "user_id": "test_user",
                "schemas": {
                    "method": "system_info_executor"
                },
                "inputs": {
                    "resource": "memory"
                },
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "progress": 0.0
            }
        ])
        
        result = runner.invoke(app, [
            "run", "flow",
            "--tasks", tasks_json
        ])
        
        assert result.exit_code == 0
        
        # Verify task tree was created
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        root_task = await task_repository.get_task_by_id("root-task")
        child_task = await task_repository.get_task_by_id("child-task")
        assert root_task is not None
        assert child_task is not None
        assert child_task.parent_id == "root-task"
    
    def test_run_flow_missing_tasks_error(self):
        """Test error when no tasks provided"""
        result = runner.invoke(app, [
            "run", "flow"
        ])
        
        assert result.exit_code == 1
        # Error message may be in stdout or stderr
        output = result.output
        assert "Error" in output or "must be provided" in output or result.exception is not None
    
    def test_run_flow_invalid_tasks_json(self):
        """Test error with invalid JSON"""
        result = runner.invoke(app, [
            "run", "flow",
            "--tasks", "invalid json"
        ])
        
        assert result.exit_code == 1
        # Should have error about invalid JSON
        output = result.output
        assert "Error" in output or "JSON" in output or result.exception is not None

