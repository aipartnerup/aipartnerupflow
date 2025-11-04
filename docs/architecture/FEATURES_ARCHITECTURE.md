# Features Architecture Design

## Task Execution Implementations

The core provides `ExecutableTask` interface, and `features/` contains various implementations of task executors.

### Current Implementations

#### 1. CrewAI Executor (`features/crewai/`)

**Purpose**: LLM-based task execution using CrewAI agents

```
features/crewai/
├── __init__.py
├── crew_manager.py     # CrewManager - ExecutableTask implementation via CrewAI
├── batch_manager.py    # BatchManager - batches multiple crews together
└── types.py            # CrewManagerState, BatchState
```

**Installation**: `pip install aipartnerupflow[crewai]`

**Use Case**: Tasks that require LLM reasoning, agent collaboration, or AI-powered analysis.

### Future Implementations

#### 2. HTTP Executor (`features/http_executor/`)

**Purpose**: Remote API call task execution (HTTP/HTTPS)

```
features/http_executor/
├── __init__.py
├── http_executor.py    # HTTPExecutor - ExecutableTask implementation for HTTP calls
├── client.py           # HTTP client with retry, timeout, auth support
└── types.py            # HTTPExecutorState, RequestConfig, ResponseConfig
```

**Installation**: `pip install aipartnerupflow[http]`

**Features**:
- HTTP/HTTPS request execution
- Retry logic with exponential backoff
- Authentication support (API keys, OAuth, etc.)
- Request/response validation
- Timeout handling

**Use Case**: Tasks that need to call external REST APIs, webhooks, or remote services.

**Example**:
```python
from aipartnerupflow.features.http_executor import HTTPExecutor

executor = HTTPExecutor(
    endpoint="https://api.example.com/analyze",
    method="POST",
    headers={"Authorization": "Bearer token"},
    timeout=30,
    retry_count=3
)
result = await executor.execute(inputs={"data": "..."})
```

#### 3. Other Potential Executors

- **`features/shell_executor/`**: Execute shell commands/scripts
- **`features/database_executor/`**: Execute database queries
- **`features/queue_executor/`**: Publish/subscribe to message queues
- **`features/workflow_executor/`**: Execute workflow definitions (Airflow, Prefect, etc.)

## Features Organization Principle

**Rule**: Each executor in `features/` is a complete, independent task execution implementation.

- **Naming**: `{executor_type}_executor/` or `{tool_name}/` (e.g., `crewai/`, `http_executor/`)
- **Structure**: Each feature should contain:
  - Executor class implementing `ExecutableTask`
  - Supporting utilities
  - Type definitions
  - Optional: Manager classes for batch/composite operations

## Extensions (`ext/`) - Purpose Clarification

**Purpose**: Predefined example implementations for **learning and quick start**, NOT production-ready implementations.

### Structure

```
examples/
├── crews/              # Example CrewManager implementations
│   ├── example_crew.py           # Simple example
│   ├── data_analysis_crew.py     # Example: data analysis
│   └── content_generation_crew.py # Example: content generation
│
├── batches/            # Example BatchManager implementations
│   ├── example_batch.py          # Simple example
│   └── multi_stage_analysis.py   # Example: multi-stage analysis
│
└── tasks/              # Example custom ExecutableTask implementations
    ├── example_task.py            # Simple custom task example
    ├── api_call_example.py        # Example: API call task
    └── data_processing_example.py # Example: data processing task
```

### Use Cases

1. **Learning**: Users learn how to implement ExecutableTask, CrewManager, BatchManager
2. **Quick Start**: Copy and modify examples to create custom implementations
3. **Testing**: Use examples in tests and demos
4. **Documentation**: Examples serve as living documentation

### NOT For

- Production-ready implementations (users should create their own)
- External library dependencies (keep ext simple)
- Complex business logic (keep examples simple and clear)

## Comparison: features/ vs examples/

| Aspect | features/ | examples/ |
|--------|-----------|-----------|
| **Purpose** | Production-ready task executors | Example/template implementations |
| **Dependencies** | Can have heavy dependencies | Lightweight, minimal dependencies |
| **Quality** | Production-grade, fully tested | Simple examples for learning |
| **Installation** | Optional extras ([crewai], [http], etc.) | [examples] extra |
| **Usage** | Direct use in production | Copy and customize |
| **Examples** | CrewManager, HTTPExecutor | Example crews, example batches |

