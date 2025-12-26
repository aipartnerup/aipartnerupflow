"""
Serve command for starting API server
"""

import typer
import uvicorn
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(name="serve", help="Start API server", invoke_without_command=True)


def _check_protocol_dependency(protocol: str):
    """
    Check if dependencies for the specified protocol are installed
    
    Uses the unified protocol checking from api/main.py
    
    Args:
        protocol: Protocol name (e.g., "a2a", "rest", "rpc")
    
    Raises:
        typer.Exit: If protocol dependencies are not installed or protocol is not supported
    """
    try:
        from aipartnerupflow.api.protocols import (
            check_protocol_dependency,
            get_protocol_dependency_info,
            get_supported_protocols,
        )
        
        # Check if protocol is supported and dependencies are installed
        check_protocol_dependency(protocol)
    except ValueError as e:
        # Protocol not supported
        supported = ", ".join(get_supported_protocols())
        typer.echo(
            f"Error: {str(e)}\n"
            f"Supported protocols: {supported}\n"
            f"Set AIPARTNERUPFLOW_API_PROTOCOL environment variable or use --protocol option.",
            err=True,
        )
        raise typer.Exit(1)
    except ImportError:
        # Dependencies not installed
        _, extra_name, description = get_protocol_dependency_info(protocol)
        typer.echo(
            f"Error: {description} dependencies are not installed.\n"
            f"The 'serve' command requires the [{extra_name}] extra to be installed.\n"
            f"Please install it using:\n"
            f"  pip install aipartnerupflow[{extra_name}]\n"
            f"Or for full installation:\n"
            f"  pip install aipartnerupflow[all]",
            err=True,
        )
        raise typer.Exit(1)


def _start_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
    protocol: str = "a2a",
):
    """
    Internal function to start the API server
    
    Args:
        host: Host address
        port: Port number
        reload: Enable auto-reload for development
        workers: Number of worker processes
        protocol: API protocol to use (optional, defaults to api/main.py default)
    """
    try:
        # Use provided protocol (defaults to "a2a")
        protocol = protocol.lower()
        
        # Check if protocol dependencies are installed
        _check_protocol_dependency(protocol)
        
        typer.echo(f"Starting API server on {host}:{port} (protocol: {protocol})")
        if reload:
            typer.echo("Auto-reload enabled (development mode)")
        if workers > 1 and not reload:
            typer.echo(f"Starting with {workers} workers")
        
        # Create app using create_runnable_app to ensure full initialization
        # (includes .env loading, extension initialization, custom TaskModel, etc.)
        from aipartnerupflow.api.main import create_runnable_app
        api_app = create_runnable_app(protocol=protocol)
        
        # Run server
        uvicorn.run(
            api_app,
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level="info",
        )
        
    except KeyboardInterrupt:
        typer.echo("\nServer stopped by user")
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error starting API server")
        raise typer.Exit(1)


@app.callback()
def serve_callback(
    ctx: typer.Context,
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
    protocol: str = typer.Option(
        "a2a",
        "--protocol",
        "-P",
        help="API protocol to use (a2a or mcp). Defaults to 'a2a'.",
    ),
):
    """
    Start API server
    
    Protocol selection:
    - Default: a2a
    - Use --protocol to specify: a2a or mcp
    
    Examples:
        # Use default protocol (a2a)
        apflow serve
        
        # Specify port
        apflow serve --port 8000
        
        # Use A2A protocol (default)
        apflow serve --protocol a2a
        
        # Use MCP protocol
        apflow serve --protocol mcp
        
        # Use subcommand (also supported)
        apflow serve start --port 8000 --protocol mcp
    """
    # If no subcommand was provided, start the server directly
    if ctx.invoked_subcommand is None:
        _start_server(host=host, port=port, reload=reload, workers=workers, protocol=protocol)


@app.command()
def start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
    protocol: str = typer.Option(
        "a2a",
        "--protocol",
        "-P",
        help="API protocol to use (a2a or mcp). Defaults to 'a2a'.",
    ),
):
    """
    Start API server (subcommand - same as running 'serve' directly)
    
    Protocol selection:
    - Default: a2a
    - Use --protocol to specify: a2a or mcp
    
    Examples:
        # Use default protocol (a2a)
        apflow serve start
        
        # Use A2A protocol
        apflow serve start --protocol a2a
        
        # Use MCP protocol
        apflow serve start --protocol mcp
    
    Args:
        host: Host address
        port: Port number
        reload: Enable auto-reload for development
        workers: Number of worker processes
        protocol: API protocol to use (a2a or mcp, defaults to a2a)
    """
    _start_server(host=host, port=port, reload=reload, workers=workers, protocol=protocol)


if __name__ == "__main__":
    # Allow direct execution for development/debugging
    # 
    # Usage examples:
    # 1. Via main CLI (requires 'start' subcommand):
    #    aipartnerupflow serve start --protocol a2a
    # 
    # 2. Direct module execution (Typer auto-calls the only command, no 'start' needed):
    #    python -m aipartnerupflow.cli.commands.serve --protocol a2a
    #    python src/aipartnerupflow/cli/commands/serve.py --protocol a2a
    # 
    # 3. No arguments (calls start with defaults):
    #    python -m aipartnerupflow.cli.commands.serve
    #    python src/aipartnerupflow/cli/commands/serve.py
    import sys
    # If no arguments provided (only script name), default to 'start' command
    # sys.argv[0] is the script name, so len == 1 means no arguments
    if len(sys.argv) == 1:
        # No arguments: call start() directly with default values
        # Pass actual default values, not Typer Option objects
        start(
            host="0.0.0.0",
            port=8000,
            reload=False,
            workers=1,
            protocol="a2a"
        )
    else:
        # Has arguments: let Typer handle it
        # Typer will automatically call the 'start' command since it's the only command
        app()

