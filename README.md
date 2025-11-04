# aipartnerupflow

**Task Orchestration and Execution Framework**

## Core Positioning

The core of `aipartnerupflow` is **task orchestration and execution specifications**. It provides a unified task orchestration framework that supports execution of multiple task types. The core is **pure orchestration** with no LLM dependencies - CrewAI support is optional.

**Core includes:**
- Task orchestration specifications (TaskManager)
- Core interfaces (ExecutableTask, BaseTask, TaskStorage)
- Storage (DuckDB default, PostgreSQL optional)
- **NO CrewAI dependency** (available via [crewai] extra)
- **NO template dependency** (available via [templates] extra)

**Optional features:**
- **CrewAI Support** [crewai]: LLM-based agent crews via CrewManager (task executor implementation)
- **Template-based Task Creation** [templates]: Create task trees from predefined templates via TaskPlanner and TaskCreator
- **HTTP Executor** [http]: Remote API calls via HTTPExecutor (future, task executor implementation)
- **Examples** [examples]: Predefined example implementations for learning and quick start
- **API Server** [api]: A2A Protocol Server (A2A Protocol is the standard protocol for agent communication)
- **CLI Tools** [cli]: Command-line interface

**Protocol Standard:**
- **A2A Protocol**: The framework adopts **A2A (Agent-to-Agent) Protocol** as the standard protocol for agent communication. A2A Protocol provides mature, production-ready specifications for agent-to-agent communication, including streaming execution, task management, and agent capability descriptions.

**Note**: CrewManager and future executors (like HTTPExecutor) are all implementations of the `ExecutableTask` interface. Each executor handles different types of task execution (LLM, HTTP, etc.).

## Core Features

### Task Orchestration Specifications (Core)
- **TaskManager**: Task tree orchestration, dependency management, priority scheduling
- **Unified Execution Specification**: All task types unified through the `ExecutableTask` interface

### Task Execution Types

All task executors implement the `ExecutableTask` interface:

- **Custom Tasks** (core): Users implement `ExecutableTask` for their own task types
- **CrewManager** [crewai]: LLM-based task execution via CrewAI (built-in executor)
- **HTTPExecutor** [http]: Remote API call execution via HTTP (future, built-in executor)
- **BatchManager** [crewai]: Batch orchestration container (batches multiple crews)

### Supporting Features
- **Storage**: Task state persistence (DuckDB default, PostgreSQL optional)
- **Unified External API**: A2A Protocol Server (HTTP, SSE, WebSocket) [api]
- **Real-time Progress Streaming**: Streaming support via A2A Protocol
- **CLI Tools**: Command-line interface [cli]

### Protocol Standard
- **A2A Protocol**: The framework adopts **A2A (Agent-to-Agent) Protocol** as the standard protocol for agent communication. A2A Protocol is a mature, production-ready specification designed specifically for AI Agent systems, providing:
  - Agent-to-agent standardized communication interface
  - Streaming task execution support
  - Agent capability description mechanism (AgentCard, AgentSkill)
  - Multiple transport methods (HTTP, SSE, WebSocket)
  - Task management and status tracking
  - JWT authentication support

## Installation

### Core Library (Minimum - Pure Orchestration Framework)

```bash
pip install aipartnerupflow
```

**Includes**: Task orchestration specifications, core interfaces, storage (DuckDB)
**Excludes**: CrewAI, batch execution, API server, CLI tools

### With Optional Features

```bash
# CrewAI LLM task support (includes batch)
pip install aipartnerupflow[crewai]
# Includes: CrewManager for LLM-based agent crews
#           BatchManager for atomic batch execution of multiple crews

# Predefined examples (example crews, batches, custom tasks)
pip install aipartnerupflow[examples]
# Includes: Example implementations for learning and customization

# A2A Protocol Server (Agent-to-Agent communication protocol)
pip install aipartnerupflow[api]
# Run A2A server: python -m aipartnerupflow.api.main
# Or: aipartnerupflow-server (CLI command)

# CLI tools
pip install aipartnerupflow[cli]
# Run CLI: aipartnerupflow or apflow

# PostgreSQL storage
pip install aipartnerupflow[postgres]

# Everything (includes all extras)
pip install aipartnerupflow[all]
```

## Quick Start

### As a Library (Pure Core)

**Using Task Orchestration Specifications:**

```python
from aipartnerupflow.execution import TaskManager, TaskTreeNode
from aipartnerupflow.storage import create_storage

# Create storage and task manager (core)
storage = create_storage()
task_manager = TaskManager(db=storage.get_session())

# Create task tree (task orchestration)
root_task = task_manager.create_task(
    name="root_task",
    user_id="user_123",
    priority=2
)

child_task = task_manager.create_task(
    name="custom_task",  # Task name corresponds to specific executor
    user_id="user_123",
    parent_id=root_task.id,
    dependencies=[],  # Dependency relationships
    input_data={"url": "https://example.com"}
)

# Build task tree and execute (task orchestration core)
task_tree = TaskTreeNode(root_task)
task_tree.add_child(TaskTreeNode(child_task))
result = await task_manager.distribute_task_tree(task_tree)
```

**Creating Custom Tasks (Traditional External Service Calls):**

```python
from aipartnerupflow.core.interfaces.plugin import ExecutableTask
from typing import Dict, Any
import aiohttp

class APICallTask(ExecutableTask):
    """Traditional external API call task"""
    
    id = "api_call_task"
    name = "API Call Task"
    description = "Call external API service"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.post(inputs["url"], json=inputs.get("data")) as response:
                result = await response.json()
                return {"status": "completed", "result": result}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "API endpoint"},
                "data": {"type": "object", "description": "Request data"}
            }
        }
```

### With CrewAI Support [crewai]

**Executing CrewAI (LLM) Tasks:**

```python
# Requires: pip install aipartnerupflow[crewai]
from aipartnerupflow.features.crewai import CrewManager

# CrewAI task execution
crew = CrewManager(
    name="Analysis Crew",
    agents=[{"role": "Analyst", "goal": "Analyze data"}],
    tasks=[{"description": "Analyze input", "agent": "Analyst"}]
)
result = await crew.execute(inputs={...})
```

### With Batch Support [crewai]

**Using BatchManager to batch multiple crews (atomic operation):**

```python
# Requires: pip install aipartnerupflow[crewai]
from aipartnerupflow.features.crewai import BatchManager, CrewManager

# BatchManager is a batch container - executes multiple crews as atomic operation
batch = BatchManager(
    id="my_batch",
    name="Batch Analysis",
    works={
        "data_collection": {
            "agents": [{"role": "Collector", "goal": "Collect data"}],
            "tasks": [{"description": "Collect data", "agent": "Collector"}]
        },
        "data_analysis": {
            "agents": [{"role": "Analyst", "goal": "Analyze data"}],
            "tasks": [{"description": "Analyze data", "agent": "Analyst"}]
        }
    }
)

# All crews execute sequentially, results are merged
# If any crew fails, entire batch fails (atomic)
result = await batch.execute(inputs={...})
```

### CLI Usage

```bash
# Run a batch
aipartnerupflow run my_batch --inputs '{"key": "value"}'

# Or use the shorthand
apflow run my_batch --inputs '{"key": "value"}'

# Start API server
apflow serve --port 8000

# Start daemon mode
apflow daemon start
```

### A2A Protocol Server

The `[api]` extra provides an **A2A (Agent-to-Agent) Protocol** server built on Starlette/FastAPI.

**A2A Protocol is the standard protocol** adopted by aipartnerupflow for agent communication. It provides:
- Mature, production-ready specifications for agent-to-agent communication
- Streaming task execution support via EventQueue
- Agent capability description mechanism (AgentCard, AgentSkill)
- Multiple transport methods (HTTP, SSE, WebSocket)
- Task management and status tracking
- JWT authentication support

```python
from aipartnerupflow.api import create_app

# Create A2A protocol server app
app = create_app()

# Run with: uvicorn app:app --port 8000
# Or use the entry point: aipartnerupflow-server
```

**Note**: The current `[api]` extra focuses on A2A protocol support. Future versions may
include additional FastAPI REST API endpoints for direct HTTP access without the A2A protocol.

## Architecture Design

```
┌─────────────────────────────────────────────────────────────┐
│              Unified External API Interface Layer            │
│  - A2A Protocol Server (HTTP/SSE/WebSocket) [api]          │
│  - REST API (Future Extension)                              │
│  - CLI Tools [cli]                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│        Task Orchestration Specification Layer (CORE)         │
│        - TaskManager: Task tree orchestration, dependency  │
│          management, priority scheduling                     │
│        - TaskPlanner: Task planning and template management │
│        - ExecutableTask: Unified task interface             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Task Execution Layer                      │
│  - Custom Tasks [core]: ExecutableTask implementations      │
│    • Traditional external service calls (API, DB, etc.)     │
│    • Automated task services (scheduled tasks, workflows)  │
│  - CrewManager [crewai]: CrewAI (LLM) task execution        │
│  - BatchManager [batch]: Batch task orchestration           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Supporting Features Layer                │
│  - Storage: Task state persistence (DuckDB/PostgreSQL)     │
│  - Streaming: Real-time progress updates                    │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
aipartnerupflow/
├── src/aipartnerupflow/
│   ├── execution/      # Task orchestration specifications (CORE) [always included]
│   │   ├── task_manager.py      # TaskManager - task orchestration core
│   │   └── streaming_callbacks.py # Streaming support
│   ├── base/           # Base interfaces and base classes [always included]
│   │   ├── plugin.py   # ExecutableTask interface, BaseTask base class
│   │   └── storage.py  # Storage interface
│   ├── storage/        # Storage implementation [always included]
│   │   ├── base.py     # TaskStorage interface
│   │   ├── factory.py # create_storage() function
│   │   ├── sqlalchemy/ # SQLAlchemy implementation
│   │   └── dialects/   # Database dialects (DuckDB/PostgreSQL)
│   ├── features/        # Optional features
│   │   ├── crewai/     # CrewAI LLM support [crewai extra]
│   │   │   ├── crew_manager.py
│   │   │   ├── batch_manager.py  # Batch execution of multiple crews
│   │   │   └── types.py
│   │   └── templates/  # Template-based task creation [templates extra]
│   │       ├── task_planner.py
│   │       └── task_creator.py
│   ├── examples/       # Predefined examples [examples extra]
│   │   ├── crews/      # Example CrewManager implementations
│   │   ├── batches/    # Example BatchManager implementations
│   │   └── tasks/      # Example custom ExecutableTask implementations
│   ├── api/            # Unified external API [api extra]
│   │   ├── main.py     # API service entry point
│   │   ├── a2a_server.py # A2A server creation
│   │   ├── agent_executor.py # A2A protocol handling
│   │   └── handlers/   # HTTP/SSE/WS handlers
│   ├── cli/            # CLI tools [cli extra]
│   │   ├── main.py     # CLI entry point
│   │   └── commands/   # CLI commands
│   │
│   └── core/           # Core framework (always included)
│       ├── interfaces/ # Core interfaces (ExecutableTask, BaseTask, TaskStorage)
│       ├── execution/  # Task orchestration (TaskManager)
│       ├── storage/    # Storage implementation
│       └── utils/      # Utility functions
│
│   Note: Protocol specifications are handled by A2A Protocol (standard protocol).
│   See api/ module for A2A Protocol implementation.
└── tests/              # Test suite
```

**Core Module Descriptions**:
- **execution/**: Task orchestration specifications (core) - TaskManager handles task tree orchestration, dependency management, priority scheduling
- **interfaces/**: Core interfaces - ExecutableTask, BaseTask, TaskStorage
- **storage/**: Task state persistence - supports DuckDB (default) and PostgreSQL
- **features/crewai/**: Optional CrewAI support - CrewManager and BatchManager [crewai]
- **features/templates/**: Optional template-based task creation - TaskPlanner and TaskCreator [templates]
- **examples/**: Predefined examples for learning and customization [examples]
- **api/**: Unified external API interface - A2A Protocol Server [api]

**Installation Strategy**:
- `pip install aipartnerupflow`: Core library only (execution, base, storage, utils) - **NO CrewAI, NO templates**
- `pip install aipartnerupflow[crewai]`: Core + CrewAI support (includes BatchManager)
- `pip install aipartnerupflow[templates]`: Core + Template-based task creation
- `pip install aipartnerupflow[examples]`: Core + Example implementations
- `pip install aipartnerupflow[api]`: Core + API server
- `pip install aipartnerupflow[cli]`: Core + CLI tools
- `pip install aipartnerupflow[all]`: Full installation (all features)

## Documentation

Full documentation is available at [docs.aipartnerup.com](https://docs.aipartnerup.com).

## License

Apache-2.0

## Contributing

Contributions are welcome! Please see our [development guide](docs/development/DEVELOPMENT.md) for setup instructions and contribution guidelines.

## Documentation

- **User Guide**: This README
- **Architecture Guide**: [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) - Detailed architecture documentation
- **Development Guide**: [docs/development/DEVELOPMENT.md](docs/development/DEVELOPMENT.md) - For developers working on the project

See [docs/README.md](docs/README.md) for complete documentation index.

## Links

- Website: [aipartnerup.com](https://aipartnerup.com)
- GitHub: [aipartnerup/aipartnerupflow](https://github.com/aipartnerup/aipartnerupflow)
- PyPI: [aipartnerupflow](https://pypi.org/project/aipartnerupflow/)
