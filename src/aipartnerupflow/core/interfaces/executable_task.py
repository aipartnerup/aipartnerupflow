"""
Executable task interface

This module defines the core interface for all executable tasks.
All task executors must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from aipartnerupflow.core.extensions.base import Extension
from aipartnerupflow.core.extensions.types import ExtensionCategory


class ExecutableTask(Extension, ABC):
    """
    Executable task interface - all executable units must implement this interface
    
    This interface extends Extension, so all executors are registered extensions.
    Implementations include:
    - CrewManager [crewai]: LLM-based agent crews (via CrewAI) - available in extensions/crewai/
    - SystemInfoExecutor [stdio]: Safe system information queries - available in extensions/stdio/
    - CommandExecutor [stdio]: Shell command execution - available in extensions/stdio/
    - Custom tasks: Non-LLM tasks (web scraping, API calls, data processing, etc.)
    
    Note: BatchManager is NOT an ExecutableTask. BatchManager is a container that batches multiple crews
    as an atomic operation (all crews execute, then merge results).
    """
    
    @property
    def category(self) -> ExtensionCategory:
        """Extension category - always EXECUTOR for ExecutableTask"""
        return ExtensionCategory.EXECUTOR
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for this task (required by Extension)"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Display name for this task (required by Extension)"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this task does (required by Extension)"""
        pass
    
    @abstractmethod
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute this task
        
        Args:
            inputs: Input parameters for task execution
            
        Returns:
            Execution result dictionary
        """
        pass
    
    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Return input parameter schema (JSON Schema format)
        
        Returns:
            JSON Schema dictionary describing input parameters
        """
        pass
    
    async def cancel(self) -> Dict[str, Any]:
        """
        Cancel task execution (optional method)
        
        This method is called by TaskManager when cancellation is requested.
        Executors that support cancellation should implement this method.
        
        Returns:
            Dictionary with cancellation result:
            {
                "status": "cancelled" | "failed",
                "message": str,  # Optional cancellation message
                "partial_result": Any,  # Optional partial result if available
                "token_usage": Dict,  # Optional token usage if available
            }
        
        Note:
            - If executor doesn't implement this method, TaskManager will handle cancellation
              by checking cancellation status and stopping execution at checkpoints
            - For executors that cannot be cancelled during execution (e.g., CrewManager),
              this method may return a result indicating cancellation will be checked after execution
        """
        # Default implementation: return not supported
        return {
            "status": "failed",
            "message": "Cancellation not supported by this executor",
            "error": "Executor does not implement cancel() method"
        }


__all__ = ["ExecutableTask"]

