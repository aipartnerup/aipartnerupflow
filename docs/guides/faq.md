# Frequently Asked Questions (FAQ)

Common questions and answers about aipartnerupflow.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Tasks and Executors](#tasks-and-executors)
3. [Task Orchestration](#task-orchestration)
4. [Troubleshooting](#troubleshooting)
5. [Advanced Topics](#advanced-topics)

## Getting Started

### Q: How do I install aipartnerupflow?

**A:** Use pip:

```bash
# Minimal installation (core only)
pip install aipartnerupflow

# Full installation (all features)
pip install aipartnerupflow[all]

# Specific features
pip install aipartnerupflow[crewai]  # LLM support
pip install aipartnerupflow[cli]      # CLI tools
pip install aipartnerupflow[a2a]      # A2A Protocol server
```

### Q: Do I need to set up a database?

**A:** No! DuckDB is used by default and requires no setup. It just works out of the box.

If you want to use PostgreSQL:

```bash
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"
```

### Q: What Python version do I need?

**A:** Python 3.10 or higher (3.12+ recommended).

### Q: Where should I start?

**A:** 
1. **[Quick Start Guide](../getting-started/quick-start.md)** - Get running in 10 minutes
2. **[First Steps Tutorial](../getting-started/tutorials/tutorial-01-first-steps.md)** - Complete beginner tutorial
3. **[Core Concepts](../getting-started/concepts.md)** - Understand the fundamentals

## Tasks and Executors

### Q: What's the difference between a Task and an Executor?

**A:**
- **Executor**: The code that does the work (reusable template)
- **Task**: An instance of work to be done (specific execution)

**Analogy:**
- **Executor** = A recipe (reusable)
- **Task** = A specific meal made from the recipe (one-time)

### Q: How do I create a custom executor?

**A:** Use `BaseTask` with `@executor_register()`:

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class MyExecutor(BaseTask):
    id = "my_executor"
    name = "My Executor"
    description = "Does something"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "result": "..."}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
```

See the **[Custom Tasks Guide](custom-tasks.md)** for details.

### Q: How do I use my custom executor?

**A:** 
1. Import it (this registers it automatically):
```python
from my_module import MyExecutor
```

2. Use it when creating tasks:
```python
task = await task_manager.task_repository.create_task(
    name="my_executor",  # Must match executor id
    user_id="user123",
    inputs={...}
)
```

### Q: My executor isn't being found. What's wrong?

**A:** Common issues:

1. **Not imported**: Make sure you import the executor class:
```python
from my_module import MyExecutor  # This registers it
```

2. **Wrong name**: The `name` field must match the executor `id`:
```python
# Executor
id = "my_executor"

# Task
name="my_executor"  # Must match!
```

3. **Not registered**: Make sure you use `@executor_register()`:
```python
@executor_register()  # Don't forget this!
class MyExecutor(BaseTask):
    ...
```

### Q: Can I use built-in executors?

**A:** Yes! Built-in executors are automatically available:

- `system_info_executor` - Get system information (CPU, memory, disk)
- `command_executor` - Execute shell commands (requires security config)
- `aggregate_results_executor` - Aggregate results from multiple tasks

Just use them by name:
```python
task = await task_manager.task_repository.create_task(
    name="system_info_executor",
    user_id="user123",
    inputs={"resource": "cpu"}
)
```

## Task Orchestration

### Q: What's the difference between `parent_id` and `dependencies`?

**A:** This is a critical distinction!

- **`parent_id`**: Organizational only (like folders) - does NOT affect execution order
- **`dependencies`**: Controls execution order - determines when tasks run

**Example:**
```python
# Task B is a child of Task A (organizational)
# But Task B depends on Task C (execution order)
task_a = create_task(name="task_a")
task_c = create_task(name="task_c")
task_b = create_task(
    name="task_b",
    parent_id=task_a.id,  # Organizational
    dependencies=[{"id": task_c.id, "required": True}]  # Execution order
)
# Execution: C runs first, then B (regardless of parent-child)
```

See **[Task Orchestration Guide](task-orchestration.md)** for details.

### Q: How do I make tasks run in parallel?

**A:** Don't add dependencies between them:

```python
# Task 1 (no dependencies)
task1 = create_task(name="task1", ...)

# Task 2 (no dependencies on task1)
task2 = create_task(name="task2", ...)

# Both run in parallel!
```

### Q: How do I make tasks run sequentially?

**A:** Add dependencies:

```python
# Task 1
task1 = create_task(name="task1", ...)

# Task 2 depends on Task 1
task2 = create_task(
    name="task2",
    dependencies=[{"id": task1.id, "required": True}],
    ...
)

# Execution order: Task 1 → Task 2
```

### Q: How do priorities work?

**A:** Lower numbers = higher priority = execute first:

```
0 = Urgent (highest)
1 = High
2 = Normal (default)
3 = Low (lowest)
```

**Important**: Dependencies take precedence over priorities!

### Q: My task is stuck in "pending" status. Why?

**A:** Common causes:

1. **Dependencies not satisfied**: Check if dependency tasks are completed
2. **Executor not found**: Verify task name matches executor ID
3. **Task not executed**: Make sure you called `distribute_task_tree()`
4. **Parent task failed**: Check parent task status

**Debug:**
```python
task = await task_manager.task_repository.get_task_by_id(task_id)
print(f"Status: {task.status}")
print(f"Error: {task.error}")
print(f"Dependencies: {task.dependencies}")
```

## Troubleshooting

### Q: Task executor not found error

**Error:** `Task executor not found: executor_id`

**Solutions:**
1. **For built-in executors**: Make sure you've imported the extension:
```python
import aipartnerupflow.extensions.stdio  # Registers built-in executors
```

2. **For custom executors**: 
   - Make sure you used `@executor_register()`
   - Import the executor class in your main script
   - Verify the `name` field matches the executor `id`

### Q: Database connection error

**Error:** Database connection issues

**Solutions:**
- **DuckDB (default)**: No setup needed! It just works.
- **PostgreSQL**: Set environment variable:
```bash
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"
```

### Q: Import error

**Error:** `ModuleNotFoundError: No module named 'aipartnerupflow'`

**Solution:**
```bash
pip install aipartnerupflow
```

### Q: Task stays in "in_progress" forever

**Problem:** Task never completes

**Solutions:**
1. Check if executor is hanging (infinite loop, waiting for resource)
2. Verify executor supports cancellation
3. Check for deadlocks in dependencies
4. Review executor implementation

**Debug:**
```python
# Check task status
task = await task_manager.task_repository.get_task_by_id(task_id)
print(f"Status: {task.status}")
print(f"Error: {task.error}")

# Try cancelling
if task.status == "in_progress":
    await task_manager.cancel_task(task_id, "Manual cancellation")
```

### Q: Dependency not satisfied

**Problem:** Task waiting for dependency that never completes

**Solutions:**
1. Verify dependency task ID is correct
2. Check if dependency task failed
3. Ensure dependency task is in the same tree
4. Check dependency task status

**Debug:**
```python
# Check dependency status
dependency = await task_manager.task_repository.get_task_by_id(dependency_id)
print(f"Dependency status: {dependency.status}")
print(f"Dependency error: {dependency.error}")
```

### Q: Priority not working

**Problem:** Tasks not executing in expected order

**Solutions:**
1. Verify priority values (lower = higher priority)
2. Check if dependencies override priority (they do!)
3. Ensure tasks are at the same level in the tree
4. Remember: dependencies take precedence!

## Advanced Topics

### Q: How do I use CrewAI (LLM tasks)?

**A:** 

1. Install:
```bash
pip install aipartnerupflow[crewai]
```

2. Create a crew:
```python
from aipartnerupflow.extensions.crewai import CrewManager
from aipartnerupflow.core.extensions import get_registry

crew = CrewManager(
    id="my_crew",
    name="My Crew",
    agents=[{"role": "Analyst", "goal": "Analyze data"}],
    tasks=[{"description": "Analyze: {text}", "agent": "Analyst"}]
)

get_registry().register(crew)
```

3. Use it:
```python
task = await task_manager.task_repository.create_task(
    name="my_crew",
    user_id="user123",
    inputs={"text": "Analyze this data"}
)
```

**Note**: Requires LLM API key (OpenAI, Anthropic, etc.)

### Q: How do I set LLM API keys?

**A:** 

**Option 1: Environment variable**
```bash
export OPENAI_API_KEY="sk-your-key"
export ANTHROPIC_API_KEY="sk-ant-your-key"
```

**Option 2: Request header** (for API server)
```
X-LLM-API-KEY: openai:sk-your-key
```

**Option 3: Configuration**
```python
# In your code
import os
os.environ["OPENAI_API_KEY"] = "sk-your-key"
```

### Q: How do I handle task failures?

**A:** 

1. **Check task status:**
```python
task = await task_manager.task_repository.get_task_by_id(task_id)
if task.status == "failed":
    print(f"Error: {task.error}")
```

2. **Handle in executor:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = perform_operation(inputs)
        return {"status": "completed", "result": result}
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__
        }
```

3. **Use optional dependencies for fallback:**
```python
# Primary task
primary = create_task(name="primary_task", ...)

# Fallback task (runs even if primary fails)
fallback = create_task(
    name="fallback_task",
    dependencies=[{"id": primary.id, "required": False}],  # Optional
    ...
)
```

### Q: Can I cancel a running task?

**A:** Yes, if the executor supports cancellation:

```python
result = await task_manager.cancel_task(
    task_id="task_123",
    error_message="User requested cancellation"
)
```

**Note**: Not all executors support cancellation. Check `executor.cancelable` property.

### Q: How do I get real-time updates?

**A:** Use streaming execution:

```python
# Execute with streaming
await task_manager.distribute_task_tree_with_streaming(
    task_tree,
    use_callback=True
)
```

Or use the API server with SSE (Server-Sent Events).

### Q: How do I use hooks?

**A:** 

**Pre-execution hook:**
```python
from aipartnerupflow import register_pre_hook

@register_pre_hook
async def validate_inputs(task):
    """Validate inputs before execution"""
    if task.inputs and "url" in task.inputs:
        url = task.inputs["url"]
        if not url.startswith(("http://", "https://")):
            task.inputs["url"] = f"https://{url}"
```

**Post-execution hook:**
```python
from aipartnerupflow import register_post_hook

@register_post_hook
async def log_results(task, inputs, result):
    """Log results after execution"""
    print(f"Task {task.id} completed:")
    print(f"  Result: {result}")
```

### Q: How do I extend TaskModel?

**A:** 

```python
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow import set_task_model_class
from sqlalchemy import Column, String

class CustomTaskModel(TaskModel):
    """Custom TaskModel with additional fields"""
    __tablename__ = "apflow_tasks"
    
    project_id = Column(String(255), nullable=True, index=True)

# Set before creating tasks
set_task_model_class(CustomTaskModel)

# Now tasks can have project_id
task = await task_manager.task_repository.create_task(
    name="my_task",
    user_id="user123",
    project_id="proj-123",  # Custom field
    inputs={...}
)
```

## Still Have Questions?

- **[Documentation Index](../index.md)** - Browse all documentation
- **[Quick Start Guide](../getting-started/quick-start.md)** - Get started quickly
- **[Examples](../examples/basic_task.md)** - See practical examples
- **[GitHub Issues](https://github.com/aipartnerup/aipartnerupflow/issues)** - Report bugs
- **[GitHub Discussions](https://github.com/aipartnerup/aipartnerupflow/discussions)** - Ask questions

---

**Found an issue?** [Report it on GitHub](https://github.com/aipartnerup/aipartnerupflow/issues)

