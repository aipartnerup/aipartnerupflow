# CLI Design and Development Guide

## Architecture Overview

The CLI is designed to provide the same functionality as the API, but through command-line interface. It uses the same execution path as the API to ensure consistency.

### Design Principles

1. **Unified Execution Path**: CLI and API both use `TaskExecutor` to execute tasks
2. **Task Array Format**: Tasks are represented as JSON arrays (same format as API)
3. **No Direct Executor Calls**: CLI never directly calls executors (BatchManager, CrewManager, etc.)
4. **Database as Source of Truth**: Task status and results come from database
5. **TaskTracker for Runtime State**: In-memory tracking for running tasks

## CLI Structure

```
aipartnerupflow/
├── cli/
│   ├── main.py              # Main entry point, registers all commands
│   ├── commands/
│   │   ├── run.py           # Execute tasks (creates task array → TaskExecutor)
│   │   ├── tasks.py         # Query and manage tasks (list, status, count, cancel)
│   │   ├── serve.py         # Start API server
│   │   └── daemon.py        # Manage daemon service
```

## Command Design

### 1. Execute Tasks (`run flow`)

**Purpose**: Execute tasks through TaskExecutor. Supports both single executor execution (legacy) and task array execution (standard).

**Flow**:
```
CLI → Parse tasks (JSON array) → Group by root → TaskExecutor.execute_tasks() (per group) → TaskManager → ExtensionRegistry → Executor
```

**Two Modes**:

1. **Legacy Mode** (backward compatible):
   ```bash
   # Execute single executor
   aipartnerupflow run flow example_executor --inputs '{"data": "test"}'
   ```

2. **Standard Mode** (recommended):
   ```bash
   # Execute task array (single task tree)
   aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "executor1"}, "inputs": {"key": "value"}}]'
   
   # Execute multiple unrelated tasks (multiple root tasks)
   aipartnerupflow run flow --tasks '[{"id": "task1", ...}, {"id": "task2", ...}]'
   
   # With tasks file
   aipartnerupflow run flow --tasks-file tasks.json --output result.json
   ```

**Implementation**:
- **Standard mode**: Accepts tasks JSON array (list of task objects)
- **Legacy mode**: Accepts `executor_id` + `inputs`, creates single task automatically
- **Multiple unrelated tasks**: CLI groups tasks by root (parent_id=None), executes each group separately
  - TaskExecutor only supports single root task tree
  - CLI handles multiple unrelated tasks by grouping and executing separately
- Calls `TaskExecutor.execute_tasks()` for each task group (same as API)
- Waits for execution to complete
- Retrieves result from database

### 2. Query Tasks (`tasks`)

**Purpose**: Query task status, list running tasks, count tasks, and manage tasks.

**Commands**:
- `tasks list` - List running tasks (from TaskTracker)
- `tasks all` - List all tasks from database with filters
- `tasks get <task_id>` - Get task details
- `tasks status <task_id>...` - Get status of specific tasks
- `tasks count` - Count running tasks
- `tasks tree <task_id>` - Get task tree structure
- `tasks children --parent-id <id>` - Get child tasks
- `tasks create --file <file>|--stdin` - Create task tree
- `tasks update <task_id> [options]` - Update task fields
- `tasks delete <task_id> [--force]` - Delete task
- `tasks cancel <task_id>...` - Cancel running tasks
- `tasks copy <task_id> [--children]` - Copy task tree
- `tasks watch [--task-id <id>|--all]` - Watch task status in real-time

**Data Sources**:
- **TaskTracker**: In-memory set of running task IDs (fast, real-time)
- **Database**: Full task details (status, progress, result, error)

**Example**:
```bash
# List all running tasks
aipartnerupflow tasks list

# Check status of specific tasks
aipartnerupflow tasks status task-123 task-456

# Count running tasks
aipartnerupflow tasks count --user-id user-123
```

### 3. Interactive Mode (Future)

**Purpose**: Provide interactive shell for continuous task management.

**Design**:
```bash
# Start interactive mode
aipartnerupflow interactive

# In interactive mode:
> run flow executor_id --inputs '{"data": "test"}'
Task started: task-123

> tasks status task-123
Status: in_progress, Progress: 45%

> tasks cancel task-123
Task cancelled: task-123

> exit
```

## Task Execution Flow

### CLI Execution Path

#### Standard Mode (Task Array)

```
1. User: aipartnerupflow run flow --tasks '[{"id": "task1", "schemas": {"method": "executor1"}, ...}, {"id": "task2", ...}]'
   ↓
2. CLI parses tasks JSON array
   ↓
3. CLI groups tasks by root (parent_id=None)
   - If multiple root tasks: group into separate task trees
   - If single root task: use all tasks as one tree
   ↓
4. For each task group:
   ↓
5. TaskExecutor.execute_tasks(task_group)
   ↓
6. TaskCreator/TaskExecutor builds task tree (single root)
   ↓
7. TaskManager.distribute_task_tree()
   ↓
8. TaskManager._execute_task_with_schemas()
   ↓
9. ExtensionRegistry.get_by_id(executor_id)
   ↓
10. Executor.execute(inputs)
   ↓
11. Result saved to database
   ↓
12. CLI collects all results and displays
```

#### Legacy Mode (Executor ID + Inputs)

```
1. User: aipartnerupflow run flow example_executor --inputs '{"key": "value"}'
   ↓
2. CLI creates single task:
   [
     {
       "id": "uuid",
       "name": "Execute example_executor",
       "user_id": "cli_user",
       "schemas": {"method": "example_executor"},
       "inputs": {"key": "value"},
       ...
     }
   ]
   ↓
3. (Same as standard mode from step 3)
```

**Key Points**:
- **TaskExecutor limitation**: Only supports single root task tree
- **CLI handles multiple unrelated tasks**: Groups by root, executes separately
- **Standard format**: Tasks array (JSON) - same as API

### API Execution Path (for comparison)

```
1. API receives tasks array in A2A protocol message
   ↓
2. AIPartnerUpFlowAgentExecutor._extract_tasks_from_context()
   ↓
3. TaskExecutor.execute_tasks(tasks)  # Same as CLI!
   ↓
4. ... (same as CLI from step 4)
```

**Key Point**: Both CLI and API use the same `TaskExecutor.execute_tasks()` method!

## Task Status Query

### Data Flow

```
CLI: tasks status task-123
  ↓
TaskExecutor.is_task_running(task_id)  # Check TaskTracker (in-memory)
  ↓
TaskRepository.get_task_by_id(task_id)  # Get full details from database
  ↓
Return: {
  "task_id": "task-123",
  "status": "in_progress",
  "progress": 45.0,
  "is_running": true,  # From TaskTracker
  "result": null,
  "error": null
}
```

### Two-Level Status

1. **TaskTracker** (in-memory):
   - Fast lookup: `is_task_running(task_id)`
   - Lists all running task IDs
   - Updated when tasks start/stop

2. **Database** (persistent):
   - Full task details: status, progress, result, error
   - Historical records
   - Survives process restarts

## Task Cancellation

### Design (Implemented)

**Approach**: Mark task as cancelled in database, TaskManager checks cancellation flag at multiple checkpoints.

**Flow**:
```
1. CLI/API: tasks cancel task-123
   ↓
2. TaskRepository.update_task_status(task_id, status="cancelled")
   ↓
3. TaskManager._execute_single_task() checks status at multiple points:
   - Before starting execution
   - After dependency resolution
   - Before calling executor
   - After executor returns
   ↓
4. If status == "cancelled", stop execution and return
   ↓
5. TaskTracker stops tracking the task
```

**Supported States**:
- ✅ **pending**: Can be cancelled (will not start execution)
- ✅ **in_progress**: Can be cancelled (TaskManager will check and stop at next checkpoint)
- ❌ **completed/failed/cancelled**: Cannot be cancelled (already finished)

**Executor-Level Cancellation Support**:

| Executor | `cancelable` | Cancellation Support | Notes |
|----------|-------------|---------------------|-------|
| **BatchManager** | `True` | ✅ **Supported** | Checks cancellation before each work. Preserves token_usage from completed works. Can stop before executing remaining works. |
| **CrewManager** | `False` | ❌ **Not Supported During Execution** | **CrewAI Limitation**: `kickoff()` is a synchronous blocking call with no cancellation support. Cancellation can only be checked before execution starts. If cancelled during execution, the crew will complete normally, then TaskManager will mark it as cancelled. Token_usage is preserved. |
| **CommandExecutor** | `False` | ❌ **Not Implemented** | Cancellation checking not implemented. Could be added by checking `cancellation_checker` during subprocess execution. |
| **SystemInfoExecutor** | `False` | ❌ **Not Supported** | Fast execution (< 1 second), cancellation not needed. |
| **Other Executors** | `False` (default) | ⚠️ **Varies** | Depends on executor implementation. TaskManager checks before/after execution. Executors can set `cancelable=True` and implement cancellation checking in their own execution loops. |

**Implementation Details**:

1. **TaskManager Level** (Always Active):
   - Checks cancellation at multiple checkpoints:
     - Before starting execution
     - After dependency resolution
     - Before calling executor
     - After executor returns
   - If cancelled, stops execution immediately

2. **Executor Level** (Optional, Implemented for BatchManager):
   - **BatchManager**: Checks cancellation before each work execution (can stop mid-batch)
   - **CrewManager**: Checks cancellation before execution only (CrewAI limitation: cannot cancel during execution)
   - **SystemInfoExecutor**: No cancellation needed (fast execution)

3. **Token Usage Preservation**:
   - ✅ **BatchManager**: Preserves token_usage from completed works when cancelled
   - ✅ **CrewManager**: Preserves token_usage even if cancelled
   - ✅ All executors: Token_usage is preserved in result even on cancellation

**Limitations**:
- **CrewAI Library Limitation**: CrewAI's `kickoff()` is a synchronous blocking call with **no cancellation support**. Once `kickoff()` starts executing, it cannot be interrupted. This means:
  - Cancellation can only be checked **before** execution starts
  - If cancellation is requested during execution, the crew will complete normally
  - TaskManager will detect cancellation after execution and mark the task as cancelled
  - Token usage is still preserved even if cancelled
  - This is a fundamental limitation of the CrewAI library, not our implementation
- **Long-running crews**: For very long-running crews, cancellation will not take effect until the crew completes. This is unavoidable due to CrewAI's design.
- **Force cancellation**: Currently, force cancellation (`--force`) only affects the error message, not the cancellation behavior. True force cancellation (immediate stop) would require process/thread termination, which is not yet implemented and may not be possible for CrewAI crews.

**Implementation Points**:
- ✅ TaskManager checks cancellation flag at multiple checkpoints
- ✅ CLI cancel command implemented
- ✅ BatchManager executor-level cancellation check (before each work, can stop mid-batch)
- ✅ CrewManager executor-level cancellation check (before execution only)
- ✅ Token_usage preservation on cancellation
- ❌ **CrewAI library limitation**: No cancellation during execution (CrewAI's `kickoff()` is blocking with no cancellation support)
- ⚠️ Force cancellation (immediate stop via process termination) - not yet implemented

## Interactive Mode Design

### Use Cases

1. **Continuous Task Management**: Start tasks, monitor status, cancel if needed
2. **Development/Testing**: Quick iteration without restarting CLI
3. **Monitoring**: Watch multiple tasks simultaneously

### Implementation Options

**Option 1: Simple REPL**
```python
import cmd

class InteractiveShell(cmd.Cmd):
    prompt = 'aipartnerupflow> '
    
    def do_run(self, args):
        # Parse and execute run command
        pass
    
    def do_tasks(self, args):
        # Parse and execute tasks command
        pass
```

**Option 2: Rich Interactive UI**
- Use `rich` library for better UI
- Real-time status updates
- Table view of running tasks
- Color-coded status

**Option 3: Watch Mode**
```bash
# Watch task status in real-time
aipartnerupflow tasks watch task-123

# Watch all tasks
aipartnerupflow tasks watch --all
```

## Development Guidelines

### Adding New Commands

1. Create command file in `cli/commands/`
2. Use Typer for command definition
3. Follow the pattern: CLI → TaskExecutor → Database
4. Never directly call executors

### Example: Adding a New Command

```python
# cli/commands/my_command.py
import typer
from aipartnerupflow.core.execution.task_executor import TaskExecutor

app = typer.Typer(name="mycommand")

@app.command()
def do_something(task_id: str):
    """Do something with a task"""
    task_executor = TaskExecutor()
    # Use task_executor methods
    # Query database via TaskRepository
    # Never call executors directly
```

### Error Handling

- Use `typer.Exit(1)` for errors
- Log errors with `logger.exception()`
- Provide helpful error messages
- Return JSON for programmatic use

### Output Format

- **Human-readable**: Use `typer.echo()` with formatting
- **Machine-readable**: Use JSON output (for scripts)
- **Interactive**: Use `rich` for tables, progress bars

## Multiple Unrelated Tasks Support

### Problem

`TaskExecutor.execute_tasks()` only supports **single root task tree**. If you pass multiple unrelated tasks (multiple tasks with `parent_id=None`), TaskExecutor will only process the first root task.

### Solution: CLI-Level Grouping

CLI handles this by:
1. **Grouping tasks by root**: `_group_tasks_by_root()` function groups tasks into separate task trees
2. **Executing separately**: Each task group is executed via `TaskExecutor.execute_tasks()` separately
3. **Collecting results**: All results are collected and returned together

### Example

```bash
# Multiple unrelated tasks
aipartnerupflow run flow --tasks '[
  {"id": "task1", "name": "Task 1", "schemas": {"method": "executor1"}, "inputs": {"key": "value"}},
  {"id": "task2", "name": "Task 2", "schemas": {"method": "executor2"}, "inputs": {"key": "value2"}}
]'

# CLI will:
# 1. Detect 2 root tasks (both have parent_id=None)
# 2. Group into 2 separate task groups
# 3. Execute group 1: TaskExecutor.execute_tasks([task1])
# 4. Execute group 2: TaskExecutor.execute_tasks([task2])
# 5. Return combined results
```

### Task Tree vs Unrelated Tasks

- **Task Tree**: Tasks with parent-child relationships
  ```json
  [
    {"id": "root", "parent_id": null, ...},
    {"id": "child1", "parent_id": "root", ...},
    {"id": "child2", "parent_id": "root", ...}
  ]
  ```
  - Single root task
  - Executed as one task tree

- **Unrelated Tasks**: Multiple independent tasks
  ```json
  [
    {"id": "task1", "parent_id": null, ...},
    {"id": "task2", "parent_id": null, ...}
  ]
  ```
  - Multiple root tasks
  - CLI groups and executes separately

## Comparison: CLI vs API

| Feature | CLI | API |
|---------|-----|-----|
| **Execution** | `TaskExecutor.execute_tasks()` (per group) | `TaskExecutor.execute_tasks()` |
| **Task Format** | JSON array (tasks list) | JSON array (A2A protocol) |
| **Multiple Unrelated Tasks** | ✅ Supported (CLI groups by root) | ❌ Not supported (single root only) |
| **Streaming** | Not yet supported | Supported via EventQueue |
| **Status Query** | `TaskTracker + Database` | `TaskTracker + Database` |
| **Cancellation** | ✅ Implemented | To be implemented |
| **Hooks** | Supported (via TaskExecutor) | Supported (via TaskExecutor) |
| **Database** | Same database | Same database |

## Future Enhancements

1. **Interactive Mode**: REPL for continuous task management
2. **Watch Mode**: Real-time status monitoring
3. **Streaming Support**: Real-time progress updates in CLI
4. **Task Cancellation**: Graceful and force cancellation
5. **Task History**: Query historical tasks
6. **Task Filtering**: Filter by status, user, date range
7. **Batch Operations**: Cancel multiple tasks, query multiple tasks

