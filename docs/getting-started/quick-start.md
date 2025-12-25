# Quick Start Guide

Get started with aipartnerupflow in 10 minutes. This guide will walk you through creating and executing your first task.

## Prerequisites

- Python 3.10 or higher (3.12+ recommended)
- Basic command-line knowledge (for CLI usage)
- Basic Python knowledge (for creating custom executors)

## Step 0: Installation

### Minimal Installation (Core Only)

```bash
pip install aipartnerupflow
```

This installs the core orchestration framework with no optional dependencies.

**What you get:**
- Task orchestration engine (TaskManager)
- Built-in executors (system_info_executor, command_executor, llm_executor)
- Storage (DuckDB - no setup needed!)

### Full Installation (All Features)

```bash
pip install aipartnerupflow[all]
```

This includes everything:
- Core orchestration framework
- CrewAI support for LLM tasks
- A2A Protocol Server
- CLI tools
- PostgreSQL storage support

**For this tutorial:** 
- **Step 1 (CLI)**: Minimal installation is enough!
- **Step 2 (API)**: Install with `[cli]` or `[all]` to get CLI tools for starting the API server
- **Step 5 (Custom Executors)**: Minimal installation is enough for creating executors

## Step 1: Your First Task (Using CLI)

Let's start with the simplest possible example - using the CLI to execute a built-in executor. No Python code needed!

### What We'll Do

We'll execute a task that gets system information (CPU, memory, disk) using the built-in `system_info_executor` via the command line.

### Execute Your First Task

Open your terminal and run:

```bash
apflow run flow system_info_executor --inputs '{"resource": "cpu"}'
```

**Expected Output:**
```json
{
  "status": "completed",
  "progress": 1.0,
  "root_task_id": "abc-123-def-456",
  "task_count": 1,
  "result": {
    "system": "Darwin",
    "cores": 8,
    "cpu_count": 8,
    ...
  }
}
```

### Try Different Resources

You can get different system information by changing the `resource` parameter:

```bash
# Get memory information
apflow run flow system_info_executor --inputs '{"resource": "memory"}'

# Get disk information
apflow run flow system_info_executor --inputs '{"resource": "disk"}'

# Get all system resources
apflow run flow system_info_executor --inputs '{"resource": "all"}'
```

### What Just Happened?

1. **CLI parsed the command**: It identified the executor (`system_info_executor`) and inputs
2. **Task was created**: A task was automatically created in the database
3. **Executor was found**: The system automatically found the built-in `system_info_executor`
4. **Task executed**: The executor ran and collected CPU information
5. **Result returned**: The result was displayed in JSON format

**That's it!** You just executed your first task with aipartnerupflow! 🎉

### Understanding the Command

Let's break down the command:

```bash
apflow run flow system_info_executor --inputs '{"resource": "cpu"}'
```

- `apflow`: The CLI command (short for `aipartnerupflow`)
- `run flow`: Execute a task flow
- `system_info_executor`: The executor ID (built-in executor)
- `--inputs`: Task input parameters (JSON format)
- `{"resource": "cpu"}`: Input data - get CPU information

**Note**: This is the "legacy mode" for backward compatibility. For more complex scenarios, you can use the standard mode with task arrays (see Step 4).

## Step 2: Using the API Server

The API server provides an alternative way to execute tasks via HTTP. This is useful for remote access, integration with other systems, or when you prefer HTTP over CLI.

### Start the API Server

In one terminal, start the API server:

```bash
apflow serve start
```

The server will start on `http://localhost:8000` by default.

### Execute a Task via API

In another terminal (or use the same one), execute a task via HTTP:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [
        {
          "id": "task1",
          "name": "system_info_executor",
          "user_id": "user123",
          "schemas": {
            "method": "system_info_executor"
          },
          "inputs": {
            "resource": "cpu"
          }
        }
      ]
    },
    "id": "request-123"
  }'
```

**Expected Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "result": {
    "status": "completed",
    "progress": 1.0,
    "root_task_id": "abc-123-def-456",
    "task_count": 1,
    "result": {
      "system": "Darwin",
      "cores": 8,
      ...
    }
  }
}
```

### Understanding the API Request

The API uses the A2A Protocol (JSON-RPC 2.0 format):

- **method**: `tasks.execute` - Execute a task tree
- **params.tasks**: Array of task objects
- **params.tasks[].schemas.method**: Executor ID (must match executor `id`)
- **params.tasks[].inputs**: Task input parameters

### CLI vs API: When to Use Which?

**Use CLI when:**
- Local development and testing
- Quick one-off tasks
- Scripts and automation
- No need for remote access

**Use API when:**
- Remote access needed
- Integration with other systems
- Multi-user scenarios
- Production deployments
- A2A Protocol integration

**Both share the same database**, so you can:
- Execute via CLI, query via API
- Execute via API, query via CLI
- Mix and match as needed!

### Task Statistics
You can quickly get an overview of all tasks in the database:
```bash
apflow tasks count
```

## Step 3: Understanding Task Execution

Let's break down what happened in more detail:

### The Components

```
┌─────────────────────────────────────────────────┐
│              User Interface                     │
│  (CLI or API)                                   │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│            TaskExecutor                         │
│  - Creates tasks                                 │
│  - Manages execution                            │
│  - Tracks status                                │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│         Task (in database)                      │
│  - name: "system_info_executor"                 │
│  - inputs: {"resource": "cpu"}                   │
│  - status: pending → in_progress → completed    │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│      Executor (system_info_executor)            │
│  - Runs the actual code                         │
│  - Returns the result                           │
└─────────────────────────────────────────────────┘
```

### Key Concepts

- **Task**: A unit of work (what you want to do)
- **Executor**: The code that does the work (how it's done)
- **TaskExecutor**: Coordinates everything (the conductor)
- **CLI/API**: User interfaces to interact with the system
- **Task Tree**: Organizes tasks (even single tasks need a tree)

### Advanced: Direct TaskManager Usage

For advanced use cases, you can use `TaskManager` directly in Python code:

```python
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

db = create_session()
task_manager = TaskManager(db)
# ... create and execute tasks
```

**Note**: This is for advanced users. Most use cases work better with CLI or API.

## Step 4: Task Dependencies

Now let's create multiple tasks where one depends on another. This is where aipartnerupflow really shines!

### Example: Sequential Tasks via CLI

Create a file `tasks.json` with a task array:

```json
[
  {
    "id": "cpu_task",
    "name": "Get CPU Info",
    "user_id": "user123",
    "schemas": {
      "method": "system_info_executor"
    },
    "inputs": {
      "resource": "cpu"
    },
    "priority": 1,
    "status": "pending"
  },
  {
    "id": "memory_task",
    "name": "Get Memory Info",
    "user_id": "user123",
    "parent_id": "cpu_task",
    "schemas": {
      "method": "system_info_executor"
    },
    "inputs": {
      "resource": "memory"
    },
    "dependencies": [
      {
        "id": "cpu_task",
        "required": true
      }
    ],
    "priority": 2,
    "status": "pending"
  }
]
```

Execute via CLI:

```bash
apflow run flow --tasks-file tasks.json
```

**What happens:**
1. `cpu_task` executes first
2. System waits for `cpu_task` to complete
3. `memory_task` executes after `cpu_task` completes

### Example: Sequential Tasks via API

Start the API server (if not already running):

```bash
apflow serve start
```

Execute via API:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [
        {
          "id": "cpu_task",
          "name": "Get CPU Info",
          "user_id": "user123",
          "schemas": {"method": "system_info_executor"},
          "inputs": {"resource": "cpu"},
          "priority": 1,
          "status": "pending"
        },
        {
          "id": "memory_task",
          "name": "Get Memory Info",
          "user_id": "user123",
          "parent_id": "cpu_task",
          "schemas": {"method": "system_info_executor"},
          "inputs": {"resource": "memory"},
          "dependencies": [{"id": "cpu_task", "required": true}],
          "priority": 2,
          "status": "pending"
        }
      ]
    },
    "id": "request-123"
  }'
```

### Understanding Dependencies

**Key Point**: `dependencies` control execution order, not `parent_id`!

- **parent_id**: Organizational (like folders) - doesn't affect when tasks run
- **dependencies**: Execution control - determines when tasks run

In the example above:
- `memory_task` is a **child** of `cpu_task` (organization via `parent_id`)
- `memory_task` **depends on** `cpu_task` (execution order via `dependencies`)

### Try It Yourself

Create three tasks in sequence (CPU → Memory → Disk):

**tasks.json:**
```json
[
  {
    "id": "cpu_task",
    "name": "Get CPU Info",
    "user_id": "user123",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "cpu"},
    "status": "pending"
  },
  {
    "id": "memory_task",
    "name": "Get Memory Info",
    "user_id": "user123",
    "parent_id": "cpu_task",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "memory"},
    "dependencies": [{"id": "cpu_task", "required": true}],
    "status": "pending"
  },
  {
    "id": "disk_task",
    "name": "Get Disk Info",
    "user_id": "user123",
    "parent_id": "memory_task",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "disk"},
    "dependencies": [{"id": "memory_task", "required": true}],
    "status": "pending"
  }
]
```

Execute:
```bash
apflow run flow --tasks-file tasks.json
```

**Execution Order**: CPU → Memory → Disk (automatic!)

## Step 5: Creating Your Own Executor

Now let's create a custom executor. This is where you add your own business logic!

### Create the Executor

Create a file `my_executor.py`:

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class GreetingTask(BaseTask):
    """A simple task that creates personalized greetings"""
    
    id = "greeting_task"
    name = "Greeting Task"
    description = "Creates a personalized greeting message"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        name = inputs.get("name", "Guest")
        language = inputs.get("language", "en")
        
        greetings = {
            "en": f"Hello, {name}!",
            "es": f"¡Hola, {name}!",
            "fr": f"Bonjour, {name}!"
        }
        
        return {
            "greeting": greetings.get(language, greetings["en"]),
            "name": name,
            "language": language
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameters"""
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the person to greet"
                },
                "language": {
                    "type": "string",
                    "enum": ["en", "es", "fr", "zh"],
                    "description": "Language for the greeting",
                    "default": "en"
                }
            },
            "required": ["name"]
        }
```

### Use Your Custom Executor via CLI

To use your custom executor, you need to import it first. Create a simple Python script that imports the executor and then uses CLI:

**Option A: Import in a wrapper script**

Create `run_greeting.py`:

```python
# Import to register the executor
from my_executor import GreetingTask

# Now you can use CLI
import subprocess
import sys

# Run via CLI
subprocess.run([
    "apflow", "run", "flow", "greeting_task",
    "--inputs", '{"name": "Alice", "language": "en"}'
])
```

Run it:
```bash
python run_greeting.py
```

**Option B: Direct CLI (after importing in Python session)**

If you're in a Python environment where the executor is already imported:

```bash
apflow run flow greeting_task --inputs '{"name": "Alice", "language": "en"}'
```

**Option C: Use task array format**

Create `greeting_task.json`:

```json
[
  {
    "id": "greeting1",
    "name": "Greet Alice",
    "user_id": "user123",
    "schemas": {
      "method": "greeting_task"
    },
    "inputs": {
            "name": "Alice",
            "language": "en"
    },
    "status": "pending"
  }
]
```

Run:
```bash
# Make sure executor is imported first (in Python)
python -c "from my_executor import GreetingTask"

# Then use CLI
apflow run flow --tasks-file greeting_task.json
```

### Use Your Custom Executor via API

Start the API server (make sure executor is imported):

```bash
# In a Python script that imports your executor
python -c "from my_executor import GreetingTask; import aipartnerupflow.api.main; aipartnerupflow.api.main.main()"
```

Or create `api_server.py`:

```python
from my_executor import GreetingTask  # Import to register
from aipartnerupflow.api.main import main

if __name__ == "__main__":
    main()
```

Then execute via API:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [
        {
          "id": "greeting1",
          "name": "Greet Alice",
          "user_id": "user123",
          "schemas": {"method": "greeting_task"},
          "inputs": {"name": "Alice", "language": "en"},
          "status": "pending"
        }
      ]
    },
    "id": "request-123"
  }'
```

### Understanding Custom Executors

**What you need to implement:**

1. **id**: Unique identifier (used in `schemas.method` when creating tasks)
2. **name**: Display name
3. **description**: What the task does
4. **execute()**: The actual work (async function)
5. **get_input_schema()**: Input parameter definition (JSON Schema)

**The `@executor_register()` decorator** automatically registers your executor when imported!

**Important**: The executor must be imported before it can be used. This happens automatically when:
- You import it in your Python script
- You import it before starting the API server
- The extension system loads it (for built-in executors)

## Step 6: Next Steps

Congratulations! You've learned the basics. Here's what to explore next:

### Immediate Next Steps

1. **[Core Concepts](concepts.md)** - Deep dive into the concepts you just used
2. **[First Steps Tutorial](tutorials/tutorial-01-first-steps.md)** - More detailed beginner tutorial
3. **[Basic Examples](../examples/basic_task.md)** - Copy-paste ready examples

### Learn More

- **[Task Orchestration Guide](../guides/task-orchestration.md)** - Master task trees and dependencies
- **[Custom Tasks Guide](../guides/custom-tasks.md)** - Create more complex executors
- **[Best Practices](../guides/best-practices.md)** - Learn from the experts

### Advanced Topics

- **[Task Trees Tutorial](tutorials/tutorial-02-task-trees.md)** - Build complex workflows
- **[Dependencies Tutorial](tutorials/tutorial-03-dependencies.md)** - Master dependency management

## Common Patterns

### Pattern 1: Simple Task (No Dependencies)

**Via CLI (Legacy Mode):**
```bash
apflow run flow executor_id --inputs '{"key": "value"}'
```

**Via CLI (Standard Mode - Task Array):**
```bash
apflow run flow --tasks '[{"id": "task1", "name": "Task 1", "user_id": "user123", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}, "status": "pending"}]'
```

**Via API:**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [{
        "id": "task1",
        "name": "Task 1",
        "user_id": "user123",
        "schemas": {"method": "system_info_executor"},
        "inputs": {"resource": "cpu"},
        "status": "pending"
      }]
    },
    "id": "request-123"
  }'
```

### Pattern 2: Sequential Tasks (With Dependencies)

**Via CLI (Task Array File):**

Create `tasks.json`:
```json
[
  {
    "id": "task1",
    "name": "Get System Info",
    "user_id": "user123",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "cpu"},
    "status": "pending"
  },
  {
    "id": "task2",
    "name": "Process Data",
    "user_id": "user123",
    "parent_id": "task1",
    "schemas": {"method": "command_executor"},
    "inputs": {"command": "echo 'Processing system info'"},
    "dependencies": [{"id": "task1", "required": true}],
    "status": "pending"
  }
]
```

Execute:
```bash
apflow run flow --tasks-file tasks.json
```

**Via API:**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [
        {
          "id": "task1",
          "name": "Get System Info",
          "user_id": "user123",
          "schemas": {"method": "system_info_executor"},
          "inputs": {"resource": "cpu"},
          "status": "pending"
        },
        {
          "id": "task2",
          "name": "Process Data",
          "user_id": "user123",
          "parent_id": "task1",
          "schemas": {"method": "command_executor"},
          "inputs": {"command": "echo 'Processing system info'"},
          "dependencies": [{"id": "task1", "required": true}],
          "status": "pending"
        }
      ]
    },
    "id": "request-123"
  }'
```

**Execution Order**: Task2 waits for Task1 automatically!

### Pattern 3: Parallel Tasks (No Dependencies)

**Via CLI (Task Array File):**

Create `parallel_tasks.json`:
```json
[
  {
    "id": "task1",
    "name": "Get CPU Info",
    "user_id": "user123",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "cpu"},
    "status": "pending"
  },
  {
    "id": "task2",
    "name": "Get Memory Info",
    "user_id": "user123",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "memory"},
    "status": "pending"
  }
]
```

Execute:
```bash
apflow run flow --tasks-file parallel_tasks.json
```

**Note**: Both tasks run in parallel since there are no dependencies between them!

## Troubleshooting

### Problem: Task Executor Not Found

**Error:** `Task executor not found: executor_id`

**Solutions:**

1. **For built-in executors**: Built-in executors are automatically available. If you get this error:
   - Make sure you've installed the required extension: `pip install aipartnerupflow[extension_name]`
   - Check that the executor ID is correct (e.g., `system_info_executor`, not `system_info`)

2. **For custom executors**: Make sure you:
   - Used `@executor_register()` decorator
   - Imported the executor class before using it
   - The `schemas.method` field matches the executor `id`
   - For CLI: Import executor in a Python script before running CLI command
   - For API: Import executor before starting the API server

**Example (Custom Executor):**
```python
# my_script.py
from my_executor import GreetingTask  # Import to register

# Now you can use CLI or API
```

### Problem: Task Stays in "pending" Status

**Possible causes:**
- Dependencies not satisfied (check if dependency tasks are completed)
- Executor not found (see above)
- Task not executed (make sure you called the CLI command or API endpoint)

**Solution - Check Task Status:**

**Via CLI:**
```bash
# Check status of a specific task
apflow tasks status <task_id>

# List all running tasks
apflow tasks list

# Get full task details
apflow tasks get <task_id>
```

**Via API:**
```bash
# Check task status
curl http://localhost:8000/api/tasks/<task_id>/status

# Get task details
curl http://localhost:8000/api/tasks/<task_id>
```

**Check for errors:**
- Look at the `error` field in the task result
- Check CLI output or API response for error messages
- Review task logs if available

### Problem: CLI Command Not Found

**Error:** `command not found: apflow` or `command not found: aipartnerupflow`

**Solution:**
```bash
# Install with CLI support
pip install aipartnerupflow[cli]

# Or install everything
pip install aipartnerupflow[all]

# Verify installation
apflow --version
# Or
aipartnerupflow --version
```

### Problem: API Server Won't Start

**Error:** Port already in use or server won't start

**Solutions:**
```bash
# Use a different port
apflow serve start --port 8080
```

# Check if port is in use
lsof -i :8000

# Kill process using the port (if needed)
kill -9 <PID>
```

### Problem: Database Error

**Error:** Database connection issues

**Solution:**
- **DuckDB (default)**: No setup needed! It just works. Database file is created automatically at `~/.aipartnerup/data/aipartnerupflow.duckdb`
- **PostgreSQL**: Set environment variable:
  ```bash
  export DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"
  ```
- **Check database connection:**
  ```bash
  # For DuckDB, check if file exists
  ls ~/.aipartnerup/data/aipartnerupflow.duckdb
  
  # For PostgreSQL, test connection
  psql $DATABASE_URL -c "SELECT 1;"
  ```

### Problem: Custom Executor Not Found When Using CLI

**Error:** Custom executor not registered when running CLI command

**Solution:**
Custom executors must be imported before they can be used. For CLI usage:

**Option 1: Import in a wrapper script**
```python
# run_my_task.py
from my_executor import MyExecutor  # Import to register
import subprocess

subprocess.run(["apflow", "run", "flow", "my_executor", "--inputs", '{"key": "value"}'])
```

**Option 2: Use Python to import, then CLI**
```bash
# Import executor first
python -c "from my_executor import MyExecutor"

# Then use CLI (in same shell session)
apflow run flow my_executor --inputs '{"key": "value"}'
```

**Option 3: Use task array with Python wrapper**
Create a Python script that imports the executor and then calls the CLI with task array format.

### Problem: Import Error

**Error:** `ModuleNotFoundError: No module named 'aipartnerupflow'`

**Solution:**
```bash
pip install aipartnerupflow

# Or with specific features
pip install aipartnerupflow[cli]
pip install aipartnerupflow[all]
```

## Try It Yourself

### Exercise 1: Multiple System Checks

Create tasks to check CPU, memory, and disk using CLI or API, then view the aggregated results.

**Hint:** Use the `system_info_executor` with different `resource` values, or create a task array with multiple tasks.

### Exercise 2: Custom Greeting in Multiple Languages

Use the `GreetingTask` example to create greetings in different languages via CLI or API, then combine them.

**Hint:** Create multiple tasks with different `language` inputs, or create a task array with sequential dependencies.

### Exercise 3: Sequential Processing

Create a pipeline: fetch data → process data → save results (each step depends on the previous).

**Hint:** Use task dependencies to ensure proper execution order. You can use built-in executors or create custom ones for each step.

## Getting Help

- **Stuck?** Check the [FAQ](../guides/faq.md)
- **Need examples?** See [Basic Examples](../examples/basic_task.md)
- **Want to understand concepts?** Read [Core Concepts](concepts.md)
- **Found a bug?** [Report it on GitHub](https://github.com/aipartnerup/aipartnerupflow/issues)
- **Have questions?** [Ask on Discussions](https://github.com/aipartnerup/aipartnerupflow/discussions)

---

**Ready for more?** → [Learn Core Concepts →](concepts.md) or [Try the First Steps Tutorial →](tutorials/tutorial-01-first-steps.md)
