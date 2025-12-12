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
│   ├── task_executor.py     # TaskExecutor - task execution interface
│   ├── task_creator.py      # TaskCreator - task tree creation and validation
│   ├── task_tracker.py      # TaskTracker - task execution tracking
│   ├── executor_registry.py # ExecutorRegistry - executor registration
│   └── streaming_callbacks.py  # Streaming support
├── extensions/     # Extension system
│   ├── base.py     # Extension base class
│   ├── decorators.py  # @extension_register decorator
│   ├── registry.py   # ExtensionRegistry
│   ├── protocol.py   # Protocol-based design (ExecutorLike, ExecutorFactory)
│   ├── types.py      # ExtensionCategory enum
│   ├── hook.py       # Hook system implementation
│   └── storage.py    # Storage extension base
├── storage/        # Storage implementation
│   ├── factory.py  # create_storage() function
│   ├── sqlalchemy/ # SQLAlchemy implementation
│   │   ├── models.py         # SQLAlchemy models
│   │   └── task_repository.py # Task repository implementation
│   └── dialects/   # Database dialects (DuckDB/PostgreSQL)
│       ├── duckdb.py
│       ├── postgres.py
│       └── registry.py
├── tools/          # Tool system
│   ├── base.py     # Tool base class
│   ├── decorators.py  # @tool_register decorator
│   └── registry.py   # ToolRegistry
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

### [stdio] - Stdio Executors

```
extensions/stdio/
├── __init__.py
├── command_executor.py      # CommandExecutor - local command execution
└── system_info_executor.py  # SystemInfoExecutor - system resource queries
```

**Installation**: Included in core (no extra required)

### [core] - Core Extensions

```
extensions/core/
├── __init__.py
└── aggregate_results_executor.py  # AggregateResultsExecutor - dependency result aggregation
```

**Installation**: Included in core (no extra required)

### [hooks] - Hook Extensions

```
extensions/hooks/
├── __init__.py
├── pre_execution_hook.py   # Pre-execution hook implementation
└── post_execution_hook.py  # Post-execution hook implementation
```

**Installation**: Included in core (no extra required)

### [storage] - Storage Extensions

```
extensions/storage/
├── __init__.py
├── duckdb_storage.py   # DuckDB storage implementation
└── postgres_storage.py # PostgreSQL storage implementation
```

**Installation**: Included in core (no extra required)

### [tools] - Tool Extensions

```
extensions/tools/
├── __init__.py
├── github_tools.py          # GitHub analysis tools
└── limited_scrape_tools.py   # Limited website scraping tools
```

**Installation**: Included in core (no extra required)

## API Service (`api/`)

Unified external API service layer supporting multiple network protocols.

**Current Implementation**: A2A Protocol Server (Agent-to-Agent communication protocol)
- Supports HTTP, SSE, and WebSocket transport layers
- Implements A2A Protocol standard for agent-to-agent communication

**Future Extensions**: May include additional protocols such as REST API endpoints

**Installation**: `pip install aipartnerupflow[a2a]`

```
api/
├── __init__.py            # API module exports
├── main.py                # CLI entry point (main() function and uvicorn server)
├── extensions.py          # Extension management (initialize_extensions, EXTENSION_CONFIG)
├── protocols.py           # Protocol management (get_protocol_from_env, check_protocol_dependency)
├── app.py                 # Application creation (create_app_by_protocol, create_a2a_server, create_mcp_server)
├── a2a/                   # A2A Protocol Server implementation
│   ├── __init__.py        # A2A module exports
│   ├── server.py          # A2A server creation
│   ├── agent_executor.py  # A2A agent executor
│   ├── custom_starlette_app.py  # Custom A2A Starlette application
│   └── event_queue_bridge.py    # Event queue bridge
├── mcp/                   # MCP (Model Context Protocol) Server implementation
│   ├── __init__.py        # MCP module exports
│   ├── server.py          # MCP server creation
│   ├── adapter.py         # TaskRoutes adapter for MCP
│   ├── tools.py           # MCP tools registry
│   ├── resources.py       # MCP resources registry
│   └── transport_*.py     # MCP transport implementations
├── routes/                 # Protocol-agnostic route handlers
│   ├── __init__.py        # Route handlers exports
│   ├── base.py            # BaseRouteHandler - shared functionality
│   ├── tasks.py           # TaskRoutes - task management handlers
│   └── system.py          # SystemRoutes - system operation handlers
└── rest/                  # REST API (future implementation)
```

**Route Handlers Architecture**:

The `api/routes/` directory contains protocol-agnostic route handlers that can be used by any protocol implementation (A2A, REST, GraphQL, etc.):

- **`base.py`**: Provides `BaseRouteHandler` class with shared functionality for permission checking, user information extraction, and common utilities
- **`tasks.py`**: Contains `TaskRoutes` class with handlers for task CRUD operations, execution, and monitoring
- **`system.py`**: Contains `SystemRoutes` class with handlers for system operations like health checks, LLM key configuration, and examples management

These handlers are designed to be protocol-agnostic, allowing them to be reused across different protocol implementations.

## CLI Tools (`cli/`)

Command-line interface for task management.

**Installation**: `pip install aipartnerupflow[cli]`

## Test Suite (`tests/`)

Test suite organized to mirror the source code structure.

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── core/                    # Core framework tests
│   ├── execution/          # Task orchestration tests
│   │   ├── test_task_manager.py
│   │   ├── test_task_creator.py
│   │   └── test_task_executor_tools_integration.py
│   ├── storage/            # Storage tests
│   │   └── sqlalchemy/
│   │       └── test_task_repository.py
│   └── test_decorators.py  # Decorator tests
├── extensions/             # Extension tests
│   ├── core/
│   │   └── test_aggregate_results_executor.py
│   ├── crewai/
│   │   ├── test_crew_manager.py
│   │   └── test_batch_manager.py
│   ├── stdio/
│   │   ├── test_command_executor.py
│   │   └── test_system_info_executor.py
│   └── tools/
│       └── test_tools_decorator.py
├── api/                    # API service tests
│   └── a2a/
│       └── test_agent_executor.py  # A2A AgentExecutor tests
├── cli/                    # CLI tests
│   ├── test_run_command.py
│   └── test_tasks_command.py
└── integration/            # Integration tests
    └── test_aggregate_results_integration.py
```

**Note**: Test structure mirrors source code structure for easy navigation and maintenance.
