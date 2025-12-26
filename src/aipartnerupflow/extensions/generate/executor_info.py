"""
Executor Information Collector

This module collects information about available executors and their schemas
for use in LLM context when generating task trees.
"""

from typing import Dict, Any, List, Optional
from aipartnerupflow.core.extensions.registry import get_registry
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def get_available_executors() -> List[Dict[str, Any]]:
    """
    Get all registered executors with their metadata
    
    Returns:
        List of executor dictionaries containing id, name, description, and schema
    """
    registry = get_registry()
    executors = []
    
    # Get all registered executor extensions
    executor_extensions = registry.list_executors()
    
    for extension in executor_extensions:
        try:
            # Get executor metadata from extension
            executor_id = extension.id
            executor_name = extension.name
            executor_description = getattr(extension, 'description', '')
            executor_tags = getattr(extension, 'tags', [])
            executor_type = extension.type or "default"
            
            # Try to get input schema
            input_schema = None
            try:
                # Try to create a temporary instance to get schema
                # Use registry's create_executor_instance method
                temp_executor = registry.create_executor_instance(executor_id, inputs={})
                if temp_executor and hasattr(temp_executor, 'get_input_schema'):
                    input_schema = temp_executor.get_input_schema()
            except Exception as e:
                logger.debug(f"Could not get schema for executor {executor_id}: {e}")
                # Try to get schema from extension if it has the method
                if hasattr(extension, 'get_input_schema'):
                    try:
                        input_schema = extension.get_input_schema()
                    except Exception:
                        pass
                # Try to get schema from class if it's a class attribute
                if not input_schema:
                    executor_class = extension.__class__
                    if hasattr(executor_class, 'inputs_schema'):
                        input_schema = executor_class.inputs_schema
                        if hasattr(input_schema, 'model_json_schema'):
                            # Pydantic model
                            input_schema = input_schema.model_json_schema()
                        elif hasattr(input_schema, 'schema'):
                            # Pydantic v1
                            input_schema = input_schema.schema()
            
            executor_info = {
                "id": executor_id,
                "name": executor_name,
                "description": executor_description,
                "tags": executor_tags,
                "task_type": executor_type,
                "input_schema": input_schema
            }
            
            executors.append(executor_info)
            
        except Exception as e:
            logger.warning(f"Error collecting info for executor {getattr(extension, 'id', 'unknown')}: {e}")
            continue
    
    return executors


def get_executor_schema(executor_id: str) -> Optional[Dict[str, Any]]:
    """
    Get input schema for a specific executor
    
    Args:
        executor_id: Executor ID to look up
        
    Returns:
        Input schema dictionary, or None if executor not found
    """
    executors = get_available_executors()
    for executor in executors:
        if executor["id"] == executor_id:
            return executor.get("input_schema")
    return None


def format_executors_for_llm(max_executors: int = 20, max_schema_props: int = 5) -> str:
    """
    Format executor information for LLM context (optimized for token limits)
    
    Args:
        max_executors: Maximum number of executors to include
        max_schema_props: Maximum number of schema properties per executor
        
    Returns:
        Formatted string containing executor information (truncated)
    """
    executors = get_available_executors()
    
    if not executors:
        return "No executors are currently registered."
    
    # Limit number of executors
    executors = executors[:max_executors]
    
    lines = ["Available Executors (showing most common):", ""]
    
    for executor in executors:
        lines.append(f"ID: {executor['id']}")
        lines.append(f"Description: {executor['description'][:200]}")  # Limit description length
        
        # Format input schema (simplified)
        input_schema = executor.get('input_schema')
        if input_schema and isinstance(input_schema, dict):
            properties = input_schema.get('properties', {})
            required = input_schema.get('required', [])
            
            # Limit number of properties shown
            prop_items = list(properties.items())[:max_schema_props]
            if prop_items:
                lines.append("Input Schema:")
                for prop_name, prop_info in prop_items:
                    prop_type = prop_info.get('type', 'unknown')
                    is_required = prop_name in required
                    req_marker = " (required)" if is_required else ""
                    lines.append(f"  - {prop_name}: {prop_type}{req_marker}")
                if len(properties) > max_schema_props:
                    lines.append(f"  ... and {len(properties) - max_schema_props} more properties")
        
        lines.append("")
    
    if len(get_available_executors()) > max_executors:
        lines.append(f"[Note: {len(get_available_executors()) - max_executors} more executors available]")
    
    return "\n".join(lines)


__all__ = [
    "get_available_executors",
    "get_executor_schema",
    "format_executors_for_llm",
]

