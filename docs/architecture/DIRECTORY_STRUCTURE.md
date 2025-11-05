# Directory Structure

This document describes the directory structure of the `aipartnerupflow` project.

## Core Framework (`core/`)

The core framework provides task orchestration and execution specifications. All core modules are always included when installing `aipartnerupflow`.

```
core/
├── interfaces/     # Core interfaces (abstract contracts)
│   └── executable_task.py  # ExecutableTask interface
├── base/           # Base class implementations
│   └── base_task.py  # BaseTask base class with common functionality
├── types.py        # Core type definitions (TaskTreeNode, TaskStatus, hooks)
├── decorators.py   # Unified decorators (Flask-style API)
│                    # register_pre_hook, register_post_hook, extension_register
├── config/         # Configuration registry
│   └── registry.py  # ConfigRegistry for hooks and TaskModel
├── execution/      # Task orchestration specifications
│   ├── task_manager.py      # TaskManager - core orchestration engine
│   └── streaming_callbacks.py  # Streaming support
├── extensions/     # Extension system
│   ├── base.py     # Extension base class
│   ├── decorators.py  # @extension_register decorator
│   ├── registry.py   # ExtensionRegistry
│   ├── protocol.py   # Protocol-based design (ExecutorLike, ExecutorFactory)
│   └── types.py      # ExtensionCategory enum
├── storage/        # Storage implementation
│   ├── factory.py  # create_storage() function
│   ├── sqlalchemy/ # SQLAlchemy implementation
│   └── dialects/   # Database dialects (DuckDB/PostgreSQL)
└── utils/          # Utility functions
    ├── logger.py   # Logging utilities
    └── helpers.py  # Helper functions
```

## Extensions (`extensions/`)

Framework extensions are optional features that require extra dependencies and are installed separately.

### [crewai] - CrewAI LLM Task Support

```
extensions/crewai/
├── __init__.py
├── crew_manager.py     # CrewManager - CrewAI wrapper
├── batch_manager.py    # BatchManager - batch execution of multiple crews
└── types.py            # CrewManagerState, BatchState
```

**Installation**: `pip install aipartnerupflow[crewai]`

### [stdio] - Stdio Executor

```
extensions/stdio/
├── __init__.py
└── executor.py         # StdioExecutor - local command execution
```

**Installation**: Included in core (no extra required)

### [templates] - Template-based Task Creation

```
extensions/templates/
├── __init__.py
├── task_planner.py     # TaskPlanner - template management
└── task_creator.py    # TaskCreator - create tasks from templates
```

**Installation**: `pip install aipartnerupflow[templates]`

## Examples (`examples/`)

Predefined example implementations for learning and customization.

**Installation**: `pip install aipartnerupflow[examples]`

## API Service (`api/`)

A2A Protocol Server for external communication.

**Installation**: `pip install aipartnerupflow[api]`

## CLI Tools (`cli/`)

Command-line interface for task management.

**Installation**: `pip install aipartnerupflow[cli]`
