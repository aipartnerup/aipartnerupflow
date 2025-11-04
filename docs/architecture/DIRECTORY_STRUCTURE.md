# Directory Structure

This document describes the directory structure of the `aipartnerupflow` project.

## Core Framework (`core/`)

The core framework provides task orchestration and execution specifications. All core modules are always included when installing `aipartnerupflow`.

```
core/
├── interfaces/     # Core interfaces
│   ├── plugin.py   # ExecutableTask interface, BaseTask base class
│   └── storage.py  # TaskStorage interface
├── execution/      # Task orchestration specifications
│   ├── task_manager.py      # TaskManager - core orchestration engine
│   └── streaming_callbacks.py  # Streaming support
├── storage/        # Storage implementation
│   ├── factory.py  # create_storage() function
│   ├── sqlalchemy/ # SQLAlchemy implementation
│   └── dialects/   # Database dialects (DuckDB/PostgreSQL)
└── utils/          # Utility functions
    ├── logger.py   # Logging utilities
    └── helpers.py  # Helper functions
```

## Optional Features (`features/`)

Optional features require extra dependencies and are installed separately.

### [crewai] - CrewAI LLM Task Support

```
features/crewai/
├── __init__.py
├── crew_manager.py     # CrewManager - CrewAI wrapper
├── batch_manager.py    # BatchManager - batch execution of multiple crews
└── types.py            # CrewManagerState, BatchState
```

**Installation**: `pip install aipartnerupflow[crewai]`

### [templates] - Template-based Task Creation

```
features/templates/
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
