"""
Tasks command for managing and querying tasks
"""
import typer
import json
import time
from typing import Optional, List
from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.utils.logger import get_logger
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout

logger = get_logger(__name__)

app = typer.Typer(name="tasks", help="Manage and query tasks")
console = Console()


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
                task = asyncio.run(get_task_safe(task_id))
                if task:
                    # Apply user_id filter if specified
                    if user_id and task.user_id != user_id:
                        continue
                    
                    tasks_info.append({
                        "task_id": task.id,
                        "name": task.name,
                        "status": task.status,
                        "progress": float(task.progress) if task.progress else 0.0,
                        "user_id": task.user_id,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                    })
                else:
                    # Task not found in database
                    tasks_info.append({
                        "task_id": task_id,
                        "name": "Unknown",
                        "status": "unknown",
                        "progress": 0.0,
                        "user_id": None,
                        "created_at": None,
                    })
            except Exception as e:
                logger.warning(f"Failed to get task {task_id}: {str(e)}")
                tasks_info.append({
                    "task_id": task_id,
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
                task = asyncio.run(get_task_safe(task_id))
                
                if task:
                    statuses.append({
                        "task_id": task.id,
                        "name": task.name,
                        "status": task.status,
                        "progress": float(task.progress) if task.progress else 0.0,
                        "is_running": is_running,
                        "error": task.error,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                    })
                else:
                    # Task not found in database, but check if it's running in memory
                    if is_running:
                        statuses.append({
                            "task_id": task_id,
                            "name": "Unknown",
                            "status": "in_progress",
                            "progress": 0.0,
                            "is_running": True,
                            "error": None,
                            "created_at": None,
                            "updated_at": None,
                        })
                    else:
                        statuses.append({
                            "task_id": task_id,
                            "name": "Unknown",
                            "status": "not_found",
                            "progress": 0.0,
                            "is_running": False,
                            "error": None,
                            "created_at": None,
                            "updated_at": None,
                        })
            except Exception as e:
                logger.warning(f"Failed to get task {task_id}: {str(e)}")
                statuses.append({
                    "task_id": task_id,
                    "name": "Unknown",
                    "status": "error",
                    "progress": 0.0,
                    "is_running": is_running,
                    "error": str(e),
                    "created_at": None,
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
                    task = asyncio.run(get_task_safe(task_id))
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
                cancel_result = asyncio.run(task_executor.cancel_task(task_id, error_message))
                
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
        failed = any(r.get("status") in ["error", "failed"] for r in results)
        if failed:
            raise typer.Exit(1)
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error cancelling tasks")
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
                task = asyncio.run(get_task_safe(tid))
                
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
                        task = asyncio.run(get_task_safe(task_id))
                        if task and task.status in ["completed", "failed", "cancelled"]:
                            typer.echo(f"\nTask {task_id} finished with status: {task.status}")
                            break
        except KeyboardInterrupt:
            typer.echo("\nStopped watching")
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error watching tasks")
        raise typer.Exit(1)

