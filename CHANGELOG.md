# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Infrastructure
- Project structure with `src-layout`
- `pyproject.toml` with optional dependencies (`[api]`, `[crewai]`, `[cli]`, `[postgres]`, `[examples]`, `[all]`)
- Comprehensive documentation in `docs/` directory
- Test suite with pytest fixtures
- Modular architecture separating core from optional features

### Notes
- Project is currently in active development
- No official release has been made yet
- Breaking changes may occur before v0.1.0 release

