# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-12-5

### Added
- **CLI Task Commands Synchronization with API**
  - Complete synchronization of CLI task commands with API task routes
  - Unified data format: CLI commands now return the same data structure as API endpoints using `task.to_dict()`
  - New CLI commands matching API functionality:
    - `tasks get <task_id>` - Get task details (equivalent to `tasks.get` API)
    - `tasks create --file <file>|--stdin` - Create task tree from JSON file or stdin (equivalent to `tasks.create` API)
    - `tasks update <task_id> [options]` - Update task fields (equivalent to `tasks.update` API)
    - `tasks delete <task_id> [--force]` - Delete task with validation (equivalent to `tasks.delete` API)
    - `tasks tree <task_id>` - Get task tree structure (equivalent to `tasks.tree` API)
    - `tasks children --parent-id <id>|--task-id <id>` - Get child tasks (equivalent to `tasks.children` API)
    - `tasks all [options]` - List all tasks from database with filters (equivalent to `tasks.list` API)
  - Enhanced existing commands:
    - `tasks list` - Now returns full `task.to_dict()` format matching API `tasks.running.list`
    - `tasks status` - Now includes `context_id`, `started_at`, and `updated_at` fields matching API format
  - All CLI commands maintain API compatibility for consistent data formats
  - Comprehensive test coverage with 43 test cases covering all CLI task commands

- **Unified A2A Protocol Task Management**
  - All task management operations now fully supported through A2A Protocol `/` route
  - Standardized method naming: `tasks.execute`, `tasks.create`, `tasks.get`, `tasks.update`, `tasks.delete`, `tasks.detail`, `tasks.tree`, `tasks.list`, `tasks.children`, `tasks.running.list`, `tasks.running.status`, `tasks.running.count`, `tasks.cancel`, `tasks.copy`
  - `TaskRoutesAdapter` component bridges A2A Protocol `RequestContext`/`EventQueue` with existing `TaskRoutes` handlers
  - Automatic conversion between A2A Protocol format and internal task representation
  - Real-time task status updates via `TaskStatusUpdateEvent` for all task management operations
  - Backward compatibility: `execute_task_tree` skill ID still supported (maps to `tasks.execute`)
  - All 14 task management skills registered in Agent Card for protocol compliance
  - Comprehensive test coverage with 17+ test cases for all task management methods
  - Fixed `MessageSendConfiguration` access error: Properly handle Pydantic model attributes instead of dictionary methods

### Fixed
- **A2A Protocol Configuration Access**
  - Fixed `AttributeError: 'MessageSendConfiguration' object has no attribute 'get'` in `TaskRoutesAdapter`
  - Properly handle Pydantic model attributes using `getattr()` and `model_dump()` instead of dictionary methods
  - Compatible with both Pydantic v1 and v2
  - All 5 previously failing integration tests now pass

- **A2A Protocol Cancel Method Implementation**
  - Complete implementation of `AgentExecutor.cancel()` method for A2A Protocol
  - Task ID extraction with priority: `task_id` > `context_id` > `metadata.task_id` > `metadata.context_id`
  - Support for custom error messages via `metadata.error_message`
  - Graceful cancellation by calling executor's `cancel()` method if supported
  - Token usage and partial results preservation during cancellation
  - Proper `TaskStatusUpdateEvent` generation with A2A Protocol compliance
  - Comprehensive error handling for task not found, already completed, and exception scenarios
  - Complete test coverage with 13 test cases covering all scenarios
  - Documentation updates in HTTP API and Python API references

- **Enhanced Task Copy Functionality**
  - `children` parameter for `create_task_copy()`: When `True`, also copy each direct child task with its dependencies
  - Deduplication ensures tasks depending on multiple copied tasks are only copied once
  - `children` parameter for `tasks.copy` API endpoint
  - `--children` flag for CLI `tasks copy` command

- **Copy Before Execution**
  - `copy_execution` parameter for `tasks.execute` API: Copy task before execution to preserve original task history
  - `copy_children` parameter: When `True` with `copy_execution=True`, also copy each direct child task with its dependencies
  - Response includes both `task_id` (copied task) and `original_task_id` (original task) when `copy_execution=True`
  - Combines `tasks.copy` and `tasks.execute` into a single API call for better user experience

- **Enhanced Task Deletion with Validation**
  - Physical deletion: Tasks are now physically removed from the database (not soft-deleted)
  - Conditional deletion: Tasks can only be deleted if all tasks (task itself + all children) are in `pending` status
  - Recursive child deletion: When deletion is allowed, all child tasks (including grandchildren) are automatically deleted
  - Dependency validation: Deletion is prevented if other tasks depend on the task being deleted
  - Detailed error messages: Returns specific error information when deletion fails:
    - Lists non-pending children with their statuses
    - Lists tasks that depend on the task being deleted
    - Indicates if the task itself is not pending
  - New TaskRepository methods:
    - `get_all_children_recursive()`: Recursively get all child tasks
    - `find_dependent_tasks()`: Find all tasks that depend on a given task (reverse dependencies)
    - `delete_task()`: Physically delete a task from the database
  - Comprehensive test coverage with 16 test cases covering all scenarios

- **Enhanced Task Update with Critical Field Validation**
  - Critical field protection: Three critical fields (`parent_id`, `user_id`, `dependencies`) are now strictly validated to prevent fatal errors
  - `parent_id` and `user_id`: Always rejected - these fields cannot be modified after task creation (task hierarchy and ownership are fixed)
  - `dependencies`: Conditional validation with four critical checks:
    1. Status check: Can only be updated when task is in `pending` status
    2. Reference validation: All dependency references must exist in the same task tree
    3. Circular dependency detection: Uses DFS algorithm to detect and prevent circular dependencies
    4. Execution check: Prevents updates if any dependent tasks are currently executing
  - Other fields: Can be updated freely without status restrictions (inputs, name, priority, params, schemas, status, result, error, progress, timestamps)
  - Comprehensive error reporting: All validation errors are collected and returned in a single response
  - New TaskRepository methods:
    - `update_task_dependencies()`: Update task dependencies with validation
    - `update_task_name()`: Update task name
    - `update_task_priority()`: Update task priority
    - `update_task_params()`: Update executor parameters
    - `update_task_schemas()`: Update validation schemas
  - New utility module: `dependency_validator.py` with reusable validation functions
  - Comprehensive test coverage with 23 test cases covering all validation scenarios


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

