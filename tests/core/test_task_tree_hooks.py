"""
Test task tree lifecycle hooks functionality
"""
import pytest
from aipartnerupflow import (
    register_task_tree_hook,
    get_task_tree_hooks,
    clear_config,
)
from aipartnerupflow.core.types import TaskTreeNode


class TestTaskTreeHooks:
    """Test task tree lifecycle hooks"""
    
    def setup_method(self):
        """Clear config registry before each test"""
        clear_config()
    
    def test_register_task_tree_hook(self):
        """Test registering task tree hooks"""
        hook_called = []
        
        @register_task_tree_hook("on_tree_created")
        async def on_tree_created(root_task, task_tree):
            hook_called.append(("created", root_task.id))
        
        @register_task_tree_hook("on_tree_started")
        async def on_tree_started(root_task):
            hook_called.append(("started", root_task.id))
        
        @register_task_tree_hook("on_tree_completed")
        async def on_tree_completed(root_task, status):
            hook_called.append(("completed", root_task.id, status))
        
        @register_task_tree_hook("on_tree_failed")
        async def on_tree_failed(root_task, error):
            hook_called.append(("failed", root_task.id, error))
        
        # Verify hooks were registered
        created_hooks = get_task_tree_hooks("on_tree_created")
        started_hooks = get_task_tree_hooks("on_tree_started")
        completed_hooks = get_task_tree_hooks("on_tree_completed")
        failed_hooks = get_task_tree_hooks("on_tree_failed")
        
        assert len(created_hooks) == 1
        assert len(started_hooks) == 1
        assert len(completed_hooks) == 1
        assert len(failed_hooks) == 1
        
        assert created_hooks[0] == on_tree_created
        assert started_hooks[0] == on_tree_started
        assert completed_hooks[0] == on_tree_completed
        assert failed_hooks[0] == on_tree_failed
    
    def test_register_multiple_task_tree_hooks(self):
        """Test registering multiple hooks for the same event"""
        @register_task_tree_hook("on_tree_started")
        async def hook1(root_task):
            pass
        
        @register_task_tree_hook("on_tree_started")
        async def hook2(root_task):
            pass
        
        @register_task_tree_hook("on_tree_started")
        async def hook3(root_task):
            pass
        
        hooks = get_task_tree_hooks("on_tree_started")
        assert len(hooks) == 3
        assert hooks == [hook1, hook2, hook3]
    
    def test_register_task_tree_hook_invalid_type(self):
        """Test that invalid hook type raises error"""
        with pytest.raises(ValueError, match="Invalid hook_type"):
            @register_task_tree_hook("invalid_hook_type")
            async def invalid_hook(root_task):
                pass
    
    def test_sync_task_tree_hook(self):
        """Test registering synchronous task tree hooks"""
        @register_task_tree_hook("on_tree_started")
        def sync_hook(root_task):
            pass
        
        hooks = get_task_tree_hooks("on_tree_started")
        assert len(hooks) == 1
        assert hooks[0] == sync_hook
    
    @pytest.mark.asyncio
    async def test_task_tree_hooks_integration(self, sync_db_session):
        """Test task tree hooks with TaskManager"""
        from aipartnerupflow.core.execution.task_manager import TaskManager
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        
        hook_events = []
        
        @register_task_tree_hook("on_tree_created")
        async def on_tree_created(root_task, task_tree):
            hook_events.append(("created", root_task.id))
        
        @register_task_tree_hook("on_tree_started")
        async def on_tree_started(root_task):
            hook_events.append(("started", root_task.id))
        
        @register_task_tree_hook("on_tree_completed")
        async def on_tree_completed(root_task, status):
            hook_events.append(("completed", root_task.id, status))
        
        # Create a simple task tree
        task_manager = TaskManager(sync_db_session, pre_hooks=[], post_hooks=[])
        task_repository = TaskRepository(sync_db_session)
        
        # Create a root task
        root_task = await task_repository.create_task(
            name="test_task",
            user_id="test_user",
            inputs={"test": "data"},
            schemas={"method": "system_info_executor"}
        )
        
        task_tree = TaskTreeNode(root_task)
        
        # Execute task tree (this should trigger hooks)
        # Note: This will fail if executor is not registered, but hooks should still be called
        try:
            await task_manager.distribute_task_tree(task_tree)
        except Exception:
            # Expected if executor not registered, but hooks should have been called
            pass
        
        # Verify hooks were called
        assert len(hook_events) >= 2  # At least created and started should be called
        assert hook_events[0][0] == "created"
        assert hook_events[1][0] == "started"

