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
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    
    possible_paths = [Path.cwd() / ".env"]
    if sys.argv and len(sys.argv) > 0:
        try:
            main_script = Path(sys.argv[0]).resolve()
            if main_script.is_file():
                possible_paths.append(main_script.parent / ".env")
        except Exception:
            pass
    
    for env_path in possible_paths:
        if env_path.exists():
            try:
                load_dotenv(env_path, override=False)
                return
            except Exception:
                continue


def _load_cli_plugins(app: typer.Typer):
    """
    Robustly load CLI extensions from entry points.
    Directly iterates over distributions to avoid metadata discovery quirks.
    """
    from importlib.metadata import distributions
    seen_plugins = set()
    
    for dist in distributions():
        try:
            for ep in dist.entry_points:
                if ep.group == 'aipartnerupflow.cli_plugins' and ep.name not in seen_plugins:
                    try:
                        plugin = ep.load()
                        if hasattr(plugin, 'app') and isinstance(plugin.app, typer.Typer):
                            app.add_typer(plugin.app, name=ep.name)
                        elif isinstance(plugin, typer.Typer):
                            app.add_typer(plugin, name=ep.name)
                        elif callable(plugin):
                            app.command(name=ep.name)(plugin)
                        
                        seen_plugins.add(ep.name)
                        logger.debug(f"Loaded CLI extension: {ep.name}")
                    except Exception as e:
                        logger.warning(f"Failed to load CLI extension {ep.name}: {e}")
        except Exception:
            continue


# Create Typer app
app = typer.Typer(
    name="aipartnerupflow",
    help="Agent workflow orchestration and execution platform CLI",
    add_completion=False,
)

@app.callback(invoke_without_command=True)
def cli_callback(ctx: typer.Context):
    _load_env_file()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

app.add_typer(run.app, name="run", help="Run a flow")
app.add_typer(serve.app, name="serve", help="Start API server")
app.add_typer(daemon.app, name="daemon", help="Manage daemon")
app.add_typer(tasks.app, name="tasks", help="Manage and query tasks")
app.add_typer(generate.app, name="generate", help="Generate task trees from natural language")

_load_cli_plugins(app)

@app.command()
def version():
    """Show version information."""
    from aipartnerupflow import __version__
    typer.echo(f"aipartnerupflow version {__version__}")

if __name__ == "__main__":
    app()