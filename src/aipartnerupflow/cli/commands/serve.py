"""
Serve command for starting API server
"""

import typer
import uvicorn
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(name="serve", help="Start API server")


@app.command()
def start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
):
    """
    Start API server
    
    Args:
        host: Host address
        port: Port number
        reload: Enable auto-reload for development
        workers: Number of worker processes
    """
    try:
        typer.echo(f"Starting API server on {host}:{port}")
        
        # Create app
        from aipartnerupflow.api import create_app
        api_app = create_app()
        
        # Run server
        uvicorn.run(
            api_app,
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
        )
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

