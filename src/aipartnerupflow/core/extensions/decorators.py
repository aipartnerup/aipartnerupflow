"""
Extension registration decorators

Provides decorators for automatic extension registration, similar to CrewAI's @CrewBase.
Extensions can use these decorators to automatically register themselves when imported,
without requiring changes to core code.
"""

from typing import Callable, Optional, Dict, Any, Type
from functools import wraps
from aipartnerupflow.core.extensions import get_registry
from aipartnerupflow.core.extensions.base import Extension
from aipartnerupflow.core.extensions.protocol import ExecutorFactory, ExecutorLike
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def extension_register(
    factory: Optional[ExecutorFactory] = None,
    override: bool = False
):
    """
    Decorator for extension registration
    
    This decorator registers an extension class when it's imported.
    Similar to CrewAI's @CrewBase decorator pattern.
    
    Usage:
        @extension_register()
        class MyExecutor(BaseTask):
            id = "my_executor"
            type = "my_type"
            ...
        
        # Or with custom factory
        @extension_register(factory=lambda inputs: MyExecutor(**inputs))
        class MyExecutor(BaseTask):
            ...
    
    Args:
        factory: Optional factory function to create executor instances.
                Signature: factory(inputs: Dict[str, Any]) -> ExecutableTask
                If not provided, will use class constructor with inputs.
        override: If True, allow overriding existing registration. Default False.
    
    Returns:
        Decorated class (same class, registered automatically)
    
    Example:
        from aipartnerupflow.core.extensions.decorators import extension_register
        from aipartnerupflow.core.base import BaseTask
        
        @extension_register()
        class StdioExecutor(BaseTask):
            id = "stdio_executor"
            name = "Stdio Executor"
            type = "stdio"
            ...
    """
    def decorator(cls: Type[Any]) -> Type[Any]:
        """
        Class decorator that registers the extension
        
        Args:
            cls: Extension class to register
        
        Returns:
            Same class (for chaining)
        """
        # Validate that class implements Extension
        if not issubclass(cls, Extension):
            raise TypeError(
                f"Class {cls.__name__} must implement Extension interface "
                f"to use @extension_register decorator"
            )
        
        # Note: We don't need to validate ExecutorLike protocol here because:
        # 1. The registry will check it when registering
        # 2. Structural typing (Protocol) allows any object with the right methods
        # 3. This avoids circular imports
        
        # Create a template instance for metadata
        # Use class attributes if available, otherwise create minimal instance
        try:
            # Try to create instance with empty inputs
            template = cls(inputs={})
        except Exception as e:
            # If instantiation fails, create a minimal template using class attributes
            logger.warning(
                f"Could not create template instance for {cls.__name__}: {e}. "
                f"Using class attributes for registration."
            )
            # Create a minimal template class
            class TemplateClass(cls):
                """Template instance for registration"""
                def __init__(self):
                    # Bypass parent __init__ to avoid errors
                    pass
            
            # Set required attributes from class
            template = TemplateClass()
            template.id = getattr(cls, 'id', cls.__name__.lower())
            template.name = getattr(cls, 'name', cls.__name__)
            template.description = getattr(cls, 'description', '')
        
        # Get registry and register
        registry = get_registry()
        
        # Determine factory function
        if factory:
            executor_factory = factory
        else:
            # Default factory: use class constructor
            # For executors that need special initialization (like CrewManager),
            # we try to pass inputs as kwargs first, then fallback to inputs parameter
            def default_factory(inputs: Dict[str, Any]) -> Any:
                try:
                    # Try to instantiate with **inputs (for classes like CrewManager)
                    return cls(**inputs)
                except TypeError:
                    # Fallback to inputs parameter (for classes like StdioExecutor)
                    return cls(inputs=inputs)
            executor_factory = default_factory
        
        # Register extension
        try:
            registry.register(
                extension=template,
                executor_class=cls,
                factory=executor_factory,
                override=override
            )
            logger.debug(
                f"Registered extension '{template.id}' "
                f"(category: {template.category.value}, type: {template.type})"
            )
        except Exception as e:
            logger.error(
                f"Failed to register extension {cls.__name__}: {e}",
                exc_info=True
            )
            # Don't raise - allow class to be used even if registration fails
            # This allows optional extensions to work without breaking imports
        
        return cls
    
    return decorator


__all__ = ["extension_register"]

