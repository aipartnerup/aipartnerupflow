"""
Example batch for demonstration purposes
"""

from typing import Dict, Any
from aipartnerupflow.extensions.crewai import BatchManager
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class ExampleBatch(BatchManager):
    """
    Example flow demonstrating basic flow structure
    
    This is a simple example that shows how to create a custom flow.
    """
    
    id = "example_flow"
    name = "Example Batch"
    description = "An example flow for demonstration"
    tags = ["example", "demo"]
    examples = [
        "Run example analysis",
        "Execute demo flow"
    ]
    
    def __init__(self, **kwargs: Any):
        """Initialize example flow"""
        # Define works (crews to execute)
        self.works = {
            "example_work": {
                "agents": [
                    {
                        "role": "Analyst",
                        "goal": "Analyze the given data",
                        "backstory": "You are a data analyst",
                    }
                ],
                "tasks": [
                    {
                        "description": "Analyze the input data",
                        "agent": "Analyst",
                    }
                ]
            }
        }
        
        super().__init__(**kwargs)
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Get input schema"""
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Input data to analyze"
                }
            },
            "required": ["data"]
        }

