"""
Stdio executor for process execution via stdin/stdout

Executes system commands and processes via stdio communication,
similar to MCP stdio transport mode.

⚠️ SECURITY WARNING:
The 'command' method allows arbitrary command execution and is DISABLED by default
for security reasons. To enable it:
1. Set environment variable: AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1
2. Optionally configure command whitelist: AIPARTNERUPFLOW_STDIO_COMMAND_WHITELIST=cmd1,cmd2,cmd3

For production use, consider:
- Using 'system_info' method instead (safer, predefined commands)
- Implementing custom executors with restricted command sets
- Running in sandboxed/containerized environments
"""

import asyncio
import subprocess
import platform
import json
import os
import shlex
from typing import Dict, Any, Optional, List, Set
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import extension_register
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
    logger.info(f"StdioExecutor: Command whitelist enabled with {len(STDIO_COMMAND_WHITELIST)} commands")


@extension_register()
class StdioExecutor(BaseTask):
    """
    Executes processes via stdio communication (inspired by MCP stdio mode)
    
    This executor can run shell commands, Python scripts, or any executable
    through stdin/stdout/stderr communication, similar to MCP stdio transport.
    
    ⚠️ SECURITY:
    - The 'command' method is DISABLED by default for security reasons
    - To enable: Set environment variable AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1
    - Optional whitelist: AIPARTNERUPFLOW_STDIO_COMMAND_WHITELIST=cmd1,cmd2,cmd3
    - The 'system_info' method is always available (uses predefined safe commands)
    
    Example usage in task schemas:
    {
        "type": "stdio",
        "method": "system_info",
        "resource": "cpu"  # or "memory", "disk", "all"
    }
    
    For command execution (requires explicit enablement):
    {
        "type": "stdio",
        "method": "command",
        "command": "python3 -c \"import sys; print(sys.version)\""
    }
    """
    
    id = "stdio_executor"
    name = "Stdio Executor"
    description = "Execute processes via stdio communication (MCP-style)"
    tags = ["stdio", "process", "system", "mcp"]
    examples = [
        "Execute shell command via stdio",
        "Get system information",
        "Run Python script"
    ]
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "stdio"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute command based on inputs
        
        Args:
            inputs: Dictionary containing:
                - command: Shell command to execute (for method="command")
                - resource: Resource type (for method="system_info": "cpu", "memory", "disk")
                - timeout: Optional timeout in seconds (default: 30)
        
        Returns:
            Dictionary with execution results
        """
        method = inputs.get("method", "command")
        
        if method == "command":
            return await self._execute_command(inputs)
        elif method == "system_info":
            return await self._execute_system_info(inputs)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    async def _execute_safe_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a predefined safe system command (bypasses security checks)
        
        This method is used internally by system_info methods to execute
        predefined, safe system queries. It does not require explicit enablement.
        """
        logger.debug(f"Executing safe system command: {command}")
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return_code = process.returncode
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()
            
            return {
                "command": command,
                "return_code": return_code,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "success": return_code == 0
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Safe command timeout after {timeout} seconds: {command}")
            return {
                "command": command,
                "success": False,
                "error": f"Command timeout after {timeout} seconds"
            }
        except Exception as e:
            logger.error(f"Error executing safe command: {e}", exc_info=True)
            return {
                "command": command,
                "success": False,
                "error": str(e)
            }
    
    async def _execute_command(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a shell command via stdio
        
        ⚠️ SECURITY: This method is disabled by default. Enable via AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1
        """
        # Security check: command execution must be explicitly enabled
        if not STDIO_ALLOW_COMMAND:
            error_msg = (
                "Command execution is disabled by default for security. "
                "To enable, set environment variable: AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND=1. "
                "Consider using 'system_info' method instead for safer system queries."
            )
            logger.error(f"Command execution blocked: {error_msg}")
            return {
                "command": inputs.get("command", ""),
                "success": False,
                "error": error_msg,
                "security_blocked": True
            }
        
        command = inputs.get("command")
        if not command:
            raise ValueError("command is required for method='command'")
        
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
                    f"Command '{base_command}' is not in the whitelist. "
                    f"Allowed commands: {', '.join(sorted(STDIO_COMMAND_WHITELIST))}"
                )
                logger.error(f"Command blocked by whitelist: {command}")
                return {
                    "command": command,
                    "success": False,
                    "error": error_msg,
                    "security_blocked": True
                }
        
        timeout = inputs.get("timeout", 30)
        
        # Log command execution with security warning
        logger.warning(
            f"Executing command via stdio (SECURITY RISK): {command}. "
            f"Ensure this is from a trusted source."
        )
        
        try:
            # Run command in subprocess with stdio communication
            # Note: Using shell=True is a security risk, but required for shell commands
            # This is why we have the whitelist and explicit enablement
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
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
            
        except asyncio.TimeoutError:
            logger.error(f"Command timeout after {timeout} seconds: {command}")
            return {
                "command": command,
                "success": False,
                "error": f"Command timeout after {timeout} seconds"
            }
        except Exception as e:
            logger.error(f"Error executing command: {e}", exc_info=True)
            return {
                "command": command,
                "success": False,
                "error": str(e)
            }
    
    async def _execute_system_info(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Get system resource information"""
        resource = inputs.get("resource", "all")
        
        if resource == "cpu":
            return await self._get_cpu_info()
        elif resource == "memory":
            return await self._get_memory_info()
        elif resource == "disk":
            return await self._get_disk_info()
        elif resource == "all":
            return {
                "cpu": await self._get_cpu_info(),
                "memory": await self._get_memory_info(),
                "disk": await self._get_disk_info()
            }
        else:
            raise ValueError(f"Unknown resource: {resource}. Use 'cpu', 'memory', 'disk', or 'all'")
    
    async def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            # Get CPU info separately to avoid parsing issues with brand name containing spaces
            brand_command = "sysctl -n machdep.cpu.brand_string"
            cores_command = "sysctl -n machdep.cpu.core_count"
            threads_command = "sysctl -n machdep.cpu.thread_count"
            
            brand_result = await self._execute_safe_command(brand_command)
            cores_result = await self._execute_safe_command(cores_command)
            threads_result = await self._execute_safe_command(threads_command)
            
            info = {"system": system}
            
            if brand_result.get("success"):
                info["brand"] = brand_result["stdout"].strip()
            
            if cores_result.get("success"):
                try:
                    info["cores"] = int(cores_result["stdout"].strip())
                except (ValueError, AttributeError):
                    pass
            
            if threads_result.get("success"):
                try:
                    info["threads"] = int(threads_result["stdout"].strip())
                except (ValueError, AttributeError):
                    pass
            
            # Fallback: get basic info if we don't have cores
            if "cores" not in info:
                command = "sysctl -n hw.ncpu"
                result = await self._execute_safe_command(command)
                if result.get("success"):
                    try:
                        info["cores"] = int(result["stdout"].strip())
                    except (ValueError, AttributeError):
                        pass
            
            return info
        elif system == "Linux":
            command = "lscpu | grep -E 'Model name|CPU\\(s\\)|Thread\\(s\\) per core' | head -3"
            result = await self._execute_safe_command(command)
            # Parse lscpu output
            info = {"system": system}
            if result.get("success"):
                for line in result["stdout"].split('\n'):
                    if 'Model name' in line:
                        info["brand"] = line.split(':')[1].strip()
                    elif 'CPU(s)' in line:
                        info["cores"] = int(line.split(':')[1].strip())
            return info
        else:  # Windows or other
            return {
                "system": system,
                "cores": platform.processor() or "Unknown"
            }
    
    async def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            command = "sysctl -n hw.memsize | awk '{print $1/1024/1024/1024}'"
            result = await self._execute_safe_command(command)
            if result.get("success"):
                try:
                    total_gb = float(result["stdout"].strip())
                    return {
                        "total_gb": round(total_gb, 2),
                        "system": system
                    }
                except ValueError:
                    pass
            
            # Fallback
            command = "sysctl -n hw.memsize"
            result = await self._execute_safe_command(command)
            if result.get("success"):
                try:
                    total_bytes = int(result["stdout"].strip())
                    return {
                        "total_bytes": total_bytes,
                        "total_gb": round(total_bytes / 1024 / 1024 / 1024, 2),
                        "system": system
                    }
                except ValueError:
                    pass
        
        elif system == "Linux":
            command = "free -h | grep Mem | awk '{print $2}'"
            result = await self._execute_safe_command(command)
            if result.get("success"):
                return {
                    "total": result["stdout"].strip(),
                    "system": system
                }
        
        return {
            "system": system,
            "note": "Memory info not available for this system"
        }
    
    async def _get_disk_info(self) -> Dict[str, Any]:
        """Get disk information"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            command = "df -h / | tail -1 | awk '{print $2, $3, $4, $5}'"
            result = await self._execute_safe_command(command)
            if result.get("success"):
                parts = result["stdout"].strip().split()
                if len(parts) >= 4:
                    return {
                        "total": parts[0],
                        "used": parts[1],
                        "available": parts[2],
                        "used_percent": parts[3],
                        "system": system
                    }
        
        elif system == "Linux":
            command = "df -h / | tail -1 | awk '{print $2, $3, $4, $5}'"
            result = await self._execute_safe_command(command)
            if result.get("success"):
                parts = result["stdout"].strip().split()
                if len(parts) >= 4:
                    return {
                        "total": parts[0],
                        "used": parts[1],
                        "available": parts[2],
                        "used_percent": parts[3],
                        "system": system
                    }
        
        return {
            "system": system,
            "note": "Disk info not available for this system"
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["command", "system_info"],
                    "description": "Execution method"
                },
                "command": {
                    "type": "string",
                    "description": "Shell command to execute (required for method='command')"
                },
                "resource": {
                    "type": "string",
                    "enum": ["cpu", "memory", "disk", "all"],
                    "description": "Resource type to query (required for method='system_info')"
                },
                "timeout": {
                    "type": "number",
                    "description": "Command timeout in seconds (default: 30)"
                }
            },
            "required": ["method"]
        }

