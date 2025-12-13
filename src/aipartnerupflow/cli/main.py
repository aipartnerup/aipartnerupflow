"""
CLI main entry point for aipartnerupflow
"""

import sys
import typer
from pathlib import Path
from aipartnerupflow.cli.commands import run, serve, daemon, tasks, generate
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def _load_env_file():
    """
    Load .env file from appropriate location
    
    Priority order:
    1. Current working directory (where script is run from)
    2. Directory of the main script (if running as a script)
    3. Library's own directory (only when running library's own CLI directly)
    
    This ensures that when used as a library, it loads .env from the calling project,
    not from the library's installation directory.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv not installed, skip .env loading
        return
    
    possible_paths = []
    
    # 1. Current working directory (where the script is run from)
    possible_paths.append(Path.cwd() / ".env")
    
    # 2. Directory of the main script (if running as a script)
    if sys.argv and len(sys.argv) > 0:
        try:
            main_script = Path(sys.argv[0]).resolve()
            if main_script.is_file():
                possible_paths.append(main_script.parent / ".env")
        except Exception:
            pass
    
    # 3. Library's own directory (only for library development)
    try:
        lib_root = Path(__file__).parent.parent.parent.parent
        if "site-packages" not in str(lib_root) and "dist-packages" not in str(lib_root):
            possible_paths.append(lib_root / ".env")
    except Exception:
        pass
    
    # Try each path and load the first one that exists
    for env_path in possible_paths:
        if env_path.exists():
            try:
                load_dotenv(env_path, override=False)
                logger.debug(f"Loaded .env file from {env_path}")
                return
            except Exception as e:
                logger.debug(f"Failed to load .env from {env_path}: {e}")
                continue


# Create Typer app
app = typer.Typer(
    name="aipartnerupflow",
    help="Agent workflow orchestration and execution platform CLI",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def cli_callback(ctx: typer.Context):
    """
    Global callback for CLI - loads .env file before any command execution
    """
    # Load .env file when CLI is invoked (not at module import time)
    _load_env_file()
    
    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

# Register subcommands
app.add_typer(run.app, name="run", help="Run a flow")
app.add_typer(serve.app, name="serve", help="Start API server")
app.add_typer(daemon.app, name="daemon", help="Manage daemon")
app.add_typer(tasks.app, name="tasks", help="Manage and query tasks")
app.add_typer(generate.app, name="generate", help="Generate task trees from natural language")


@app.command()
def version():
    """Show version information"""
    from aipartnerupflow import __version__
    typer.echo(f"aipartnerupflow version {__version__}")


if __name__ == "__main__":
    # CLI callback will load .env file automatically
    app()

