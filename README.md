# aipartnerupflow

**Task Orchestration and Execution Framework**

## Core Positioning

The core of `aipartnerupflow` is **task orchestration and execution specifications**. It provides a unified task orchestration framework that supports execution of multiple task types. The core is **pure orchestration** with no LLM dependencies - CrewAI support is optional.

**Core includes:**
- Task orchestration specifications (TaskManager)
- Core interfaces (ExecutableTask, BaseTask, TaskStorage)
- Storage (DuckDB default, PostgreSQL optional)
- **NO CrewAI dependency** (available via [crewai] extra)

**Optional features:**
- **CrewAI Support** [crewai]: LLM-based agent crews via CrewManager (task executor implementation)
- **HTTP/REST Executor** [http]: Remote API calls via RestExecutor (task executor implementation)
- **SSH Executor** [ssh]: Remote command execution via SSH (task executor implementation)
- **Docker Executor** [docker]: Containerized command execution (task executor implementation)
- **gRPC Executor** [grpc]: gRPC service calls (task executor implementation)
- **WebSocket Executor**: Bidirectional WebSocket communication (task executor implementation)
- **aipartnerupflow API Executor**: Inter-instance API calls for distributed execution (task executor implementation)
- **MCP Executor**: Model Context Protocol executor for accessing external tools and data sources (task executor implementation)
- **MCP Server** [a2a]: MCP (Model Context Protocol) server exposing task orchestration as MCP tools and resources
- **LLM Executor** [llm]: Direct LLM interaction via LiteLLM (supports OpenAI, Anthropic, Gemini, etc.)
- **A2A Protocol Server** [a2a]: A2A Protocol Server (A2A Protocol is the standard protocol for agent communication)
- **CLI Tools** [cli]: Command-line interface

**Note**: CrewManager and future executors are all implementations of the `ExecutableTask` interface. Each executor handles different types of task execution (LLM, HTTP, etc.).

## Core Features

### Task Orchestration Specifications (Core)
- **TaskManager**: Task tree orchestration, dependency management, priority scheduling
- **Unified Execution Specification**: All task types unified through the `ExecutableTask` interface

### Task Execution Types

All task executors implement the `ExecutableTask` interface:

- **Custom Tasks** (core): Users implement `ExecutableTask` for their own task types
- **CrewManager** [crewai]: LLM-based task execution via CrewAI (built-in executor)
- **RestExecutor** [http]: HTTP/REST API calls with authentication and retry (built-in executor)
- **SshExecutor** [ssh]: Remote command execution via SSH (built-in executor)
- **DockerExecutor** [docker]: Containerized command execution (built-in executor)
- **GrpcExecutor** [grpc]: gRPC service calls (built-in executor)
- **WebSocketExecutor**: Bidirectional WebSocket communication (built-in executor)
- **ApFlowApiExecutor**: Inter-instance API calls for distributed execution (built-in executor)
- **McpExecutor**: Model Context Protocol executor for accessing external tools and data sources (built-in executor)
- **GenerateExecutor**: Generate task tree JSON arrays from natural language requirements using LLM (built-in executor)
- **LLMExecutor** [llm]: Direct LLM interaction via LiteLLM (supports 100+ providers)
- **BatchManager** [crewai]: Batch orchestration container (batches multiple crews)

### Supporting Features
- **Storage**: Task state persistence (DuckDB default, PostgreSQL optional)
- **Unified External API**: A2A Protocol Server (HTTP, SSE, WebSocket) [a2a]
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

# A2A Protocol Server (Agent-to-Agent communication protocol)
pip install aipartnerupflow[a2a]
# Run A2A server: python -m aipartnerupflow.api.main
# Or: aipartnerupflow-server (CLI command)

# CLI tools
pip install aipartnerupflow[cli]
# Run CLI: aipartnerupflow or apflow

# PostgreSQL storage
pip install aipartnerupflow[postgres]

# SSH executor (remote command execution)
pip install aipartnerupflow[ssh]

# Docker executor (containerized execution)
pip install aipartnerupflow[docker]

# gRPC executor (gRPC service calls)
pip install aipartnerupflow[grpc]

# LLM support (LiteLLM, supports 100+ providers)
pip install aipartnerupflow[llm]

# Everything (includes all extras)
pip install aipartnerupflow[all]
```

## 🚀 Quick Start

Get started with aipartnerupflow in minutes!

### Installation

```bash
# Minimal installation (core only)
pip install aipartnerupflow

# With all features
pip install aipartnerupflow[all]
```

### As a Library (Pure Core)

**Using Task Orchestration Specifications:**

```python
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

# Create database session and task manager (core)
db = create_session()  # or: db = get_default_session()
task_manager = TaskManager(db)

# Create task tree (task orchestration)
# Use task_repository to create tasks
root_task = await task_manager.task_repository.create_task(
    name="root_task",
    user_id="user_123",
    priority=2
)

child_task = await task_manager.task_repository.create_task(
    name="custom_task",  # Task name corresponds to specific executor
    user_id="user_123",
    parent_id=root_task.id,
    dependencies=[],  # Dependency relationships
    inputs={"url": "https://example.com"}
)

# Build task tree and execute (task orchestration core)
task_tree = TaskTreeNode(root_task)
task_tree.add_child(TaskTreeNode(child_task))
result = await task_manager.distribute_task_tree(task_tree)
```

**Creating Custom Tasks (Traditional External Service Calls):**

```python
from aipartnerupflow import ExecutableTask
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
from aipartnerupflow.extensions.crewai import CrewManager

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
from aipartnerupflow.extensions.crewai import BatchManager, CrewManager

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
# Run tasks (standard mode - recommended)
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "executor_id"}, "inputs": {"key": "value"}}]'

# Or use the shorthand
apflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "executor_id"}, "inputs": {"key": "value"}}]'

# Or legacy mode (executor ID + inputs)
apflow run flow executor_id --inputs '{"key": "value"}'

# Start API server
apflow serve --port 8000

# Start daemon mode
apflow daemon start

# Stop daemon mode
apflow daemon stop
```

### A2A Protocol Server

The `[a2a]` extra provides an **A2A (Agent-to-Agent) Protocol** server built on Starlette/FastAPI.

```python
from aipartnerupflow.api import create_app

# Create A2A protocol server app
app = create_app()

# Run with: uvicorn app:app --port 8000
# Or use the entry point: aipartnerupflow-server
```

**Note**: The current `[a2a]` extra focuses on A2A protocol support. Future versions may
include additional FastAPI REST API endpoints for direct HTTP access without the A2A protocol.

## Architecture Design

```
┌─────────────────────────────────────────────────────────────┐
│              Unified External API Interface Layer            │
│  - A2A Protocol Server (HTTP/SSE/WebSocket) [a2a]          │
│  - CLI Tools [cli]                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│        Task Orchestration Specification Layer (CORE)         │
│        - TaskManager: Task tree orchestration, dependency  │
│          management, priority scheduling                     │
│        - ExecutableTask: Unified task interface             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Task Execution Layer                      │
│  - Custom Tasks [core]: ExecutableTask implementations      │
│    • Traditional external service calls (API, DB, etc.)     │
│    • Automated task services (scheduled tasks, workflows)  │
│  - CrewManager [crewai]: CrewAI (LLM) task execution        │
│  - BatchManager [crewai]: Batch task orchestration           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Supporting Features Layer                │
│  - Storage: Task state persistence (DuckDB/PostgreSQL)     │
│  - Streaming: Real-time progress updates                    │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

See [docs/architecture/DIRECTORY_STRUCTURE.md](docs/architecture/DIRECTORY_STRUCTURE.md) for detailed directory structure and module descriptions.

**Installation Strategy**:
- `pip install aipartnerupflow`: Core library only (execution, base, storage, utils) - **NO CrewAI**
- `pip install aipartnerupflow[crewai]`: Core + CrewAI support (includes BatchManager)
- `pip install aipartnerupflow[a2a]`: Core + A2A Protocol Server
- `pip install aipartnerupflow[cli]`: Core + CLI tools
- `pip install aipartnerupflow[all]`: Full installation (all features)

**Note**: For examples and learning templates, see the test cases in `tests/integration/` and `tests/extensions/`.

## 📚 Documentation

**Quick Links:**
- **[📖 Full Documentation](docs/index.md)** - Complete documentation index
- **[🚀 Quick Start](docs/getting-started/quick-start.md)** - Get running in 10 minutes
- **[📘 Tutorials](docs/tutorials/)** - Step-by-step tutorials
- **[📝 Guides](docs/guides/)** - Comprehensive guides
- **[💡 Examples](docs/examples/)** - Practical examples
- **[🔧 API Reference](docs/api/)** - Complete API documentation

**For New Users:**
- Start with [Getting Started](docs/getting-started/index.md)
- Follow the [Quick Start Guide](docs/getting-started/quick-start.md)
- Try the [First Steps Tutorial](docs/tutorials/tutorial-01-first-steps.md)

**For Developers:**
- [Task Orchestration Guide](docs/guides/task-orchestration.md)
- [Custom Tasks Guide](docs/guides/custom-tasks.md)
- [Best Practices](docs/guides/best-practices.md)
- [API Reference](docs/api/python.md)

**For Contributors:**
- [Development Setup](docs/development/setup.md)
- [Contributing Guide](docs/development/contributing.md)
- [Architecture Overview](docs/architecture/overview.md)

Full documentation is also available at [flow-docs.aipartnerup.com](https://flow-docs.aipartnerup.com).

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](docs/development/contributing.md) for setup instructions and contribution guidelines.

## 📄 License

Apache-2.0

## 🔗 Links

- **Documentation**: [docs/index.md](docs/index.md) - Complete documentation
- **Website**: [aipartnerup.com](https://aipartnerup.com)
- **GitHub**: [aipartnerup/aipartnerupflow](https://github.com/aipartnerup/aipartnerupflow)
- **PyPI**: [aipartnerupflow](https://pypi.org/project/aipartnerupflow/)
- **Issues**: [GitHub Issues](https://github.com/aipartnerup/aipartnerupflow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/aipartnerup/aipartnerupflow/discussions)
