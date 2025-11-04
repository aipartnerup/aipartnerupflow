"""
Task execution interfaces for crews and custom tasks

Note: Batch is not a task interface - it's a batch container for crews (atomic operation).
All executable units (LLM-based crews or custom non-LLM tasks) implement ExecutableTask.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ExecutableTask(ABC):
    """
    Executable task interface - all executable units must implement this interface
    
    This interface is implemented by:
    - CrewManager [crewai]: LLM-based agent crews (via CrewAI) - available in features/crewai/
    - Custom tasks: Non-LLM tasks (web scraping, API calls, data processing, etc.)
    
    Note: BatchManager is NOT an ExecutableTask. BatchManager is a container that batches multiple crews
    as an atomic operation (all crews execute, then merge results).
    """
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for this task"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Display name for this task"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this task does"""
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


class BaseTask(ExecutableTask):
    """
    Base task class with common implementations (optional base class)
    
    Provides common functionality for executable tasks, similar to BaseManager in aisee-core.
    You can inherit from BaseTask to get common implementations, or implement ExecutableTask
    directly for maximum flexibility.
    
    Inherit from BaseTask if you need:
    - Common initialization and input management
    - Streaming context support
    - Input validation utilities
    
    Implement ExecutableTask directly if you want:
    - Full control over implementation
    - Minimal dependencies
    """
    
    # Task definition properties - should be overridden by subclasses
    id: str = ""
    name: str = ""
    description: str = ""
    tags: list[str] = []
    examples: list[str] = []
    
    def __init__(self, inputs: Optional[Dict[str, Any]] = None, **kwargs: Any):
        """
        Initialize BaseTask
        
        Args:
            inputs: Initial input parameters
            **kwargs: Additional configuration options
        """
        self.inputs: Dict[str, Any] = inputs or {}
        
        # Streaming context for progress updates
        self.event_queue = None
        self.context = None
        
        # Initialize with any provided kwargs
        self.init(**kwargs)
    
    def init(self, **kwargs: Any) -> None:
        """Initialize task with configuration"""
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
        if "inputs" in kwargs:
            self.inputs = kwargs["inputs"]
    
    def set_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Set input parameters
        
        Args:
            inputs: Dictionary of inputs
        """
        self.inputs = inputs
    
    def set_streaming_context(self, event_queue: Any, context: Any) -> None:
        """
        Set streaming context for progress updates
        
        Args:
            event_queue: Event queue for streaming updates
            context: Request context
        """
        self.event_queue = event_queue
        self.context = context
    
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Get input parameter schema (default implementation)
        
        Returns:
            Empty dictionary - subclasses should override this
        """
        return {}

