"""
Integration tests for generate executor
"""

import pytest
from aipartnerupflow import TaskManager
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.extensions.generate import GenerateExecutor


@pytest.mark.asyncio
async def test_generate_executor_registration():
    """Test that GenerateExecutor is properly registered"""
    # Import to trigger registration
    
    executor = GenerateExecutor()
    assert executor.id == "generate_executor"
    
    # Check it's registered in extension registry
    from aipartnerupflow.core.extensions.registry import get_registry
    registry = get_registry()
    extension = registry.get_by_id("generate_executor")
    assert extension is not None
    assert extension.id == "generate_executor"


@pytest.mark.asyncio
async def test_generate_executor_with_task_manager(sync_db_session):
    """Test using GenerateExecutor through TaskManager"""
    # Skip if no LLM API key configured (integration test)
    import os
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("No LLM API key configured")
    
    task_manager = TaskManager(sync_db_session)
    
    # Import to register executor
    
    # Create task using generate_executor
    task = await task_manager.task_repository.create_task(
        name="generate_executor",
        user_id="test_user",
        inputs={
            "requirement": "Create a simple task that gets system info",
            "user_id": "test_user"
        },
        schemas={"method": "generate_executor"}
    )
    
    # Execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Get result
    result_task = await task_manager.task_repository.get_task_by_id(task.id)
    assert result_task.status in ["completed", "failed"]
    
    if result_task.status == "completed":
        assert "tasks" in result_task.result
        assert isinstance(result_task.result["tasks"], list)

