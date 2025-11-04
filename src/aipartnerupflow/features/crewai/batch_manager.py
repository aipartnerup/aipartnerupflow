"""
BatchManager class for atomic execution of multiple crews

BatchManager is NOT an ExecutableTask - it's a container that executes multiple crews
as an atomic operation. All crews execute, then results are merged.
This ensures all crews complete together (all-or-nothing semantics).

Simple implementation: Multiple crew tasks executed sequentially and merged.
No complex workflow - just batch execution with atomic semantics.
"""

from typing import Dict, Any, Optional, Type
from aipartnerupflow.features.crewai.types import BatchState
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class BatchManager:
    """
    BatchManager class for atomic execution of multiple crews (batch container)
    
    BatchManager coordinates the execution of multiple crews (works) as an atomic operation:
    - All crews execute sequentially
    - Results are collected and merged
    - If any crew fails, the entire batch fails (atomic operation)
    - Final result combines all crew outputs
    
    This is different from ExecutableTask (which CrewManager implements):
    - CrewManager: Single executable unit (LLM-based or custom)
    - BatchManager: Container for multiple crews (ensures atomic execution)
    
    Simple implementation: No CrewAI Flow dependency, just sequential execution and merge.
    """
    
    initial_state = BatchState
    
    # BatchManager definition properties
    id: str = ""
    name: str = ""
    description: str = ""
    tags: list[str] = []
    examples: list[str] = []
    works: Dict[str, Any] = {}
    llm: str = ""
    
    def __init__(self, **kwargs: Any):
        """Initialize BatchManager"""
        self.inputs: Dict[str, Any] = {}
        self.storage = None
        self.event_queue = None
        self.context = None
        self.init(**kwargs)
    
    def init(self, **kwargs: Any) -> None:
        """Initialize batch manager with configuration"""
        if "id" in kwargs:
            self.id = kwargs["id"]
        if "name" in kwargs:
            self.name = kwargs["name"]
        if "description" in kwargs:
            self.description = kwargs["description"]
        if "tags" in kwargs:
            self.tags = kwargs["tags"]
        if "examples" in kwargs:
            self.examples = kwargs["examples"]
        if "works" in kwargs:
            self.works = kwargs["works"]
        if "llm" in kwargs:
            self.llm = kwargs["llm"]
        if "inputs" in kwargs:
            self.inputs = kwargs["inputs"]
        if "storage" in kwargs:
            self.storage = kwargs["storage"]
        if "event_queue" in kwargs:
            self.event_queue = kwargs["event_queue"]
        if "context" in kwargs:
            self.context = kwargs["context"]
    
    def set_inputs(self, inputs: Dict[str, Any]) -> None:
        """Set input parameters"""
        self.inputs = inputs
    
    def set_streaming_context(self, event_queue, context) -> None:
        """Set streaming context for progress updates"""
        self.event_queue = event_queue
        self.context = context
    
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Get input parameters schema (JSON Schema format)
        
        Returns:
            Dictionary containing parameter metadata
        """
        # Default implementation - should be overridden by subclasses
        return {}
    
    async def execute_works(self) -> Dict[str, Any]:
        """
        Execute all works sequentially
        
        Works are executed one by one. If any work fails, the entire batch fails
        (atomic operation). Results are collected and returned as a dictionary.
        
        Returns:
            Dictionary mapping work names to their results
        """
        if not self.works:
            raise ValueError("No works found in batch")
        
        # Execute works sequentially
        data = {}
        
        for work_name, work in self.works.items():
            logger.info(f"Executing work: {work_name}")
            
            # Create fresh inputs for each crew
            fresh_inputs = self.inputs.copy() if self.inputs else {}
            logger.debug(f"Fresh inputs for {work_name}: {fresh_inputs}")
            
            # Import CrewManager here to avoid circular imports
            from aipartnerupflow.features.crewai.crew_manager import CrewManager
            
            # Create crew manager instance
            _crew_manager = CrewManager(
                name=work_name,
                agents=work.get("agents", []),
                tasks=work.get("tasks", []),
                inputs=fresh_inputs,
                is_sub_crew=True,
                llm=self.llm
            )
            
            # Set streaming context if available
            if self.event_queue and self.context:
                _crew_manager.set_streaming_context(self.event_queue, self.context)
            
            # Execute crew
            result = await _crew_manager.execute(inputs=fresh_inputs)
            
            # Check if execution failed
            if isinstance(result, dict) and result.get("status") == "failed":
                error_str = result.get("error", "Unknown error")
                logger.error(f"Work {work_name} failed: {error_str}")
                raise Exception(f"Failed works: {work_name}")
            
            logger.info(f"Work {work_name} completed successfully")
            data[work_name] = result
        
        logger.debug(f"Results: {data}")
        logger.info("All works completed successfully")
        return data
    
    async def execute(self, inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Execute batch works (atomic operation)
        
        Args:
            inputs: Input parameters
            
        Returns:
            Execution result dictionary
        """
        try:
            logger.info(f"Starting batch execution: {self.name}")
            
            if inputs:
                self.set_inputs(inputs)
            
            if not self.works:
                raise ValueError("No works found in batch")
            
            # Execute works sequentially
            results = await self.execute_works()
            logger.debug(f"Batch results: {results}")
            
            # Process results
            processed_results = self.process_result(results)
            logger.info(f"Batch execution completed: {self.name}")
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Batch execution failed: {str(e)}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "result": None
            }
    
    def process_result(self, result: Any) -> Any:
        """
        Process execution result
        
        Args:
            result: Raw execution result from batch
            
        Returns:
            Processed result as dictionary
        """
        try:
            if isinstance(result, dict):
                processed_result = {}
                for work_name, work_result in result.items():
                    if isinstance(work_result, str):
                        # Try to parse JSON string
                        import json
                        try:
                            parsed_result = json.loads(work_result)
                            processed_result[work_name] = parsed_result
                        except json.JSONDecodeError:
                            processed_result[work_name] = work_result
                    else:
                        processed_result[work_name] = work_result
                return processed_result
            else:
                return str(result)
                
        except Exception as e:
            logger.error(f"Error processing result: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

