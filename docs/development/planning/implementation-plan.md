# Implementation Plan

**Status**: ⏳ **IN PROGRESS** - Some features are implemented, others are planned.

> **Note**: This document tracks planned and in-progress implementation tasks. For completed architecture documentation, see [overview.md](../../architecture/overview.md) and [directory-structure.md](../../architecture/directory-structure.md).

## Summary

This document described the implementation plan for the current architecture. All phases have been completed:

- ✅ **Phase 1**: Unified extension system with `ExtensionRegistry` and Protocol-based design
- ✅ **Phase 2**: Dependencies organized (CrewAI in optional extras)
- ✅ **Phase 3**: All imports and references updated
- ✅ **Phase 4**: Test cases serve as examples (see `tests/integration/` and `tests/extensions/`)
- ✅ **Phase 5**: All documentation updated to reflect current structure

## Current Architecture

The current architecture matches the design described in [overview.md](../../architecture/overview.md):

- **Core**: `core/` - Pure orchestration framework
- **Extensions**: `extensions/` - Framework extensions (crewai, stdio)
- **API**: `api/` - A2A Protocol Server
- **CLI**: `cli/` - CLI tools
- **Test cases**: Serve as examples (see `tests/integration/` and `tests/extensions/`)

## Key Features Implemented

1. ✅ Unified extension system with `ExtensionRegistry` and Protocol-based design
2. ✅ All documentation updated to reflect current structure
3. ✅ Circular import issues resolved via Protocol-based architecture
4. ✅ Extension registration system implemented with decorators
5. ✅ Clean separation between core and optional features

## Core Library Principles

**aipartnerupflow is a task orchestration engine core library** that focuses on:

1. **Task Orchestration Specifications**: Task tree construction, dependency management, priority scheduling
2. **Task Execution Interface**: Unified execution interface (`ExecutableTask`) supporting multiple task types
3. **Extension System**: Support for custom executors and extensions
4. **Standardization**: A2A Protocol as the standard communication protocol
5. **Robustness**: Core functionality is stable and reliable
6. **Extensibility**: Support for AI agent and other custom functionality through extensions

**What the core library does NOT include**:
- Infrastructure features (queues, schedulers, rate limiting) - should be implemented externally
- Advanced features (distributed execution) - should be optional extensions or built on top of core
- Execution strategies (retry mechanisms) - should be implemented via extensions

## Core Features

### Task Tree Dependent Validation

**Status**: ✅ **COMPLETED**

#### ✅ Completed
- Circular dependency detection using DFS algorithm
- Single task tree validation (ensures all tasks are in the same tree)
- Validation that only one root task exists
- Verification that all tasks are reachable from root task via parent_id chain
- **Dependent Task Inclusion Validation**
  - ✅ Identify tasks that depend on a given task
  - ✅ Transitive dependency detection
  - ✅ Validation step to check dependent task inclusion
  - ✅ Comprehensive unit tests for dependent task inclusion validation
- **Task Copy Functionality**
  - ✅ Task tree re-execution support (`TaskCreator.create_task_copy()`)
  - ✅ Automatically include dependent tasks when copying
  - ✅ Handle transitive dependencies
  - ✅ Special handling for failed leaf nodes
  - ✅ Build minimal subtree containing required tasks
  - ✅ Link copied tasks to original tasks via `original_task_id` field
  - ✅ API endpoint `tasks.copy` via JSON-RPC
  - ✅ CLI command `tasks copy <task_id>`
  - ✅ Comprehensive test coverage

## External/Extension Features

The following features are **not part of the core library**. They should be implemented externally or as optional extensions:

### Task Queue and Scheduling System

**Status**: 🔄 **EXTERNAL IMPLEMENTATION**

**Recommendation**: Use external schedulers (cron, celery beat, APScheduler, etc.)

**Why not in core**:
- Task queue is infrastructure functionality, not core orchestration
- Core library focuses on task orchestration specifications, not infrastructure management
- External schedulers are mature and well-tested solutions

**Implementation Approach**:
- External schedulers call API endpoints (`tasks.create` or `tasks.copy`) at scheduled times
- Core library provides task creation and execution interfaces
- Existing `priority` field already supports priority-based execution
- Dependency management is already handled by core library

**Example**:
```bash
# Cron job to create tasks at scheduled time
0 0 * * * curl -X POST http://localhost:8000/tasks -d '{"method": "tasks.create", "params": {...}}'

# Or use celery beat for recurring tasks
@periodic_task(run_every=crontab(hour=0, minute=0))
def scheduled_task():
    # Call API to create/copy tasks
    pass
```

### Retry Mechanism

**Status**: 🔄 **EXTENSION IMPLEMENTATION**

**Recommendation**: Implement via extension system (RetryExecutor wrapper) or use `create_task_copy` for manual retry

**Why not in core**:
- Retry is an execution strategy, not core orchestration functionality
- Core library should remain simple and focused
- Can be implemented as an extension wrapper around executors

**Implementation Approaches**:

1. **Extension-based Retry** (Recommended):
   ```python
   # Create RetryExecutor extension
   class RetryExecutor(ExecutableTask):
       def __init__(self, executor: ExecutableTask, max_retries: int = 3):
           self.executor = executor
           self.max_retries = max_retries
       
       async def execute(self, inputs):
           for attempt in range(self.max_retries):
               try:
                   return await self.executor.execute(inputs)
               except Exception as e:
                   if attempt == self.max_retries - 1:
                       raise
                   await asyncio.sleep(2 ** attempt)  # Exponential backoff
   ```

2. **Manual Retry via Task Copy**:
   ```python
   # Use create_task_copy for failed tasks
   if task.status == "failed":
       new_tree = await task_creator.create_task_copy(task)
       await task_manager.distribute_task_tree(new_tree)
   ```

### Concurrency Control

**Status**: 🔄 **EXTERNAL IMPLEMENTATION**

**Recommendation**: Implement at API layer (middleware/gateway) or use external rate limiting services

**Why not in core**:
- Rate limiting is infrastructure functionality, not core orchestration
- Core library should focus on task orchestration, not infrastructure concerns
- Can be implemented at API gateway level (e.g., nginx, API Gateway, middleware)

**Implementation Approaches**:

1. **API Middleware** (Recommended):
   ```python
   # Rate limiting middleware
   @app.middleware("http")
   async def rate_limit_middleware(request, call_next):
       user_id = get_user_id(request)
       if not check_rate_limit(user_id):
           return Response("Rate limit exceeded", status_code=429)
       return await call_next(request)
   ```

2. **External Services**:
   - Use API Gateway (AWS API Gateway, Kong, etc.)
   - Use rate limiting services (Redis-based rate limiting)
   - Use reverse proxy (nginx rate limiting)

### Distributed Collaborative Execution

**Status**: 🔄 **OPTIONAL EXTENSION** (Advanced Feature)

**Recommendation**: Implement as optional extension `[distributed]` or let users build on top of core library

**Why not in core**:
- Distributed execution is an advanced feature beyond core orchestration
- Core library should focus on single-node task orchestration
- Can be implemented as an optional extension for users who need it

**Implementation Approach**:
- Option 1: Implement as optional extension `pip install aipartnerupflow[distributed]`
- Option 2: Let users build distributed solutions on top of core library
- Core library provides task state persistence (database), which is sufficient for distributed implementations

**Note**: If implemented as extension, it should:
- Be completely optional (no impact on core library)
- Use existing database for state persistence
- Leverage existing task execution interfaces
- Maintain backward compatibility with single-node mode

## For Current Development

- **Architecture**: See [overview.md](../../architecture/overview.md)
- **Directory Structure**: See [directory-structure.md](../../architecture/directory-structure.md)
- **Extension System**: See [extension-registry-design.md](../../architecture/extension-registry-design.md)
- **Development Guide**: See [setup.md](../setup.md)
