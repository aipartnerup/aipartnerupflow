"""
CrewManager class for defining agent crews (LLM-based via CrewAI)

CrewManager implements ExecutableTask interface and can be used:
1. Standalone: Execute a single crew directly
2. In Batch: As part of a batch operation (multiple crews executed atomically)
"""

from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel
from crewai import Crew as CrewAI, LLM
from crewai.agent import Agent
from crewai.task import Task
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import extension_register
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.core.tools import resolve_tool

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
        works: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        is_sub_crew: bool = False,
        **kwargs: Any
    ):
        """
        Initialize CrewManager
        
        Args:
            name: Crew name
            works: Dictionary of works (required, matches aisee_agents format).
                   Format: {"agents": {agent_name: agent_config}, "tasks": {task_name: task_config}}
                   Or: {"work_name": {"agents": {...}, "tasks": {...}}} (for batch compatibility)
            inputs: Input parameters
            is_sub_crew: Whether this is a sub-crew in a batch
            **kwargs: Additional configuration
        """
        # Initialize BaseTask first
        super().__init__(inputs=inputs, **kwargs)
        
        # Set name (override base if provided)
        if name:
            self.name = name
        self.name = self.name or self.id
        
        # Initialize agent and task storage (dict format, like aisee_agents)
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.task_config: Dict[str, Any] = {}
        
        self.is_sub_crew = is_sub_crew
        self.llm: Optional[str] = None
        
        # Process works parameter (required)
        if not works:
            raise ValueError("works parameter is required")
        
        if not isinstance(works, dict):
            raise ValueError("works must be a dictionary")

        if "agents" not in works or "tasks" not in works:
            raise ValueError("works must contain agents and tasks")

        
        # Create agents and tasks from works
        self.create_agents(works["agents"])
        self.create_tasks(works["tasks"])
        
        # Initialize CrewAI crew
        self.crew = None
        self._initialize_crew()
    
    def create_agents(self, agents: Optional[Dict[str, Any]] = None) -> Dict[str, Agent]:
        """
        Create agents from configuration (dict format, like aisee_agents)
        
        Args:
            agents: Dictionary of agent configurations {agent_name: agent_config}
            
        Returns:
            Dictionary of created agents
        """
        if not agents:
            return self.agents
        
        for agent_name, agent_config in agents.items():
            self.create_agent(agent_name, agent_config)
        
        return self.agents
    
    def create_agent(self, agent_name: str, agent_config: Dict[str, Any]) -> Agent:
        """
        Create agent from configuration
        
        Args:
            agent_name: Name of the agent
            agent_config: Dictionary of agent configuration
            
        Returns:
            Created Agent instance
        """
        try:
            logger.info(f"Creating agent: {agent_name}")
            
            # Create a copy of agent_config for processing
            processed_config = agent_config.copy()
            
            # Process LLM: if llm is a string, convert to LLM object
            llm_name = processed_config.get("llm")
            if llm_name and isinstance(llm_name, str):
                llm = LLM(model=llm_name)
                logger.info(f"Creating agent {agent_name} with LLM: {llm_name}")
                processed_config["llm"] = llm
            elif llm_name:
                # If llm is already an object, use it directly
                processed_config["llm"] = llm_name
            
            # Process tools: convert string tool names to callable objects
            if "tools" in processed_config:
                tools = processed_config.get("tools", [])
                if tools:
                    processed_config["tools"] = [resolve_tool(tool) for tool in tools]
            
            agent = Agent(**processed_config)
            self.agents[agent_name] = agent
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name}: {str(e)}")
            raise
    
    def create_tasks(self, tasks: Optional[Dict[str, Any]] = None) -> Dict[str, Task]:
        """
        Create tasks from configuration (dict format, like aisee_agents)
        
        Args:
            tasks: Dictionary of task configurations {task_name: task_config}
            
        Returns:
            Dictionary of created tasks
        """
        if not tasks:
            return self.tasks
        
        for task_name, task_config in tasks.items():
            self.create_task(task_name, task_config)
        
        return self.tasks
    
    def create_task(self, task_name: str, task_config: Dict[str, Any]) -> Task:
        """
        Create task from configuration
        
        Args:
            task_name: Name of the task
            task_config: Dictionary of task configuration
            
        Returns:
            Created Task instance
        """
        try:
            logger.info(f"Creating task: {task_name}")
            
            # Store task config for reference
            self.task_config[task_name] = task_config
            
            # Create a copy of task_config for processing
            processed_config = task_config.copy()
            
            # Process agent reference: if agent is a string, find the agent by name
            agent_name = processed_config.get("agent")
            if agent_name:
                if isinstance(agent_name, str):
                    if agent_name not in self.agents:
                        raise ValueError(f"Agent '{agent_name}' not found for task '{task_name}'")
                    processed_config["agent"] = self.agents[agent_name]
                # If agent is already an Agent object, use it directly
            else:
                # Set agent to None if empty string or not provided
                processed_config["agent"] = None
            
            task = Task(**processed_config)
            self.tasks[task_name] = task
            return task
            
        except Exception as e:
            logger.error(f"Failed to create task {task_name}: {str(e)}")
            raise
    
    def _initialize_crew(self) -> None:
        """Initialize CrewAI crew instance"""
        if not self.agents:
            raise ValueError("No agents created")
        
        if not self.tasks:
            raise ValueError("No tasks created")
        
        # Create CrewAI crew
        crew_kwargs = {
            "agents": list(self.agents.values()),
            "tasks": list(self.tasks.values()),
        }
        
        # Process crew-level LLM if provided
        if self.llm and isinstance(self.llm, str):
            crew_kwargs["llm"] = LLM(model=self.llm)
        elif self.llm:
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
            Execution result dictionary with status, result/error, and token_usage
        """
        token_usage = None  # Initialize token_usage to track LLM consumption
        
        try:
            logger.info(f"Starting crew execution: {self.name}")
            
            if inputs:
                self.set_inputs(inputs)
            
            if not self.crew:
                raise ValueError("Crew not initialized")
            
            # Execute crew (synchronously - CrewAI doesn't support async yet)
            result = self.crew.kickoff(inputs=self.inputs)
            
            # Extract token usage from result (primary method when execution succeeds)
            if hasattr(result, 'token_usage'):
                token_usage = self._parse_token_usage(result.token_usage)
                if token_usage:
                    token_usage['status'] = "success"
                    logger.info(f"Token usage from result: {token_usage}")
            
            # Process result
            processed_result = self.process_result(result)
            logger.info(f"Crew execution completed: {self.name}")
            
            # Build success result with token_usage
            success_result = {
                "status": "success",
                "result": processed_result
            }
            
            # Add token usage information to result
            if token_usage:
                success_result['token_usage'] = token_usage
            
            return success_result
            
        except Exception as e:
            logger.error(f"Crew execution failed: {str(e)}", exc_info=True)
            
            # Try to extract token usage from handlers when execution fails
            if token_usage is None:
                token_usage = self._extract_token_usage_from_handlers()
                if token_usage:
                    token_usage['status'] = "failed"
                    logger.info(f"Token usage from handlers (after failure): {token_usage}")
            
            # Build error result with token_usage
            error_result = {
                "status": "failed",
                "error": str(e),
                "result": None
            }
            
            # Add token usage information even when execution fails
            if token_usage:
                error_result['token_usage'] = token_usage
            
            return error_result
    
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
    
    def _parse_token_usage(self, token_usage_obj: Any) -> Optional[Dict[str, Any]]:
        """
        Parse token_usage object to dictionary
        
        Args:
            token_usage_obj: Token usage object from CrewAI result (can be dict, string, or object)
            
        Returns:
            Dictionary with token usage information or None if parsing fails
        """
        try:
            # If it's already a dictionary, return it
            if isinstance(token_usage_obj, dict):
                return token_usage_obj
            
            # If it's a string, try to parse it (e.g., "total_tokens=5781 prompt_tokens=5554 ...")
            if isinstance(token_usage_obj, str):
                usage_dict = {}
                parts = token_usage_obj.split()
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        try:
                            # Try to convert to int, fallback to string if it fails
                            usage_dict[key] = int(value)
                        except ValueError:
                            usage_dict[key] = value
                return usage_dict if usage_dict else None
            
            # If it's an object, try to get attributes
            if hasattr(token_usage_obj, '__dict__'):
                usage_dict = {
                    'total_tokens': getattr(token_usage_obj, 'total_tokens', 0),
                    'prompt_tokens': getattr(token_usage_obj, 'prompt_tokens', 0),
                    'completion_tokens': getattr(token_usage_obj, 'completion_tokens', 0),
                    'cached_prompt_tokens': getattr(token_usage_obj, 'cached_prompt_tokens', 0),
                    'successful_requests': getattr(token_usage_obj, 'successful_requests', 0),
                }
                # Only return if we have meaningful data
                if usage_dict.get('total_tokens', 0) > 0:
                    return usage_dict
            
            # Try to access as attributes directly
            if hasattr(token_usage_obj, 'total_tokens'):
                return {
                    'total_tokens': getattr(token_usage_obj, 'total_tokens', 0),
                    'prompt_tokens': getattr(token_usage_obj, 'prompt_tokens', 0),
                    'completion_tokens': getattr(token_usage_obj, 'completion_tokens', 0),
                    'cached_prompt_tokens': getattr(token_usage_obj, 'cached_prompt_tokens', 0),
                    'successful_requests': getattr(token_usage_obj, 'successful_requests', 0),
                }
                
        except Exception as e:
            logger.warning(f"Failed to parse token_usage: {str(e)}")
        
        return None
    
    def _extract_token_usage_from_handlers(self) -> Optional[Dict[str, Any]]:
        """
        Extract token usage from TokenCalcHandler or LiteLLM callbacks (fallback method)
        This method is used when execution fails and we can't access result.token_usage
        
        Returns:
            Dictionary with token usage information or None if extraction fails
        """
        try:
            import litellm
            
            # Method 1: Extract from LiteLLM global callbacks
            if hasattr(litellm, 'callbacks'):
                for callback in litellm.callbacks or []:
                    if 'TokenCalcHandler' in str(type(callback)):
                        if hasattr(callback, 'token_cost_process'):
                            process = callback.token_cost_process  # type: ignore
                            usage = {
                                'prompt_tokens': getattr(process, 'prompt_tokens', 0),
                                'completion_tokens': getattr(process, 'completion_tokens', 0),
                                'total_tokens': getattr(process, 'total_tokens', 0),
                                'cached_prompt_tokens': getattr(process, 'cached_prompt_tokens', 0),
                                'successful_requests': getattr(process, 'successful_requests', 0),
                            }
                            if usage.get('total_tokens', 0) > 0:
                                return usage
            
            # Method 2: Extract from agents' LLM callbacks
            total_usage = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cached_prompt_tokens': 0,
                'successful_requests': 0
            }
            
            # Try to extract from crew's agents if available
            if hasattr(self, 'crew') and self.crew:
                if hasattr(self.crew, 'agents'):
                    for agent in self.crew.agents or []:
                        if hasattr(agent, 'llm') and hasattr(agent.llm, 'callbacks'):
                            for callback in agent.llm.callbacks or []:
                                if 'TokenCalcHandler' in str(type(callback)):
                                    if hasattr(callback, 'token_cost_process'):
                                        process = callback.token_cost_process  # type: ignore
                                        total_usage['prompt_tokens'] += getattr(process, 'prompt_tokens', 0)
                                        total_usage['completion_tokens'] += getattr(process, 'completion_tokens', 0)
                                        total_usage['total_tokens'] += getattr(process, 'total_tokens', 0)
                                        total_usage['cached_prompt_tokens'] += getattr(process, 'cached_prompt_tokens', 0)
                                        total_usage['successful_requests'] += getattr(process, 'successful_requests', 0)
            
            # Only return if we have meaningful data
            if total_usage.get('total_tokens', 0) > 0:
                return total_usage
                
        except Exception as e:
            logger.warning(f"Failed to extract token_usage from handlers: {str(e)}")
        
        return None

