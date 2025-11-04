"""
Test TaskRepository functionality

This replaces test_task_model.py as it's more appropriate to test the repository
layer that provides actual functionality, rather than just the model layer.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import Column, String
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository


class TestTaskRepository:
    """Test TaskRepository core functionality"""
    
    @pytest.mark.asyncio
    async def test_create_task_basic(self, sync_db_session):
        """Test creating a basic task"""
        repo = TaskRepository(sync_db_session)
        
        task = await repo.create_task(
            name="Test Task",
            user_id="test-user"
        )
        
        assert task is not None
        assert task.name == "Test Task"
        assert task.user_id == "test-user"
        assert task.status == "pending"
        assert task.priority == 1
        assert task.progress == 0.0
        assert task.id is not None
    
    @pytest.mark.asyncio
    async def test_create_task_with_dependencies(self, sync_db_session):
        """Test creating a task with dependencies"""
        repo = TaskRepository(sync_db_session)
        
        # Create a task that will be a dependency
        dep_task = await repo.create_task(
            name="Dependency Task",
            user_id="test-user"
        )
        
        # Create task with dependency
        task = await repo.create_task(
            name="Test Task",
            user_id="test-user",
            dependencies=[
                {"id": dep_task.id, "required": True}
            ]
        )
        
        assert task.dependencies is not None
        assert len(task.dependencies) == 1
        assert task.dependencies[0]["id"] == dep_task.id
        assert task.dependencies[0]["required"] is True
    
    @pytest.mark.asyncio
    async def test_get_task_by_id(self, sync_db_session):
        """Test retrieving a task by ID"""
        repo = TaskRepository(sync_db_session)
        
        # Create a task
        created_task = await repo.create_task(
            name="Test Task",
            user_id="test-user"
        )
        
        # Retrieve it
        retrieved_task = await repo.get_task_by_id(created_task.id)
        
        assert retrieved_task is not None
        assert retrieved_task.id == created_task.id
        assert retrieved_task.name == "Test Task"
        assert retrieved_task.user_id == "test-user"
    
    @pytest.mark.asyncio
    async def test_get_task_by_id_not_found(self, sync_db_session):
        """Test retrieving a non-existent task"""
        repo = TaskRepository(sync_db_session)
        
        retrieved_task = await repo.get_task_by_id("non-existent-id")
        
        assert retrieved_task is None
    
    @pytest.mark.asyncio
    async def test_get_child_tasks_by_parent_id(self, sync_db_session):
        """Test retrieving child tasks by parent ID"""
        repo = TaskRepository(sync_db_session)
        
        # Create parent task
        parent = await repo.create_task(
            name="Parent Task",
            user_id="test-user"
        )
        
        # Create child tasks
        child1 = await repo.create_task(
            name="Child 1",
            user_id="test-user",
            parent_id=parent.id
        )
        
        child2 = await repo.create_task(
            name="Child 2",
            user_id="test-user",
            parent_id=parent.id
        )
        
        # Retrieve children
        children = await repo.get_child_tasks_by_parent_id(parent.id)
        
        assert len(children) == 2
        child_ids = [c.id for c in children]
        assert child1.id in child_ids
        assert child2.id in child_ids
    
    @pytest.mark.asyncio
    async def test_update_task_status(self, sync_db_session):
        """Test updating task status"""
        repo = TaskRepository(sync_db_session)
        
        # Create a task
        task = await repo.create_task(
            name="Test Task",
            user_id="test-user"
        )
        
        assert task.status == "pending"
        
        # Update status
        await repo.update_task_status(
            task_id=task.id,
            status="completed",
            result={"output": "result"},
            progress=1.0
        )
        
        # Retrieve and verify
        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.status == "completed"
        assert updated_task.result == {"output": "result"}
        assert float(updated_task.progress) == 1.0
    
    @pytest.mark.asyncio
    async def test_update_task_input_data(self, sync_db_session):
        """Test updating task input data"""
        repo = TaskRepository(sync_db_session)
        
        # Create a task
        task = await repo.create_task(
            name="Test Task",
            user_id="test-user",
            input_data={"initial": "data"}
        )
        
        # Update input data
        new_input = {"updated": "data", "url": "https://example.com"}
        await repo.update_task_input_data(task.id, new_input)
        
        # Retrieve and verify
        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.input_data == new_input
    
    @pytest.mark.asyncio
    async def test_get_root_task(self, sync_db_session):
        """Test retrieving root task from a task tree"""
        repo = TaskRepository(sync_db_session)
        
        # Create task tree
        root = await repo.create_task(
            name="Root Task",
            user_id="test-user"
        )
        
        child = await repo.create_task(
            name="Child Task",
            user_id="test-user",
            parent_id=root.id
        )
        
        grandchild = await repo.create_task(
            name="Grandchild Task",
            user_id="test-user",
            parent_id=child.id
        )
        
        # Get root from grandchild (pass task object, not task id)
        retrieved_root = await repo.get_root_task(grandchild)
        
        assert retrieved_root is not None
        assert retrieved_root.id == root.id
    
    @pytest.mark.asyncio
    async def test_custom_task_model(self, sync_db_session):
        """
        Test using custom TaskModel with additional fields
        
        Note: This test requires dropping and recreating tables to add custom columns.
        In production, this would be done via Alembic migrations.
        
        Since SQLAlchemy's metadata.tables is immutable, we use a new Base instance
        for the custom model to avoid conflicts.
        """
        import uuid
        from aipartnerupflow.core.storage.sqlalchemy.models import TASK_TABLE_NAME
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
            input_data = Column(JSON, nullable=True)
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

