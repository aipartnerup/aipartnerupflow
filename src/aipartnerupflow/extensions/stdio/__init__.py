"""
Stdio executor feature

This feature provides stdio-based process execution capabilities for tasks,
inspired by MCP (Model Context Protocol) stdio transport mode.
Useful for system operations, data processing, and other non-LLM tasks.

This package provides two executors:
- SystemInfoExecutor: Safe system information queries (CPU, memory, disk)
- CommandExecutor: Shell command execution (requires explicit enablement for security)
"""

from aipartnerupflow.extensions.stdio.system_info_executor import SystemInfoExecutor
from aipartnerupflow.extensions.stdio.command_executor import CommandExecutor

__all__ = ["SystemInfoExecutor", "CommandExecutor"]

