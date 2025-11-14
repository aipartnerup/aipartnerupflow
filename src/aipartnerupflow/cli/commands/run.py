"""
Run command for executing flows
"""

import typer
import json
import uuid
from typing import Optional, List, Dict, Any
from pathlib import Path
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.core.execution.task_executor import TaskExecutor
import asyncio

logger = get_logger(__name__)

app = typer.Typer(name="run", help="Run a flow")


def _group_tasks_by_root(tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Group tasks into separate task trees based on root tasks.
    
    TaskExecutor only supports single root task tree. This function groups
    unrelated tasks (multiple root tasks with parent_id=None) into separate groups.
    
    Args:
        tasks: List of task dictionaries
        
    Returns:
        List of task groups, each group is a task tree with a single root
    """
    if not tasks:
        return []
    
    # Build a map of task_id to task
    task_map = {}
    root_tasks = []
    
    for task in tasks:
        task_id = task.get("id") or str(uuid.uuid4())
        task["id"] = task_id
        task_map[task_id] = task
        
        parent_id = task.get("parent_id")
        if not parent_id:
            root_tasks.append(task)
    
    # If there's only one root task, return all tasks as one group
    if len(root_tasks) == 1:
        return [tasks]
    
    # Multiple root tasks: group tasks by their root
    def find_root_task_id(task_id: str, visited: set = None) -> Optional[str]:
        """Find the root task ID for a given task"""
        if visited is None:
            visited = set()
        
        if task_id in visited:
            # Circular reference
            return None
        
        visited.add(task_id)
        task = task_map.get(task_id)
        if not task:
            return None
        
        parent_id = task.get("parent_id")
        if not parent_id:
            return task_id
        
        return find_root_task_id(parent_id, visited)
    
    # Group tasks by root task ID
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for task in tasks:
        task_id = task.get("id")
        root_id = find_root_task_id(task_id)
        if root_id:
            if root_id not in groups:
                groups[root_id] = []
            groups[root_id].append(task)
    
    return list(groups.values())


@app.command()
def flow(
    executor_id: Optional[str] = typer.Argument(None, help="Executor ID to execute (deprecated: use --tasks instead)"),
    tasks: Optional[str] = typer.Option(None, "--tasks", "-t", help="Tasks JSON array (list of task objects)"),
    tasks_file: Optional[Path] = typer.Option(None, "--tasks-file", "-f", help="Tasks JSON file"),
    # Legacy support: executor_id + inputs (for backward compatibility)
    inputs: Optional[str] = typer.Option(None, "--inputs", "-i", help="Input JSON string (legacy: use with executor_id)"),
    inputs_file: Optional[Path] = typer.Option(None, "--inputs-file", help="Input JSON file (legacy: use with executor_id)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    user_id: str = typer.Option("cli_user", "--user-id", "-u", help="User ID for task execution"),
    background: bool = typer.Option(False, "--background", "-b", help="Run in background (returns immediately with task ID)"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch task status in real-time after starting"),
):
    """
    Execute tasks through TaskExecutor (same execution path as API)
    
    This command executes tasks through TaskExecutor. It supports:
    1. Single executor execution (legacy mode): executor_id + inputs
    2. Task array execution (standard mode): tasks list (JSON array)
    
    For multiple unrelated tasks (multiple root tasks), CLI will execute them separately
    since TaskExecutor only supports single root task tree.
    
    Args:
        executor_id: Executor ID (legacy mode, use --tasks instead)
        tasks: Tasks JSON array (list of task objects)
        tasks_file: Tasks JSON file
        inputs: Input JSON string (legacy mode, use with executor_id)
        inputs_file: Input JSON file (legacy mode, use with executor_id)
        output: Optional output file path
        user_id: User ID for task execution (default: "cli_user")
    """
    try:
        # Parse tasks or inputs
        tasks_list: List[Dict[str, Any]] = []
        
        if tasks_file:
            with open(tasks_file, "r") as f:
                tasks_data = json.load(f)
                if isinstance(tasks_data, list):
                    tasks_list = tasks_data
                else:
                    raise ValueError("tasks_file must contain a JSON array")
        elif tasks:
            tasks_data = json.loads(tasks)
            if isinstance(tasks_data, list):
                tasks_list = tasks_data
            else:
                raise ValueError("--tasks must be a JSON array")
        elif executor_id:
            # Legacy mode: executor_id + inputs
        if inputs_file:
            with open(inputs_file, "r") as f:
                inputs_dict = json.load(f)
        elif inputs:
            inputs_dict = json.loads(inputs)
        else:
            inputs_dict = {}
        
            typer.echo(f"Running executor: {executor_id} (legacy mode)")
            if inputs_dict:
        typer.echo(f"Inputs: {json.dumps(inputs_dict, indent=2)}")
        
            # Create a single task for executor
            task = {
                "id": str(uuid.uuid4()),
                "name": f"Execute {executor_id}",
                "user_id": user_id,
                "schemas": {
                    "method": executor_id,  # Use executor_id as executor ID
                },
                "input_data": inputs_dict,
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "progress": 0.0,
            }
            tasks_list = [task]
        else:
            typer.echo("Error: Either --tasks/--tasks-file or executor_id must be provided", err=True)
            raise typer.Exit(1)
        
        if not tasks_list:
            typer.echo("Error: No tasks provided", err=True)
            raise typer.Exit(1)
        
        # Ensure all tasks have user_id
        for task in tasks_list:
            if "user_id" not in task:
                task["user_id"] = user_id
        
        typer.echo(f"Executing {len(tasks_list)} task(s)...")
        
        # Group tasks by root (handle multiple unrelated tasks)
        task_groups = _group_tasks_by_root(tasks_list)
        
        if len(task_groups) > 1:
            typer.echo(f"Found {len(task_groups)} unrelated task groups, executing separately...")
        
        # Execute through TaskExecutor (same path as API)
        task_executor = TaskExecutor()
        
        # Execute each task group separately
        all_results = []
        all_root_task_ids = []
        
        async def execute_task_group(task_group: List[Dict[str, Any]], group_index: int) -> Dict[str, Any]:
            """Execute a single task group"""
            try:
                if len(task_groups) > 1:
                    typer.echo(f"Executing task group {group_index + 1}/{len(task_groups)}...")
                
                execution_result = await task_executor.execute_tasks(
                    tasks=task_group,
                    root_task_id=None,
                    use_streaming=False,
                    require_existing_tasks=False,
                )
                return execution_result
            except Exception as e:
                logger.error(f"Task group {group_index + 1} execution failed: {str(e)}", exc_info=True)
                return {
                    "status": "failed",
                    "error": str(e),
                    "root_task_id": None
                }
        
        if background:
            # Background mode: start execution and return immediately
            typer.echo("Starting task(s) in background...")
            
            # Start execution in background (non-blocking)
            import threading
            import time
            
            def run_in_background():
                try:
                    async def run_all_groups():
                        results = []
                        for i, task_group in enumerate(task_groups):
                            result = await execute_task_group(task_group, i)
                            results.append(result)
                        return results
                    
                    all_results = asyncio.run(run_all_groups())
                except Exception as e:
                    logger.error(f"Background task execution failed: {str(e)}", exc_info=True)
            
            thread = threading.Thread(target=run_in_background, daemon=True)
            thread.start()
            
            # Wait a moment for tasks to be created
            time.sleep(0.5)
            
            # Get root task IDs from task groups
            root_task_ids = []
            for task_group in task_groups:
                # Find root task (parent_id is None)
                for task in task_group:
                    if not task.get("parent_id"):
                        root_task_ids.append(task.get("id"))
                        break
            
            typer.echo(f"Task(s) started in background")
            if len(root_task_ids) == 1:
                typer.echo(f"Task ID: {root_task_ids[0]}")
                typer.echo(f"Monitor with: aipartnerupflow tasks status {root_task_ids[0]}")
                typer.echo(f"Watch with: aipartnerupflow tasks watch --task-id {root_task_ids[0]}")
            else:
                typer.echo(f"Task IDs: {', '.join(root_task_ids)}")
                typer.echo(f"Monitor with: aipartnerupflow tasks status {' '.join(root_task_ids)}")
                typer.echo(f"Watch with: aipartnerupflow tasks watch --all")
            
            if watch:
                # Start watch mode
                typer.echo("\nWatching task status (Press Ctrl+C to stop)...")
                from rich.console import Console
                from rich.table import Table
                from rich.live import Live
                
                console = Console()
                
                # Get database session for watching
                from aipartnerupflow.core.storage import get_default_session
                from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
                from aipartnerupflow.core.config import get_task_model_class
                
                db_session = get_default_session()
                task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
                
                def create_status_table():
                    """Create a table showing task status"""
                    table = Table(title="Task Status Monitor")
                    table.add_column("Task ID", style="cyan", no_wrap=True)
                    table.add_column("Name", style="magenta")
                    table.add_column("Status", style="green")
                    table.add_column("Progress", style="yellow")
                    table.add_column("Running", style="blue")
                    
                    for root_task_id in root_task_ids:
                        is_running = task_executor.is_task_running(root_task_id)
                        task = asyncio.run(task_repository.get_task_by_id(root_task_id))
                        
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
                                task.id[:16],
                                task.name[:40],
                                f"[{status_style}]{task.status}[/{status_style}]",
                                progress_str,
                                running_str
                            )
                        else:
                            table.add_row(
                                root_task_id[:16],
                                "Unknown",
                                "[dim]unknown[/dim]",
                                "0.0%",
                                "✓" if is_running else "✗"
                            )
                    
                    return table
                
                try:
                    with Live(create_status_table(), refresh_per_second=1, console=console) as live:
                        while True:
                            time.sleep(1)
                            live.update(create_status_table())
                            
                            # Check if all tasks are finished
                            all_finished = True
                            for root_task_id in root_task_ids:
                                task = asyncio.run(task_repository.get_task_by_id(root_task_id))
                                if task and task.status not in ["completed", "failed", "cancelled"]:
                                    all_finished = False
                                    break
                            
                            if all_finished:
                                typer.echo(f"\nAll tasks finished")
                                break
                except KeyboardInterrupt:
                    typer.echo("\nStopped watching (tasks continue in background)")
            
            return
        
        # Foreground mode: wait for execution to complete
        typer.echo("Executing tasks through TaskExecutor...")
        
        try:
            # Execute all task groups sequentially
            async def execute_all_groups():
                results = []
                root_ids = []
                for i, task_group in enumerate(task_groups):
                    if len(task_groups) > 1:
                        typer.echo(f"\nExecuting task group {i + 1}/{len(task_groups)}...")
                    
                    execution_result = await execute_task_group(task_group, i)
                    results.append(execution_result)
                    
                    if execution_result.get("root_task_id"):
                        root_ids.append(execution_result["root_task_id"])
                return results, root_ids
            
            all_results, all_root_task_ids = asyncio.run(execute_all_groups())
            
            # Format result
            if len(all_results) == 1:
                # Single task group
                execution_result = all_results[0]
                result = {
                    "status": execution_result.get("status", "unknown"),
                    "progress": execution_result.get("progress", 0.0),
                    "root_task_id": execution_result.get("root_task_id"),
                    "task_count": len(tasks_list),
                }
                
                # Try to get task result from database
                if execution_result.get("root_task_id"):
                    try:
                        from aipartnerupflow.core.storage import get_default_session
                        from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
                        from aipartnerupflow.core.config import get_task_model_class
                        
                        db_session = get_default_session()
                        task_repository = TaskRepository(
                            db_session, 
                            task_model_class=get_task_model_class()
                        )
                        
                        root_task = asyncio.run(
                            task_repository.get_task_by_id(execution_result["root_task_id"])
                        )
                        
                        if root_task:
                            result["result"] = root_task.result
                            result["error"] = root_task.error
                    except Exception as e:
                        logger.warning(f"Failed to get task result from database: {str(e)}")
            else:
                # Multiple task groups
                result = {
                    "status": "completed" if all(r.get("status") == "completed" for r in all_results) else "partial",
                    "task_groups": len(all_results),
                    "root_task_ids": all_root_task_ids,
                    "results": all_results,
                }
            
        except Exception as e:
            logger.error(f"Task execution failed: {str(e)}", exc_info=True)
            result = {
                "status": "failed",
                "error": str(e),
                "result": None
            }
        
        # Output result
        if output:
            with open(output, "w") as f:
                json.dump(result, f, indent=2)
            typer.echo(f"Result saved to: {output}")
        else:
            typer.echo(f"Result: {json.dumps(result, indent=2)}")
        
        # Exit with error code if execution failed
        if result.get("status") == "failed":
            raise typer.Exit(1)
        
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Unexpected error in run command")
        raise typer.Exit(1)

