"""
Generate command for generating task trees from natural language
"""
import typer
import json
import os
from pathlib import Path
from typing import Optional
from aipartnerupflow.core.execution.task_executor import TaskExecutor
from aipartnerupflow.core.storage import get_default_session
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(name="generate", help="Generate task trees from natural language requirements")

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env file from project root
    env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(f"Loaded .env file from {env_path}")
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass


def run_async_safe(coro):
    """Safely run async coroutine"""
    import asyncio
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        
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
        return asyncio.run(coro)


@app.command("task-tree")
def task_tree(
    requirement: str = typer.Argument(..., help="Natural language requirement for the task tree"),
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="User ID for the generated tasks"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider (openai or anthropic)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model name"),
    temperature: Optional[float] = typer.Option(None, "--temperature", "-t", help="LLM temperature (0.0 to 2.0, default: 0.7)"),
    max_tokens: Optional[int] = typer.Option(None, "--max-tokens", help="Maximum tokens in LLM response (default: 4000)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
    pretty: bool = typer.Option(True, "--pretty/--no-pretty", help="Pretty print JSON output"),
    save: bool = typer.Option(False, "--save/--no-save", help="Save generated tasks to database"),
):
    """
    Generate a task tree JSON array from natural language requirement
    
    This command uses the generate_executor to create a valid task tree structure
    that can be used with TaskCreator.create_task_tree_from_array().
    
    Examples:
        # Generate and preview task tree
        apflow generate task-tree "Fetch data from API and process it"
        
        # Generate with specific LLM provider
        apflow generate task-tree "Create a workflow" --provider openai --model gpt-4
        
        # Generate with custom temperature and max_tokens
        apflow generate task-tree "Create a workflow" --temperature 0.9 --max-tokens 6000
        
        # Save to file
        apflow generate task-tree "My requirement" --output tasks.json
        
        # Save to database
        apflow generate task-tree "My requirement" --save --user-id user123
    """
    try:
        # Import to register executor
        from aipartnerupflow.extensions.generate import GenerateExecutor  # noqa: F401
        
        # Set LLM key from CLI params (if provided via environment or params)
        # Priority: params -> LLMKeyConfigManager -> env
        from aipartnerupflow.core.utils.llm_key_context import (
            clear_llm_key_context,
            set_llm_key_from_cli_params
        )
        
        # Clear context at start (security: prevent using stale keys)
        clear_llm_key_context()
        
        # Try to get API key from environment (CLI context)
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            # Set in CLI context for unified access
            set_llm_key_from_cli_params(api_key, provider=provider)
        elif not api_key:
            # Check if key exists via unified getter (will check config and env)
            from aipartnerupflow.core.utils.llm_key_context import get_llm_key
            api_key = get_llm_key(user_id=user_id or "cli_user", provider=provider, context="cli")
            if not api_key:
                typer.echo(
                    "Warning: No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY "
                    "environment variable or create a .env file in the project root.",
                    err=True
                )
                typer.echo(
                    "\nExample .env file:\n  OPENAI_API_KEY=sk-your-key-here",
                    err=True
                )
                raise typer.Exit(1)
        
        # Create task using generate_executor
        async def generate_task_tree():
            db = get_default_session()
            task_repository = TaskRepository(db, task_model_class=get_task_model_class())
            
            # Create generate task
            # Note: api_key can be passed via inputs for CLI context, or executor will get from unified context
            generate_task = await task_repository.create_task(
                name="generate_executor",
                user_id=user_id or "cli_user",
                inputs={
                    "requirement": requirement,
                    "user_id": user_id,
                    "llm_provider": provider,
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "api_key": api_key,  # Pass via inputs for CLI context
                },
                schemas={"method": "generate_executor"}  # Required for TaskManager to find executor
            )
            
            # Initialize extensions before executing tasks
            # This ensures all executors (including generate_executor) are registered
            from aipartnerupflow.api.extensions import initialize_extensions
            initialize_extensions()
            
            # Execute generate_executor
            task_tree = TaskTreeNode(generate_task)
            task_executor = TaskExecutor()
            await task_executor.execute_task_tree(
                task_tree=task_tree,
                root_task_id=generate_task.id,
                use_streaming=False,
                use_demo=False,
                db_session=db
            )
            
            # Get result
            result_task = await task_repository.get_task_by_id(generate_task.id)
            
            if result_task.status == "failed":
                error_msg = result_task.error or "Unknown error"
                typer.echo(f"Error generating task tree: {error_msg}", err=True)
                raise typer.Exit(1)
            
            if result_task.status != "completed":
                typer.echo(f"Task generation incomplete. Status: {result_task.status}", err=True)
                raise typer.Exit(1)
            
            # Extract generated tasks
            result_data = result_task.result or {}
            generated_tasks = result_data.get("tasks", [])
            
            if not generated_tasks:
                typer.echo("No tasks were generated.", err=True)
                raise typer.Exit(1)
            
            # Output tasks array
            if pretty:
                output_json = json.dumps(generated_tasks, indent=2, ensure_ascii=False)
            else:
                output_json = json.dumps(generated_tasks, ensure_ascii=False)
            
            if output:
                # Save to file
                output_path = Path(output)
                output_path.write_text(output_json, encoding="utf-8")
                typer.echo(f"Generated {len(generated_tasks)} task(s) and saved to {output_path}")
            else:
                # Print to stdout
                typer.echo(output_json)
            
            # Optionally save to database
            if save:
                from aipartnerupflow.core.execution.task_creator import TaskCreator
                creator = TaskCreator(db)
                final_task_tree = await creator.create_task_tree_from_array(generated_tasks)
                typer.echo(f"\nSaved {len(generated_tasks)} task(s) to database.")
                typer.echo(f"Root task ID: {final_task_tree.task.id}")
            
            return generated_tasks
        
        # Run async function
        run_async_safe(generate_task_tree())
        
    except ImportError as e:
        typer.echo(f"Error: {e}", err=True)
        typer.echo(
            "\nTo use generate_executor, install required LLM package:\n"
            "  pip install openai\n"
            "  # or\n"
            "  pip install anthropic",
            err=True
        )
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error generating task tree")
        raise typer.Exit(1)

