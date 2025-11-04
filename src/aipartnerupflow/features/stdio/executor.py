"""
Stdio executor for process execution via stdin/stdout

Executes system commands and processes via stdio communication,
similar to MCP stdio transport mode.
"""

import asyncio
import subprocess
import platform
import json
from typing import Dict, Any, Optional
from aipartnerupflow.core.interfaces.plugin import BaseTask
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class StdioExecutor(BaseTask):
    """
    Executes processes via stdio communication (inspired by MCP stdio mode)
    
    This executor can run shell commands, Python scripts, or any executable
    through stdin/stdout/stderr communication, similar to MCP stdio transport.
    
    Example usage in task schemas:
    {
        "type": "stdio",
        "method": "command",
        "command": "python3 -c \"import sys; print(sys.version)\""
    }
    
    Or for system resource monitoring:
    {
        "type": "stdio",
        "method": "system_info",
        "resource": "cpu"  # or "memory", "disk"
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
    
    async def _execute_command(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command via stdio"""
        command = inputs.get("command")
        if not command:
            raise ValueError("command is required for method='command'")
        
        timeout = inputs.get("timeout", 30)
        
        logger.info(f"Executing command via stdio: {command}")
        
        try:
            # Run command in subprocess with stdio communication
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
            
            brand_result = await self._execute_command({"command": brand_command, "method": "command"})
            cores_result = await self._execute_command({"command": cores_command, "method": "command"})
            threads_result = await self._execute_command({"command": threads_command, "method": "command"})
            
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
                result = await self._execute_command({"command": command, "method": "command"})
                if result.get("success"):
                    try:
                        info["cores"] = int(result["stdout"].strip())
                    except (ValueError, AttributeError):
                        pass
            
            return info
        elif system == "Linux":
            command = "lscpu | grep -E 'Model name|CPU\\(s\\)|Thread\\(s\\) per core' | head -3"
            result = await self._execute_command({"command": command, "method": "command"})
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
            result = await self._execute_command({"command": command, "method": "command"})
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
            result = await self._execute_command({"command": command, "method": "command"})
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
            result = await self._execute_command({"command": command, "method": "command"})
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
            result = await self._execute_command({"command": command, "method": "command"})
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
            result = await self._execute_command({"command": command, "method": "command"})
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

