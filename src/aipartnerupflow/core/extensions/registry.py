"""
Unified extension registry

This registry manages all extensions (executors, storage, hooks, etc.)
using globally unique IDs and category-based discovery.

Uses Protocol-based design to avoid circular dependencies with ExecutableTask.
"""

from typing import Dict, List, Optional, Type, Callable, Any
from aipartnerupflow.core.extensions.base import Extension
from aipartnerupflow.core.extensions.types import ExtensionCategory
from aipartnerupflow.core.extensions.protocol import ExecutorFactory, ExecutorLike
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class ExtensionRegistry:
    """
    Unified registry for all extension types
    
    This registry provides:
    - ID-based registration (globally unique)
    - Category + type-based discovery
    - Conflict detection and error reporting
    
    Architecture:
    - Primary index: id -> Extension (for precise lookup)
    - Category index: category -> type -> List[Extension] (for discovery)
    
    Example:
        registry = ExtensionRegistry()
        
        # Register extension
        registry.register(stdio_executor)
        
        # Lookup by ID
        executor = registry.get_by_id("stdio_executor")
        
        # Lookup by category and type
        executor = registry.get_by_type(ExtensionCategory.EXECUTOR, "stdio")
    """
    
    _instance: Optional["ExtensionRegistry"] = None
    _by_id: Dict[str, Extension] = {}
    _by_category: Dict[ExtensionCategory, Dict[str, List[Extension]]] = {}
    _factory_functions: Dict[str, ExecutorFactory] = {}
    _executor_classes: Dict[str, Type[Any]] = {}
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._by_id = {}
            cls._instance._by_category = {}
            cls._instance._factory_functions = {}
            cls._instance._executor_classes = {}
        return cls._instance
    
    def register(
        self,
        extension: Extension,
        executor_class: Optional[Type[Any]] = None,
        factory: Optional[Callable[[Dict[str, Any]], Any]] = None,
        override: bool = False
    ) -> None:
        """
        Register an extension
        
        Args:
            extension: Extension instance to register (template for metadata)
            executor_class: Optional executor class for creating new instances
                           (required for executors that need per-task instantiation)
            factory: Optional factory function to create executor instances.
                     Signature: factory(inputs: Dict[str, Any]) -> ExecutableTask (or Any)
                     If provided, this will be used instead of executor_class.
            override: If True, allow overriding existing registration
        
        Raises:
            ValueError: If extension.id is already registered and override=False
            ValueError: If extension.id is empty
            ValueError: If extension.category is invalid
        
        Example:
            # Register with instance (for simple executors)
            registry = get_registry()
            registry.register(StdioExecutor())
            
            # Register with class (for executors that need per-task instantiation)
            registry.register(
                CrewManagerTemplate(),
                executor_class=CrewManager,
                factory=lambda inputs: CrewManager(**inputs)
            )
        """
        # Validate extension
        if not extension.id:
            raise ValueError("Extension must have a non-empty id")
        
        if not isinstance(extension.category, ExtensionCategory):
            raise ValueError(f"Extension category must be ExtensionCategory enum, got {type(extension.category)}")
        
        # Check ID conflict
        if extension.id in self._by_id and not override:
            existing = self._by_id[extension.id]
            raise ValueError(
                f"Extension ID '{extension.id}' is already registered by "
                f"{existing.__class__.__name__} (category: {existing.category.value}). "
                f"Use override=True to replace it, or use a different ID."
            )
        
        # Register to primary index
        self._by_id[extension.id] = extension
        
        # Register to category index
        category = extension.category
        ext_type = extension.type or "default"
        
        if category not in self._by_category:
            self._by_category[category] = {}
        if ext_type not in self._by_category[category]:
            self._by_category[category][ext_type] = []
        
        # Add to type list (allow multiple extensions with same type)
        self._by_category[category][ext_type].append(extension)
        
        # Store executor class and factory for instantiation
        # Use Protocol-based check to avoid circular import
        if category == ExtensionCategory.EXECUTOR:
            # Check if extension implements ExecutorLike protocol (structural typing)
            # This works for ExecutableTask without importing it directly
            # Protocol check: verify extension has required methods
            if hasattr(extension, 'execute') and hasattr(extension, 'get_input_schema'):
                if factory:
                    self._factory_functions[extension.id] = factory
                elif executor_class:
                    self._executor_classes[extension.id] = executor_class
                else:
                    # If extension is already an ExecutorLike instance, use its class
                    self._executor_classes[extension.id] = extension.__class__
        
        logger.info(
            f"Registered extension '{extension.name}' "
            f"(id: {extension.id}, category: {category.value}, type: {ext_type})"
        )
    
    def get_by_id(self, extension_id: str) -> Optional[Extension]:
        """
        Get extension by globally unique ID
        
        Args:
            extension_id: Extension ID
        
        Returns:
            Extension instance, or None if not found
        
        Example:
            executor = registry.get_by_id("stdio_executor")
        """
        return self._by_id.get(extension_id)
    
    def get_by_type(
        self,
        category: ExtensionCategory,
        ext_type: str
    ) -> Optional[Extension]:
        """
        Get extension by category and type
        
        Returns the first extension matching the category and type.
        Useful for lookup based on task schemas (e.g., {"type": "stdio"}).
        
        Args:
            category: Extension category
            ext_type: Extension type identifier
        
        Returns:
            Extension instance (template), or None if not found
        
        Example:
            # Task schema: {"type": "stdio", "method": "command"}
            executor_template = registry.get_by_type(ExtensionCategory.EXECUTOR, "stdio")
        """
        category_dict = self._by_category.get(category, {})
        extensions = category_dict.get(ext_type, [])
        return extensions[0] if extensions else None
    
    def create_executor_instance(
        self,
        extension_id: str,
        inputs: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Create a new executor instance for task execution
        
        This method creates a new executor instance based on the registered extension.
        Uses Protocol-based design to avoid circular dependencies.
        Used by TaskManager to get fresh executor instances for each task execution.
        
        Args:
            extension_id: Extension ID
            inputs: Optional input parameters for executor initialization
        
        Returns:
            Executor instance (implements ExecutorLike protocol), or None if not found or not an executor
        
        Example:
            executor = registry.create_executor_instance("stdio_executor", inputs={...})
        """
        extension = self._by_id.get(extension_id)
        if not extension or extension.category != ExtensionCategory.EXECUTOR:
            return None
        
        # Use factory function if available
        if extension_id in self._factory_functions:
            factory = self._factory_functions[extension_id]
            return factory(inputs or {})
        
        # Use executor class if available
        if extension_id in self._executor_classes:
            executor_class = self._executor_classes[extension_id]
            try:
                return executor_class(inputs=inputs or {})
            except Exception as e:
                logger.error(f"Failed to instantiate executor '{executor_class.__name__}': {e}")
                raise
        
        # If extension is already an ExecutorLike instance, try to create a new one
        # Check if it has the required methods (structural typing via Protocol)
        if hasattr(extension, 'execute') and hasattr(extension, 'get_input_schema'):
            try:
                return extension.__class__(inputs=inputs or {})
            except Exception as e:
                logger.error(f"Failed to instantiate executor from template: {e}")
                raise
        
        return None
    
    def get_all_by_category(self, category: ExtensionCategory) -> List[Extension]:
        """
        Get all extensions in a category
        
        Args:
            category: Extension category
        
        Returns:
            List of all extensions in the category
        """
        result = []
        category_dict = self._by_category.get(category, {})
        for extensions in category_dict.values():
            result.extend(extensions)
        return result
    
    def get_all_by_type(
        self,
        category: ExtensionCategory,
        ext_type: str
    ) -> List[Extension]:
        """
        Get all extensions matching category and type
        
        Args:
            category: Extension category
            ext_type: Extension type
        
        Returns:
            List of extensions (may be multiple if same type)
        """
        category_dict = self._by_category.get(category, {})
        return category_dict.get(ext_type, [])
    
    def is_registered(self, extension_id: str) -> bool:
        """Check if an extension ID is registered"""
        return extension_id in self._by_id
    
    def unregister(self, extension_id: str) -> bool:
        """
        Unregister an extension by ID
        
        Args:
            extension_id: Extension ID to unregister
        
        Returns:
            True if unregistered, False if not found
        """
        if extension_id not in self._by_id:
            return False
        
        extension = self._by_id[extension_id]
        category = extension.category
        ext_type = extension.type or "default"
        
        # Remove from primary index
        del self._by_id[extension_id]
        
        # Remove from category index
        if category in self._by_category:
            if ext_type in self._by_category[category]:
                self._by_category[category][ext_type] = [
                    ext for ext in self._by_category[category][ext_type]
                    if ext.id != extension_id
                ]
                # Clean up empty type lists
                if not self._by_category[category][ext_type]:
                    del self._by_category[category][ext_type]
            # Clean up empty category dicts
            if not self._by_category[category]:
                del self._by_category[category]
        
        # Remove from executor registries
        if extension_id in self._factory_functions:
            del self._factory_functions[extension_id]
        if extension_id in self._executor_classes:
            del self._executor_classes[extension_id]
        
        logger.info(f"Unregistered extension '{extension_id}'")
        return True
    
    def list_registered(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered extensions
        
        Returns:
            Dictionary mapping extension_id to extension info
        """
        return {
            ext_id: {
                "name": ext.name,
                "category": ext.category.value,
                "type": ext.type,
                "version": ext.version,
                "class": ext.__class__.__name__
            }
            for ext_id, ext in self._by_id.items()
        }
    
    def list_by_category(self, category: ExtensionCategory) -> List[str]:
        """
        List all extension IDs in a category
        
        Args:
            category: Extension category
        
        Returns:
            List of extension IDs
        """
        return [ext.id for ext in self.get_all_by_category(category)]


# Global registry instance
_registry = ExtensionRegistry()


def get_registry() -> ExtensionRegistry:
    """
    Get the global extension registry instance
    
    Returns:
        ExtensionRegistry singleton instance
    """
    return _registry


def register_extension(
    extension: Extension,
    override: bool = False
) -> None:
    """
    Register an extension (convenience function)
    
    Args:
        extension: Extension instance to register
        override: Allow overriding existing registration
    
    Example:
        from aipartnerupflow.core.extensions import register_extension, ExtensionCategory
        
        from aipartnerupflow.core.interfaces.executable_task import ExecutableTask
        from aipartnerupflow.core.base import BaseTask
        
        class MyExecutor(BaseTask):
            id = "my_executor"
            name = "My Executor"
            type = "custom"
            ...
        
        register_extension(MyExecutor())
    """
    _registry.register(extension, override=override)


__all__ = [
    "ExtensionRegistry",
    "get_registry",
    "register_extension",
]

