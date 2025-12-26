"""
SSH Executor for executing commands on remote servers

This executor allows tasks to execute commands on remote servers
via SSH with password or key-based authentication.
"""

import asyncio
import os
import stat
from typing import Dict, Any, Optional
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.execution.errors import ValidationError, ConfigurationError
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import asyncssh
    ASYNCSSH_AVAILABLE = True
except ImportError:
    ASYNCSSH_AVAILABLE = False
    logger.warning(
        "asyncssh is not installed. SSH executor will not be available. "
        "Install it with: pip install aipartnerupflow[ssh]"
    )


@executor_register()
class SshExecutor(BaseTask):
    """
    Executor for executing commands on remote servers via SSH
    
    Supports password and key-based authentication.
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "ssh_executor"  # Executor id
        },
        "inputs": {
            "host": "example.com",
            "username": "user",
            "key_file": "/path/to/key",
            "command": "ls -la",
            "timeout": 30
        }
    }
    """
    
    id = "ssh_executor"
    name = "SSH Executor"
    description = "Execute commands on remote servers via SSH"
    tags = ["ssh", "remote", "command"]
    examples = [
        "Execute command on remote server",
        "Run script on remote host",
        "Remote system administration"
    ]
    
    # Cancellation support: Can be cancelled by closing SSH connection
    cancelable: bool = True
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "ssh"
    
    def _validate_key_file(self, key_file: str) -> None:
        """
        Validate SSH key file permissions
        
        SSH keys should have restrictive permissions (600 or 400)
        """
        if not os.path.exists(key_file):
            raise FileNotFoundError(f"SSH key file not found: {key_file}")
        
        file_stat = os.stat(key_file)
        mode = stat.filemode(file_stat.st_mode)
        
        # Check if permissions are too permissive
        # Should be 600 (rw-------) or 400 (r--------)
        permissions = file_stat.st_mode & 0o777
        if permissions not in (0o600, 0o400):
            logger.warning(
                f"SSH key file {key_file} has permissions {mode}. "
                f"Recommended: 600 (rw-------) or 400 (r--------)"
            )
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command on a remote server via SSH
        
        Args:
            inputs: Dictionary containing:
                - host: Remote hostname or IP (required)
                - port: SSH port (default: 22)
                - username: SSH username (required)
                - password: SSH password (optional, if key_file not provided)
                - key_file: Path to SSH private key file (optional, if password not provided)
                - command: Command to execute (required)
                - timeout: Command timeout in seconds (default: 30)
                - env: Environment variables dict (optional)
        
        Returns:
            Dictionary with execution results:
                - command: Executed command
                - stdout: Standard output
                - stderr: Standard error
                - return_code: Exit code
                - success: Boolean indicating success (return_code == 0)
        """
        # Validate basic required inputs first (before checking ASYNCSSH_AVAILABLE)
        # This ensures tests can verify validation logic even when asyncssh is not installed
        host = inputs.get("host")
        if not host:
            raise ValidationError(f"[{self.id}] host is required")
        
        username = inputs.get("username")
        if not username:
            raise ValidationError(f"[{self.id}] username is required")
        
        command = inputs.get("command")
        if not command:
            raise ValidationError(f"[{self.id}] command is required")
        
        # Check if asyncssh is available before authentication validation
        # If not available, raise ConfigurationError immediately
        if not ASYNCSSH_AVAILABLE:
            raise ConfigurationError(
                f"[{self.id}] asyncssh is not installed. Install it with: pip install aipartnerupflow[ssh]"
            )
        
        # Validate authentication (only if asyncssh is available)
        password = inputs.get("password")
        key_file = inputs.get("key_file")
        if not password and not key_file:
            raise ValidationError(f"[{self.id}] Either password or key_file must be provided")
        
        port = inputs.get("port", 22)
        timeout = inputs.get("timeout", 30)
        env = inputs.get("env", {})
        
        # Validate key file if provided
        # Exceptions from _validate_key_file (e.g., FileNotFoundError) will propagate
        if key_file:
            self._validate_key_file(key_file)
        
        logger.info(f"Executing SSH command on {username}@{host}:{port}: {command}")
        
        # Prepare client kwargs
        client_kwargs = {
            "host": host,
            "port": port,
            "username": username,
        }
        
        # Add authentication
        if key_file:
            client_kwargs["client_keys"] = [key_file]
        if password:
            client_kwargs["password"] = password
        
        # Check for cancellation before connecting
        if self.cancellation_checker and self.cancellation_checker():
            logger.info("SSH command cancelled before connection")
            return {
                "success": False,
                "error": "Command was cancelled",
                "host": host,
                "command": command
            }
        
        # Exceptions (e.g., asyncssh.Error, asyncio.TimeoutError)
        # will propagate to TaskManager
        async with asyncssh.connect(**client_kwargs) as conn:
            # Check for cancellation after connection
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("SSH command cancelled after connection")
                return {
                    "success": False,
                    "error": "Command was cancelled",
                    "host": host,
                    "command": command
                }
            
            # Prepare environment variables
            env_vars = " ".join([f"{k}={v}" for k, v in env.items()]) if env else ""
            full_command = f"{env_vars} {command}".strip() if env_vars else command
            
            # Execute command with timeout
            result = await asyncio.wait_for(
                conn.run(full_command),
                timeout=timeout
            )
            
            # Check for cancellation after execution
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("SSH command cancelled after execution")
                return {
                    "success": False,
                    "error": "Command was cancelled",
                    "host": host,
                    "command": command,
                    "return_code": result.exit_status
                }
            
            return {
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.exit_status,
                "success": result.exit_status == 0,
                "host": host,
                "username": username
            }
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo SSH command execution result"""
        command = inputs.get("command", "echo 'Hello from remote server'")
        host = inputs.get("host", "demo.example.com")
        return {
            "host": host,
            "command": command,
            "return_code": 0,
            "stdout": "Hello from remote server\nDemo SSH execution result",
            "stderr": "",
            "success": True,
            "_demo_sleep": 0.5  # Simulate SSH connection and command execution time
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Remote hostname or IP address"
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)"
                },
                "username": {
                    "type": "string",
                    "description": "SSH username"
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (if key_file not provided)"
                },
                "key_file": {
                    "type": "string",
                    "description": "Path to SSH private key file (if password not provided)"
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute on remote server"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Command timeout in seconds (default: 30)"
                },
                "env": {
                    "type": "object",
                    "description": "Environment variables to set for command execution"
                }
            },
            "required": ["host", "username", "command"]
        }

