"""
System Info Executor for querying system resource information

This executor provides safe, predefined system information queries
for CPU, memory, and disk resources. All commands are predefined and safe.
"""

import asyncio
import platform
from typing import Dict, Any
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


@executor_register()
class SystemInfoExecutor(BaseTask):
    """
    Executor for querying system resource information
    
    This executor provides safe, predefined system information queries
    for CPU, memory, and disk resources. All commands are predefined and safe.
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "system_info_executor"  # Executor id
        },
        "input_data": {
            "resource": "cpu"  # "cpu", "memory", "disk", or "all"
        }
    }
    """
    
    id = "system_info_executor"
    name = "System Info Executor"
    description = "Query system resource information (CPU, memory, disk)"
    tags = ["stdio", "system", "info", "safe"]
    examples = [
        "Get CPU information",
        "Get memory information",
        "Get disk information",
        "Get all system resources"
    ]
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "stdio"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get system resource information
        
        Args:
            inputs: Dictionary containing:
                - resource: Resource type to query: "cpu", "memory", "disk", or "all"
                - timeout: (optional) Timeout in seconds (default: 30)
        
        Returns:
            Dictionary with system resource information
        """
        resource = inputs.get("resource", "all")
        
        if resource == "cpu":
            return await self._get_cpu_info(inputs.get("timeout", 30))
        elif resource == "memory":
            return await self._get_memory_info(inputs.get("timeout", 30))
        elif resource == "disk":
            return await self._get_disk_info(inputs.get("timeout", 30))
        elif resource == "all":
            return {
                "cpu": await self._get_cpu_info(inputs.get("timeout", 30)),
                "memory": await self._get_memory_info(inputs.get("timeout", 30)),
                "disk": await self._get_disk_info(inputs.get("timeout", 30))
            }
        else:
            raise ValueError(f"Unknown resource: {resource}. Use 'cpu', 'memory', 'disk', or 'all'")
    
    async def _execute_safe_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a predefined safe system command
        
        This method is used internally to execute predefined, safe system queries.
        All commands are predefined and safe.
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
    
    async def _get_cpu_info(self, timeout: int = 30) -> Dict[str, Any]:
        """Get CPU information"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            # Get CPU info separately to avoid parsing issues with brand name containing spaces
            brand_command = "sysctl -n machdep.cpu.brand_string"
            cores_command = "sysctl -n machdep.cpu.core_count"
            threads_command = "sysctl -n machdep.cpu.thread_count"
            
            brand_result = await self._execute_safe_command(brand_command, timeout)
            cores_result = await self._execute_safe_command(cores_command, timeout)
            threads_result = await self._execute_safe_command(threads_command, timeout)
            
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
                result = await self._execute_safe_command(command, timeout)
                if result.get("success"):
                    try:
                        info["cores"] = int(result["stdout"].strip())
                    except (ValueError, AttributeError):
                        pass
            
            return info
        elif system == "Linux":
            command = "lscpu | grep -E 'Model name|CPU\\(s\\)|Thread\\(s\\) per core' | head -3"
            result = await self._execute_safe_command(command, timeout)
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
    
    async def _get_memory_info(self, timeout: int = 30) -> Dict[str, Any]:
        """Get memory information"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            command = "sysctl -n hw.memsize | awk '{print $1/1024/1024/1024}'"
            result = await self._execute_safe_command(command, timeout)
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
            result = await self._execute_safe_command(command, timeout)
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
            result = await self._execute_safe_command(command, timeout)
            if result.get("success"):
                return {
                    "total": result["stdout"].strip(),
                    "system": system
                }
        
        return {
            "system": system,
            "note": "Memory info not available for this system"
        }
    
    async def _get_disk_info(self, timeout: int = 30) -> Dict[str, Any]:
        """Get disk information"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            command = "df -h / | tail -1 | awk '{print $2, $3, $4, $5}'"
            result = await self._execute_safe_command(command, timeout)
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
            result = await self._execute_safe_command(command, timeout)
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
                "resource": {
                    "type": "string",
                    "enum": ["cpu", "memory", "disk", "all"],
                    "description": "Resource type to query: 'cpu', 'memory', 'disk', or 'all'"
                },
                "timeout": {
                    "type": "number",
                    "description": "Command timeout in seconds (default: 30)"
                }
            },
            "required": ["resource"]
        }

