"""
Run command for executing flows
"""

import typer
import json
from typing import Optional
from pathlib import Path
from aipartnerupflow.core.utils.logger import get_logger
import asyncio

logger = get_logger(__name__)

app = typer.Typer(name="run", help="Run a flow")


@app.command()
def flow(
    batch_id: str = typer.Argument(..., help="Batch ID to execute"),
    inputs: Optional[str] = typer.Option(None, "--inputs", "-i", help="Input JSON string"),
    inputs_file: Optional[Path] = typer.Option(None, "--inputs-file", "-f", help="Input JSON file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """
    Execute a batch
    
    Args:
        batch_id: Batch identifier
        inputs: Input parameters as JSON string
        inputs_file: Input parameters from JSON file
        output: Optional output file path
    """
    try:
        # Parse inputs
        if inputs_file:
            with open(inputs_file, "r") as f:
                inputs_dict = json.load(f)
        elif inputs:
            inputs_dict = json.loads(inputs)
        else:
            inputs_dict = {}
        
        typer.echo(f"Running batch: {batch_id}")
        typer.echo(f"Inputs: {json.dumps(inputs_dict, indent=2)}")
        
        # TODO: Implement actual batch execution
        # Requires [crewai] extra: from aipartnerupflow.features.crewai import BatchManager
        # batch = BatchManager(id=batch_id)
        # result = await batch.execute(inputs=inputs_dict)
        
        result = {"status": "not_implemented", "message": "Batch execution not yet implemented"}
        
        # Output result
        if output:
            with open(output, "w") as f:
                json.dump(result, f, indent=2)
            typer.echo(f"Result saved to: {output}")
        else:
            typer.echo(f"Result: {json.dumps(result, indent=2)}")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

