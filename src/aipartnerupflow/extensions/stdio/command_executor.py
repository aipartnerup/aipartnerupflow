"""
Command Executor for executing shell commands via stdio

⚠️ SECURITY WARNING:
This executor allows arbitrary command execution and is DISABLED by default
for security reasons. To enable it:
1. Set environment variable: AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1
2. Optionally configure command whitelist: AIPARTNERUPFLOW_STDIO_COMMAND_WHITELIST=cmd1,cmd2,cmd3

For production use, consider:
- Using SystemInfoExecutor instead (safer, predefined commands)
- Implementing custom executors with restricted command sets
- Running in sandboxed/containerized environments
"""

import asyncio
import os
import shlex
from typing import Dict, Any, Optional, Set
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.execution.errors import ValidationError, ConfigurationError
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Security configuration
# Command execution is disabled by default for security
STDIO_ALLOW_COMMAND = os.getenv("AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND", "").lower() in ("1", "true", "yes", "on")
STDIO_COMMAND_WHITELIST: Optional[Set[str]] = None

# Parse whitelist if provided
_whitelist_str = os.getenv("AIPARTNERUPFLOW_STDIO_COMMAND_WHITELIST", "").strip()
if _whitelist_str:
    STDIO_COMMAND_WHITELIST = {cmd.strip() for cmd in _whitelist_str.split(",") if cmd.strip()}
    logger.info(f"CommandExecutor: Command whitelist enabled with {len(STDIO_COMMAND_WHITELIST)} commands")


@executor_register()
class CommandExecutor(BaseTask):
    """
    Executor for executing shell commands via stdio
    
    ⚠️ SECURITY:
    - Command execution is DISABLED by default for security reasons
    - To enable: Set environment variable AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1
    - Optional whitelist: AIPARTNERUPFLOW_STDIO_COMMAND_WHITELIST=cmd1,cmd2,cmd3
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "command_executor"  # Executor id
        },
        "inputs": {
            "command": "python3 -c \"import sys; print(sys.version)\"",
            "timeout": 30  # optional
        }
    }
    """
    
    id = "command_executor"
    name = "Command Executor"
    description = "Execute shell commands via stdio communication (MCP-style)"
    tags = ["stdio", "command", "process", "mcp"]
    examples = [
        "Execute shell command via stdio",
        "Run Python script",
        "Execute system commands"
    ]
    
    # Cancellation support: Not implemented (could be added by checking cancellation_checker during execution)
    cancelable: bool = False
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "stdio"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a shell command via stdio
        
        ⚠️ SECURITY: This executor is disabled by default. Enable via AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1
        
        Args:
            inputs: Dictionary containing:
                - command: Shell command to execute (required)
                - timeout: (optional) Timeout in seconds (default: 30)
        
        Returns:
            Dictionary with execution results
        """
        # Security check: command execution must be explicitly enabled
        if not STDIO_ALLOW_COMMAND:
            error_msg = (
                f"[{self.id}] Command execution is disabled by default for security. "
                "To enable, set environment variable: AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1. "
                "Consider using 'system_info_executor' instead for safer system queries."
            )
            logger.error(f"Command execution blocked: {error_msg}")
            raise ConfigurationError(error_msg)
        
        command = inputs.get("command")
        if not command:
            raise ValidationError(f"[{self.id}] command is required in inputs")
        
        # Security check: whitelist validation if configured
        if STDIO_COMMAND_WHITELIST is not None:
            # Extract the base command (first word) for whitelist checking
            try:
                parsed = shlex.split(command)
                base_command = parsed[0] if parsed else command.split()[0]
            except (ValueError, IndexError):
                # If parsing fails, use first word as fallback
                base_command = command.split()[0] if command.split() else command
            
            if base_command not in STDIO_COMMAND_WHITELIST:
                error_msg = (
                    f"[{self.id}] Command '{base_command}' is not in the whitelist. "
                    f"Allowed commands: {', '.join(sorted(STDIO_COMMAND_WHITELIST))}"
                )
                logger.error(f"Command blocked by whitelist: {command}")
                raise ConfigurationError(error_msg)
        
        timeout = inputs.get("timeout", 30)
        
        # Log command execution with security warning
        logger.warning(
            f"Executing command via stdio (SECURITY RISK): {command}. "
            f"Ensure this is from a trusted source."
        )
        
        # Run command in subprocess with stdio communication
        # Note: Using shell=True is a security risk, but required for shell commands
        # This is why we have the whitelist and explicit enablement
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Exceptions (e.g., asyncio.TimeoutError) will propagate to TaskManager
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        return_code = process.returncode
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        
        result = {
            "command": command,
            "return_code": return_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "success": return_code == 0
        }
        
        if return_code != 0:
            logger.warning(f"Command failed with return code {return_code}: {stderr_text}")
        
        return result
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo command execution result"""
        command = inputs.get("command", "echo 'Hello, World!'")
        return {
            "command": command,
            "return_code": 0,
            "stdout": "Hello, World!\nDemo execution result",
            "stderr": "",
            "success": True,
            "_demo_sleep": 0.1  # Simulate local command execution time
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute (requires AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1)"
                },
                "timeout": {
                    "type": "number",
                    "description": "Command timeout in seconds (default: 30)"
                }
            },
            "required": ["command"]
        }

