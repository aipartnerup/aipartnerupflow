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

logger = get_logger(__name__)

app = typer.Typer(name="tasks", help="Manage and query tasks")
console = Console()


def run_async_safe(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Safely run async coroutine in CLI context.
    
    Handles the case where asyncpg connections need to be created and destroyed
    within the same event loop. This ensures database connections don't get
    bound to closed event loops.
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Result of the coroutine
    """
    try:
        # Check if event loop is already running
        loop = asyncio.get_running_loop()
        # Event loop is running (e.g., in test environment), use nest_asyncio
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        # This creates and closes an event loop for the entire coroutine operation
        return asyncio.run(coro)





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
    root_only: bool = typer.Option(False, "--root-only", "-r", help="Count only root tasks (task trees)"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: json or table"),
):
    """
    Get count of tasks from database, grouped by status
    
    Examples:
        apflow tasks count              # All tasks by status
        apflow tasks count --root-only  # Root tasks only (task trees)
        apflow tasks count -f table     # Table format
        apflow tasks count -u user_id   # Filter by user
    """
    try:
        from aipartnerupflow.core.storage import get_default_session
        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from aipartnerupflow.core.config import get_task_model_class
        from aipartnerupflow.core.types import TaskStatus
        
        # All possible statuses
        all_statuses = [
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]
        
        # parent_id filter: "" means root tasks (parent_id is None), None means all tasks
        parent_id_filter = "" if root_only else None
        
        async def get_counts():
            # Create database session inside async context
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
            
            try:
                counts = {}
                total = 0
                
                # Count all statuses
                for status in all_statuses:
                    tasks = await task_repository.query_tasks(
                        user_id=user_id,
                        status=status,
                        parent_id=parent_id_filter,
                        limit=10000  # High limit for counting
                    )
                    counts[status] = len(tasks)
                    total += len(tasks)
                
                return {"total": total, **counts}
            finally:
                # Ensure session is properly closed
                from sqlalchemy.ext.asyncio import AsyncSession
                if isinstance(db_session, AsyncSession):
                    await db_session.close()
                else:
                    db_session.close()
        
        result = run_async_safe(get_counts())
        
        # Add metadata to result
        if user_id:
            result["user_id"] = user_id
        if root_only:
            result["root_only"] = True
        
        # Output based on format
        if output_format == "table":
            _print_count_table(result)
        else:
            typer.echo(json.dumps(result, indent=2))
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


def _print_count_table(counts: dict):
    """Print counts as a formatted table"""
    table = Table(title="Task Statistics")
    table.add_column("Status", style="cyan", no_wrap=True)
    table.add_column("Count", style="magenta", justify="right")
    
    # Status display order and styles
    status_styles = {
        "total": ("bold white", "Total"),
        "pending": ("dim", "Pending"),
        "in_progress": ("blue", "In Progress"),
        "completed": ("green", "Completed"),
        "failed": ("red", "Failed"),
        "cancelled": ("yellow", "Cancelled"),
    }
    
    # Add filter info rows
    if "user_id" in counts:
        table.add_row("[dim]User ID[/dim]", f"[dim]{counts['user_id']}[/dim]")
    if counts.get("root_only"):
        table.add_row("[dim]Filter[/dim]", "[dim]Root tasks only[/dim]")
    if "user_id" in counts or counts.get("root_only"):
        table.add_section()
    
    # Add status rows in order
    for status, (style, label) in status_styles.items():
        if status in counts:
            table.add_row(f"[{style}]{label}[/{style}]", f"[{style}]{counts[status]}[/{style}]")
    
    console.print(table)





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
    copy_mode: str = typer.Option("minimal", "--copy-mode", help="Copy mode: 'minimal' (default), 'full', or 'custom'"),
    custom_task_ids: Optional[str] = typer.Option(None, "--custom-task-ids", help="Comma-separated list of task IDs (required when copy-mode='custom')"),
    custom_include_children: bool = typer.Option(False, "--custom-include-children", help="Include all children recursively (used when copy-mode='custom')"),
    reset_fields: Optional[str] = typer.Option(None, "--reset-fields", help="Comma-separated list of field names to reset (e.g., 'status,progress,result')"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview task copy without saving to database"),
):
    """
    Create a copy of a task tree for re-execution
    
    This command creates a new copy of an existing task tree.
    
    Copy modes:
    - minimal (default): Copies minimal subtree (original_task + children + dependents).
      All copied tasks are marked as pending for re-execution.
    - full: Copies complete tree from root. Tasks that need re-execution are marked as pending,
      unrelated successful tasks are marked as completed with preserved token_usage.
    - custom: Copies only specified task_ids with auto-include dependencies.
      Requires --task-ids parameter. Optionally include children with --include-children.
    
    When --children is used, each direct child task is also copied with its dependencies.
    Tasks that depend on multiple copied tasks are only copied once (deduplication).
    
    The copied tasks are linked to the original task via original_task_id field.
    
    Args:
        task_id: ID of the task to copy (can be root or any task in tree)
        output: Optional output file path to save the copied task tree JSON
        children: If True, also copy each direct child task with its dependencies
        copy_mode: Copy mode - "minimal" (default), "full", or "custom"
        custom_task_ids: Comma-separated list of task IDs (required when copy-mode='custom')
        custom_include_children: Include all children recursively (used when copy-mode='custom')
        reset_fields: Comma-separated list of field names to reset
        dry_run: Preview task copy without saving to database
    """
    try:
        if copy_mode not in ("minimal", "full", "custom"):
            typer.echo(f"Error: Invalid copy_mode '{copy_mode}'. Must be 'minimal', 'full', or 'custom'", err=True)
            raise typer.Exit(1)
        
        if copy_mode == "custom" and not custom_task_ids:
            typer.echo("Error: --custom-task-ids is required when copy-mode='custom'", err=True)
            raise typer.Exit(1)
        
        # Parse custom_task_ids if provided
        parsed_custom_task_ids = None
        if custom_task_ids:
            parsed_custom_task_ids = [tid.strip() for tid in custom_task_ids.split(",") if tid.strip()]
        
        # Parse reset_fields if provided
        parsed_reset_fields = None
        if reset_fields:
            parsed_reset_fields = [field.strip() for field in reset_fields.split(",") if field.strip()]
        
        # Convert dry_run to save parameter
        save = not dry_run
        
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
            return await task_creator.create_task_copy(
                original_task,
                children=children,
                copy_mode=copy_mode,
                custom_task_ids=parsed_custom_task_ids,
                custom_include_children=custom_include_children,
                reset_fields=parsed_reset_fields,
                save=save
            )
        
        result = run_async_safe(copy_task())
        
        # Handle result based on save parameter
        if save:
            # Convert TaskTreeNode to dict
            result_dict = tree_node_to_dict(result)
            task_count = 1  # Root task
            if hasattr(result, 'children'):
                def count_children(node):
                    return 1 + sum(count_children(child) for child in node.children)
                task_count = count_children(result)
        else:
            # Task array (already in dict format)
            result_dict = {"tasks": result, "saved": False}
            task_count = len(result)
        
        # Output result
        if output:
            with open(output, 'w') as f:
                json.dump(result_dict, f, indent=2)
            typer.echo(f"Task copy {'preview' if dry_run else 'result'} saved to {output}")
        else:
            typer.echo(json.dumps(result_dict, indent=2))
        
        if save:
            typer.echo(f"\n✅ Successfully copied task {task_id} to new task {result.task.id} (mode: {copy_mode})")
        else:
            typer.echo(f"\n✅ Preview generated: {task_count} tasks (mode: {copy_mode}, not saved)")
        
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


@app.command("list")
def list_tasks(
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="Filter by user ID"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    root_only: bool = typer.Option(True, "--root-only/--all-tasks", help="Only show root tasks (default: True)"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of tasks to return"),
    offset: int = typer.Option(0, "--offset", "-o", help="Pagination offset"),
):
    """
    List tasks from database
    
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
        
        async def get_all_tasks():
            # Create database session inside async context to ensure proper event loop binding
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
            
            try:
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
            finally:
                # Ensure session is properly closed
                # Ensure session is properly closed
                from sqlalchemy.ext.asyncio import AsyncSession
                if isinstance(db_session, AsyncSession):
                    await db_session.close()
                else:
                    db_session.close()
        
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

