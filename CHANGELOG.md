# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

