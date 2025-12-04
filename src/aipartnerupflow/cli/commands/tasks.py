"""
Tasks command for managing and querying tasks
"""
import typer
import json
import time
import asyncio
from pathlib import Path
from typing import Optional, List, Coroutine, Any
from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.core.utils.helpers import tree_node_to_dict
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout

logger = get_logger(__name__)

app = typer.Typer(name="tasks", help="Manage and query tasks")
console = Console()


def run_async_safe(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Safely run async coroutine, handling both cases:
    - No event loop running: use asyncio.run()
    - Event loop already running: create task and wait
    
    This is needed for CLI commands that may be called from test environments
    where an event loop is already running.
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Result of the coroutine
    """
    try:
        # Check if event loop is already running
        loop = asyncio.get_running_loop()
        # Event loop is running, we need to run in a new thread or use nest_asyncio
        # For CLI commands, we'll use a workaround: create a new event loop in a thread
        import concurrent.futures
        import threading
        
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        return asyncio.run(coro)


@app.command()
def list(
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="Filter by user ID"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of tasks to return"),
):
    """
    List currently running tasks
    
    Args:
        user_id: Optional user ID filter
        limit: Maximum number of tasks to return
    """
    try:
        task_executor = TaskExecutor()
        running_task_ids = task_executor.get_all_running_tasks()
        
        if not running_task_ids:
            typer.echo("No running tasks found")
            return
        
        typer.echo(f"Found {len(running_task_ids)} running task(s):")
        typer.echo("")
        
        # Get task details from database
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        tasks_info = []
        import asyncio
        
        # Helper function to get task (handles both sync and async)
        async def get_task_safe(task_id: str):
            try:
                return await task_repository.get_task_by_id(task_id)
            except Exception as e:
                logger.warning(f"Failed to get task {task_id}: {str(e)}")
                return None
        
        for task_id in running_task_ids[:limit]:
            try:
                # TaskRepository.get_task_by_id is async, but works with sync sessions too
                task = run_async_safe(get_task_safe(task_id))
                if task:
                    # Apply user_id filter if specified
                    if user_id and task.user_id != user_id:
                        continue
                    
                    # Use task.to_dict() to match API format
                    task_dict = task.to_dict()
                    tasks_info.append(task_dict)
                else:
                    # Task not found in database
                    tasks_info.append({
                        "id": task_id,
                        "task_id": task_id,  # Keep for backward compatibility
                        "name": "Unknown",
                        "status": "unknown",
                        "progress": 0.0,
                        "user_id": None,
                        "created_at": None,
                    })
            except Exception as e:
                logger.warning(f"Failed to get task {task_id}: {str(e)}")
                tasks_info.append({
                    "id": task_id,
                    "task_id": task_id,  # Keep for backward compatibility
                    "name": "Unknown",
                    "status": "unknown",
                    "progress": 0.0,
                    "user_id": None,
                    "created_at": None,
                })
        
        # Display tasks
        if tasks_info:
            typer.echo(json.dumps(tasks_info, indent=2))
        else:
            typer.echo("No tasks found matching the criteria")
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def status(
    task_ids: List[str] = typer.Argument(..., help="Task IDs to check status for"),
):
    """
    Get status of one or more tasks
    
    Args:
        task_ids: List of task IDs to check
    """
    try:
        task_executor = TaskExecutor()
        
        # Get task details from database
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        statuses = []
        import asyncio
        
        # Helper function to get task (handles both sync and async)
        async def get_task_safe(task_id: str):
            try:
                return await task_repository.get_task_by_id(task_id)
            except Exception as e:
                logger.warning(f"Failed to get task {task_id}: {str(e)}")
                return None
        
        for task_id in task_ids:
            is_running = task_executor.is_task_running(task_id)
            
            try:
                task = run_async_safe(get_task_safe(task_id))
                
                if task:
                    # Match API format: (task_id, context_id, status, progress, error, is_running, started_at, updated_at)
                    # Keep name field for CLI display convenience
                    statuses.append({
                        "task_id": task.id,
                        "context_id": task.id,  # For API compatibility
                        "name": task.name,  # Keep for CLI display
                        "status": task.status,
                        "progress": float(task.progress) if task.progress else 0.0,
                        "is_running": is_running,
                        "error": task.error,
                        "started_at": task.started_at.isoformat() if task.started_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                    })
                else:
                    # Task not found in database, but check if it's running in memory
                    if is_running:
                        statuses.append({
                            "task_id": task_id,
                            "context_id": task_id,  # For API compatibility
                            "name": "Unknown",
                            "status": "in_progress",
                            "progress": 0.0,
                            "is_running": True,
                            "error": None,
                            "started_at": None,
                            "updated_at": None,
                        })
                    else:
                        statuses.append({
                            "task_id": task_id,
                            "context_id": task_id,  # For API compatibility
                            "name": "Unknown",
                            "status": "not_found",
                            "progress": 0.0,
                            "is_running": False,
                            "error": None,
                            "started_at": None,
                            "updated_at": None,
                        })
            except Exception as e:
                logger.warning(f"Failed to get task {task_id}: {str(e)}")
                statuses.append({
                    "task_id": task_id,
                    "context_id": task_id,  # For API compatibility
                    "name": "Unknown",
                    "status": "error",
                    "progress": 0.0,
                    "is_running": is_running,
                    "error": str(e),
                    "started_at": None,
                    "updated_at": None,
                })
        
        typer.echo(json.dumps(statuses, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def count(
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="Filter by user ID"),
):
    """
    Get count of currently running tasks
    
    Args:
        user_id: Optional user ID filter
    """
    try:
        task_executor = TaskExecutor()
        
        if user_id:
            # Filter by user_id: get all running tasks and filter by user_id
            running_task_ids = task_executor.get_all_running_tasks()
            if not running_task_ids:
                typer.echo(json.dumps({"count": 0, "user_id": user_id}))
                return
            
            # Get database session to check user_id
            from aipartnerupflow.core.storage import get_default_session
            from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
            from aipartnerupflow.core.config import get_task_model_class
            
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
            
            count = 0
            import asyncio
            
            # Helper function to get task (handles both sync and async)
            async def get_task_safe(task_id: str):
                try:
                    return await task_repository.get_task_by_id(task_id)
                except Exception:
                    return None
            
            for task_id in running_task_ids:
                try:
                    task = run_async_safe(get_task_safe(task_id))
                    if task and task.user_id == user_id:
                        count += 1
                except Exception:
                    continue
            
            typer.echo(json.dumps({"count": count, "user_id": user_id}))
        else:
            # No user_id filter, return total count from memory
            count = task_executor.get_running_tasks_count()
            typer.echo(json.dumps({"count": count}))
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def cancel(
    task_ids: List[str] = typer.Argument(..., help="Task IDs to cancel"),
    force: bool = typer.Option(False, "--force", "-f", help="Force cancellation (immediate stop)"),
):
    """
    Cancel one or more running tasks
    
    This calls TaskExecutor.cancel_task() which:
    1. Calls executor.cancel() if executor supports cancellation
    2. Updates database with cancelled status and token_usage
    
    Args:
        task_ids: List of task IDs to cancel
        force: If True, force immediate cancellation (may lose data)
    """
    try:
        task_executor = TaskExecutor()
        
        import asyncio
        
        results = []
        for task_id in task_ids:
            try:
                # Prepare error message
                error_message = "Cancelled by user" if not force else "Force cancelled by user"
                
                # Call TaskExecutor.cancel_task() which handles:
                # 1. Calling executor.cancel() if executor supports cancellation
                # 2. Updating database with cancelled status and token_usage
                cancel_result = run_async_safe(task_executor.cancel_task(task_id, error_message))
                
                # Add task_id to result
                cancel_result["task_id"] = task_id
                cancel_result["force"] = force
                
                results.append(cancel_result)
                    
            except Exception as e:
                logger.error(f"Error cancelling task {task_id}: {str(e)}", exc_info=True)
                results.append({
                    "task_id": task_id,
                    "status": "error",
                    "error": str(e)
                })
        
        # Output results
        typer.echo(json.dumps(results, indent=2))
        
        # Check if any cancellation failed
        # Note: "failed" status for already completed/cancelled tasks is acceptable (not an error)
        # Only treat actual errors as failures
        failed = any(
            r.get("status") == "error" or 
            (r.get("status") == "failed" and "not found" in r.get("message", "").lower())
            for r in results
        )
        if failed:
            raise typer.Exit(1)
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error cancelling tasks")
        raise typer.Exit(1)


@app.command()
def copy(
    task_id: str = typer.Argument(..., help="Task ID to copy"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path for copied task tree"),
    children: bool = typer.Option(False, "--children", help="Also copy each direct child task with its dependencies"),
):
    """
    Create a copy of a task tree for re-execution
    
    This command creates a new copy of an existing task tree, including:
    - The original task and all its children
    - All tasks that depend on the original task (including transitive dependencies)
    - Automatically handles failed leaf nodes (filters out pending dependents)
    
    When --children is used, each direct child task is also copied with its dependencies.
    Tasks that depend on multiple copied tasks are only copied once (deduplication).
    
    The copied tasks are linked to the original task via original_task_id field.
    All execution-specific fields (status, result, progress, etc.) are reset to initial values.
    
    Args:
        task_id: ID of the task to copy (can be root or any task in tree)
        output: Optional output file path to save the copied task tree JSON
        children: If True, also copy each direct child task with its dependencies
    """
    try:
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        from aipartnerupflow.core.execution.task_creator import TaskCreator
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        # Get original task
        async def get_original_task():
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            return task
        
        original_task = run_async_safe(get_original_task())
        
        # Create TaskCreator and copy task
        task_creator = TaskCreator(db_session)
        
        async def copy_task():
            return await task_creator.create_task_copy(original_task, children=children)
        
        new_tree = run_async_safe(copy_task())
        
        # Convert task tree to dictionary format
        result = tree_node_to_dict(new_tree)
        
        # Output result
        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2)
            typer.echo(f"Copied task tree saved to {output}")
        else:
            typer.echo(json.dumps(result, indent=2))
        
        typer.echo(f"\n✅ Successfully copied task {task_id} to new task {new_tree.task.id}")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error copying task")
        raise typer.Exit(1)


@app.command()
def get(
    task_id: str = typer.Argument(..., help="Task ID to get"),
):
    """
    Get task by ID (equivalent to tasks.get API)
    
    Args:
        task_id: Task ID to retrieve
    """
    try:
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def get_task():
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            return task.to_dict()
        
        task_dict = run_async_safe(get_task())
        typer.echo(json.dumps(task_dict, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error getting task")
        raise typer.Exit(1)


@app.command()
def create(
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="JSON file containing task(s) definition"),
    stdin: bool = typer.Option(False, "--stdin", help="Read from stdin instead of file"),
):
    """
    Create task tree from JSON file or stdin (equivalent to tasks.create API)
    
    Args:
        file: JSON file containing task(s) definition
        stdin: Read from stdin instead of file
    """
    try:
        import sys
        
        # Read task data
        if stdin:
            task_data = json.load(sys.stdin)
        elif file:
            with open(file, 'r') as f:
                task_data = json.load(f)
        else:
            typer.echo("Error: Either --file or --stdin must be specified", err=True)
            raise typer.Exit(1)
        
        # Convert to tasks array format if needed
        if isinstance(task_data, dict):
            tasks_array = [task_data]
        elif isinstance(task_data, list):
            tasks_array = task_data
        else:
            raise ValueError("Task data must be a dict (single task) or list (tasks array)")
        
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.execution.task_creator import TaskCreator
        
        db_session = get_default_session()
        task_creator = TaskCreator(db_session)
        
        async def create_task():
            return await task_creator.create_task_tree_from_array(tasks=tasks_array)
        
        task_tree = run_async_safe(create_task())
        result = tree_node_to_dict(task_tree)
        
        typer.echo(json.dumps(result, indent=2))
        typer.echo(f"\n✅ Successfully created task tree: root task {task_tree.task.id}")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error creating task")
        raise typer.Exit(1)


@app.command()
def update(
    task_id: str = typer.Argument(..., help="Task ID to update"),
    name: Optional[str] = typer.Option(None, "--name", help="Update task name"),
    status: Optional[str] = typer.Option(None, "--status", help="Update task status"),
    progress: Optional[float] = typer.Option(None, "--progress", help="Update task progress (0.0-1.0)"),
    error: Optional[str] = typer.Option(None, "--error", help="Update task error message"),
    result: Optional[str] = typer.Option(None, "--result", help="Update task result (JSON string)"),
    priority: Optional[int] = typer.Option(None, "--priority", help="Update task priority"),
    inputs: Optional[str] = typer.Option(None, "--inputs", help="Update task inputs (JSON string)"),
    params: Optional[str] = typer.Option(None, "--params", help="Update task params (JSON string)"),
    schemas: Optional[str] = typer.Option(None, "--schemas", help="Update task schemas (JSON string)"),
):
    """
    Update task fields (equivalent to tasks.update API)
    
    Args:
        task_id: Task ID to update
        name: Update task name
        status: Update task status
        progress: Update task progress (0.0-1.0)
        error: Update task error message
        result: Update task result (JSON string)
        priority: Update task priority
        inputs: Update task inputs (JSON string)
        params: Update task params (JSON string)
        schemas: Update task schemas (JSON string)
    """
    try:
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        # Build update params
        update_params = {}
        if name is not None:
            update_params["name"] = name
        if status is not None:
            update_params["status"] = status
        if progress is not None:
            update_params["progress"] = progress
        if error is not None:
            update_params["error"] = error
        if result is not None:
            update_params["result"] = json.loads(result)
        if priority is not None:
            update_params["priority"] = priority
        if inputs is not None:
            update_params["inputs"] = json.loads(inputs)
        if params is not None:
            update_params["params"] = json.loads(params)
        if schemas is not None:
            update_params["schemas"] = json.loads(schemas)
        
        if not update_params:
            typer.echo("Error: At least one field must be specified for update", err=True)
            raise typer.Exit(1)
        
        async def update_task():
            # Get task first
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Update status-related fields if status is provided
            if "status" in update_params:
                await task_repository.update_task_status(
                    task_id=task_id,
                    status=update_params["status"],
                    error=update_params.get("error"),
                    result=update_params.get("result"),
                    progress=update_params.get("progress"),
                )
            else:
                # Update individual fields
                if "error" in update_params:
                    await task_repository.update_task_status(
                        task_id=task_id,
                        status=task.status,
                        error=update_params["error"]
                    )
                if "result" in update_params:
                    await task_repository.update_task_status(
                        task_id=task_id,
                        status=task.status,
                        result=update_params["result"]
                    )
                if "progress" in update_params:
                    await task_repository.update_task_status(
                        task_id=task_id,
                        status=task.status,
                        progress=update_params["progress"]
                    )
            
            # Update other fields
            if "name" in update_params:
                await task_repository.update_task_name(task_id, update_params["name"])
            if "priority" in update_params:
                await task_repository.update_task_priority(task_id, update_params["priority"])
            if "inputs" in update_params:
                await task_repository.update_task_inputs(task_id, update_params["inputs"])
            if "params" in update_params:
                await task_repository.update_task_params(task_id, update_params["params"])
            if "schemas" in update_params:
                await task_repository.update_task_schemas(task_id, update_params["schemas"])
            
            # Get updated task
            updated_task = await task_repository.get_task_by_id(task_id)
            if not updated_task:
                raise ValueError(f"Task {task_id} not found after update")
            
            return updated_task.to_dict()
        
        task_dict = run_async_safe(update_task())
        typer.echo(json.dumps(task_dict, indent=2))
        typer.echo(f"\n✅ Successfully updated task {task_id}")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error updating task")
        raise typer.Exit(1)


@app.command()
def delete(
    task_id: str = typer.Argument(..., help="Task ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion (if needed)"),
):
    """
    Delete task (equivalent to tasks.delete API)
    
    Args:
        task_id: Task ID to delete
        force: Force deletion (if needed)
    """
    try:
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def delete_task():
            # Get task first to check if exists
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Get all children recursively
            all_children = await task_repository.get_all_children_recursive(task_id)
            
            # Check if all tasks are pending
            all_tasks_to_check = [task] + all_children
            non_pending = [t for t in all_tasks_to_check if t.status != "pending"]
            
            # Check for dependent tasks
            dependent_tasks = await task_repository.find_dependent_tasks(task_id)
            
            # Build error message if deletion is not allowed
            error_parts = []
            if non_pending:
                non_pending_children = [t for t in non_pending if t.id != task_id]
                if non_pending_children:
                    children_info = ", ".join([f"{t.id}: {t.status}" for t in non_pending_children])
                    error_parts.append(f"task has {len(non_pending_children)} non-pending children: [{children_info}]")
                if any(t.id == task_id for t in non_pending):
                    main_task_status = next(t.status for t in non_pending if t.id == task_id)
                    error_parts.append(f"task status is '{main_task_status}' (must be 'pending')")
            
            if dependent_tasks:
                dependent_task_ids = [t.id for t in dependent_tasks]
                error_parts.append(f"{len(dependent_tasks)} tasks depend on this task: [{', '.join(dependent_task_ids)}]")
            
            if error_parts and not force:
                error_message = "Cannot delete task: " + "; ".join(error_parts)
                raise ValueError(error_message)
            
            # Delete all tasks (children first, then parent)
            deleted_count = 0
            for child in all_children:
                success = await task_repository.delete_task(child.id)
                if success:
                    deleted_count += 1
            
            # Delete the main task
            success = await task_repository.delete_task(task_id)
            if success:
                deleted_count += 1
            
            return {
                "success": True,
                "task_id": task_id,
                "deleted_count": deleted_count,
                "children_deleted": len(all_children)
            }
        
        result = run_async_safe(delete_task())
        typer.echo(json.dumps(result, indent=2))
        typer.echo(f"\n✅ Successfully deleted task {task_id} and {result['children_deleted']} children")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error deleting task")
        raise typer.Exit(1)


@app.command()
def tree(
    task_id: str = typer.Argument(..., help="Task ID to get tree for"),
):
    """
    Get task tree structure (equivalent to tasks.tree API)
    
    Args:
        task_id: Task ID (root or any task in tree)
    """
    try:
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def get_tree():
            # Get task
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # If task has parent, find root first
            root_task = await task_repository.get_root_task(task)
            
            # Build task tree
            task_tree_node = await task_repository.build_task_tree(root_task)
            
            # Convert TaskTreeNode to dictionary format
            return tree_node_to_dict(task_tree_node)
        
        result = run_async_safe(get_tree())
        typer.echo(json.dumps(result, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error getting task tree")
        raise typer.Exit(1)


@app.command()
def children(
    parent_id: Optional[str] = typer.Option(None, "--parent-id", "-p", help="Parent task ID"),
    task_id: Optional[str] = typer.Option(None, "--task-id", "-t", help="Task ID (alternative to parent-id)"),
):
    """
    Get child tasks (equivalent to tasks.children API)
    
    Args:
        parent_id: Parent task ID
        task_id: Task ID (alternative to parent-id)
    """
    try:
        parent_task_id = parent_id or task_id
        if not parent_task_id:
            typer.echo("Error: Either --parent-id or --task-id must be specified", err=True)
            raise typer.Exit(1)
        
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def get_children():
            # Get parent task to verify it exists
            parent_task = await task_repository.get_task_by_id(parent_task_id)
            if not parent_task:
                raise ValueError(f"Parent task {parent_task_id} not found")
            
            # Get child tasks
            children = await task_repository.get_child_tasks_by_parent_id(parent_task_id)
            
            # Convert to dictionaries
            return [child.to_dict() for child in children]
        
        result = run_async_safe(get_children())
        typer.echo(json.dumps(result, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error getting child tasks")
        raise typer.Exit(1)


@app.command()
def all(
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="Filter by user ID"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    root_only: bool = typer.Option(True, "--root-only/--all-tasks", help="Only show root tasks (default: True)"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of tasks to return"),
    offset: int = typer.Option(0, "--offset", "-o", help="Pagination offset"),
):
    """
    List all tasks from database, not just running ones (equivalent to tasks.list API)
    
    Args:
        user_id: Filter by user ID
        status: Filter by status
        root_only: Only show root tasks (default: True)
        limit: Maximum number of tasks to return
        offset: Pagination offset
    """
    try:
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def get_all_tasks():
            # Query tasks with filters
            parent_id_filter = "" if root_only else None
            tasks = await task_repository.query_tasks(
                user_id=user_id,
                status=status,
                parent_id=parent_id_filter,
                limit=limit,
                offset=offset,
                order_by="created_at",
                order_desc=True
            )
            
            # Convert to dictionaries and check if tasks have children
            task_dicts = []
            for task in tasks:
                task_dict = task.to_dict()
                
                # Check if task has children (if has_children field is not set or False, check database)
                if not task_dict.get("has_children"):
                    children = await task_repository.get_child_tasks_by_parent_id(task.id)
                    task_dict["has_children"] = len(children) > 0
                
                task_dicts.append(task_dict)
            
            return task_dicts
        
        tasks = run_async_safe(get_all_tasks())
        typer.echo(json.dumps(tasks, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error listing all tasks")
        raise typer.Exit(1)


@app.command()
def watch(
    task_id: Optional[str] = typer.Option(None, "--task-id", "-t", help="Watch specific task ID"),
    interval: float = typer.Option(1.0, "--interval", "-i", help="Update interval in seconds"),
    all_tasks: bool = typer.Option(False, "--all", "-a", help="Watch all running tasks"),
):
    """
    Watch task status in real-time (interactive mode)
    
    This command provides real-time monitoring of task status updates.
    Press Ctrl+C to stop watching.
    
    Args:
        task_id: Specific task ID to watch (optional)
        interval: Update interval in seconds (default: 1.0)
        all_tasks: Watch all running tasks instead of specific task
    """
    try:
        task_executor = TaskExecutor()
        
        # Get database session
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        import asyncio
        
        # Helper function to get task
        async def get_task_safe(task_id: str):
            try:
                return await task_repository.get_task_by_id(task_id)
            except Exception:
                return None
        
        def create_status_table(task_ids: List[str]) -> Table:
            """Create a table showing task statuses"""
            table = Table(title="Task Status Monitor")
            table.add_column("Task ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Progress", style="yellow")
            table.add_column("Running", style="blue")
            
            for tid in task_ids:
                is_running = task_executor.is_task_running(tid)
                task = run_async_safe(get_task_safe(tid))
                
                if task:
                    status_style = {
                        "completed": "green",
                        "failed": "red",
                        "cancelled": "yellow",
                        "in_progress": "blue",
                        "pending": "dim"
                    }.get(task.status, "white")
                    
                    progress_str = f"{float(task.progress) * 100:.1f}%" if task.progress else "0.0%"
                    running_str = "✓" if is_running else "✗"
                    
                    table.add_row(
                        task.id[:8] + "...",
                        task.name[:30] + "..." if len(task.name) > 30 else task.name,
                        f"[{status_style}]{task.status}[/{status_style}]",
                        progress_str,
                        running_str
                    )
                else:
                    table.add_row(
                        tid[:8] + "...",
                        "Unknown",
                        "[dim]unknown[/dim]",
                        "0.0%",
                        "✓" if is_running else "✗"
                    )
            
            return table
        
        # Determine which tasks to watch
        if all_tasks:
            # Watch all running tasks
            task_ids_to_watch = task_executor.get_all_running_tasks()
            if not task_ids_to_watch:
                typer.echo("No running tasks to watch")
                return
        elif task_id:
            # Watch specific task
            task_ids_to_watch = [task_id]
        else:
            typer.echo("Error: Either --task-id or --all must be specified", err=True)
            raise typer.Exit(1)
        
        typer.echo(f"Watching {len(task_ids_to_watch)} task(s). Press Ctrl+C to stop.")
        
        try:
            # Create live display
            with Live(create_status_table(task_ids_to_watch), refresh_per_second=1/interval, console=console) as live:
                while True:
                    time.sleep(interval)
                    live.update(create_status_table(task_ids_to_watch))
                    
                    # Check if all tasks are finished
                    if not all_tasks:
                        # For single task, check if it's finished
                        task = run_async_safe(get_task_safe(task_id))
                        if task and task.status in ["completed", "failed", "cancelled"]:
                            typer.echo(f"\nTask {task_id} finished with status: {task.status}")
                            break
        except KeyboardInterrupt:
            typer.echo("\nStopped watching")
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error watching tasks")
        raise typer.Exit(1)

