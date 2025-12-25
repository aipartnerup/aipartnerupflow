# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] 2025-12-25

### Added
- **LLM Executor Integration**
  - Added `LLMExecutor` (`llm_executor`) for direct LLM interaction via LiteLLM
  - Supports unified `model` parameter for 100+ providers (OpenAI, Anthropic, Gemini, etc.)
  - Support for `stream=True` in inputs or context metadata for Server-Sent Events (SSE)
  - Automatic API key handling via `LLMKeyConfigManager` or environment variables
  - Auto-registration via extensions mechanism
  - Added `[llm]` optional dependency including `litellm`

- **CLI: Plugin Mechanism for Extensions**
  - Added `CLIExtension` class to facilitate creating CLI subcommands in external projects.
  - Implemented dynamic subcommands discovery using Python `entry_points` (`aipartnerupflow.cli_plugins`).
  - Allows projects like `aipartnerupflow-demo` to register commands (e.g., `apflow users stat`) without modifying the core library.
  - Supports both full `typer.Typer` apps and single-command callables as plugins.

- **CLI: Improved Task Count Output**
  * Changed default output format of `apflow tasks count` from `json` to `table` for better terminal readability.

### Changed
- **CLI: Simplified `apflow tasks` commands**
  - `apflow tasks count` now defaults to providing comprehensive database statistics grouped by status.
  - Removed redundant `--all` and `--status` flags from `count` command (database statistics are now the default).
  - Renamed `apflow tasks all` command to `apflow tasks list` for better alignment with API naming conventions.
  - Removed the legacy `apflow tasks list` command (which only showed running tasks).
  - The new `apflow tasks list` command now lists all tasks from the database with support for filtering and pagination.

### Fixed
- **Tests: Infrastructure and LLM Integration**
  - Updated `tests/conftest.py` to automatically load `.env` file environment variables at the start of the test session.
  - Added auto-registration for `LLMExecutor` in the test `conftest.py` fixture.
  - Fixed `LLMExecutor` integration tests to correctly use real API keys from `.env` when available.

## [0.7.3] 2025-12-22

### Fixed
- **CLI: event-loop handling for async database operations**
  - Ensured async database sessions and repositories are created and closed inside
    the same event loop to avoid "no running event loop" and "Event loop is closed" errors
  - Updated `apflow tasks` commands to run async work in a safe context
  - Added `nest_asyncio` support for nested event loops in test environments

- **Logging: clean CLI output by default**
  - Default log level for the library is now `ERROR` to keep CLI output clean
  - Support `LOG_LEVEL` and `DEBUG` environment variables to override logging when needed
  - Debug logs can be enabled with `LOG_LEVEL=DEBUG apflow ...`

- **Extensions registration noise reduced**
  - Demoted expected registration instantiation messages to `DEBUG` (no longer printed by default)
  - This prevents benign initialization messages from appearing during normal CLI runs

- **Miscellaneous**
  - Added `nest_asyncio` to CLI optional dependencies to improve compatibility in nested-loop contexts

## [0.7.2] 2025-12-21

### Fixed
- **Documentation Corrections for `schemas.method` Field**
  - Clarified that `schemas.method` is a required field when `schemas` is provided
  - Updated documentation to explicitly state that `schemas.method` must match an executor ID from the extensions registry
  - Fixed all documentation examples to use real executor IDs instead of placeholder values
  - Updated examples across all documentation files:
    - `docs/api/http.md`: Replaced generic `"executor_id"` with concrete IDs like `"system_info_executor"`, `"rest_executor"`, `"command_executor"`
    - `docs/getting-started/quick-start.md`: Updated all task examples to use valid executor IDs
    - `docs/guides/cli.md`: Fixed CLI command examples with correct executor IDs
    - `docs/development/design/cli-design.md`: Updated design documentation examples
    - `docs/development/setup.md`: Fixed setup guide examples
  - Fixed `generate_executor.py` LLM prompt to correctly instruct LLM to use `schemas.method` (not `name`) as executor ID
  - Updated task structure examples in LLM prompt to reflect correct usage

- **API Endpoint Test Coverage**
  - Added missing test cases for API endpoints:
    - `test_jsonrpc_tasks_list`: Tests `tasks.list` endpoint with pagination
    - `test_jsonrpc_tasks_running_status`: Tests `tasks.running.status` endpoint with array format
    - `test_jsonrpc_tasks_running_count`: Tests `tasks.running.count` endpoint
    - `test_jsonrpc_tasks_cancel`: Tests `tasks.cancel` endpoint with array format
    - `test_jsonrpc_tasks_generate`: Tests `tasks.generate` endpoint for task tree generation
  - Fixed test parameter format issues:
    - `tasks.running.status` and `tasks.cancel` now correctly use `task_ids` array parameter instead of single `task_id`
    - Tests now expect array responses instead of single object responses
  - All API endpoints now have comprehensive test coverage

- **CLI Command Test Coverage**
  - Added `test_tasks_watch` test cases for `tasks watch` CLI command
    - Uses mock to avoid interactive `Live` display component issues in automated tests
    - Tests parameter validation and basic functionality
    - Properly handles error messages in stderr

- **API Documentation Completeness**
  - Added missing response example for `tasks.running.status` endpoint
    - Includes complete response format with all fields (task_id, context_id, status, progress, error, is_running, timestamps)
    - Documents error cases (not_found, permission_denied)
    - Clarifies that method returns array format even for single task queries

### Added
- **Comprehensive Documentation Review**
  - Verified all documentation examples use valid executor IDs
  - Ensured all examples are functional and can be parsed correctly
  - Validated that all CLI commands have corresponding test cases
  - Confirmed API endpoint documentation matches actual implementation

## [0.7.1] 2025-12-20

### Fixed
- **DuckDB Custom Path Directory Creation**
  - Fixed issue where DuckDB would fail when using custom directory paths that don't exist
  - Added `_ensure_database_directory_exists()` function to automatically create parent directories before creating DuckDB connections
  - Directory creation is now handled automatically in `create_session()`, `SessionPoolManager.initialize()`, and `PooledSessionContext.__init__()`
  - Skips directory creation for in-memory databases (`:memory:`) and handles errors gracefully with appropriate logging
  - Users can now specify custom DuckDB file paths without manually creating directories first
- **Missing Return Type Annotations**
  - Added missing return type annotation `-> None` to `check_input_schema()` function in `core/utils/helpers.py`
  - Added missing return type annotation `-> ParseResult` to `validate_url()` function in `core/utils/helpers.py`
  - Fixed type checker errors and ensured 100% type annotation compliance as required by code quality rules
- **Module-Level Resource Creation**
  - Refactored `core/storage/factory.py` to eliminate module-level global variables for database sessions
  - Replaced `_default_session` and `_session_pool_manager` module-level globals with `SessionRegistry` class
  - Session state is now encapsulated in `SessionRegistry` class following dependency injection principles
  - All session management functions (`get_default_session()`, `set_default_session()`, `reset_default_session()`, `get_session_pool_manager()`, `reset_session_pool_manager()`) now use `SessionRegistry` class methods
  - Maintains full backward compatibility - all public APIs remain unchanged
  - Follows code quality rules requiring dependency injection instead of module-level resource creation


## [0.7.0] 2025-12-20

### Added
- **Task Context Sharing and LLM Key Management**
  - **Task Context Sharing**: TaskManager now passes the entire `task` object (TaskModel instance) to executors
    - Executors can access all task fields including custom TaskModel fields via `self.task`
    - Supports custom TaskModel classes with additional fields
    - Enables executors to modify task context (e.g., update status, progress, custom fields)
    - BaseTask uses weak references (`weakref.ref`) to store task objects, preventing memory leaks
    - Task context is automatically cleared after execution or cancellation
    - `task_id` is stored separately for future extension (e.g., Redis-based task storage)
  - **Unified user_id Access**: BaseTask provides `user_id` property that automatically retrieves from `task.user_id`
    - Executors can use `self.user_id` instead of `inputs.get("user_id")`
    - Falls back to `_user_id` when task is not available (for backward compatibility and testing)
    - All LLM executors (`generate_executor`, `crew_manager`) now use `self.user_id`
  - **Unified LLM Key Retrieval**: Centralized LLM key management with context-aware priority order
    - New `get_llm_key()` function with unified priority logic for API and CLI contexts
    - API context priority: header → LLMKeyConfigManager → environment variables
    - CLI context priority: params → LLMKeyConfigManager → environment variables
    - Auto-detection mode (`context="auto"`) automatically detects API or CLI context
    - All LLM executors now proactively retrieve keys using unified mechanism
    - Removed hardcoded LLM key injection logic from TaskManager (separation of concerns)
  - **LLM Key Context Optimization**: Refactored `llm_key_context.py` to eliminate code duplication
    - Extracted `_get_key_from_user_config()` helper function for user config lookup
    - Extracted `_get_key_from_source()` helper function for header/CLI params retrieval
    - Reduced code duplication by ~40%, improved maintainability
    - All functionality preserved, backward compatible

- **Enhanced Task Copy Functionality**
  - **UUID Generation for Task IDs**: Task copy now always generates new UUIDs for copied tasks, regardless of `save` parameter value
    - Ensures clear task tree relationships and prevents ID conflicts
    - All copied tasks receive unique IDs for proper dependency mapping
    - Compatible with `tasks.create` API when `save=False` (returns task array with complete data)
  - **Save Parameter Support**: New `save` parameter for `create_task_copy()` method and `tasks.copy` API
    - `save=True` (default): Saves copied tasks to database and returns TaskTreeNode
    - `save=False`: Returns task array without saving to database, suitable for preview or direct use with `tasks.create`
    - Task array format includes all required fields (id, name, parent_id, dependencies) with new UUIDs
    - Dependencies correctly reference new task IDs within the copied tree
  - **Parameter Renaming for Clarity**: Renamed parameters in custom copy mode for better clarity
    - `task_ids` → `custom_task_ids` (required when `copy_mode="custom"`)
    - `include_children` → `custom_include_children` (used when `copy_mode="custom"`)
    - Old parameter names removed (no backward compatibility)
    - CLI: `--task-ids` → `--custom-task-ids`, `--include-children` → `--custom-include-children`
  - **Improved Dependency Mapping**: Fixed dependency resolution in copied task trees
    - Dependencies now correctly reference new task IDs within the copied tree
    - Original task IDs properly mapped to new IDs for all tasks in the tree
    - Circular dependency detection works correctly with new task IDs
    - `original_task_id` correctly points to each task's direct original counterpart (not root)
  - **Comprehensive Test Coverage**: Added extensive test cases for API and CLI
    - API tests: 11 test cases covering all copy modes, save parameter, error handling
    - CLI tests: 7 test cases covering all copy modes, dry-run, reset_fields
    - Tests verify UUID generation, dependency mapping, and database interaction
- **API Module Refactoring for Better Library Usage**
  - Split `api/main.py` into modular components for improved code organization
  - New `api/extensions.py`: Extension management module with `initialize_extensions()` and extension configuration
  - New `api/protocols.py`: Protocol management module with protocol selection and dependency checking
  - New `api/app.py`: Application creation module with `create_app_by_protocol()` and protocol-specific server creation functions
  - `api/main.py` now contains library-friendly entry points (`main()` and `create_runnable_app()` functions)
  - **Benefits**: Better separation of concerns, easier to use in external projects like aipartnerupflow-demo
  - **Migration**: Import paths updated:
    - `from aipartnerupflow.api.extensions import initialize_extensions`
    - `from aipartnerupflow.api.protocols import get_protocol_from_env, check_protocol_dependency`
    - `from aipartnerupflow.api.app import create_app_by_protocol, create_a2a_server, create_mcp_server`
  - All existing imports from `api/main` continue to work via re-exports for backward compatibility

- **Enhanced Library Usage Support in `api/main.py`**
  - **New `create_runnable_app()` function**: Replaces `create_app()` with clearer naming
    - Returns a fully initialized, runnable application instance
    - Handles all initialization steps: .env loading, extension initialization, custom TaskModel loading, examples initialization
    - Supports custom routes, middleware, and TaskRoutes class via `**kwargs`
    - Can be used when you need the app object but want to run the server yourself
    - Usage: `from aipartnerupflow.api.main import create_runnable_app; app = create_runnable_app()`
  - **Enhanced `main()` function**: Now fully supports library usage
    - Can be called directly from external projects with custom configuration
    - Separates application configuration (passed to `create_runnable_app()`) from server configuration (uvicorn parameters)
    - Supports all uvicorn parameters: `host`, `port`, `workers`, `loop`, `limit_concurrency`, `limit_max_requests`, `access_log`
    - Usage: `from aipartnerupflow.api.main import main; main(custom_routes=[...], port=8080)`
  - **Smart .env File Loading**: New `_load_env_file()` function with priority-based discovery
    - Priority order: 1) Current working directory, 2) Main script's directory, 3) Library's own directory (development only)
    - Ensures that when used as a library, it loads `.env` from the consuming project, not from the library's installation directory
    - Respects existing environment variables (`override=False`)
    - Gracefully handles missing `python-dotenv` package
  - **Development Environment Setup**: New `_setup_development_environment()` function
    - Only runs when executing library's own `main.py` directly (not when installed as package)
    - Suppresses specific warnings for cleaner output
    - Adds project root to Python path for development mode
    - Does not affect library usage in external projects
  - **Backward Compatibility**: All existing code continues to work
    - `create_app()` name deprecated but still available via alias
    - All initialization steps remain the same, just better organized

- **Enhanced API Server Creation Functions**
  - Added `auto_initialize_extensions` parameter to `create_a2a_server()` in `api/a2a/server.py`
  - Matches behavior of `create_app_by_protocol()` for consistent API
  - Default: `False` (backward compatible)
  - Added `task_routes_class` parameter to `create_app_by_protocol()` and server creation functions
  - Supports custom `TaskRoutes` class injection throughout the server creation chain
  - Enables aipartnerupflow-demo to use standard API functions directly without workarounds
  - All new parameters are optional with safe defaults for backward compatibility

- **Executor Metadata API**
  - New `get_executor_metadata(executor_id)` function to query executor metadata
  - New `validate_task_format(task, executor_id)` function to validate tasks against executor schemas
  - New `get_all_executor_metadata()` function to get metadata for all executors
  - Located in `aipartnerupflow.core.extensions.executor_metadata`
  - Used by demo applications to generate accurate demo tasks
  - Returns: id, name, description, input_schema, examples, tags

### Removed
- **Examples Module Deprecation**
  - Removed `aipartnerupflow.examples` module from core library
  - Removed `examples` CLI command (`aipartnerupflow examples init`)
  - Removed `examples = []` optional dependency from `pyproject.toml`
  - **Migration**: Demo task initialization has been moved to the **aipartnerupflow-demo** project
  - Demo task definitions are now managed separately from the core library
  - This keeps the core library focused on orchestration functionality
  - For demo tasks, please use [aipartnerupflow-demo](https://github.com/aipartnerup/aipartnerupflow-demo)

- **Examples API Methods**
  - Removed `examples.init` and `examples.status` API methods from system routes
  - These methods are no longer available in the API
  - **Migration**: Use aipartnerupflow-demo for demo task initialization

### Changed
- **Session Management Refactoring**
  - Replaced `get_default_session()` with `create_pooled_session()` context manager in all API routes
  - Renamed `create_task_tree_session` to `create_pooled_session` in `storage/factory.py`
  - Updated `TaskExecutor` to use `create_pooled_session` as fallback
  - Improved concurrency safety for API requests
  - **Breaking Change**: `get_default_session()` is now deprecated for route handlers
- **LLM Key Management Architecture**
  - Executors now proactively retrieve LLM keys instead of receiving them via inputs
  - TaskManager no longer handles LLM key injection for specific executors
  - LLM key retrieval is now executor responsibility, following separation of concerns
  - All executors use unified `get_llm_key()` function with consistent priority order


## [0.6.1] 2025-12-11

### Added
- **JWT Token Generation Support**
  - New `generate_token()` function in `aipartnerupflow.api.a2a.server` for generating JWT tokens
  - Supports custom payload, secret key, algorithm (default: HS256), and expiration (default: 30 days)
  - Uses `python-jose[cryptography]` for token generation and verification
  - Complements existing `verify_token()` function for complete JWT token lifecycle management
  - Usage: `from aipartnerupflow.api.a2a.server import generate_token; token = generate_token({"user_id": "user123"}, secret_key)`

- **Cookie-based JWT Authentication**
  - Support for JWT token extraction from `request.cookies.get("Authorization")` in addition to Authorization header
  - Priority: Authorization header is checked first, then falls back to cookie if header is not present
  - Enables cookie-based authentication for web applications and browser-based clients
  - Maintains security: Only JWT tokens are trusted (no fallback to HTTP headers for user identification)
  - Updated `_extract_user_id_from_request()` method in `BaseRouteHandler` to support both header and cookie sources

- **Dependency Updates**
  - Added `python-jose[cryptography]>=3.3.0` to `[a2a]` optional dependencies in `pyproject.toml`
  - Required for JWT token generation and verification functionality


## [0.6.0] 2025-12-10

### Added
- **TaskRoutes Extension Mechanism**
  - Added `task_routes_class` parameter to `create_a2a_server()` and `_create_request_handler()` for custom TaskRoutes injection
  - Eliminates the need for monkey patching when extending TaskRoutes functionality
  - Supports custom routes via `custom_routes` parameter in `CustomA2AStarletteApplication`
  - Backward compatible: optional parameter with default `TaskRoutes` class
  - Usage: `create_a2a_server(task_routes_class=CustomTaskRoutes, custom_routes=[...])`

- **Task Tree Lifecycle Hooks**
  - New `register_task_tree_hook()` decorator for task tree lifecycle events
  - Four hook types: `on_tree_created`, `on_tree_started`, `on_tree_completed`, `on_tree_failed`
  - Explicit lifecycle tracking without manual root task detection
  - Hooks receive root task and relevant context (status, error message)
  - Usage: `@register_task_tree_hook("on_tree_completed") async def on_completed(root_task, status): ...`

- **Executor-Specific Hooks**
  - Added `pre_hook` and `post_hook` parameters to `@executor_register()` decorator
  - Runtime hook registration via `add_executor_hook(executor_id, hook_type, hook_func)`
  - Inject custom logic (e.g., quota checks, demo data fallback) for specific executors
  - `pre_hook` can return a result to skip executor execution (useful for demo mode)
  - `post_hook` receives executor, task, inputs, and result for post-processing
  - Supports both decorator-based and runtime registration for existing executors

- **Automatic user_id Extraction**
  - Automatic `user_id` extraction from JWT token in `TaskRoutes.handle_task_generate` and `handle_task_create`
  - Only extracts from JWT token payload for security (HTTP headers can be spoofed)
  - Supports `user_id` field or standard JWT `sub` claim in token payload
  - Extracted `user_id` automatically set on task data
  - Simplifies custom route implementations and ensures consistent user identification
  - Security: Only trusted JWT tokens are used, no fallback to HTTP headers

- **Demo Mode Support**
  - Built-in demo mode via `use_demo` parameter in task inputs
  - CLI support: `--use-demo` flag for `apflow run flow` command
  - API support: `use_demo` parameter in task creation and execution
  - Executors can override `get_demo_result()` method in `BaseTask` for custom demo data
  - Default demo data format: `{"result": "Demo execution result", "demo_mode": True}`
  - All built-in executors now implement `get_demo_result()` method:
    - `SystemInfoExecutor`, `CommandExecutor`, `AggregateResultsExecutor`
    - `RestExecutor`, `GenerateExecutor`, `ApiExecutor`
    - `SshExecutor`, `GrpcExecutor`, `WebSocketExecutor`
    - `McpExecutor`, `DockerExecutor`
    - `CrewManager`, `BatchManager` (CrewAI executors)
  - **Realistic Demo Execution Timing**: All executors include `_demo_sleep` values to simulate real execution time:
    - Network operations (HTTP, SSH, API): 0.2-0.5 seconds
    - Container operations (Docker): 1.0 second
    - LLM operations (CrewAI, Generate): 1.0-1.5 seconds
    - Local operations (SystemInfo, Command, Aggregate): 0.05-0.1 seconds
  - **Global Demo Sleep Scale**: Configurable via `AIPARTNERUPFLOW_DEMO_SLEEP_SCALE` environment variable (default: 1.0)
    - Allows adjusting demo execution speed globally (e.g., `0.5` for faster, `2.0` for slower)
    - API: `set_demo_sleep_scale(scale)` and `get_demo_sleep_scale()` functions
  - **CrewAI Demo Support**: `CrewManager` and `BatchManager` generate realistic demo results:
    - Based on `works` definition (agents and tasks) from task params or schemas
    - Includes simulated `token_usage` matching real LLM execution patterns
    - `BatchManager` aggregates token usage across multiple works
  - Demo mode helps developers test workflows without external dependencies

- **TaskModel Customization Improvements**
  - Enhanced `set_task_model_class()` with improved validation and error messages
  - New `@task_model_register()` decorator for convenient TaskModel registration
  - Validation ensures custom classes inherit from `TaskModel` with helpful error messages
  - Supports `__table_args__ = {'extend_existing': True}` for extending existing table definitions
  - Better support for user-defined `MyTaskModel(TaskModel)` with additional fields

- **Documentation for Hook Types**
  - Added comprehensive documentation explaining differences between hook types
  - `pre_hook` / `post_hook`: Task-level hooks for individual task execution
  - `task_tree_hook`: Task tree-level hooks for tree lifecycle events
  - Clear usage scenarios and examples in `docs/development/extending.md`

### Changed
- **LLM Model Parameter Naming**: Unified LLM model parameter naming to `model` across all components
  - **Breaking Change**: `llm_model` parameter in `generate_executor` has been renamed to `model`
    - GenerateExecutor: `inputs["llm_model"]` → `inputs["model"]`
    - API Routes: `params["llm_model"]` → `params["model"]`
    - CLI: `--model` parameter remains unchanged (internal mapping updated)
  - **New Feature**: Support for `schemas["model"]` configuration for CrewAI executor
    - Model configuration can now be specified in task schemas and will be passed to CrewManager
    - Priority: `schemas["model"]` > `params.works.agents[].llm` (CrewAI standard)
  - **Impact**: Only affects generate functionality introduced in 0.5.0, minimal breaking change
  - **Migration**: Update any code using `llm_model` parameter to use `model` instead

### Removed
- **Redundant decorators.py file**
  - Removed `src/aipartnerupflow/decorators.py` as it was no longer used
  - Functionality superseded by `src/aipartnerupflow/core/decorators.py`
  - No impact on existing code (file was not imported by any other modules)


## [0.5.0] 2025-12-7

### Added

- **Extended Executor Framework with Mainstream Execution Methods**
  - **HTTP/REST API Executor** (`rest_executor`)
    - Support for all HTTP methods (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
    - Authentication support (Bearer token, Basic auth, API keys)
    - Configurable timeout and retry mechanisms
    - Request/response headers and body handling
    - JSON and form data support
    - Comprehensive error handling for HTTP status codes
    - Full test coverage with 15+ test cases
  
  - **SSH Remote Executor** (`ssh_executor`)
    - Execute commands on remote servers via SSH
    - Support for password and key-based authentication
    - Key file validation with security checks (permissions, existence)
    - Environment variable injection
    - Custom SSH port configuration
    - Timeout and cancellation support
    - Comprehensive error handling for connection and execution failures
    - Full test coverage with 12+ test cases
  
  - **Docker Container Executor** (`docker_executor`)
    - Execute commands in isolated Docker containers
    - Support for custom Docker images
    - Volume mounts for data persistence
    - Environment variable configuration
    - Resource limits (CPU, memory)
    - Container lifecycle management (create, start, wait, remove)
    - Timeout handling with automatic container cleanup
    - Option to keep containers after execution
    - Comprehensive error handling for image not found, execution failures
    - Full test coverage with 13+ test cases
  
  - **gRPC Executor** (`grpc_executor`)
    - Call gRPC services and microservices
    - Support for dynamic proto file loading
    - Method invocation with parameter serialization
    - Metadata and timeout configuration
    - Error handling for gRPC status codes
    - Support for unary, server streaming, client streaming, and bidirectional streaming
    - Full test coverage with 10+ test cases
  
  - **WebSocket Executor** (`websocket_executor`)
    - Bidirectional WebSocket communication
    - Send and receive messages in real-time
    - Support for JSON and text messages
    - Custom headers for authentication
    - Optional response waiting with timeout
    - Connection error handling (invalid URI, connection closed, timeout)
    - Cancellation support
    - Full test coverage with 13+ test cases
  
  - **aipartnerupflow API Executor** (`apflow_api_executor`)
    - Call other aipartnerupflow API instances for distributed execution
    - Support for all task management methods (tasks.execute, tasks.create, tasks.get, etc.)
    - Authentication via JWT tokens
    - Task completion polling with production-grade retry logic:
      - Exponential backoff on failures (1s → 2s → 4s → 8s → 30s max)
      - Circuit breaker pattern (stops after 10 consecutive failures)
      - Error classification (retryable vs non-retryable)
      - Total failure threshold (20 failures across all polls)
      - Detailed logging for debugging
    - Timeout protection and cancellation support
    - Comprehensive error handling for network, server, and client errors
    - Full test coverage with 12+ test cases
  
  - **Dependency Management**
    - Optional dependencies for new executors:
      - `[ssh]`: asyncssh for SSH executor
      - `[docker]`: docker for Docker executor
      - `[grpc]`: grpcio, grpcio-tools for gRPC executor
      - `[all]`: Includes all optional dependencies
    - Graceful handling when optional dependencies are not installed
    - Clear error messages with installation instructions
  
  - **Documentation**
    - Comprehensive usage examples for all new executors in `docs/guides/custom-tasks.md`
    - Configuration parameters and examples for each executor
    - Best practices and common patterns
    - Error handling guidelines
  
  - **Auto-discovery**
    - All new executors automatically registered via extension system
    - Auto-imported in API service startup
    - Available immediately after installation

- **MCP (Model Context Protocol) Executor** (`mcp_executor`)
  - Interact with MCP servers to access external tools and data sources
  - Support for stdio and HTTP transport modes
  - Operations: list_tools, call_tool, list_resources, read_resource
  - JSON-RPC 2.0 protocol compliance
  - Environment variable injection for stdio mode
  - Custom headers support for HTTP mode
  - Timeout and cancellation support
  - Comprehensive error handling for MCP protocol errors
  - Full test coverage with 20+ test cases

- **MCP (Model Context Protocol) Server** (`api/mcp/`)
  - Expose aipartnerupflow task orchestration capabilities as MCP tools and resources
  - Support for stdio and HTTP/SSE transport modes
  - MCP Tools (8 tools):
    - `execute_task` - Execute tasks or task trees
    - `create_task` - Create new tasks or task trees
    - `get_task` - Get task details by ID
    - `update_task` - Update existing tasks
    - `delete_task` - Delete tasks (if all pending)
    - `list_tasks` - List tasks with filtering
    - `get_task_status` - Get status of running tasks
    - `cancel_task` - Cancel running tasks
  - MCP Resources:
    - `task://{task_id}` - Access individual task data
    - `tasks://` - Access task list with query parameters
  - JSON-RPC 2.0 protocol compliance
  - Integration with existing TaskRoutes for protocol-agnostic design
  - HTTP mode: FastAPI/Starlette integration with `/mcp` endpoint
  - stdio mode: Standalone process for local integration
  - Comprehensive error handling with proper HTTP status codes
  - Full test coverage with 45+ test cases across all components
  - Protocol selection via `AIPARTNERUPFLOW_API_PROTOCOL=mcp` environment variable
  - CLI protocol selection: `--protocol` parameter for `serve` and `daemon` commands
    - Default protocol: `a2a`
    - Supported protocols: `a2a`, `mcp`
    - Usage: `apflow serve --protocol mcp` or `apflow daemon start --protocol mcp`

- **Task Tree Generator Executor** (`generate_executor`)
  - Generate valid task tree JSON arrays from natural language requirements using LLM
  - Automatically collects available executors and their input schemas for LLM context
  - Loads framework documentation (task orchestration, examples, concepts) as LLM context
  - Supports multiple LLM providers (OpenAI, Anthropic) via configurable backend
  - Comprehensive validation ensures generated tasks conform to TaskCreator requirements:
    - Validates task structure (name, id consistency, parent_id, dependencies)
    - Detects circular dependencies
    - Ensures single root task
    - Validates all references exist in the array
  - LLM prompt engineering with framework context, executor information, and examples
  - JSON response parsing with markdown code block support
  - Can be used through both API and CLI as a standard executor
  - **API Endpoint**: `tasks.generate` method via JSON-RPC `/tasks` endpoint
    - Supports all LLM configuration parameters (provider, model, temperature, max_tokens)
    - Optional `save` parameter to automatically save generated tasks to database
    - Returns generated task tree JSON array with count and status message
    - Full test coverage with 8 API endpoint test cases
  - **CLI Command**: `apflow generate task-tree` for direct task tree generation
    - Supports output to file or stdout
    - Optional database persistence with `--save` flag
    - Comprehensive test command examples in documentation
  - Configuration via environment variables or input parameters:
    - `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for LLM authentication
    - `AIPARTNERUPFLOW_LLM_PROVIDER` for provider selection (default: openai)
    - `AIPARTNERUPFLOW_LLM_MODEL` for model selection
  - Full test coverage with 28+ executor test cases and 8 API endpoint test cases
  - Usage examples:
    ```python
    # Python API
    task = await task_manager.task_repository.create_task(
        name="generate_executor",
        inputs={"requirement": "Fetch data from API, process it, and save to database"}
    )
    ```
    ```json
    // JSON-RPC API
    {
      "jsonrpc": "2.0",
      "method": "tasks.generate",
      "params": {
        "requirement": "Fetch data from API and process it",
        "save": true
      }
    }
    ```
    ```bash
    # CLI
    apflow generate task-tree "Fetch data from API and process it" --save
    ```

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
  - Standardized method naming: `tasks.execute`, `tasks.create`, `tasks.get`, `tasks.update`, `tasks.delete`, `tasks.detail`, `tasks.tree`, `tasks.list`, `tasks.children`, `tasks.running.list`, `tasks.running.status`, `tasks.running.count`, `tasks.cancel`, `tasks.copy`, `tasks.generate`
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

### Fixed
- **Docker Executor Exit Code Extraction**
  - Fixed incorrect exit code handling: `container.wait()` returns `{"StatusCode": 0}` dict, not integer
  - Properly extract `StatusCode` from wait result dictionary
  - Fixed container removal logic to prevent duplicate cleanup calls
  - Improved cancellation handling before container start

- **WebSocket Executor Exception Handling**
  - Fixed `ConnectionClosed` exception construction in tests
  - Fixed `InvalidURI` exception construction in tests
  - Added proper `asyncio` import for timeout error handling
  - Improved error handling for WebSocket connection failures

- **SSH Executor Key File Validation**
  - Fixed key file validation in tests by properly mocking file system operations
  - Added proper handling for key file permissions and existence checks
  - Improved error messages for authentication failures

- **API Executor Infinite Polling Loop**
  - Fixed infinite polling loop when API calls fail repeatedly
  - Implemented production-grade retry logic with exponential backoff
  - Added circuit breaker pattern to stop polling after consecutive failures
  - Added total failure threshold to prevent resource waste
  - Improved error classification (retryable vs non-retryable errors)
  - Enhanced logging for better debugging in production environments

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

