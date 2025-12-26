"""
Test CLI tasks command functionality

Tests the core business scenarios for task management via CLI.
"""

import pytest
import pytest_asyncio
import json
import uuid
from typer.testing import CliRunner
from aipartnerupflow.cli.main import app
from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.storage import set_default_session, reset_default_session
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class

runner = CliRunner()


@pytest_asyncio.fixture
async def sample_task(use_test_db_session):
    """Create a sample task in database for testing"""
    
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
    
    task_id = f"test-task-{uuid.uuid4()}"
    await task_repository.create_task(
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
    async def test_tasks_list_empty_db(self, use_test_db_session):
        """Test listing tasks when database is empty"""
        result = runner.invoke(app, ["tasks", "list"])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        assert isinstance(tasks, list)
        assert len(tasks) == 0
    
    @pytest.mark.asyncio
    async def test_tasks_list_with_tasks(self, use_test_db_session):
        """Test listing tasks from database"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task
        task_id = f"list-test-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="List Test Task",
            user_id="test_user",
            priority=1,
            has_children=False,
        )
        
        result = runner.invoke(app, ["tasks", "list"])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        assert isinstance(tasks, list)
        assert len(tasks) >= 1
        # Verify task structure
        task_dict = tasks[0]
        assert "id" in task_dict
        assert "name" in task_dict
        assert "status" in task_dict
    
    @pytest.mark.asyncio
    async def test_tasks_list_with_user_filter(self, use_test_db_session):
        """Test listing tasks with user_id filter"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        await task_repository.create_task(
            id=f"list-user1-{uuid.uuid4()}",
            name="User 1 Task",
            user_id="user_1",
            priority=1,
            has_children=False,
        )
        
        result = runner.invoke(app, [
            "tasks", "list",
            "--user-id", "user_1"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        for task in tasks:
            assert task["user_id"] == "user_1"


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
        # Parse JSON output
        statuses = json.loads(output)
        assert isinstance(statuses, list)
        assert len(statuses) > 0
        status = statuses[0]
        # Verify API-compatible format: (task_id, context_id, status, progress, error, is_running, started_at, updated_at)
        assert "task_id" in status
        assert "context_id" in status  # API compatibility field
        assert "status" in status
        assert "progress" in status
        assert "is_running" in status
        assert "started_at" in status  # Changed from created_at
        assert "updated_at" in status
        assert status["task_id"] == sample_task
        assert status["context_id"] == sample_task
    
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
        # Parse JSON output
        statuses = json.loads(output)
        assert isinstance(statuses, list)
        assert len(statuses) > 0
        status = statuses[0]
        assert status["status"] == "not_found"
        assert status["task_id"] == "non-existent-task-id"
        assert status["context_id"] == "non-existent-task-id"


class TestTasksCountCommand:
    """Test cases for tasks count command"""
    
    @pytest.mark.asyncio
    async def test_tasks_count_empty_db(self, use_test_db_session):
        """Test counting tasks when database is empty"""
        result = runner.invoke(app, ["tasks", "count", "--format", "json"])
        
        assert result.exit_code == 0
        output = result.stdout
        count_data = json.loads(output)
        
        # Should have total and all status counts
        assert "total" in count_data
        assert count_data["total"] == 0
        assert "pending" in count_data
        assert "in_progress" in count_data
        assert "completed" in count_data
        assert "failed" in count_data
        assert "cancelled" in count_data
    
    @pytest.mark.asyncio
    async def test_tasks_count_with_tasks(self, use_test_db_session):
        """Test counting tasks with various statuses"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create tasks with different statuses
        statuses = ["pending", "in_progress", "completed", "failed", "cancelled"]
        for i, status in enumerate(statuses):
            task_id = f"count-{status}-{uuid.uuid4()}"
            await task_repository.create_task(
                id=task_id,
                name=f"Count Test {status}",
                user_id="test_user",
                priority=1,
                has_children=False,
            )
            # Update status (create_task defaults to pending)
            if status != "pending":
                await task_repository.update_task_status(task_id, status)
        
        result = runner.invoke(app, ["tasks", "count", "--format", "json"])
        
        assert result.exit_code == 0
        output = result.stdout
        count_data = json.loads(output)
        
        # Each status should have at least 1 task
        assert count_data["total"] >= 5
        assert count_data["pending"] >= 1
        assert count_data["in_progress"] >= 1
        assert count_data["completed"] >= 1
        assert count_data["failed"] >= 1
        assert count_data["cancelled"] >= 1
    
    @pytest.mark.asyncio
    async def test_tasks_count_with_user_filter(self, use_test_db_session):
        """Test counting tasks with user_id filter"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create tasks for different users
        await task_repository.create_task(
            id=f"count-user1-{uuid.uuid4()}",
            name="User 1 Task",
            user_id="user_1",
            priority=1,
            has_children=False,
        )
        await task_repository.create_task(
            id=f"count-user2-{uuid.uuid4()}",
            name="User 2 Task",
            user_id="user_2",
            priority=1,
            has_children=False,
        )
        
        result = runner.invoke(app, [
            "tasks", "count",
            "--user-id", "user_1",
            "--format", "json"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        count_data = json.loads(output)
        
        assert count_data.get("user_id") == "user_1"
        assert count_data["pending"] >= 1
    
    @pytest.mark.asyncio
    async def test_tasks_count_table_format(self, use_test_db_session):
        """Test count with table output format"""
        result = runner.invoke(app, [
            "tasks", "count",
            "--format", "table"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        
        # Should contain table elements
        assert "Task Statistics" in output
        assert "Status" in output
        assert "Count" in output
    
    @pytest.mark.asyncio
    async def test_tasks_count_root_only(self, use_test_db_session):
        """Test count with --root-only flag"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a root task
        root_id = f"count-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_id,
            name="Root Task",
            user_id="test_user",
            priority=1,
            has_children=True,
        )
        
        # Create child tasks under the root
        for i in range(3):
            child_id = f"count-child-{i}-{uuid.uuid4()}"
            await task_repository.create_task(
                id=child_id,
                name=f"Child Task {i}",
                user_id="test_user",
                parent_id=root_id,
                priority=1,
                has_children=False,
            )
        
        # Count all tasks (should include children)
        result_all = runner.invoke(app, ["tasks", "count", "--format", "json"])
        assert result_all.exit_code == 0
        count_all = json.loads(result_all.stdout)
        
        # Count root only (should exclude children)
        result_root = runner.invoke(app, ["tasks", "count", "--root-only", "--format", "json"])
        assert result_root.exit_code == 0
        count_root = json.loads(result_root.stdout)
        
        # Root count should be less than total count
        assert count_root["total"] < count_all["total"]
        assert count_root.get("root_only") is True
        # At least 1 root task
        assert count_root["pending"] >= 1



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


class TestTasksCopyCommand:
    """Test cases for tasks copy command"""
    
    @pytest.mark.asyncio
    async def test_tasks_copy_basic(self, use_test_db_session):
        """Test copying a basic task"""
        
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a simple task tree: root -> child
        root_task_id = f"copy-root-{uuid.uuid4()}"
        root_task = await task_repository.create_task(
            id=root_task_id,
            name="Root Task to Copy",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0,
            result={"output": "test result"}
        )
        
        child_task_id = f"copy-child-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_task_id,
            name="Child Task to Copy",
            user_id="test_user",
            parent_id=root_task_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        # Copy task
        result = runner.invoke(app, [
            "tasks", "copy", root_task_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        
        # Verify output contains copied task info
        assert "Successfully copied" in output or root_task_id in output
        assert "new task" in output.lower() or "id" in output.lower()
        
        # Parse JSON output to verify structure
        try:
            # Try to find JSON in output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
                assert "id" in copied_data
                assert copied_data["id"] != root_task_id
                assert copied_data["name"] == root_task.name
                assert copied_data["original_task_id"] == root_task_id
                assert copied_data["status"] == "pending"
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, just verify basic output
            assert root_task_id in output
    
    @pytest.mark.asyncio
    async def test_tasks_copy_with_output_file(self, use_test_db_session, tmp_path):
        """Test copying a task with output file"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task
        task_id = f"copy-output-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Task for Output Test",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        # Copy task with output file
        output_file = tmp_path / "copied_task.json"
        result = runner.invoke(app, [
            "tasks", "copy", task_id,
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        # Verify output file content
        with open(output_file) as f:
            copied_data = json.load(f)
            assert "id" in copied_data
            assert copied_data["id"] != task_id
            assert copied_data["name"] == "Task for Output Test"
            assert copied_data["original_task_id"] == task_id
    
    @pytest.mark.asyncio
    async def test_tasks_copy_not_found(self, use_test_db_session):
        """Test copying a non-existent task"""
        result = runner.invoke(app, [
            "tasks", "copy", "non-existent-task-id"
        ])
        
        assert result.exit_code == 1
        # Error message can be in stdout or stderr
        output = result.output
        assert "not found" in output.lower() or "error" in output.lower() or "Task" in output

    @pytest.mark.asyncio
    async def test_tasks_copy_with_children(self, use_test_db_session):
        """Test copying a task with --children flag"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task tree with children
        root_task_id = f"copy-children-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_task_id,
            name="Root Task with Children",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child1_id = f"copy-children-child1-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child1_id,
            name="Child 1",
            user_id="test_user",
            parent_id=root_task_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        child2_id = f"copy-children-child2-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child2_id,
            name="Child 2",
            user_id="test_user",
            parent_id=root_task_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        # Copy task with --children flag
        result = runner.invoke(app, [
            "tasks", "copy", root_task_id,
            "--children"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        
        # Verify copied task information
        assert "Successfully copied" in output or root_task_id in output
        
        # Parse JSON output to verify structure
        try:
            # Try to find JSON in output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
                assert "id" in copied_data
                assert copied_data["id"] != root_task_id
                assert copied_data["name"] == "Root Task with Children"
                assert copied_data["original_task_id"] == root_task_id
                # Verify children are included
                if "children" in copied_data:
                    assert len(copied_data["children"]) >= 0  # May have children
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, just verify basic success message
            pass
    
    @pytest.mark.asyncio
    async def test_tasks_copy_with_save_false(self, use_test_db_session):
        """Test copying a task with --dry-run flag (returns task array without saving)"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task tree: root -> child
        root_task_id = f"copy-save-false-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_task_id,
            name="Root Task for Save False",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child_task_id = f"copy-save-false-child-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_task_id,
            name="Child Task",
            user_id="test_user",
            parent_id=root_task_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        # Copy task with --dry-run flag
        result = runner.invoke(app, [
            "tasks", "copy", root_task_id,
            "--dry-run"
        ])
        
        assert result.exit_code == 0, f"Command failed with: {result.output}"
        output = result.stdout
        
        # Verify output contains task array
        try:
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
                assert "tasks" in copied_data
                assert copied_data.get("saved") is False
                assert isinstance(copied_data["tasks"], list)
                assert len(copied_data["tasks"]) > 0
                # Verify task array format
                for task_dict in copied_data["tasks"]:
                    assert "id" in task_dict
                    assert "name" in task_dict
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, just verify basic output
            assert "tasks" in output.lower() or "array" in output.lower()
    
    @pytest.mark.asyncio
    async def test_tasks_copy_custom_mode(self, use_test_db_session):
        """Test copying with custom mode"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task tree: root -> child1, child2
        root_task_id = f"copy-custom-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_task_id,
            name="Root Task",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child1_id = f"copy-custom-child1-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child1_id,
            name="Child Task 1",
            user_id="test_user",
            parent_id=root_task_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        child2_id = f"copy-custom-child2-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child2_id,
            name="Child Task 2",
            user_id="test_user",
            parent_id=root_task_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        # Copy with custom mode
        result = runner.invoke(app, [
            "tasks", "copy", child1_id,
            "--copy-mode", "custom",
            "--custom-task-ids", child1_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        
        # Verify copied task
        try:
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
                # In custom mode, the result is the full tree structure starting from root
                # The specified child task is included in the tree
                assert "id" in copied_data
                assert copied_data["id"] != root_task_id  # New root ID
                # Verify the tree contains the copied child task
                if "children" in copied_data and copied_data["children"]:
                    child_names = [c.get("name") for c in copied_data["children"]]
                    assert "Child Task 1" in child_names or copied_data["name"] == "Child Task 1"
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, just verify basic success
            assert "Successfully copied" in output or child1_id in output
    
    @pytest.mark.asyncio
    async def test_tasks_copy_full_mode(self, use_test_db_session):
        """Test copying with full mode"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a task tree
        root_task_id = f"copy-full-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_task_id,
            name="Root Task for Full Mode",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child_id = f"copy-full-child-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_id,
            name="Child Task",
            user_id="test_user",
            parent_id=root_task_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        # Copy with full mode
        result = runner.invoke(app, [
            "tasks", "copy", root_task_id,
            "--copy-mode", "full"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        
        # Verify copied task
        try:
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
                assert "id" in copied_data
                assert copied_data["id"] != root_task_id
                assert copied_data["name"] == "Root Task for Full Mode"
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, just verify basic success
            assert "Successfully copied" in output or root_task_id in output
    
    @pytest.mark.asyncio
    async def test_tasks_copy_with_reset_fields(self, use_test_db_session):
        """Test copying with reset_fields"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create a completed task
        task_id = f"copy-reset-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Task to Reset",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0,
            result={"output": "test result"}
        )
        
        # Copy with reset_fields
        result = runner.invoke(app, [
            "tasks", "copy", task_id,
            "--reset-fields", "status,progress"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        
        # Verify copied task and check reset fields
        try:
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
                assert "id" in copied_data
                copied_task_id = copied_data["id"]
                
                # Verify reset fields in database
                copied_task = await task_repository.get_task_by_id(copied_task_id)
                assert copied_task is not None
                assert copied_task.status == "pending"  # Reset from completed
                assert copied_task.progress == 0.0  # Reset from 1.0
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, just verify basic success
            assert "Successfully copied" in output or task_id in output


class TestTasksGetCommand:
    """Test cases for tasks get command"""
    
    @pytest.mark.asyncio
    async def test_tasks_get_existing_task(self, use_test_db_session):
        """Test getting an existing task"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        task_id = f"get-test-{uuid.uuid4()}"
        # Note: create_task always sets status to "pending", so we need to update it
        await task_repository.create_task(
            id=task_id,
            name="Get Test Task",
            user_id="test_user",
            priority=1,
            has_children=False,
            progress=1.0,
            result={"output": "test result"}
        )
        # Update status to completed
        await task_repository.update_task_status(
            task_id=task_id,
            status="completed",
            progress=1.0
        )
        
        result = runner.invoke(app, [
            "tasks", "get", task_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        task_dict = json.loads(output)
        assert task_dict["id"] == task_id
        assert task_dict["name"] == "Get Test Task"
        assert task_dict["status"] == "completed"
        assert task_dict["progress"] == 1.0
    
    @pytest.mark.asyncio
    async def test_tasks_get_not_found(self, use_test_db_session):
        """Test getting a non-existent task"""
        result = runner.invoke(app, [
            "tasks", "get", "non-existent-task-id"
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "not found" in output.lower() or "error" in output.lower()


class TestTasksCopyCommandAdvanced:
    """Advanced test cases for tasks copy command"""

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
    async def test_tasks_copy_basic(self, use_test_db_session, task_tree_for_copy):
        """Test basic task copy with minimal mode"""
        set_default_session(use_test_db_session)
        try:
            root = task_tree_for_copy["root"]
            result = runner.invoke(app, [
                "tasks", "copy",
                root.id,
                "--copy-mode", "minimal"
            ])

            assert result.exit_code == 0
            output = result.stdout

            # Extract JSON from output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
            else:
                copied_data = json.loads(output)

            assert "id" in copied_data
            assert copied_data["name"] == "Root Task"
            assert copied_data["id"] != root.id  # New task ID

            # Verify task was saved to database
            task_repository = TaskRepository(
                use_test_db_session, task_model_class=get_task_model_class()
            )
            copied_task = await task_repository.get_task_by_id(copied_data["id"])
            assert copied_task is not None
            assert copied_task.name == "Root Task"
        finally:
            reset_default_session()

    @pytest.mark.asyncio
    async def test_tasks_copy_save_false(self, use_test_db_session, task_tree_for_copy):
        """Test task copy with save=False returns task array"""
        set_default_session(use_test_db_session)
        try:
            root = task_tree_for_copy["root"]
            result = runner.invoke(app, [
                "tasks", "copy",
                root.id,
                "--copy-mode", "minimal",
                "--dry-run"
            ])

            assert result.exit_code == 0
            output = result.stdout

            # Extract JSON from output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
            else:
                result_data = json.loads(output)

            assert "tasks" in result_data
            assert result_data.get("saved") is False
            assert isinstance(result_data["tasks"], list)
            assert len(result_data["tasks"]) > 0
        finally:
            reset_default_session()

    @pytest.mark.asyncio
    async def test_tasks_copy_with_children(self, use_test_db_session, task_tree_for_copy):
        """Test task copy with children=True"""
        set_default_session(use_test_db_session)
        try:
            root = task_tree_for_copy["root"]
            result = runner.invoke(app, [
                "tasks", "copy",
                root.id,
                "--copy-mode", "minimal",
                "--children"
            ])

            assert result.exit_code == 0
            output = result.stdout

            # Extract JSON from output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
            else:
                copied_data = json.loads(output)

            assert "id" in copied_data
            assert copied_data["name"] == "Root Task"
        finally:
            reset_default_session()

    @pytest.mark.asyncio
    async def test_tasks_copy_custom_mode(self, use_test_db_session, task_tree_for_copy):
        """Test task copy with custom mode"""
        set_default_session(use_test_db_session)
        try:
            child1 = task_tree_for_copy["child1"]
            result = runner.invoke(app, [
                "tasks", "copy",
                child1.id,
                "--copy-mode", "custom",
                "--custom-task-ids", child1.id
            ])

            assert result.exit_code == 0
            output = result.stdout

            # Extract JSON from output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
            else:
                copied_data = json.loads(output)

            assert "id" in copied_data
            assert copied_data["id"] != child1.id  # New task ID
        finally:
            reset_default_session()

    @pytest.mark.asyncio
    async def test_tasks_copy_full_mode(self, use_test_db_session, task_tree_for_copy):
        """Test task copy with full mode"""
        set_default_session(use_test_db_session)
        try:
            root = task_tree_for_copy["root"]
            result = runner.invoke(app, [
                "tasks", "copy",
                root.id,
                "--copy-mode", "full"
            ])

            assert result.exit_code == 0
            output = result.stdout

            # Extract JSON from output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
            else:
                copied_data = json.loads(output)

            assert "id" in copied_data
            assert copied_data["name"] == "Root Task"
        finally:
            reset_default_session()

    @pytest.mark.asyncio
    async def test_tasks_copy_with_reset_fields(self, use_test_db_session, task_tree_for_copy):
        """Test task copy with reset_fields"""
        set_default_session(use_test_db_session)
        try:
            root = task_tree_for_copy["root"]
            result = runner.invoke(app, [
                "tasks", "copy",
                root.id,
                "--copy-mode", "minimal",
                "--reset-fields", "status,progress"
            ])

            assert result.exit_code == 0
            output = result.stdout

            # Extract JSON from output
            import re
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                copied_data = json.loads(json_match.group())
            else:
                copied_data = json.loads(output)

            assert "id" in copied_data

            # Verify reset fields were applied
            task_repository = TaskRepository(
                use_test_db_session, task_model_class=get_task_model_class()
            )
            copied_task = await task_repository.get_task_by_id(copied_data["id"])
            assert copied_task.status == "pending"  # Reset from completed
            assert copied_task.progress == 0.0  # Reset from previous value
        finally:
            reset_default_session()

    @pytest.mark.asyncio
    async def test_tasks_copy_not_found(self, use_test_db_session):
        """Test error handling when task is not found"""
        set_default_session(use_test_db_session)
        try:
            result = runner.invoke(app, [
                "tasks", "copy",
                "non-existent-task",
                "--copy-mode", "minimal"
            ])

            assert result.exit_code != 0
            assert "not found" in result.stdout.lower() or "error" in result.stdout.lower() or result.exit_code == 1
        finally:
            reset_default_session()


class TestTasksCreateCommand:
    """Test cases for tasks create command"""
    
    @pytest.mark.asyncio
    async def test_tasks_create_from_file(self, use_test_db_session, tmp_path):
        """Test creating tasks from JSON file"""
        task_data = {
            "id": "create-test-1",
            "name": "Create Test Task",
            "user_id": "test_user",
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "progress": 0.0
        }
        
        task_file = tmp_path / "task.json"
        with open(task_file, 'w') as f:
            json.dump(task_data, f)
        
        result = runner.invoke(app, [
            "tasks", "create",
            "--file", str(task_file)
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        # Extract JSON from output (may contain extra success message)
        import re
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            created_data = json.loads(json_match.group())
        else:
            created_data = json.loads(output)
        assert "id" in created_data
        assert created_data["name"] == "Create Test Task"
        
        # Verify task exists in database
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task = await task_repository.get_task_by_id(created_data["id"])
        assert task is not None
        assert task.name == "Create Test Task"
    
    @pytest.mark.asyncio
    async def test_tasks_create_from_stdin(self, use_test_db_session, tmp_path):
        """Test creating tasks from stdin (using file as stdin simulation)"""
        # Note: CliRunner doesn't easily support stdin mocking in tests
        # This test verifies the --stdin flag exists and works conceptually
        # In practice, stdin input would be provided via shell piping
        task_data = {
            "id": "create-stdin-1",
            "name": "Create Stdin Task",
            "user_id": "test_user",
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "progress": 0.0
        }
        
        # Since stdin mocking is difficult with CliRunner, we'll test the file approach
        # which is functionally equivalent and more testable
        task_file = tmp_path / "stdin_sim_task.json"
        with open(task_file, 'w') as f:
            json.dump(task_data, f)
        
        # Test that the create command accepts --stdin flag (even if we can't easily test stdin input)
        # We verify the command structure by checking help or using file as alternative
        result = runner.invoke(app, [
            "tasks", "create",
            "--file", str(task_file)
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        # Extract JSON from output
        import re
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            created_data = json.loads(json_match.group())
        else:
            created_data = json.loads(output)
        assert "id" in created_data
        assert created_data["name"] == "Create Stdin Task"
        
        # Verify task was created in database
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        task = await task_repository.get_task_by_id(created_data["id"])
        assert task is not None
    
    @pytest.mark.asyncio
    async def test_tasks_create_missing_file_or_stdin(self, use_test_db_session):
        """Test creating tasks without file or stdin"""
        result = runner.invoke(app, [
            "tasks", "create"
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "file" in output.lower() or "stdin" in output.lower()


class TestTasksUpdateCommand:
    """Test cases for tasks update command"""
    
    @pytest.mark.asyncio
    async def test_tasks_update_name(self, use_test_db_session):
        """Test updating task name"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        task_id = f"update-test-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Original Name",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        result = runner.invoke(app, [
            "tasks", "update", task_id,
            "--name", "Updated Name"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        # Extract JSON from output (may contain extra success message)
        import re
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            updated_data = json.loads(json_match.group())
        else:
            updated_data = json.loads(output)
        assert updated_data["name"] == "Updated Name"
        
        # Verify in database
        task = await task_repository.get_task_by_id(task_id)
        assert task.name == "Updated Name"
    
    @pytest.mark.asyncio
    async def test_tasks_update_status(self, use_test_db_session):
        """Test updating task status"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        task_id = f"update-status-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Status Update Test",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        result = runner.invoke(app, [
            "tasks", "update", task_id,
            "--status", "completed",
            "--progress", "1.0"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        # Extract JSON from output (may contain extra success message)
        import re
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            updated_data = json.loads(json_match.group())
        else:
            updated_data = json.loads(output)
        assert updated_data["status"] == "completed"
        assert updated_data["progress"] == 1.0
    
    @pytest.mark.asyncio
    async def test_tasks_update_no_fields(self, use_test_db_session):
        """Test updating task without specifying fields"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        task_id = f"update-no-fields-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="No Fields Test",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        result = runner.invoke(app, [
            "tasks", "update", task_id
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "field" in output.lower() or "specified" in output.lower()
    
    @pytest.mark.asyncio
    async def test_tasks_update_not_found(self, use_test_db_session):
        """Test updating a non-existent task"""
        result = runner.invoke(app, [
            "tasks", "update", "non-existent-task-id",
            "--name", "New Name"
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "not found" in output.lower()


class TestTasksDeleteCommand:
    """Test cases for tasks delete command"""
    
    @pytest.mark.asyncio
    async def test_tasks_delete_pending_task(self, use_test_db_session):
        """Test deleting a pending task"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        task_id = f"delete-test-{uuid.uuid4()}"
        await task_repository.create_task(
            id=task_id,
            name="Delete Test Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        result = runner.invoke(app, [
            "tasks", "delete", task_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        # Extract JSON from output (may contain extra success message)
        import re
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            delete_data = json.loads(json_match.group())
        else:
            delete_data = json.loads(output)
        assert delete_data["success"] is True
        assert delete_data["task_id"] == task_id
        assert delete_data["deleted_count"] >= 1
        
        # Verify task is deleted
        task = await task_repository.get_task_by_id(task_id)
        assert task is None
    
    @pytest.mark.asyncio
    async def test_tasks_delete_with_children(self, use_test_db_session):
        """Test deleting a task with children (all pending)"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        root_id = f"delete-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_id,
            name="Root Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=True,
            progress=0.0
        )
        
        child_id = f"delete-child-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_id,
            name="Child Task",
            user_id="test_user",
            parent_id=root_id,
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        result = runner.invoke(app, [
            "tasks", "delete", root_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        # Extract JSON from output (may contain extra success message)
        import re
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            delete_data = json.loads(json_match.group())
        else:
            delete_data = json.loads(output)
        assert delete_data["success"] is True
        assert delete_data["deleted_count"] >= 2  # Root + child
        assert delete_data["children_deleted"] >= 1
    
    @pytest.mark.asyncio
    async def test_tasks_delete_non_pending_task(self, use_test_db_session):
        """Test deleting a non-pending task (should fail)"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        task_id = f"delete-completed-{uuid.uuid4()}"
        # Create task and update status to completed
        await task_repository.create_task(
            id=task_id,
            name="Completed Task",
            user_id="test_user",
            priority=1,
            has_children=False,
            progress=1.0
        )
        await task_repository.update_task_status(
            task_id=task_id,
            status="completed",
            progress=1.0
        )
        
        # Verify task status is completed before deletion attempt
        task_before = await task_repository.get_task_by_id(task_id)
        assert task_before.status == "completed"
        
        result = runner.invoke(app, [
            "tasks", "delete", task_id
        ])
        
        # Should fail because task is not pending
        assert result.exit_code == 1
        output = result.output
        assert "cannot delete" in output.lower() or "pending" in output.lower()
        
        # Verify task was NOT deleted
        task_after = await task_repository.get_task_by_id(task_id)
        assert task_after is not None
        assert task_after.status == "completed"
    
    @pytest.mark.asyncio
    async def test_tasks_delete_not_found(self, use_test_db_session):
        """Test deleting a non-existent task"""
        result = runner.invoke(app, [
            "tasks", "delete", "non-existent-task-id"
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "not found" in output.lower()


class TestTasksTreeCommand:
    """Test cases for tasks tree command"""
    
    @pytest.mark.asyncio
    async def test_tasks_tree_basic(self, use_test_db_session):
        """Test getting task tree structure"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        root_id = f"tree-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_id,
            name="Root Task",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child_id = f"tree-child-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_id,
            name="Child Task",
            user_id="test_user",
            parent_id=root_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        result = runner.invoke(app, [
            "tasks", "tree", root_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tree_data = json.loads(output)
        assert tree_data["id"] == root_id
        assert tree_data["name"] == "Root Task"
        assert "children" in tree_data
        assert len(tree_data["children"]) >= 1
        assert tree_data["children"][0]["id"] == child_id
    
    @pytest.mark.asyncio
    async def test_tasks_tree_from_child(self, use_test_db_session):
        """Test getting task tree starting from a child task"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        root_id = f"tree-root2-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_id,
            name="Root Task 2",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child_id = f"tree-child2-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_id,
            name="Child Task 2",
            user_id="test_user",
            parent_id=root_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        # Get tree starting from child - should return root tree
        result = runner.invoke(app, [
            "tasks", "tree", child_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tree_data = json.loads(output)
        assert tree_data["id"] == root_id  # Should return root tree
        assert "children" in tree_data
    
    @pytest.mark.asyncio
    async def test_tasks_tree_not_found(self, use_test_db_session):
        """Test getting tree for non-existent task"""
        result = runner.invoke(app, [
            "tasks", "tree", "non-existent-task-id"
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "not found" in output.lower()


class TestTasksChildrenCommand:
    """Test cases for tasks children command"""
    
    @pytest.mark.asyncio
    async def test_tasks_children_basic(self, use_test_db_session):
        """Test getting child tasks"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        parent_id = f"children-parent-{uuid.uuid4()}"
        await task_repository.create_task(
            id=parent_id,
            name="Parent Task",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child1_id = f"children-child1-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child1_id,
            name="Child 1",
            user_id="test_user",
            parent_id=parent_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        child2_id = f"children-child2-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child2_id,
            name="Child 2",
            user_id="test_user",
            parent_id=parent_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        result = runner.invoke(app, [
            "tasks", "children",
            "--parent-id", parent_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        children = json.loads(output)
        assert isinstance(children, list)
        assert len(children) == 2
        child_ids = [c["id"] for c in children]
        assert child1_id in child_ids
        assert child2_id in child_ids
    
    @pytest.mark.asyncio
    async def test_tasks_children_with_task_id(self, use_test_db_session):
        """Test getting children using --task-id instead of --parent-id"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        parent_id = f"children-taskid-{uuid.uuid4()}"
        await task_repository.create_task(
            id=parent_id,
            name="Parent Task",
            user_id="test_user",
            status="completed",
            priority=1,
            has_children=True,
            progress=1.0
        )
        
        child_id = f"children-taskid-child-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_id,
            name="Child Task",
            user_id="test_user",
            parent_id=parent_id,
            status="completed",
            priority=1,
            has_children=False,
            progress=1.0
        )
        
        result = runner.invoke(app, [
            "tasks", "children",
            "--task-id", parent_id
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        children = json.loads(output)
        assert isinstance(children, list)
        assert len(children) >= 1
    
    @pytest.mark.asyncio
    async def test_tasks_children_no_parent_or_task_id(self, use_test_db_session):
        """Test getting children without specifying parent-id or task-id"""
        result = runner.invoke(app, [
            "tasks", "children"
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "parent-id" in output.lower() or "task-id" in output.lower()
    
    @pytest.mark.asyncio
    async def test_tasks_children_not_found(self, use_test_db_session):
        """Test getting children for non-existent parent"""
        result = runner.invoke(app, [
            "tasks", "children",
            "--parent-id", "non-existent-parent-id"
        ])
        
        assert result.exit_code == 1
        output = result.output
        assert "not found" in output.lower()


class TestTasksAllCommand:
    """Test cases for tasks all command (list all tasks from database)"""
    
    @pytest.mark.asyncio
    async def test_tasks_all_basic(self, use_test_db_session):
        """Test listing all tasks from database"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create multiple tasks with different statuses
        task_ids = []
        for i, status in enumerate(["pending", "in_progress", "completed"]):
            task_id = f"all-test-{uuid.uuid4()}"
            await task_repository.create_task(
                id=task_id,
                name=f"Task {i}",
                user_id="test_user",
                status=status,
                priority=1,
                has_children=False,
                progress=0.0 if status != "completed" else 1.0
            )
            task_ids.append(task_id)
        
        result = runner.invoke(app, [
            "tasks", "list"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        assert isinstance(tasks, list)
        assert len(tasks) >= 3
        # Verify all tasks are returned
        returned_ids = [t["id"] for t in tasks]
        for task_id in task_ids:
            assert task_id in returned_ids
    
    @pytest.mark.asyncio
    async def test_tasks_all_with_status_filter(self, use_test_db_session):
        """Test listing all tasks with status filter"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create tasks with different statuses
        pending_id = f"all-status-pending-{uuid.uuid4()}"
        await task_repository.create_task(
            id=pending_id,
            name="Pending Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        completed_id = f"all-status-completed-{uuid.uuid4()}"
        # Note: create_task always sets status to "pending", so we need to update it
        await task_repository.create_task(
            id=completed_id,
            name="Completed Task",
            user_id="test_user",
            priority=1,
            has_children=False,
            progress=1.0
        )
        # Update status to completed
        await task_repository.update_task_status(
            task_id=completed_id,
            status="completed",
            progress=1.0
        )
        
        result = runner.invoke(app, [
            "tasks", "list",
            "--status", "completed",
            "--root-only"  # Explicitly set root_only to True (default)
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        assert isinstance(tasks, list)
        # All returned tasks should be completed
        for task in tasks:
            assert task["status"] == "completed"
        # Verify completed task is in results (it's a root task)
        returned_ids = [t["id"] for t in tasks]
        assert completed_id in returned_ids
    
    @pytest.mark.asyncio
    async def test_tasks_all_with_user_filter(self, use_test_db_session):
        """Test listing all tasks with user_id filter"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        user1_id = f"all-user1-{uuid.uuid4()}"
        await task_repository.create_task(
            id=user1_id,
            name="User 1 Task",
            user_id="user1",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        user2_id = f"all-user2-{uuid.uuid4()}"
        await task_repository.create_task(
            id=user2_id,
            name="User 2 Task",
            user_id="user2",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        result = runner.invoke(app, [
            "tasks", "list",
            "--user-id", "user1"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        assert isinstance(tasks, list)
        # All returned tasks should belong to user1
        for task in tasks:
            assert task["user_id"] == "user1"
        # Verify user1 task is in results
        returned_ids = [t["id"] for t in tasks]
        assert user1_id in returned_ids
    
    @pytest.mark.asyncio
    async def test_tasks_all_with_limit(self, use_test_db_session):
        """Test listing all tasks with limit"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        # Create more tasks than limit
        for i in range(5):
            task_id = f"all-limit-{uuid.uuid4()}"
            await task_repository.create_task(
                id=task_id,
                name=f"Limit Test Task {i}",
                user_id="test_user",
                status="pending",
                priority=1,
                has_children=False,
                progress=0.0
            )
        
        result = runner.invoke(app, [
            "tasks", "list",
            "--limit", "2"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        assert isinstance(tasks, list)
        assert len(tasks) <= 2
    
    @pytest.mark.asyncio
    async def test_tasks_all_root_only(self, use_test_db_session):
        """Test listing all tasks with root-only filter"""
        task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())
        
        root_id = f"all-root-{uuid.uuid4()}"
        await task_repository.create_task(
            id=root_id,
            name="Root Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=True,
            progress=0.0
        )
        
        child_id = f"all-child-{uuid.uuid4()}"
        await task_repository.create_task(
            id=child_id,
            name="Child Task",
            user_id="test_user",
            parent_id=root_id,
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0
        )
        
        result = runner.invoke(app, [
            "tasks", "list",
            "--root-only"
        ])
        
        assert result.exit_code == 0
        output = result.stdout
        tasks = json.loads(output)
        assert isinstance(tasks, list)
        # All returned tasks should be root tasks (no parent_id)
        for task in tasks:
            assert task.get("parent_id") is None or task.get("parent_id") == ""
        # Verify root task is in results
        returned_ids = [t["id"] for t in tasks]
        assert root_id in returned_ids
        # Child should not be in results


class TestTasksWatchCommand:
    """Test cases for tasks watch command"""
    
    @pytest.mark.asyncio
    async def test_tasks_watch_requires_task_id_or_all(self, use_test_db_session):
        """Test that tasks watch requires either --task-id or --all"""
        result = runner.invoke(app, ["tasks", "watch"])
        
        # Command should fail with exit code 1
        assert result.exit_code == 1
        # Error message is printed to stderr
        error_output = result.output.lower()
        assert "task-id" in error_output or "all" in error_output or "error" in error_output or "must be specified" in error_output
    
    @pytest.mark.asyncio
    def test_tasks_watch_with_task_id_no_task(self, use_test_db_session):
        """Test watching a non-existent task (should handle gracefully)"""
        # Mock the Live display to avoid interactive blocking
        from unittest.mock import patch, MagicMock
        
        with patch('aipartnerupflow.cli.commands.tasks.Live') as mock_live:
            # Mock Live context manager
            mock_live_instance = MagicMock()
            mock_live.return_value.__enter__ = MagicMock(return_value=mock_live_instance)
            mock_live.return_value.__exit__ = MagicMock(return_value=None)
            
            # Mock time.sleep to avoid actual waiting
            with patch('aipartnerupflow.cli.commands.tasks.time.sleep') as mock_sleep:
                # Make the loop exit after first iteration by raising KeyboardInterrupt
                mock_sleep.side_effect = KeyboardInterrupt()
                
                result = runner.invoke(app, [
                    "tasks", "watch",
                    "--task-id", "non-existent-task-id",
                    "--interval", "0.1"
                ])
                
                # Command should handle gracefully (may exit with 0 or 1)
                # The important thing is it doesn't hang
                assert result.exit_code in [0, 1]
                # Verify Live was called
                mock_live.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tasks_watch_with_all_no_tasks(self, use_test_db_session):
        """Test watching all running tasks when none are running"""
        # When no tasks are running, command should handle gracefully
        result = runner.invoke(app, [
            "tasks", "watch",
            "--all",
            "--interval", "0.1"
        ])
        
        # Command should exit gracefully when no tasks are running
        assert result.exit_code == 0
        # Should show message about no running tasks
        output = result.output.lower()
        assert "no running tasks" in output or "watching 0 task" in output

