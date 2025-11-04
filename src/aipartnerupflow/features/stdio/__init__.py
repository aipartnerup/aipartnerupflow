"""
Stdio executor feature

This feature provides stdio-based process execution capabilities for tasks,
inspired by MCP (Model Context Protocol) stdio transport mode.
Useful for system operations, data processing, and other non-LLM tasks.
"""

from aipartnerupflow.features.stdio.executor import StdioExecutor

__all__ = ["StdioExecutor"]

