"""
Docker Executor for executing commands in Docker containers

This executor allows tasks to execute commands in Docker containers
with custom images, environment variables, and volume mounts.
"""

import asyncio
from typing import Dict, Any, Optional
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.execution.errors import ValidationError, ConfigurationError
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.warning(
        "docker is not installed. Docker executor will not be available. "
        "Install it with: pip install aipartnerupflow[docker]"
    )


@executor_register()
class DockerExecutor(BaseTask):
    """
    Executor for executing commands in Docker containers
    
    Supports custom images, environment variables, volume mounts,
    and resource limits.
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "docker_executor"  # Executor id
        },
        "inputs": {
            "image": "python:3.11",
            "command": "python -c 'print(\"Hello\")'",
            "env": {"KEY": "value"},
            "volumes": {"/host/path": "/container/path"},
            "timeout": 60
        }
    }
    """
    
    id = "docker_executor"
    name = "Docker Executor"
    description = "Execute commands in Docker containers"
    tags = ["docker", "container", "isolated"]
    examples = [
        "Run command in Docker container",
        "Execute script in isolated environment",
        "Containerized task execution"
    ]
    
    # Cancellation support: Can be cancelled by stopping container
    cancelable: bool = True
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "docker"
    
    def __init__(self, inputs: Optional[Dict[str, Any]] = None, **kwargs: Any):
        """Initialize DockerExecutor"""
        super().__init__(inputs=inputs, **kwargs)
        self._client: Optional[Any] = None
    
    def _get_client(self):
        """Get Docker client instance"""
        if not DOCKER_AVAILABLE:
            raise ConfigurationError(
                "docker is not installed. Install it with: pip install aipartnerupflow[docker]"
            )
        
        if self._client is None:
            try:
                self._client = docker.from_env()
            except Exception as e:
                logger.error(f"Failed to connect to Docker daemon: {e}")
                raise
        
        return self._client
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command in a Docker container
        
        Args:
            inputs: Dictionary containing:
                - image: Docker image name (required)
                - command: Command to execute in container (required)
                - env: Environment variables dict (optional)
                - volumes: Volume mounts dict {"host_path": "container_path"} (optional)
                - working_dir: Working directory in container (optional)
                - timeout: Command timeout in seconds (default: 60)
                - remove: Remove container after execution (default: True)
                - resources: Resource limits dict:
                    - cpu: CPU limit (e.g., "1.0" or "0.5")
                    - memory: Memory limit (e.g., "512m" or "1g")
        
        Returns:
            Dictionary with execution results:
                - container_id: Container ID
                - logs: Container logs (stdout + stderr)
                - exit_code: Container exit code
                - success: Boolean indicating success (exit_code == 0)
        """
        if not DOCKER_AVAILABLE:
            raise ConfigurationError(
                "docker is not installed. Install it with: pip install aipartnerupflow[docker]"
            )
        
        image = inputs.get("image")
        if not image:
            raise ValidationError(f"[{self.id}] image is required in inputs")
        
        command = inputs.get("command")
        if not command:
            raise ValidationError(f"[{self.id}] command is required in inputs")
        
        env = inputs.get("env", {})
        volumes = inputs.get("volumes", {})
        working_dir = inputs.get("working_dir")
        timeout = inputs.get("timeout", 60)
        remove = inputs.get("remove", True)
        resources_config = inputs.get("resources", {})
        
        logger.info(f"Executing Docker command in image {image}: {command}")
        
        client = self._get_client()
        
        # Check for cancellation before creating container
        if self.cancellation_checker and self.cancellation_checker():
            logger.info("Docker command cancelled before container creation")
            return {
                "success": False,
                "error": "Command was cancelled",
                "image": image,
                "command": command
            }
        
        # Prepare volume mounts
        volume_mounts = []
        if volumes:
            for host_path, container_path in volumes.items():
                volume_mounts.append(f"{host_path}:{container_path}")
        
        # Prepare resource limits
        mem_limit = resources_config.get("memory")
        cpu_limit = resources_config.get("cpu")
        
        # Exceptions (e.g., docker.errors.ImageNotFound, docker.errors.APIError)
        # will propagate to TaskManager
        # Create container
        container = client.containers.create(
            image=image,
            command=command,
            environment=env if env else None,
            volumes=volume_mounts if volume_mounts else None,
            working_dir=working_dir,
            detach=True,
            mem_limit=mem_limit,
            cpu_period=100000,  # Default CPU period
            cpu_quota=int(float(cpu_limit) * 100000) if cpu_limit else None,
        )
        
        container_id = container.id
        logger.debug(f"Created container {container_id}")
        
        try:
            # Check for cancellation before starting
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("Docker command cancelled before container start")
                # Container was created but not started
                # Removal will be handled in finally block
                return {
                    "success": False,
                    "error": "Command was cancelled",
                    "image": image,
                    "command": command,
                    "container_id": container_id
                }
            
            # Start container
            container.start()
            logger.debug(f"Started container {container_id}")
            
            # Wait for container to finish with timeout
            try:
                wait_result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait),
                    timeout=timeout
                )
                # Extract StatusCode from wait result
                exit_code = wait_result.get("StatusCode", -1) if isinstance(wait_result, dict) else wait_result
            except asyncio.TimeoutError:
                logger.warning(f"Container {container_id} timeout after {timeout} seconds, stopping...")
                container.stop(timeout=5)
                exit_code = -1
            
            # Check for cancellation after execution
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("Docker command cancelled after execution")
                # Removal will be handled in finally block
                return {
                    "success": False,
                    "error": "Command was cancelled",
                    "image": image,
                    "command": command,
                    "container_id": container_id,
                    "exit_code": exit_code
                }
            
            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
            
            result = {
                "container_id": container_id,
                "logs": logs,
                "exit_code": exit_code,
                "success": exit_code == 0,
                "image": image,
                "command": command
            }
            
            if exit_code != 0:
                logger.warning(f"Container {container_id} exited with code {exit_code}")
            
            return result
            
        finally:
            # Remove container if requested
            if remove:
                try:
                    container.remove(force=True)
                    logger.debug(f"Removed container {container_id}")
                except Exception as e:
                    logger.warning(f"Failed to remove container {container_id}: {e}")
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "image": {
                    "type": "string",
                    "description": "Docker image name (e.g., 'python:3.11')"
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute in container"
                },
                "env": {
                    "type": "object",
                    "description": "Environment variables as key-value pairs"
                },
                "volumes": {
                    "type": "object",
                    "description": "Volume mounts as {'host_path': 'container_path'}"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory in container"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Command timeout in seconds (default: 60)"
                },
                "remove": {
                    "type": "boolean",
                    "description": "Remove container after execution (default: True)"
                },
                "resources": {
                    "type": "object",
                    "description": "Resource limits",
                    "properties": {
                        "cpu": {
                            "type": "string",
                            "description": "CPU limit (e.g., '1.0' or '0.5')"
                        },
                        "memory": {
                            "type": "string",
                            "description": "Memory limit (e.g., '512m' or '1g')"
                        }
                    }
                }
            },
            "required": ["image", "command"]
        }
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo Docker container execution result"""
        image = inputs.get("image", "python:3.11")
        command = inputs.get("command", "echo 'Hello from Docker'")
        
        return {
            "image": image,
            "command": command,
            "container_id": "demo-container-123",
            "return_code": 0,
            "stdout": "Hello from Docker\nDemo Docker execution result",
            "stderr": "",
            "success": True,
            "execution_time": 1.5,
            "_demo_sleep": 1.0  # Simulate Docker container startup and execution time
        }

