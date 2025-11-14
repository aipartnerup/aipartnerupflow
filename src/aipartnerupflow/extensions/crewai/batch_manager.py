"""
BatchManager class for atomic execution of multiple crews

BatchManager is NOT an ExecutableTask - it's a container that executes multiple crews
as an atomic operation. All crews execute, then results are merged.
This ensures all crews complete together (all-or-nothing semantics).

Simple implementation: Multiple crew tasks executed sequentially and merged.
No complex workflow - just batch execution with atomic semantics.
"""

from typing import Dict, Any, Optional, Type
from aipartnerupflow.extensions.crewai.types import BatchState
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


@executor_register()
class BatchManager(BaseTask):
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
    id: str = "batch_crewai_executor"
    name: str = "Batch CrewAI Executor"
    description: str = "Batch execution of multiple crews via CrewAI"
    tags: list[str] = []
    examples: list[str] = ["Execute multiple crews as a batch"]
    works: Dict[str, Any] = {}
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "crewai"
    
    def __init__(self, **kwargs: Any):
        """Initialize BatchManager"""
        # Initialize BaseTask first
        inputs = kwargs.pop("inputs", {})
        super().__init__(inputs=inputs, **kwargs)
        
        # Additional BatchManager-specific initialization
        self.storage = kwargs.get("storage")
        self.works = kwargs.get("works", {})
    
    def init(self, **kwargs: Any) -> None:
        """Initialize batch manager with configuration"""
        # Call parent init first to handle common properties
        super().init(**kwargs)
        
        # Handle BatchManager-specific properties
        if "works" in kwargs:
            self.works = kwargs["works"]
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
        Even if a work fails, its result (including token_usage) is collected.
        
        Returns:
            Dictionary mapping work names to their results
        """
        if not self.works:
            raise ValueError("No works found in batch")
        
        # Execute works sequentially
        data = {}
        failed_works = []
        
        for work_name, work in self.works.items():
            try:
                logger.info(f"Executing work: {work_name}")
                
                # Create fresh inputs for each crew
                fresh_inputs = self.inputs.copy() if self.inputs else {}
                logger.debug(f"Fresh inputs for {work_name}: {fresh_inputs}")

                if "agents" not in work or "tasks" not in work:
                    raise ValueError("works must contain agents and tasks")
                
                # Import CrewManager here to avoid circular imports
                from aipartnerupflow.extensions.crewai.crew_manager import CrewManager
                
                # Create crew manager instance using works format
                # Works format: {"work_name": {"agents": {...}, "tasks": {...}}}
                # Or direct format: {"agents": {...}, "tasks": {...}}
                # CrewManager now supports both formats
                _crew_manager = CrewManager(
                    name=work_name,
                    works=work,
                    inputs=fresh_inputs,
                    is_sub_crew=True
                )
                
                # Set streaming context if available
                if self.event_queue and self.context:
                    _crew_manager.set_streaming_context(self.event_queue, self.context)
                
                # Execute crew
                result = await _crew_manager.execute(inputs=fresh_inputs)
                
                # Store result (even if failed, to collect token_usage)
                data[work_name] = result
                
                # Check if execution failed
                if isinstance(result, dict) and result.get("status") == "failed":
                    failed_works.append(work_name)
                    error_str = result.get("error", "Unknown error")
                    logger.error(f"Work {work_name} failed: {error_str}")
                else:
                    logger.info(f"Work {work_name} completed successfully")
                    
            except Exception as e:
                # If execution throws exception, create a failed result
                logger.error(f"Work {work_name} threw exception: {str(e)}", exc_info=True)
                failed_works.append(work_name)
                data[work_name] = {
                    "status": "failed",
                    "error": str(e),
                    "result": None
                }
        
        # If any work failed, raise exception (atomic operation)
        if failed_works:
            error_msg = f"Failed works: {', '.join(failed_works)}"
            logger.error(error_msg)
            # Store results before raising exception (for token_usage aggregation)
            self._last_results = data
            raise Exception(error_msg)
        
        logger.debug(f"Results: {data}")
        logger.info("All works completed successfully")
        return data
    
    async def execute(self, inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Execute batch works (atomic operation)
        
        Args:
            inputs: Input parameters
            
        Returns:
            Execution result dictionary with status, result/error, and aggregated token_usage
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
            
            # Store results for potential error handling
            self._last_results = results
            
            # Aggregate token usage from all works
            aggregated_token_usage = self._aggregate_token_usage(results)
            
            # Process results
            processed_results = self.process_result(results)
            logger.info(f"Batch execution completed: {self.name}")
            
            # Build success result with aggregated token_usage
            success_result = {
                "status": "success",
                "result": processed_results
            }
            
            # Add aggregated token usage to final result if available
            if aggregated_token_usage and aggregated_token_usage.get('total_tokens', 0) > 0:
                success_result['token_usage'] = aggregated_token_usage
                logger.info(f"Aggregated token usage from all works: {aggregated_token_usage}")
            
            return success_result
            
        except Exception as e:
            logger.error(f"Batch execution failed: {str(e)}", exc_info=True)
            
            # Try to aggregate token usage from already executed works
            aggregated_token_usage = None
            try:
                # If we have partial results, try to aggregate token usage from them
                if hasattr(self, '_last_results'):
                    aggregated_token_usage = self._aggregate_token_usage(self._last_results)
                    if aggregated_token_usage:
                        aggregated_token_usage['status'] = 'failed'
            except Exception as agg_error:
                logger.warning(f"Failed to aggregate token usage after failure: {str(agg_error)}")
            
            # Build error result with aggregated token_usage
            error_result = {
                "status": "failed",
                "error": str(e),
                "result": None
            }
            
            # Add aggregated token usage even when execution fails
            if aggregated_token_usage:
                error_result['token_usage'] = aggregated_token_usage
                logger.info(f"Aggregated token usage from executed works (marked as failed): {aggregated_token_usage}")
            
            return error_result
    
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
    
    def _aggregate_token_usage(self, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Aggregate token usage from all works in the batch
        
        Args:
            results: Dictionary mapping work names to their results
            
        Returns:
            Aggregated token usage dictionary or None if no token usage found
        """
        try:
            aggregated_token_usage = {
                'total_tokens': 0,
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'cached_prompt_tokens': 0,
                'successful_requests': 0,
                'status': 'success'
            }
            
            has_token_usage = False
            
            for work_name, work_result in results.items():
                work_token_usage = None
                if isinstance(work_result, dict):
                    work_token_usage = work_result.get('token_usage')
                
                if work_token_usage:
                    has_token_usage = True
                    # Aggregate token counts from all works
                    aggregated_token_usage['total_tokens'] += work_token_usage.get('total_tokens', 0)
                    aggregated_token_usage['prompt_tokens'] += work_token_usage.get('prompt_tokens', 0)
                    aggregated_token_usage['completion_tokens'] += work_token_usage.get('completion_tokens', 0)
                    aggregated_token_usage['cached_prompt_tokens'] += work_token_usage.get('cached_prompt_tokens', 0)
                    aggregated_token_usage['successful_requests'] += work_token_usage.get('successful_requests', 0)
                    
                    # If any work has failed status, mark aggregated as failed
                    if work_token_usage.get('status') == 'failed':
                        aggregated_token_usage['status'] = 'failed'
            
            # Only return if we have meaningful data
            if has_token_usage:
                return aggregated_token_usage
                
        except Exception as e:
            logger.warning(f"Failed to aggregate token usage: {str(e)}")
        
        return None

