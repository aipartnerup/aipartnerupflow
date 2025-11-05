"""
List command for listing available flows
"""

import typer
from rich.console import Console
from rich.table import Table
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(name="list", help="List available flows")

console = Console()


@app.command()
def flows():
    """List all available flows"""
    try:
        # TODO: Implement actual batch/crew discovery
        # This will scan examples/ and extensions/crewai/ for available implementations
        batches = [
            {"id": "example_batch", "name": "Example Batch", "description": "An example batch"},
        ]
        
        # Create table
        table = Table(title="Available Batches/Crews")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Description", style="green")
        
        for batch in batches:
            table.add_row(batch["id"], batch["name"], batch["description"])
        
        console.print(table)
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

