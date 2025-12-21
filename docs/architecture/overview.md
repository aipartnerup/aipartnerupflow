# aipartnerupflow Architecture Design Document

## Core Positioning

**The core of aipartnerupflow is task orchestration and execution specifications**

This is a **task orchestration framework library** that provides:
1. **Task Orchestration Specifications**: Task tree construction, dependency management, priority scheduling
2. **Task Execution Specifications**: Unified execution interface supporting multiple task types
3. **Supporting Features**: Storage, unified external API interfaces

aipartnerupflow is a reusable **framework library**.

## Architecture Layers

The aipartnerupflow architecture consists of four main layers:

```mermaid
flowchart TD
    subgraph APILayer["Unified External API Interface Layer"]
        A2AServer["A2A Protocol Server<br/>(HTTP/SSE/WebSocket)"]
        CLI["CLI Tools"]
    end
    
    subgraph OrchestrationLayer["Task Orchestration Specification Layer (CORE)"]
        TaskManager["TaskManager<br/>- Task tree orchestration<br/>- Dependency management<br/>- Priority scheduling"]
        ExecutableTask["ExecutableTask<br/>- Task execution interface"]
    end
    
    subgraph ExecutionLayer["Task Execution Layer"]
        CrewManager["CrewManager [crewai]<br/>- LLM task execution"]
        BatchManager["BatchManager [crewai]<br/>- Batch orchestration"]
        CustomTasks["Custom Tasks<br/>- External services<br/>- Automated tasks"]
    end
    
    subgraph SupportLayer["Supporting Features Layer"]
        Storage["Storage<br/>- DuckDB/PostgreSQL<br/>- Task state persistence"]
        Streaming["Streaming<br/>- Real-time updates"]
    end
    
    APILayer --> OrchestrationLayer
    OrchestrationLayer --> ExecutionLayer
    ExecutionLayer --> SupportLayer
    
    style APILayer fill:#e1f5ff
    style OrchestrationLayer fill:#fff4e1
    style ExecutionLayer fill:#e8f5e9
    style SupportLayer fill:#f3e5f5
```

### Layer Details

**Unified External API Interface Layer**
- A2A Protocol Server (HTTP/SSE/WebSocket) [a2a]
  - A2A Protocol is the standard protocol for agent communication
- CLI Tools [cli]

### Protocol Standard

**A2A (Agent-to-Agent) Protocol** is the standard protocol adopted by aipartnerupflow for agent communication.

**Why A2A Protocol?**
- **Mature Standard**: A2A Protocol is a mature, production-ready specification designed specifically for AI Agent systems
- **Complete Features**: Provides streaming execution, task management, agent capability descriptions, and multiple transport methods
- **Well-Designed Abstraction**: `RequestContext` encapsulates all request information, `EventQueue` unifies streaming updates
- **Protocol-Agnostic**: Can be implemented over different transport layers (HTTP REST, SSE, WebSocket)

**A2A Protocol Components:**
- `AgentExecutor`: Interface for executing agent tasks
- `RequestContext`: Encapsulates method, parameters, metadata, and message content
- `EventQueue`: Unified interface for streaming updates and real-time progress notifications
- `AgentCard` / `AgentSkill`: Agent capability description mechanism

**Task Orchestration Specification Layer (CORE)**
- TaskManager: Task tree orchestration, dependency management, priority scheduling
- ExecutableTask: Task execution specification interface

**Task Execution Layer**
- CrewManager [crewai]: CrewAI (LLM) task execution
- BatchManager [crewai]: Batch task orchestration
- Custom Tasks: Traditional external service calls, automated task services, etc.

**Supporting Features Layer**
- Storage: Task state persistence (DuckDB/PostgreSQL)
- Streaming: Real-time progress updates

## Module Organization

### Core (pip install aipartnerupflow)

**Pure task orchestration framework - NO CrewAI dependency**

```
execution/          # Task orchestration specifications (CORE)
├── task_manager.py      # TaskManager - core orchestration engine
└── streaming_callbacks.py  # Streaming support

interfaces/        # Core interfaces
├── executable_task.py  # ExecutableTask interface
├── base/               # Base class implementations
│   └── base_task.py   # BaseTask base class
└── storage.py          # TaskStorage interface

storage/           # Storage implementation
├── factory.py         # create_storage() function
├── sqlalchemy/        # SQLAlchemy implementation
└── dialects/          # Database dialects (DuckDB/PostgreSQL)

utils/             # Utility functions
```

### Optional Features

#### [crewai] - CrewAI LLM Task Support

```
extensions/crewai/
├── __init__.py
├── crew_manager.py     # CrewManager - CrewAI wrapper
├── batch_manager.py    # BatchManager - batch execution of multiple crews
└── types.py            # CrewManagerState, BatchState
```

**Installation**: `pip install aipartnerupflow[crewai]`

**Includes**:
- CrewManager for LLM-based agent crews
- BatchManager for atomic batch execution of multiple crews
- Related type definitions

**Note**: BatchManager is part of [crewai] because it's specifically designed for batching multiple CrewAI crews together.

#### [http_executor] - HTTP/Remote API Task Execution

```
extensions/http_executor/
├── __init__.py
├── http_executor.py    # HTTPExecutor - ExecutableTask implementation for HTTP calls
├── client.py           # HTTP client with retry, timeout, auth support
└── types.py            # HTTPExecutorState, RequestConfig, ResponseConfig
```

**Installation**: `pip install aipartnerupflow[http]`

**Purpose**: Execute tasks by calling remote HTTP/HTTPS APIs.

**Features**:
- HTTP/HTTPS request execution
- Retry logic with exponential backoff
- Authentication support (API keys, OAuth, etc.)
- Request/response validation
- Timeout handling

**Use Case**: Tasks that need to call external REST APIs, webhooks, or remote services.

**Note**: For examples and learning templates, see the test cases in `tests/integration/` and `tests/extensions/`. Test cases serve as comprehensive examples demonstrating real-world usage patterns.

#### [a2a] - A2A Protocol Server

```
api/                   # Unified API service layer (supports multiple protocols)
├── __init__.py        # Unified entry point, backward compatible
├── main.py            # CLI entry point (main() function and uvicorn server)
├── extensions.py      # Extension management (initialize_extensions, EXTENSION_CONFIG)
├── protocols.py       # Protocol management (get_protocol_from_env, check_protocol_dependency)
├── app.py             # Application creation (create_app_by_protocol, create_a2a_server, create_mcp_server)
├── a2a/               # A2A Protocol Server implementation
│   ├── __init__.py    # A2A module exports
│   ├── server.py      # A2A server creation
│   ├── agent_executor.py      # A2A agent executor
│   ├── custom_starlette_app.py # Custom A2A Starlette application
│   └── event_queue_bridge.py   # Event queue bridge
├── mcp/               # MCP (Model Context Protocol) Server implementation
│   ├── __init__.py    # MCP module exports
│   ├── server.py      # MCP server creation
│   ├── adapter.py     # TaskRoutes adapter for MCP
│   └── ...            # Other MCP components
├── routes/            # Protocol-agnostic route handlers
│   ├── __init__.py    # Route handlers exports
│   ├── base.py        # BaseRouteHandler - shared functionality
│   ├── tasks.py       # TaskRoutes - task management handlers
│   └── system.py      # SystemRoutes - system operation handlers
```

#### [cli] - CLI Tools

```
cli/                   # Command-line interface
├── main.py            # CLI entry point
└── commands/          # CLI commands
```

## Installation Strategy

### Core Only

```bash
pip install aipartnerupflow
```

**Includes**:
- Task orchestration specifications (TaskManager)
- Core interfaces (ExecutableTask, BaseTask, TaskStorage)
- Storage (DuckDB default)
- NO CrewAI dependency

**Use case**: Users who want pure orchestration framework with custom task implementations.

### With CrewAI Support

```bash
pip install aipartnerupflow[crewai]
```

**Adds**:
- CrewManager for LLM-based tasks via CrewAI
- BatchManager for atomic batch execution of multiple crews

**Use case**: Users who want LLM agent capabilities and/or batch execution of multiple crews.

### Full Installation

```bash
pip install aipartnerupflow[all]
```

**Includes**: Core + crewai + batch + api + cli + examples + postgres

## Core Components

### 1. Task Orchestration Specifications (Core)

#### TaskManager (`execution/task_manager.py`)
- **Core Responsibility**: Task orchestration and execution specifications
- **Features**:
  - Task tree construction and management (TaskTreeNode)
  - Dependency resolution and execution order control
  - Priority scheduling
  - Task state management (pending, in_progress, completed, failed)
  - Task lifecycle management (create, execute, complete, failure handling)

#### ExecutableTask (`interfaces/executable_task.py`)
- **Responsibility**: Define task execution specification interface
- **Implementations**:
  - `CrewManager` [crewai]: LLM-based tasks (via CrewAI)
  - Custom tasks: Traditional external service calls, automated task services, etc.


### 2. Task Execution Layer

#### CrewManager (`extensions/crewai/crew_manager.py`) [crewai]
- **Responsibility**: CrewAI (LLM) task execution - **ExecutableTask implementation**
- **Features**:
  - Wraps CrewAI Crew functionality
  - Supports LLM-based agent collaboration
  - Implements ExecutableTask interface
- **Type**: Task executor (one of many possible implementations)

#### BatchManager (`extensions/crewai/batch_manager.py`) [crewai]
- **Responsibility**: Batch task orchestration for multiple crews (simple merging)
- **Features**:
  - Atomic execution of multiple crews
  - Result merging
  - **Not an ExecutableTask** (it's a container, not a task)
- **Location**: Part of [crewai] because it's specifically for batching CrewAI crews together

#### HTTPExecutor (`extensions/http_executor/http_executor.py`) [http]
- **Responsibility**: Remote HTTP/API call task execution - **ExecutableTask implementation**
- **Features**:
  - HTTP/HTTPS request execution
  - Retry logic, timeout handling
  - Authentication support
- **Type**: Task executor
- **Use Case**: Tasks that call external REST APIs or remote services

#### Custom Tasks (Core)
- **Types**:
  - User-defined implementations of ExecutableTask
  - Can be any task type (database operations, file processing, etc.)
- **Implementation**: Inherit from `ExecutableTask` or `BaseTask`
- **Location**: Users create these in their own codebase

#### Built-in Executors (Features)
- **CrewManager** [crewai]: LLM-based tasks via CrewAI
- **HTTPExecutor** [http]: Remote API calls via HTTP
- **Future executors**: database executor, queue executor, etc.
- **Location**: `extensions/` directory

### 3. Supporting Features

#### Storage (`storage/`)
- **Responsibility**: Task state persistence
- **Implementations**:
  - DuckDB (default, embedded, zero-config)
  - PostgreSQL (optional, production environment)
- **Features**:
  - Task creation, querying, updating
  - Task tree state management

**TaskModel Design and A2A Protocol Integration:**

The storage layer uses `TaskModel` (SQLAlchemy model) to persist task definitions and execution results. A key design decision is the separation between `TaskModel` (task definition) and A2A Protocol's `Task` (execution instance).

**Conceptual Separation:**

| Component | Nature | Purpose | Lifecycle |
|-----------|--------|---------|-----------|
| **TaskModel** | Task definition (static) | Task orchestration, dependency management, task tree structure | Persistent (can have multiple executions) |
| **A2A Protocol Task** | Execution instance (dynamic) | LLM message context management, execution tracking | Single execution lifecycle |

**Key Understanding:**

A2A Protocol's `Task` is primarily designed for LLM message context management. It represents an execution instance with:
- `Task.history`: LLM conversation history
- `Task.artifacts`: LLM-generated results
- `Task.status.message`: LLM response messages

**TaskModel**, on the other hand, focuses on task orchestration:
- Task definition metadata (name, dependencies, priority, schemas)
- Task tree structure (parent_id, children)
- Latest execution results (extracted from A2A Task.artifacts)
- Execution status and progress

**Mapping Relationship:**

```
TaskModel (Task Definition)          A2A Protocol Task (Execution Instance)
───────────────────────────────────────────────────────────────────────────
TaskModel.id          →  Task.context_id    (task definition ID = context ID)
TaskModel.status      →  TaskStatus.state   (status mapping)
TaskModel.result      →  Task.artifacts     (execution result)
TaskModel.error       →  TaskStatus.message (error message)
TaskModel.user_id     →  Task.metadata["user_id"] (optional user identifier)

Task.id               →  Execution instance ID (A2A Protocol internal, auto-generated)
Task.history           →  Not stored in TaskModel (LLM conversation history, execution-level)
```

**Design Decisions:**

1. **TaskModel does NOT store execution-level fields**:
   - ❌ `context_id`: Execution-level concept (TaskModel.id serves this purpose)
   - ❌ `artifacts`: Execution instance field (extracted to TaskModel.result)
   - ❌ `history`: Execution instance field (LLM conversation history, managed by A2A Protocol)
   - ❌ `metadata`: Execution instance field (orchestration info stored in TaskModel fields)
   - ❌ `kind`: A2A Protocol-specific field

2. **One-to-Many Relationship**:
   - One `TaskModel` can have multiple `Task` execution instances
   - Each execution creates a new A2A Protocol `Task` with a unique execution instance ID
   - `TaskModel.id` (task definition ID) maps to `Task.context_id`

3. **Table Name**:
   - Default table name: `apflow_tasks` (prefixed to distinguish from A2A Protocol's `tasks` table)
   - Configurable via `AIPARTNERUPFLOW_TASK_TABLE_NAME` environment variable
   - See [Configuration](configuration.md) for details

4. **Storage Bridge**:
   - Uses A2A SDK's `InMemoryTaskStore` for A2A Protocol task execution instances
   - TaskModel persistence is handled by `TaskRepository` (separate from A2A TaskStore)
   - Converts between `TaskModel` (task definition) and A2A Protocol `Task` (execution instance)
   - Updates `TaskModel` with execution results from A2A Protocol `Task`

#### API (`api/`) [a2a]
- **Responsibility**: Unified external API service layer supporting multiple network protocols
- **Current Implementation**: A2A Protocol Server (`api/a2a/`)
  - **Protocol Standard**: A2A (Agent-to-Agent) Protocol
  - **Transport Layers**: HTTP, SSE, WebSocket (all implementing A2A Protocol)
  - **Structure**: A2A implementation organized in `api/a2a/` subdirectory for better code organization
- **Future Extensions**: May include additional protocols (e.g., REST API in `api/rest/`) for direct HTTP access

#### Streaming (`execution/streaming_callbacks.py`)
- **Responsibility**: Real-time progress updates
- **Features**: Real-time task execution state updates

## Task Type Support

### 1. LLM Tasks (CrewAI) [crewai]
```python
# Requires: pip install aipartnerupflow[crewai]
from aipartnerupflow.extensions.crewai import CrewManager

crew = CrewManager(
    agents=[{"role": "Analyst", "goal": "Analyze data"}],
    tasks=[{"description": "Analyze input", "agent": "Analyst"}]
)
result = await crew.execute(inputs={...})
```

### 2. Traditional External Service Calls
```python
from aipartnerupflow.core.interfaces.plugin import ExecutableTask

class APICallTask(ExecutableTask):
    async def execute(self, inputs):
        # Call external API
        response = await http_client.post(url, data=inputs)
        return response.json()
```

### 3. Automated Task Services
```python
class ScheduledTask(ExecutableTask):
    async def execute(self, inputs):
        # Execute scheduled task logic
        return {"status": "completed"}
```

## Task Orchestration Patterns

### Simple Batch Orchestration (BatchManager) [crewai]
- Multiple crews execute sequentially, results are merged
- Atomic operation: failure of any crew causes entire batch to fail
- Part of [crewai] extra (designed for batching CrewAI crews)

### Complex Task Tree Orchestration (TaskManager) [core]
- Supports dependencies
- Supports priorities
- Supports hierarchical task tree structure
- Automatic scheduling and execution
- No external dependencies

## Design Principles

1. **Clear Core**: Task orchestration and execution specifications are the core
2. **Pure Core**: Core has no external LLM/AI dependencies (CrewAI optional)
3. **Unified Interface**: All task types unified through ExecutableTask interface
4. **Executor Pattern**: Different executors (CrewAI, HTTP, etc.) are separate features
5. **Flexible Orchestration**: Supports simple batch to complex task tree
6. **Optional Storage**: Provides persistence but configurable
7. **Unified API**: Provides unified external interface using A2A Protocol (standard protocol)
8. **Modular Installation**: Users install only what they need
9. **Learning Resources**: Test cases in `tests/integration/` and `tests/extensions/` serve as comprehensive examples
