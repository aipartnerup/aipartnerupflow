"""
Test TaskModel customization functionality

This file contains all tests related to custom TaskModel fields (e.g., project_id, priority_level, department).
These tests use extend_existing=True which modifies Base.metadata, so they are excluded from default test runs
to avoid Base.metadata pollution.

Run these tests explicitly with: pytest -m no_auto_run
"""
import pytest
from sqlalchemy import Column, String, Integer
from aipartnerupflow import (
    set_task_model_class,
    get_task_model_class,
    task_model_register,
    clear_config,
)
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel



class TestTaskModelCustomization:
    """Test TaskModel customization features"""
    
    def setup_method(self):
        """Clear config before each test"""
        clear_config()
    
    def test_task_model_register_decorator(self):
        """Test @task_model_register() decorator"""
        @task_model_register()
        class CustomTaskModel(TaskModel):
            __tablename__ = "apflow_tasks"
            __table_args__ = {'extend_existing': True}
            project_id = Column(String(255), nullable=True)  # Removed index=True to avoid conflicts
            department = Column(String(100), nullable=True)
        
        # Verify class was registered
        retrieved_class = get_task_model_class()
        assert retrieved_class == CustomTaskModel
        assert retrieved_class.__name__ == "CustomTaskModel"
    
    def test_task_model_register_validation(self):
        """Test that task_model_register validates inheritance"""
        with pytest.raises(TypeError, match="must be a subclass of TaskModel"):
            @task_model_register()
            class NotTaskModel:
                pass
    
    def test_set_task_model_class_validation(self):
        """Test that set_task_model_class validates inheritance"""
        class NotTaskModel:
            pass
        
        with pytest.raises(TypeError, match="must be a subclass of TaskModel"):
            set_task_model_class(NotTaskModel)
    
    def test_set_task_model_class_improved_error_message(self):
        """Test that set_task_model_class provides helpful error message"""
        class NotTaskModel:
            pass
        
        try:
            set_task_model_class(NotTaskModel)
            assert False, "Should have raised TypeError"
        except TypeError as e:
            error_msg = str(e)
            assert "must be a subclass of TaskModel" in error_msg
            assert "Please ensure your custom class inherits from TaskModel" in error_msg
            assert "class MyTaskModel(TaskModel):" in error_msg
    
    def test_task_model_register_error_message(self):
        """Test that task_model_register provides helpful error message"""
        try:
            @task_model_register()
            class NotTaskModel:
                pass
            assert False, "Should have raised TypeError"
        except TypeError as e:
            error_msg = str(e)
            assert "must be a subclass of TaskModel" in error_msg
            assert "Please ensure your class inherits from TaskModel" in error_msg
    
    def test_custom_task_model_with_fields(self):
        """Test creating and using custom TaskModel with additional fields"""
        @task_model_register()
        class ProjectTaskModel(TaskModel):
            __tablename__ = "apflow_tasks"
            __table_args__ = {'extend_existing': True}
            project_id = Column(String(255), nullable=True)  # Removed index=True to avoid conflicts
            department = Column(String(100), nullable=True)
            priority_level = Column(Integer, default=2)
        
        # Verify model class
        model_class = get_task_model_class()
        assert model_class == ProjectTaskModel
        
        # Verify custom fields exist
        assert hasattr(model_class, 'project_id')
        assert hasattr(model_class, 'department')
        assert hasattr(model_class, 'priority_level')
        
        # Verify it still has base TaskModel fields
        assert hasattr(model_class, 'id')
        assert hasattr(model_class, 'name')
        assert hasattr(model_class, 'status')
        assert hasattr(model_class, 'inputs')
        assert hasattr(model_class, 'result')
    
    def test_set_task_model_class_none(self):
        """Test that set_task_model_class(None) resets to default"""
        # Set custom model
        @task_model_register()
        class CustomTaskModel(TaskModel):
            __tablename__ = "apflow_tasks"
            __table_args__ = {'extend_existing': True}
            pass
        
        assert get_task_model_class() == CustomTaskModel
        
        # Reset to None (should use default)
        set_task_model_class(None)
        assert get_task_model_class() == TaskModel
    
    def test_get_task_model_class_default(self):
        """Test that get_task_model_class returns default when not set"""
        clear_config()
        model_class = get_task_model_class()
        assert model_class == TaskModel


class TestCustomTaskModelWithRepository:
    """Test custom TaskModel with TaskRepository"""
    
    @pytest.mark.asyncio
    async def test_custom_task_model(self, sync_db_session):
        """
        Test creating tasks with custom TaskModel that has additional fields
        
        Note: This test requires dropping and recreating tables to add custom columns.
        In production, this would be done via Alembic migrations.
        
        Since SQLAlchemy's metadata.tables is immutable, we use a new Base instance
        for the custom model to avoid conflicts.
        """
        import uuid
        from aipartnerupflow.core.storage.sqlalchemy.models import TASK_TABLE_NAME
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from sqlalchemy import (
            Column, String, Integer, JSON, Text, Numeric, 
            Boolean, DateTime, func
        )
        from sqlalchemy import text
        from sqlalchemy.orm import declarative_base
        
        # Drop existing table using raw SQL first
        try:
            sync_db_session.execute(text(f"DROP TABLE IF EXISTS {TASK_TABLE_NAME}"))
            sync_db_session.commit()
        except Exception:
            sync_db_session.rollback()
        
        # Create a new Base instance for the custom model to avoid metadata conflicts
        CustomBase = declarative_base()
        
        # Define custom TaskModel with project_id field using the new Base
        class CustomTaskModel(CustomBase):
            __tablename__ = TASK_TABLE_NAME
            
            # Copy all columns from TaskModel (including id default generator)
            id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
            parent_id = Column(String(255), nullable=True, index=True)
            user_id = Column(String(255), nullable=True, index=True)
            name = Column(String(100), nullable=False, index=True)
            status = Column(String(50), default="pending")
            priority = Column(Integer, default=1)
            dependencies = Column(JSON, nullable=True)
            inputs = Column(JSON, nullable=True)
            params = Column(JSON, nullable=True)
            result = Column(JSON, nullable=True)
            error = Column(Text, nullable=True)
            schemas = Column(JSON, nullable=True)
            progress = Column(Numeric(3, 2), default=0.0)
            created_at = Column(DateTime(timezone=True), server_default=func.now())
            started_at = Column(DateTime(timezone=True), nullable=True)
            updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
            completed_at = Column(DateTime(timezone=True), nullable=True)
            has_children = Column(Boolean, default=False)
            
            # Add custom field
            project_id = Column(String(255), nullable=True)
        
        # Create table with custom model
        CustomBase.metadata.create_all(sync_db_session.bind)
        
        repo = TaskRepository(sync_db_session, task_model_class=CustomTaskModel)
        
        # Create task with custom field
        task = await repo.create_task(
            name="Project Task",
            user_id="test-user",
            project_id="proj-123"  # Custom field
        )
        
        assert task.project_id == "proj-123"
        assert isinstance(task, CustomTaskModel)


class TestCustomTaskModelWithAgentExecutor:
    """Test custom TaskModel with AgentExecutor and hooks"""
    
    @pytest.fixture
    def mock_event_queue(self):
        """Create mock event queue"""
        from unittest.mock import AsyncMock
        from a2a.server.events import EventQueue
        event_queue = AsyncMock(spec=EventQueue)
        event_queue.enqueue_event = AsyncMock()
        return event_queue
    
    def _create_request_context(self, tasks: list, metadata: dict = None):
        """Helper to create RequestContext with tasks array"""
        from unittest.mock import Mock
        from a2a.server.agent_execution import RequestContext
        from a2a.types import Message, DataPart
        import uuid
        
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
    @pytest.mark.integration
    async def test_execute_with_custom_task_model_and_hooks(self, use_test_db_session, sync_db_session, mock_event_queue):
        """
        Integration test: Real task execution with custom TaskModel and decorator-based hooks
        
        This test demonstrates the complete decorator workflow:
        1. Custom TaskModel with additional fields (project_id)
        2. set_task_model_class() to configure custom model
        3. @register_pre_hook to modify task data before execution
        4. @register_post_hook to process results after execution
        
        This verifies that all decorator features work together in a real execution environment.
        """
        # Clear any existing configuration
        from aipartnerupflow import clear_config, set_task_model_class
        clear_config()
        
        # ========================================================================
        # Step 1: Define and set custom TaskModel with additional field
        # ========================================================================
        from sqlalchemy import Column, String, text
        from aipartnerupflow.core.storage.sqlalchemy.models import TASK_TABLE_NAME, TaskModel
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        # Add project_id column to existing table (if not exists)
        # In production, this would be done via Alembic migrations
        try:
            sync_db_session.execute(text(f"ALTER TABLE {TASK_TABLE_NAME} ADD COLUMN project_id VARCHAR(100)"))
            sync_db_session.commit()
        except Exception:
            # Column might already exist, ignore
            sync_db_session.rollback()
        
        # Inherit from TaskModel to satisfy registry check
        # Define custom TaskModel that inherits from TaskModel
        # This satisfies the registry's issubclass check
        class CustomTaskModel(TaskModel):
            """Custom TaskModel with project_id field"""
            __tablename__ = TASK_TABLE_NAME
            __table_args__ = {'extend_existing': True}  # Allow extending existing table
            
            # Custom field
            project_id = Column(String(100), nullable=True, comment="Project ID for task grouping")
            
            def to_dict(self):
                """Convert to dictionary including custom field"""
                base_dict = super().to_dict()
                base_dict["project_id"] = self.project_id
                return base_dict
        
        # ========================================================================
        # Step 2: Register hooks using decorators
        # ========================================================================
        pre_hook_calls = []
        post_hook_calls = []
        
        from aipartnerupflow import register_pre_hook, register_post_hook
        
        @register_pre_hook
        async def custom_pre_hook(task):
            """Pre-hook that adds project context and modifies inputs"""
            pre_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "has_project_id": hasattr(task, "project_id"),
                "project_id": getattr(task, "project_id", None),
                "original_input": dict(task.inputs) if task.inputs else {},
            })
            
            # Modify inputs to add hook-generated data
            if task.inputs is None:
                task.inputs = {}
            task.inputs["_pre_hook_executed"] = True
            task.inputs["_hook_timestamp"] = "2024-01-01T00:00:00Z"
            
            # If project_id is set, add it to inputs for executor
            if hasattr(task, "project_id") and task.project_id:
                task.inputs["_project_id"] = task.project_id
        
        @register_post_hook
        async def custom_post_hook(task, inputs, result):
            """Post-hook that validates custom fields and processes results"""
            post_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "task_status": task.status,
                "has_project_id": hasattr(task, "project_id"),
                "project_id": getattr(task, "project_id", None),
                "inputs_keys": list(inputs.keys()) if inputs else [],
                "has_pre_hook_marker": inputs.get("_pre_hook_executed", False) if inputs else False,
                "result_type": type(result).__name__,
                "result_keys": list(result.keys()) if isinstance(result, dict) else None,
            })
        
        # Set custom TaskModel using decorator API (after hooks are registered)
        set_task_model_class(CustomTaskModel)
        
        # Create executor AFTER registering hooks and setting custom TaskModel
        # In production, hooks and TaskModel are registered at application startup before executor creation
        # For testing, we register hooks and set TaskModel first, then create executor to match production pattern
        # Since TaskExecutor is singleton, we need to refresh its config to pick up newly registered hooks and model
        from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
        from aipartnerupflow.core.execution.task_executor import TaskExecutor
        from unittest.mock import patch
        
        executor = AIPartnerUpFlowAgentExecutor()
        # Refresh TaskExecutor singleton's hooks and model to pick up newly registered values
        # This is only needed for testing; in production, hooks and model are registered before executor creation
        TaskExecutor().refresh_config()
        
        # ========================================================================
        # Step 3: Create and execute task with custom model
        # ========================================================================
        user_id = "test-user-custom"
        project_id = "test-project-123"
        
        # Create task using repository with custom model (to set project_id)
        # Then execute via executor using require_existing_tasks=True mode
        repo = TaskRepository(sync_db_session, task_model_class=CustomTaskModel)
        
        # Create task with custom field first (using kwargs for id)
        task = await repo.create_task(
            name="Custom Task with Project",
            user_id=user_id,
            priority=1,
            schemas={
                "method": "system_info_executor"  # Executor id
            },
            inputs={
                "resource": "cpu"
            },
            id="custom-task-1",  # Custom field via kwargs
            project_id=project_id  # Custom field
        )
        
        # Verify task was created with custom field
        assert task.id == "custom-task-1"
        assert task.project_id == project_id
        
        # Now execute the task via executor using require_existing_tasks=True
        # This mode loads existing tasks from database instead of creating new ones
        tasks = [
            {
                "id": "custom-task-1",  # Use same ID as created task
                # Only need id for require_existing_tasks=True mode
            }
        ]
        
        # Set require_existing_tasks=True in metadata to use existing task mode
        context = self._create_request_context(tasks, metadata={"require_existing_tasks": True})
        
        # Execute with real database and custom model
        with patch('aipartnerupflow.api.a2a.agent_executor.get_default_session') as mock_get_session_agent:
            mock_get_session_agent.return_value = sync_db_session
            
            # Execute using executor with custom config
            result = await executor.execute(context, mock_event_queue)
            
            # ========================================================================
            # Step 4: Verify execution results
            # ========================================================================
            assert result is not None
            # Result format depends on execution mode, check if it's a dict with status
            if isinstance(result, dict) and "status" in result:
                assert result["status"] == "completed", f"Expected completed, got {result.get('status')}"
            # Also verify via database
            
            # Reload task from database to verify custom field persisted
            repo = TaskRepository(sync_db_session, task_model_class=CustomTaskModel)
            task_after = await repo.get_task_by_id("custom-task-1")
            assert task_after is not None
            assert task_after.status == "completed"
            assert task_after.result is not None
            
            # Verify custom field was saved and persisted
            assert hasattr(task_after, "project_id"), "Custom TaskModel should have project_id field"
            assert task_after.project_id == project_id, f"Expected project_id={project_id}, got {task_after.project_id}"
            
            # ========================================================================
            # Step 5: Verify hooks were called correctly
            # ========================================================================
            # Verify pre-hook was called
            assert len(pre_hook_calls) == 1, f"Expected 1 pre-hook call, got {len(pre_hook_calls)}"
            pre_call = pre_hook_calls[0]
            assert pre_call["task_id"] == "custom-task-1"
            assert pre_call["has_project_id"] is True, "Pre-hook should see custom field"
            assert pre_call["project_id"] == project_id
            
            # Verify pre-hook modified inputs
            assert pre_call["original_input"].get("resource") == "cpu"
            
            # Verify post-hook was called
            assert len(post_hook_calls) == 1, f"Expected 1 post-hook call, got {len(post_hook_calls)}"
            post_call = post_hook_calls[0]
            assert post_call["task_id"] == "custom-task-1"
            assert post_call["task_status"] == "completed"
            assert post_call["has_project_id"] is True, "Post-hook should see custom field"
            assert post_call["project_id"] == project_id
            
            # Verify post-hook received modified inputs from pre-hook
            assert post_call["has_pre_hook_marker"] is True, "Post-hook should see pre-hook modifications"
            assert "_pre_hook_executed" in post_call["inputs_keys"]
            assert "_hook_timestamp" in post_call["inputs_keys"]
            
            # Verify post-hook received result
            assert post_call["result_type"] == "dict"
            assert post_call["result_keys"] is not None
            assert len(post_call["result_keys"]) > 0
            
            # ========================================================================
            # Step 6: Verify data flow: inputs -> pre-hook -> execution -> post-hook
            # ========================================================================
            # The inputs should have been modified by pre-hook before execution
            # We can verify this by checking the task's inputs (if persisted)
            # or by checking what post-hook received
            
            import json
            from aipartnerupflow.core.utils.logger import get_logger
            logger = get_logger(__name__)
            
            logger.info("==Custom TaskModel Test Results==")
            logger.info(f"Pre-hook calls: {json.dumps(pre_hook_calls, indent=2)}")
            logger.info(f"Post-hook calls: {json.dumps(post_hook_calls, indent=2)}")
            logger.info(f"Task project_id: {task_after.project_id}")
            logger.info(f"Task result keys: {list(task_after.result.keys()) if isinstance(task_after.result, dict) else 'N/A'}")
            
            # Final verification: All decorator features work together
            assert task_after.project_id == project_id, "Custom TaskModel field should be preserved"
            assert pre_call["has_project_id"] is True, "Pre-hook should access custom field"
            assert post_call["has_project_id"] is True, "Post-hook should access custom field"
            assert post_call["has_pre_hook_marker"] is True, "Pre-hook modifications should be visible to post-hook"
            
            logger.info("✅ All decorator features verified: custom TaskModel, pre-hook, post-hook")
