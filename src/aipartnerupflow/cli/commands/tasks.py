"""
Tasks command for managing and querying tasks
"""
import typer
import json
from typing import Optional, List
from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(name="tasks", help="Manage and query tasks")


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
        for task_id in running_task_ids[:limit]:
            # Note: This is a simplified version - in production, you might want to use async
            try:
                import asyncio
                task = asyncio.run(task_repository.get_task_by_id(task_id))
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
        for task_id in task_ids:
            is_running = task_executor.is_task_running(task_id)
            
            try:
                import asyncio
                task = asyncio.run(task_repository.get_task_by_id(task_id))
                
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
            for task_id in running_task_ids:
                try:
                    import asyncio
                    task = asyncio.run(task_repository.get_task_by_id(task_id))
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

