"""
CrewManager class for defining agent crews (LLM-based via CrewAI)

CrewManager implements ExecutableTask interface and can be used:
1. Standalone: Execute a single crew directly
2. In Batch: As part of a batch operation (multiple crews executed atomically)
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from crewai import Crew as CrewAI
from crewai.agent import Agent
from crewai.task import Task
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import extension_register
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


@extension_register()
class CrewManager(BaseTask):
    """
    CrewManager class for executing agent crews (LLM-based via CrewAI)
    
    Implements ExecutableTask interface (via BaseTask), so CrewManager can be:
    - Executed standalone as a single task
    - Used within a Batch for atomic batch execution (with other crews)
    
    Wraps CrewAI Crew functionality with additional features like
    streaming context, input validation, and result processing.
    
    This class is similar to CrewManager in aisee-core, providing a wrapper
    around CrewAI Crew with enhanced functionality.
    """
    
    # Crew definition properties
    id: str = "crewai_executor"
    name: str = "CrewAI Executor"
    description: str = "LLM-based agent crew execution via CrewAI"
    tags: list[str] = []
    examples: list[str] = []
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "crewai"
    
    def __init__(
        self,
        name: str = "",
        agents: Optional[List[Dict[str, Any]]] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        is_sub_crew: bool = False,
        llm: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize CrewManager
        
        Args:
            name: Crew name
            agents: List of agent configurations
            tasks: List of task configurations
            inputs: Input parameters
            is_sub_crew: Whether this is a sub-crew in a batch
            llm: LLM provider configuration
            **kwargs: Additional configuration
        """
        # Initialize BaseTask first
        super().__init__(inputs=inputs, **kwargs)
        
        # Set name (override base if provided)
        if name:
            self.name = name
        self.name = self.name or self.id
        
        self.agents_config = agents or []
        self.tasks_config = tasks or []
        self.is_sub_crew = is_sub_crew
        self.llm = llm
        
        # Initialize CrewAI crew
        self.crew = None
        self._initialize_crew()
    
    def _initialize_crew(self) -> None:
        """Initialize CrewAI crew instance"""
        # Convert agent configs to Agent instances
        agents = []
        for agent_config in self.agents_config:
            agent = Agent(**agent_config)
            agents.append(agent)
        
        # Convert task configs to Task instances
        tasks = []
        for task_config in self.tasks_config:
            task = Task(**task_config)
            tasks.append(task)
        
        # Create CrewAI crew
        crew_kwargs = {
            "agents": agents,
            "tasks": tasks,
        }
        
        if self.llm:
            crew_kwargs["llm"] = self.llm
        
        self.crew = CrewAI(**crew_kwargs)
    
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
        # Default implementation
        return {}
    
    async def execute(self, inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Execute crew tasks
        
        Args:
            inputs: Input parameters
            
        Returns:
            Execution result dictionary
        """
        try:
            logger.info(f"Starting crew execution: {self.name}")
            
            if inputs:
                self.set_inputs(inputs)
            
            if not self.crew:
                raise ValueError("Crew not initialized")
            
            # Execute crew (synchronously - CrewAI doesn't support async yet)
            result = self.crew.kickoff(inputs=self.inputs)
            
            # Process result
            processed_result = self.process_result(result)
            logger.info(f"Crew execution completed: {self.name}")
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Crew execution failed: {str(e)}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "result": None
            }
    
    def process_result(self, result: Any) -> Any:
        """
        Process execution result
        
        Args:
            result: Raw execution result from CrewAI
            
        Returns:
            Processed result as dictionary
        """
        try:
            if isinstance(result, str):
                # Try to parse JSON string
                import json
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return result
            elif hasattr(result, 'raw'):
                # CrewAI result object
                return result.raw
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error processing result: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

