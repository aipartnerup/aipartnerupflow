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
    
    # Cancellation support: BatchManager can be cancelled between works
    cancelable: bool = True
    _cancelled: bool = False  # Internal flag for cancellation
    
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
        
        # Cancellation checker is set by BaseTask.__init__ if provided in kwargs
        # self.cancellation_checker is available from BaseTask
    
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
    
    def _check_cancellation(self) -> bool:
        """
        Check if task has been cancelled
        
        Uses cancellation_checker callback (provided by TaskManager) to check cancellation status.
        Executor doesn't access database directly - cancellation state is managed by TaskManager.
        
        Returns:
            True if task is cancelled, False otherwise
        """
        # Check internal cancellation flag first
        if self._cancelled:
            return True
        
        if not self.cancellation_checker:
            return False
        
        try:
            cancelled = self.cancellation_checker()
            if cancelled:
                self._cancelled = True  # Set internal flag
            return cancelled
        except Exception as e:
            logger.warning(f"Failed to check cancellation: {str(e)}")
            return False
    
    async def cancel(self) -> Dict[str, Any]:
        """
        Cancel batch execution
        
        This method is called by TaskManager when cancellation is requested.
        BatchManager can be cancelled between works, preserving partial results and token_usage.
        
        Returns:
            Dictionary with cancellation result:
            {
                "status": "cancelled",
                "message": str,
                "partial_result": Dict,  # Partial results from completed works
                "token_usage": Dict,  # Aggregated token usage from completed works
            }
        """
        logger.info(f"Cancelling batch execution: {self.name}")
        
        # Set cancellation flag
        self._cancelled = True
        
        # Try to get partial results and token usage
        partial_result = None
        token_usage = None
        
        try:
            # If we have partial results from executed works, use them
            if hasattr(self, '_last_results') and self._last_results:
                partial_result = self._last_results
                # Aggregate token usage from completed works
                token_usage = self._aggregate_token_usage(self._last_results)
        except Exception as e:
            logger.warning(f"Failed to get partial results during cancellation: {str(e)}")
        
        # Build cancellation result
        cancel_result = {
            "status": "cancelled",
            "message": f"Batch execution cancelled: {self.name}",
        }
        
        if partial_result:
            cancel_result["partial_result"] = partial_result
        
        if token_usage:
            cancel_result["token_usage"] = token_usage
        
        logger.info(f"Batch cancellation result: {cancel_result}")
        return cancel_result
    
    async def execute_works(self) -> Dict[str, Any]:
        """
        Execute all works sequentially
        
        Works are executed one by one. If any work fails, the entire batch fails
        (atomic operation). Results are collected and returned as a dictionary.
        Even if a work fails, its result (including token_usage) is collected.
        
        Cancellation support: Checks task status before executing each work.
        If task is cancelled, stops execution and returns partial results with token_usage.
        
        Returns:
            Dictionary mapping work names to their results
        """
        if not self.works:
            raise ValueError("No works found in batch")
        
        # Check cancellation before starting
        if self._check_cancellation():
            raise Exception("Task was cancelled before batch execution started")
        
        # Execute works sequentially
        data = {}
        failed_works = []
        
        for work_name, work in self.works.items():
            # Check cancellation before each work
            if self._check_cancellation():
                logger.info(f"Task was cancelled, stopping batch execution after {len(data)}/{len(self.works)} works")
                # Store partial results for token_usage aggregation
                self._last_results = data
                # Return partial results with token_usage from completed works
                # This ensures we don't lose token_usage data

                raise Exception(f"Task was cancelled. Completed {len(data)}/{len(self.works)} works. Token usage preserved.")

            
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
                # Pass cancellation_checker to CrewManager for cancellation checking
                _crew_manager = CrewManager(
                    name=work_name,
                    works=work,
                    inputs=fresh_inputs,
                    is_sub_crew=True,
                    cancellation_checker=self.cancellation_checker  # Pass cancellation checker callback
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
                elif isinstance(result, dict) and result.get("status") == "cancelled":
                    # If a sub-crew was cancelled, treat the batch as cancelled
                    failed_works.append(work_name) # Mark as failed to trigger batch cancellation logic
                    logger.warning(f"Work {work_name} was cancelled, propagating cancellation to batch")
                else:
                    logger.info(f"Work {work_name} completed successfully")
                
                # Check cancellation after each work completes (allows cancellation between works)
                if self._check_cancellation():
                    logger.info(f"Task was cancelled after completing {len(data)}/{len(self.works)} works")
                    # Store partial results for token_usage aggregation
                    self._last_results = data
                    # Return partial results with token_usage from completed works
                    raise Exception(f"Task was cancelled. Completed {len(data)}/{len(self.works)} works. Token usage preserved.")
                    
            except Exception as e:
                # Check if this is a cancellation exception (re-raise it to propagate)
                if "cancelled" in str(e).lower() and "Task was cancelled" in str(e):
                    raise  # Re-raise cancellation exception to propagate it
                
                # If execution throws exception, create a failed result
                logger.error(f"Work {work_name} threw exception: {str(e)}", exc_info=True)
                failed_works.append(work_name)
                data[work_name] = {
                    "status": "failed",
                    "error": str(e),
                    "result": None
                }
        
        # If any work failed, raise exception (atomic operation)
        # But preserve token_usage from completed works
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
            error_msg = str(e)
            logger.error(f"Batch execution failed: {error_msg}", exc_info=True)
            
            # Check if this is a cancellation error
            is_cancelled = "cancelled" in error_msg.lower()
            
            # Try to aggregate token usage from already executed works
            # This ensures token_usage is preserved even when execution fails or is cancelled
            aggregated_token_usage = None
            try:
                # If we have partial results (from cancellation or failure), aggregate token usage
                if hasattr(self, '_last_results') and self._last_results:
                    aggregated_token_usage = self._aggregate_token_usage(self._last_results)
                    if aggregated_token_usage:
                        # Note: token_usage doesn't need status field, result already has status
                        logger.info(f"Aggregated token usage from executed works: {aggregated_token_usage}")
            except Exception as agg_error:
                logger.warning(f"Failed to aggregate token usage after failure: {str(agg_error)}")
            
            # Build error result with aggregated token_usage
            error_result = {
                "status": "cancelled" if is_cancelled else "failed",
                "error": error_msg,
                "result": None
            }
            
            # Add aggregated token usage even when execution fails or is cancelled
            # This preserves token_usage from completed works
            if aggregated_token_usage:
                error_result['token_usage'] = aggregated_token_usage
                logger.info(f"Token usage preserved: {aggregated_token_usage}")
            
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
                'successful_requests': 0
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
                    # Note: token_usage doesn't need status field, result already has status
            
            # Only return if we have meaningful data
            if has_token_usage:
                return aggregated_token_usage
                
        except Exception as e:
            logger.warning(f"Failed to aggregate token usage: {str(e)}")
        
        return None

