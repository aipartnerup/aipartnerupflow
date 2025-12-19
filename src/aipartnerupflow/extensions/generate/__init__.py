"""
Generate Executor Extension

This extension provides a generate_executor that generates valid task tree
JSON arrays from natural language requirements using LLM.
"""

from typing import Any, Dict, Optional
from aipartnerupflow.extensions.generate.generate_executor import GenerateExecutor
from aipartnerupflow.core.extensions.registry import add_executor_hook
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


async def _inject_llm_key_pre_hook(
    executor: Any,
    task: Any,
    inputs: Dict[str, Any]
) -> None:
    """
    Pre-hook to inject LLM API key from thread-local context into task inputs.
    
    This hook extracts the LLM API key from X-LLM-API-KEY header (stored in
    thread-local context by LLMAPIKeyMiddleware) and adds it to inputs
    so that generate_executor can use it.
    
    Args:
        executor: Executor instance (GenerateExecutor)
        task: TaskModel instance
        inputs: Input parameters dictionary (will be modified in-place)
    """
    # Check if this is generate_executor by checking executor type
    if not hasattr(executor, 'id') or executor.id != "generate_executor":
        # Also check task.name and schemas.method as fallback
        if task.name != "generate_executor":
            schemas = task.schemas or {}
            if schemas.get("method") != "generate_executor":
                return
    
    # Skip if api_key is already in inputs (don't override)
    if "api_key" in inputs:
        logger.debug(f"api_key already present in inputs for task {task.id}, skipping injection")
        return
    
    # Extract LLM key from thread-local context
    from aipartnerupflow.core.utils.llm_key_context import (
        get_llm_key_from_header,
        get_llm_provider_from_header
    )
    
    api_key = get_llm_key_from_header()
    if not api_key:
        logger.debug(f"No LLM key found in thread-local context for task {task.id}")
        return
    
    # Add api_key to inputs
    inputs["api_key"] = api_key
    logger.debug(f"Injected LLM API key from header into inputs for task {task.id}")
    
    # Optionally update llm_provider if specified in header
    provider = get_llm_provider_from_header()
    if provider and "llm_provider" not in inputs:
        inputs["llm_provider"] = provider
        logger.debug(f"Injected LLM provider '{provider}' from header into inputs for task {task.id}")


# Register the pre-hook for generate_executor
try:
    add_executor_hook("generate_executor", "pre_hook", _inject_llm_key_pre_hook)
    logger.info("Registered LLM API key injection pre-hook for generate_executor")
except Exception as e:
    logger.warning(f"Failed to register LLM API key injection pre-hook: {e}")

__all__ = ["GenerateExecutor"]

