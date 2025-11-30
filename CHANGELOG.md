# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-11-30

### Added
- **Webhook Support for Task Execution**
  - Webhook callbacks for `tasks.execute` JSON-RPC endpoint (similar to A2A Protocol push notifications)
  - `WebhookStreamingContext` class for sending HTTP callbacks during task execution
  - Real-time progress updates sent to configured webhook URL
  - Configurable webhook settings:
    - `url` (required): Webhook callback URL
    - `headers` (optional): Custom HTTP headers (e.g., Authorization)
    - `method` (optional): HTTP method (default: POST)
    - `timeout` (optional): Request timeout in seconds (default: 30.0)
    - `max_retries` (optional): Maximum retry attempts (default: 3)
  - Automatic retry mechanism with exponential backoff for failed requests
  - Error handling: Client errors (4xx) are not retried, server errors (5xx) and network errors are retried
  - Webhook payload includes: protocol identifier, task status, progress, result, error, and timestamp
  - Update types: `task_start`, `progress`, `task_completed`, `task_failed`, `final`
  - Comprehensive test coverage for webhook functionality

- **Protocol Identification**
  - Added `protocol` field to all API responses to distinguish between execution modes
    - JSON-RPC endpoints return `"protocol": "jsonrpc"` in response
    - A2A Protocol endpoints include `"protocol": "a2a"` in metadata and event data
  - Enables clients to identify which protocol was used for task execution
  - Consistent protocol identification across streaming updates and webhook callbacks

- **Streaming Mode for JSON-RPC**
  - Streaming mode support for `tasks.execute` endpoint via `use_streaming` parameter
  - Real-time progress updates via Server-Sent Events (SSE) - returns `StreamingResponse` directly when `use_streaming=true`
  - `TaskStreamingContext` class for in-memory event storage
  - Consistent behavior with A2A Protocol streaming mode
  - Asynchronous task execution with immediate response

- **Examples Module**
  - New `examples` module for initializing example task data to help beginners get started
  - CLI command `examples init` for initializing example tasks in the database
  - `--force` flag to re-initialize examples even if they already exist
  - Example tasks demonstrate various features:
    - Tasks with different statuses (completed, failed, pending, in_progress)
    - Task trees with parent-child relationships
    - Tasks with different priorities
    - Tasks with dependencies
    - CrewAI task example (requires LLM key)
  - Auto-initialization: API server automatically initializes examples if database is empty on startup
  - Example user ID: `example_user` for demo tasks

- **LLM API Key Management**
  - Request header support: `X-LLM-API-KEY` header for demo/one-time usage
    - Simple format: `X-LLM-API-KEY: <api-key>` (provider auto-detected from model name)
    - Provider-specific format: `X-LLM-API-KEY: <provider>:<api-key>` (e.g., `openai:sk-xxx`, `anthropic:sk-ant-xxx`)
  - User configuration support via `llm-key-config` extension for multi-user scenarios
    - In-memory storage of user-specific LLM keys (never stored in database)
    - Support for multiple providers per user (provider-specific keys)
    - `LLMKeyConfigManager` singleton for managing user keys
  - LLM Key Context Manager: Thread-local context for LLM keys during task execution
  - LLM Key Injector: Automatic provider detection from model names and works configuration
  - Priority order: Request header > User config > Environment variables
  - Supported providers: OpenAI, Anthropic, Google/Gemini, Mistral, Groq, Cohere, Together, and more
  - Automatic environment variable injection for CrewAI/LiteLLM compatibility
  - Keys are never stored in database, only used during task execution

- **Documentation Updates**
  - Added `examples` command documentation in CLI guide
  - Added LLM API key management documentation in API server guide
  - Added LLM key header documentation in HTTP API reference
  - Updated examples documentation with quick start guide and example task structure
  - Comprehensive examples for using LLM keys with CrewAI tasks
  - Added webhook configuration documentation in HTTP API reference
  - Added protocol identification documentation

### Changed
- **Unified Task Execution Architecture**
  - Refactored task execution logic to unify behavior across A2A Protocol and JSON-RPC endpoints
  - Added `TaskExecutor.execute_task_by_id()` method for executing tasks by ID with automatic dependency handling
  - Moved dependency collection and subtree building logic from protocol handlers to core `TaskExecutor` layer
  - Unified execution modes:
    - **Root task execution**: Executes the entire task tree when a root task is specified
    - **Child task execution**: Automatically collects all dependencies (including transitive) and executes the task with required dependencies
  - Both A2A Protocol and JSON-RPC now use the same core execution methods for consistent behavior
  - Protocol handlers are now thin wrappers around core execution logic, making the system more library-friendly
  - Improved code reusability and maintainability by centralizing execution logic in `TaskExecutor`

- **Task Re-execution Support**
  - Added support for re-executing failed tasks via `tasks.execute` endpoint
  - Failed tasks can now be re-executed by calling `tasks.execute` with the failed task's ID
  - When re-executing a task, all its dependency tasks are also re-executed (even if they are completed) to ensure consistency
  - Only `pending` and `failed` status tasks are executed; `completed` and `in_progress` tasks are skipped unless marked for re-execution
  - Dependency satisfaction logic updated to allow completed tasks marked for re-execution to satisfy dependencies (results are available)
  - Newly created tasks (status: `pending`) are not marked for re-execution and execute normally

- **Task Execution Order Clarification**
  - **Important**: Parent-child relationships (`parent_id`) are now explicitly documented as **organizational only** and do NOT affect execution order
  - **Only dependencies (`dependencies`) determine execution order** - a task executes when its dependencies are satisfied
  - This clarification ensures developers understand that task tree structure (parent-child) is separate from execution order (dependencies)
  - Updated all documentation to clearly distinguish between organizational relationships and execution dependencies

- **CLI Command Improvements**
  - `serve` command now accepts options directly (e.g., `apflow serve --port 8000`) without requiring `start` subcommand
  - `serve start` subcommand still works for backward compatibility
  - Improved command structure and user experience

- **CORS Support**
  - Added CORS middleware to API server for cross-origin requests
  - Default configuration allows `localhost:3000`, `localhost:3001` and common development ports
  - Configurable via `AIPARTNERUPFLOW_CORS_ORIGINS` environment variable (comma-separated list)
  - Development mode: `AIPARTNERUPFLOW_CORS_ALLOW_ALL=true` to allow all origins
  - Supports credentials, all HTTP methods, and all headers

- **API Architecture Refactoring**
  - Moved documentation routes (`/docs`, `/openapi.json`) to `api/routes/docs.py` for better code organization
  - Consolidated OpenAPI schema generation logic into `DocsRoutes` class
  - Improved separation of concerns: route handlers in `api/routes/`, documentation tools in `api/docs/`
  - All custom routes (tasks, system, docs) are now defined in a unified structure

- **SSE Streaming Simplification**
  - SSE streaming is now handled directly by `tasks.execute` with `use_streaming=true`
  - When `use_streaming=true`, `tasks.execute` returns a `StreamingResponse` with Server-Sent Events
  - Simplified API design: one endpoint (`tasks.execute`) handles both regular POST and SSE streaming modes
  - Webhook callbacks remain independent and can be used with either response mode

### Fixed
- **Test Infrastructure**
  - Consolidated database session management in `conftest.py` with global `use_test_db_session` fixture
  - All tests now use isolated in-memory DuckDB databases to prevent data pollution
  - Removed dependency on persistent database files for testing
  - Improved test isolation and reliability
  - Fixed `test_webhook_config_validation` test by using `patch.object()` for TaskTracker singleton
  - Updated `test_jsonrpc_tasks_execute_with_streaming` to correctly parse SSE stream responses
  - Added comprehensive test coverage for documentation routes (`/docs` and `/openapi.json`) with 14 test cases

- **Documentation Corrections**
  - Fixed incorrect command examples in README.md and docs:
    - Corrected `run my_batch` to proper `run flow --tasks` or `run flow executor_id` format
    - Corrected `run flow example_flow` to proper executor ID format
    - Removed non-existent `list-flows` command from documentation
  - Ensured all command examples in documentation are accurate and testable
  - Updated SSE streaming documentation to reflect direct integration with `tasks.execute`

## [0.2.0] - 2025-11-21

### Added
- **Task Tree Validation**
  - Circular dependency detection using DFS algorithm in `TaskCreator.create_task_tree_from_array()`
  - Single task tree validation ensuring all tasks are in the same tree structure
  - Validation that only one root task exists
  - Verification that all tasks are reachable from root task via parent_id chain
  - Dependent task inclusion validation (ensures all tasks that depend on tasks in the tree are included)
  - Comprehensive test coverage for circular dependency scenarios

- **Task Copy Functionality**
  - `TaskCreator.create_task_copy()` method for creating executable copies of task trees
  - Automatic inclusion of dependent tasks (including transitive dependencies) when copying
  - Special handling for failed leaf nodes (filters out pending dependents)
  - Minimal subtree construction to include only required tasks
  - Task copy fields in `TaskModel`: `original_task_id` (links copy to original) and `has_copy` (indicates if task has copies)
  - API endpoint `tasks.copy` via JSON-RPC `/tasks` endpoint
  - CLI command `tasks copy <task_id>` for copying task trees
  - Comprehensive test coverage for task copy functionality

## [0.1.0] - 2025-11-19

### Added
- **Task Orchestration Engine**
  - `TaskManager`: Core task orchestration with dependency management and tree execution
  - `TaskRepository`: Data access layer for task CRUD operations
  - `TaskModel`: Task definition model with support for custom fields via inheritance
  - Task tree structure with parent-child relationships
  - Priority-based task execution
  - Dependency resolution and satisfaction checking

- **A2A Protocol Integration**
  - A2A Protocol as the standard communication protocol
  - Task definition (TaskModel) vs execution instance (A2A Task) separation
  - Context ID mapping: TaskModel.id → A2A Task.context_id
  - Uses A2A SDK's InMemoryTaskStore for task execution instances
  - TaskModel persistence handled by TaskRepository (separate from A2A TaskStore)

- **API Service Layer**
  - A2A server implementation with Starlette
  - Custom A2A Starlette application with system routes
  - Task management APIs: `/system/task_create`, `/system/task_get`, `/system/task_update`, `/system/task_delete`
  - Optional JWT authentication middleware
  - Support for custom TaskModel via `task_model_class` parameter
  - Environment variable support for custom TaskModel loading (`AIPARTNERUPFLOW_TASK_MODEL_CLASS`)

- **Storage Module**
  - SQLAlchemy-based storage with DuckDB (default) and PostgreSQL support
  - Automatic table creation on first use
  - Configurable table name via `AIPARTNERUPFLOW_TASK_TABLE_NAME` (default: `apflow_tasks`)
  - Session factory with sync/async support

- **Custom TaskModel Support**
  - Users can define custom TaskModel subclasses with additional fields
  - TaskRepository supports custom TaskModel classes
  - Custom fields automatically handled in task creation APIs
  - Example: `MyTaskModel(TaskModel)` with `project_id`, `department` fields

- **Event Queue Bridge**
  - Streaming callbacks integration with A2A Protocol EventQueue
  - Real-time task execution progress updates

- **Base Task Infrastructure**
  - `BaseTask`: Optional base class for executable tasks with common implementations
  - Input validation utilities (`get_input_schema`, `validate_input_schema`, `check_input_schema`)
  - Cancellation support via `cancellation_checker` callback
  - Streaming context support for progress updates
  - Support for Pydantic BaseModel or JSON schema dict for input validation

- **Executor Extension System**
  - Unified `ExtensionRegistry` for executor registration and discovery
  - `@executor_register()` decorator for automatic registration
  - Category and type-based executor discovery
  - Extension system supporting executors, storage, hooks, and tools
  - Globally unique ID-based extension lookup

- **Built-in Executors**
  - `AggregateResultsExecutor`: Aggregates dependency task results into structured format
  - `SystemInfoExecutor`: Safe system resource queries (CPU, memory, disk) with predefined commands
  - `CommandExecutor`: Shell command execution (stdio extension)
  - `CrewManager`: LLM-based agent crew execution via CrewAI with token usage tracking
  - `BatchManager`: Atomic batch execution of multiple crews with result merging

### Infrastructure
- Project structure with `src-layout`
- `pyproject.toml` with optional dependencies (`[a2a]`, `[crewai]`, `[cli]`, `[postgres]`, `[all]`)
- Comprehensive documentation in `docs/` directory
- Test suite with pytest fixtures
- Modular architecture separating core from optional features

