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

## Planned Features

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

### Task Queue and Scheduling System

**Status**: ⏳ **PLANNED**

#### Core Requirements
1. **Task Queue System**
   - Priority-based task queue (using existing `priority` field)
   - Dependency-aware queue (tasks wait for dependencies to complete)
   - Queue persistence (store queue state in database)
   - Queue monitoring and metrics

2. **Task Scheduling**
   - Automatic task scheduling based on dependencies and priority
   - Support for scheduled execution (future execution time)
   - Support for recurring tasks (cron-like scheduling)
   - Task scheduling conflict resolution

### Retry Mechanism

**Status**: ⏳ **PLANNED**

#### Core Requirements
1. **Automatic Retry on Failure**
   - Configurable retry count per task (default: 0, no retry)
   - Configurable retry delay strategies:
     - Fixed delay
     - Exponential backoff
     - Custom backoff function
   - Retry condition configuration (which errors trigger retry)
   - Maximum retry timeout

2. **Retry State Management**
   - Track retry attempts and history
   - Final failure handling after max retries

3. **Retry Strategies**
   - Immediate retry (for transient errors)
   - Delayed retry (for rate limiting, temporary failures)
   - Exponential backoff (for overloaded services)
   - Custom retry logic (user-defined)

### Concurrency Control

**Status**: ⏳ **PLANNED**

#### Core Requirements
1. **User-Level Concurrency Limits**
   - Limit concurrent root tasks per user (`user_id`)
   - Configurable per-user limits (default: unlimited)
   - Per-user queue management
   - User-level rate limiting

2. **Root Task-Level Concurrency Limits**
   - Limit concurrent execution of tasks within a single root task tree
   - Configurable per root task (default: unlimited)
   - Root task queue management
   - Prevent resource exhaustion from large task trees

3. **Global Concurrency Limits**
   - Global maximum concurrent tasks across all users
   - Global queue management
   - System-wide resource protection
   - Configurable global limits (default: unlimited)

4. **Concurrency Control Implementation**
   - Semaphore-based concurrency control
   - Queue-based task waiting when limits reached
   - Priority-based queue ordering when waiting
   - Concurrency metrics and monitoring

**Design Considerations**:
- Concurrency limits should be checked before task execution starts
- Tasks should be queued (not rejected) when limits are reached
- Queue should respect priority and dependencies
- Concurrency state should be recoverable (persist in database for distributed systems)

### Distributed Collaborative Execution

**Status**: ⏳ **PLANNED** (Advanced Feature)

#### Core Design Principles
1. **Unified Execution Model**
   - Single-node and distributed execution share the same codebase
   - Any node can run as a task execution server
   - Seamless switching between single-node and distributed modes
   - No code changes required when switching modes

2. **Task Tree Sub-task Distribution**
   - A single task tree can be split across multiple nodes
   - Sub-tasks (children of root) can be assigned to different nodes
   - Sub-tree distribution (entire branches assigned to nodes)
   - Fine-grained task distribution (individual tasks assigned to nodes)
   - Automatic dependency resolution across nodes

3. **Fault Tolerance and Task Takeover**
   - Automatic detection of node failures
   - Uncompleted tasks from failed nodes can be taken over by healthy nodes
   - Task ownership tracking and transfer
   - No task loss on node failure
   - Automatic recovery and continuation

4. **Collaborative Execution**
   - Multiple nodes can collaborate on a single task tree
   - Load balancing across available nodes
   - Dynamic task reassignment based on node capacity
   - Real-time task state synchronization

#### Core Requirements

##### 1. Node Management
- **Node Registration and Discovery**
  - Node registration with unique node ID
  - Node capability reporting (CPU, memory, current load)
  - Node health monitoring (heartbeat mechanism)
  - Node status tracking (active, idle, overloaded, failed)
  - Automatic node discovery (via message queue or service registry)

- **Node Roles**
  - **Coordinator Node**: Manages task distribution and coordination (optional, can be distributed)
  - **Worker Node**: Executes assigned tasks
  - **Hybrid Node**: Can act as both coordinator and worker
  - Any node can take over coordinator role if coordinator fails

##### 2. Task Distribution
- **Task Assignment Strategies**
  - **Round-robin**: Distribute tasks evenly across nodes
  - **Load-based**: Assign tasks to nodes with lowest load
  - **Capability-based**: Match task requirements to node capabilities
  - **Affinity-based**: Prefer nodes that have cached resources or data
  - **User-defined**: Custom distribution strategy

- **Distribution Granularity**
  - **Root-level**: Each root task assigned to a node (simple)
  - **Sub-task level**: Sub-tasks of root assigned to different nodes
  - **Sub-tree level**: Entire branches assigned to nodes
  - **Task level**: Individual tasks assigned to nodes (fine-grained)

- **Dependency Handling**
  - Cross-node dependency resolution
  - Task result sharing between nodes
  - Dependency waiting across nodes
  - Automatic dependency notification

##### 3. Fault Tolerance
- **Node Failure Detection**
  - Heartbeat mechanism (configurable interval)
  - Timeout-based failure detection
  - Health check endpoints
  - Automatic failure detection and notification

- **Task Takeover Mechanism**
  - Track task ownership (node_id, assigned_at, last_heartbeat)
  - Detect orphaned tasks (tasks owned by failed nodes)
  - Automatic task reassignment to healthy nodes
  - Task state recovery (resume from last checkpoint if available)
  - Prevent duplicate execution (task ownership locking)

- **Task State Persistence**
  - Task state stored in shared database
  - Task execution progress checkpointing
  - Task result caching for cross-node dependencies
  - Task ownership records in database

##### 4. State Synchronization
- **Shared State Management**
  - Task state stored in shared database (PostgreSQL recommended)
  - Real-time state updates via database or message queue
  - Task status synchronization across nodes
  - Dependency result sharing

- **Distributed Locking**
  - Task ownership locking (prevent duplicate execution)
  - Critical section locking for task assignment
  - Database-based locking or distributed lock service (Redis, etcd)
  - Lock timeout and automatic release

##### 5. Message Queue Integration (Optional)
- **Message Queue Abstraction**
  - Pluggable message queue backend
  - Support for Redis, RabbitMQ, Kafka, etc.
  - Fallback to database polling if no message queue

- **Message Types**
  - Task assignment messages
  - Task completion notifications
  - Node failure notifications
  - Task takeover requests
  - Heartbeat messages

**Design Considerations**:
1. **Backward Compatibility**
   - Single-node mode is the default (no distributed overhead)
   - Distributed features are opt-in via configuration
   - Existing code works without changes in single-node mode

2. **Stateless Nodes**
   - Nodes should be stateless (all state in shared database)
   - Any node can be restarted without data loss
   - Task state persists in database, not in node memory

3. **Fault Tolerance**
   - No single point of failure (coordinator can be distributed)
   - Automatic task takeover on node failure
   - Graceful node shutdown (finish current tasks, don't accept new tasks)

4. **Performance**
   - Minimize cross-node communication overhead
   - Cache task results for dependency resolution
   - Batch state updates when possible
   - Efficient task assignment algorithms

5. **Scalability**
   - Support dynamic node addition/removal
   - Horizontal scaling (add more nodes to increase capacity)
   - Load balancing across nodes
   - Support for large task trees (thousands of tasks)

6. **Consistency**
   - Task ownership must be unique (prevent duplicate execution)
   - Task state must be consistent across nodes
   - Dependency resolution must be correct across nodes

**Installation**: `pip install aipartnerupflow[distributed]` (future)

## For Current Development

- **Architecture**: See [overview.md](../../architecture/overview.md)
- **Directory Structure**: See [directory-structure.md](../../architecture/directory-structure.md)
- **Extension System**: See [extension-registry-design.md](../../architecture/extension-registry-design.md)
- **Development Guide**: See [setup.md](../setup.md)
