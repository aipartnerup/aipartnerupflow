"""
CLI main entry point for aipartnerupflow
"""

import typer
import json
from typing import Optional
from pathlib import Path
from aipartnerupflow.cli.commands import run, serve, daemon, tasks
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

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


@app.command()
def version():
    """Show version information"""
    from aipartnerupflow import __version__
    typer.echo(f"aipartnerupflow version {__version__}")


if __name__ == "__main__":
    app()

