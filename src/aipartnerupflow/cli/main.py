"""
CLI main entry point for aipartnerupflow
"""

import typer
from pathlib import Path
from aipartnerupflow.cli.commands import run, serve, daemon, tasks, examples, generate
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env file from project root (try multiple possible locations)
    possible_paths = [
        Path.cwd() / ".env",  # Current working directory
        Path(__file__).parent.parent.parent.parent / ".env",  # Project root
    ]
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded .env file from {env_path}")
            break
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# Create Typer app
app = typer.Typer(
    name="aipartnerupflow",
    help="Agent workflow orchestration and execution platform CLI",
    add_completion=False,
)

# Register subcommands
app.add_typer(run.app, name="run", help="Run a flow")
app.add_typer(serve.app, name="serve", help="Start API server")
app.add_typer(daemon.app, name="daemon", help="Manage daemon")
app.add_typer(tasks.app, name="tasks", help="Manage and query tasks")
app.add_typer(examples.app, name="examples", help="Manage example task data")
app.add_typer(generate.app, name="generate", help="Generate task trees from natural language")


@app.command()
def version():
    """Show version information"""
    from aipartnerupflow import __version__
    typer.echo(f"aipartnerupflow version {__version__}")


if __name__ == "__main__":
    app()

