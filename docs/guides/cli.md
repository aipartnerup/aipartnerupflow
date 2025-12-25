# CLI Usage Guide

## Overview

The CLI is **completely independent** from the API server. You can use CLI commands without starting the API server. CLI and API share the same database, so they can work together or independently.

## Architecture: CLI vs API

```
┌─────────────────────────────────────────────────────────────┐
│                    Shared Database                          │
│  (DuckDB default, or PostgreSQL if configured)             │
└─────────────────────────────────────────────────────────────┘
         ▲                              ▲
         │                              │
    ┌────┴────┐                  ┌─────┴─────┐
    │   CLI   │                  │    API    │
    │         │                  │  Server   │
    │ Direct  │                  │  (HTTP)   │
    │ Access  │                  │           │
    └─────────┘                  └───────────┘
```

**Key Points**:
- **CLI**: Direct database access via session pool
- **API**: Direct database access via session pool
- **No dependency**: CLI does NOT need API server to be running
- **Shared data**: Both CLI and API read/write to the same database

## Quick Start

### 1. Installation

```bash
# Install with CLI support
pip install -e ".[cli]"

# Or install everything
pip install -e ".[all]"
```

### 2. Basic Usage (No API Server Required)

```bash
# Execute a task (no API server needed)
# Standard mode (recommended):
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'
# Or legacy mode:
aipartnerupflow run flow system_info_executor --inputs '{"resource": "cpu"}'

# Query task status (no API server needed)
aipartnerupflow tasks status task-123

# List tasks from database (not just running)
aipartnerupflow tasks list
```

## Usage Scenarios

### Scenario 1: CLI Only (No API Server)

**Use Case**: Local development, testing, or simple automation scripts.

```bash
# 1. Execute tasks (standard mode - recommended)
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'

# Or legacy mode (backward compatible)
aipartnerupflow run flow system_info_executor --inputs '{"resource": "cpu"}'

# 2. Check status (in another terminal or after execution)
aipartnerupflow tasks status <task_id>

# 3. List tasks (not just running)
aipartnerupflow tasks list

# 4. Cancel a task if needed
aipartnerupflow tasks cancel <task_id>
```

**Advantages**:
- ✅ No server setup required
- ✅ Fast execution (direct database access)
- ✅ Simple for local development
- ✅ Can be used in scripts/automation

**Limitations**:
- ❌ No HTTP API access
- ❌ No remote access
- ❌ No A2A protocol support

### Scenario 2: API Server Only

**Use Case**: Production deployment, remote access, A2A protocol integration.

```bash
# 1. Start API server (default: A2A protocol)
aipartnerupflow serve start --host 0.0.0.0 --port 8000

# Or start with MCP protocol
aipartnerupflow serve start --host 0.0.0.0 --port 8000 --protocol mcp

# 2. Use HTTP API or A2A protocol to execute tasks
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"tasks": [...]}'

# 3. Query via API
curl http://localhost:8000/api/tasks/task-123/status
```

**Advantages**:
- ✅ HTTP API access
- ✅ Remote access
- ✅ A2A protocol support
- ✅ Multi-user support

### Scenario 3: CLI + API Server (Hybrid)

**Use Case**: Development with both CLI convenience and API testing.

```bash
# Terminal 1: Start API server (default: A2A protocol)
aipartnerupflow serve start --port 8000

# Or start with MCP protocol
aipartnerupflow serve start --port 8000 --protocol mcp

# Terminal 2: Use CLI to execute tasks
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'

# Terminal 2: Query via CLI (faster, direct DB access)
aipartnerupflow tasks status <task_id>

# Or query via API (for testing API endpoints)
curl http://localhost:8000/api/tasks/<task_id>/status
```

**Advantages**:
- ✅ Best of both worlds
- ✅ CLI for quick operations
- ✅ API for integration testing
- ✅ Shared database, consistent data

## Complete Workflow Examples

### Workflow 1: Execute and Monitor (CLI Only)

```bash
# Step 1: Execute tasks in background (standard mode)
aipartnerupflow run flow \
  --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]' \
  --background \
  --watch

# Or legacy mode
aipartnerupflow run flow executor_id \
  --inputs '{"data": "test"}' \
  --background \
  --watch

# Output:
# Task(s) started in background
# Task ID: abc-123-def-456
# Watching task status...

# Step 2: (Optional) In another terminal, check status
aipartnerupflow tasks status abc-123-def-456

# Step 3: (Optional) Cancel if needed
aipartnerupflow tasks cancel abc-123-def-456
```

### Workflow 2: Execute and Query Later

```bash
# Step 1: Execute tasks (foreground, wait for completion)
aipartnerupflow run flow \
  --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]' \
  --output result.json

# Step 2: Check result
cat result.json

# Step 3: (If needed) Query task details
aipartnerupflow tasks status <task_id_from_result>
```

### Workflow 3: Monitor Multiple Tasks

```bash
# Step 1: Start multiple unrelated tasks in one command
aipartnerupflow run flow \
  --tasks '[
    {"id": "task1", "name": "Get CPU Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}},
    {"id": "task2", "name": "Get Memory Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "memory"}},
    {"id": "task3", "name": "Get Disk Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "disk"}}
  ]' \
  --background

# Or start separately (legacy mode)
aipartnerupflow run flow executor1 --inputs '{}' --background
aipartnerupflow run flow executor2 --inputs '{}' --background
aipartnerupflow run flow executor3 --inputs '{}' --background

# Step 2: Monitor all running tasks
aipartnerupflow tasks watch --all

# Step 3: Check specific tasks
aipartnerupflow tasks status task1-id task2-id task3-id

# Step 4: Cancel specific tasks
aipartnerupflow tasks cancel task1-id task2-id
```

### Workflow 4: Development with API Server

```bash
# Terminal 1: Start API server (development mode, default: A2A protocol)
aipartnerupflow serve start --port 8000 --reload

# Or start with MCP protocol
aipartnerupflow serve start --port 8000 --reload --protocol mcp

# Terminal 2: Execute via CLI (standard mode)
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'

# Terminal 2: Query via CLI (direct DB, fast)
aipartnerupflow tasks list

# Terminal 3: Test API endpoints
curl http://localhost:8000/api/tasks
curl http://localhost:8000/api/tasks/<task_id>/status
```

## Command Reference

### Execute Tasks

#### Standard Mode (Recommended): Task Array

```bash
# Execute single task (task array with one task)
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'

# Execute task tree (parent-child relationships)
aipartnerupflow run flow --tasks '[
  {"id": "root", "name": "Get System Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}},
  {"id": "child1", "name": "Process Info", "parent_id": "root", "schemas": {"method": "command_executor"}, "inputs": {"command": "echo Processing"}]
]'

# Execute multiple unrelated tasks (multiple root tasks)
aipartnerupflow run flow --tasks '[
  {"id": "task1", "name": "Get CPU Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}},
  {"id": "task2", "name": "Get Memory Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "memory"}}
]'

# With tasks file
aipartnerupflow run flow --tasks-file tasks.json

# Background execution
aipartnerupflow run flow --tasks '[{...}]' --background

# Background with real-time monitoring
aipartnerupflow run flow --tasks '[{...}]' --background --watch

# Save result to file
aipartnerupflow run flow --tasks '[{...}]' --output result.json
```

#### Legacy Mode (Backward Compatible): Executor ID + Inputs

```bash
# Execute single executor (legacy mode)
aipartnerupflow run flow <executor_id> --inputs '{"key": "value"}'

# With input file
aipartnerupflow run flow <executor_id> --inputs-file inputs.json

# Background execution
aipartnerupflow run flow <executor_id> --inputs '{"key": "value"}' --background

# Custom user ID
aipartnerupflow run flow <executor_id> --inputs '{"key": "value"}' --user-id my-user
```

**Note**: Legacy mode is for backward compatibility. Use standard mode (--tasks) for new code.

### Query Tasks

#### List Tasks

```bash
# List all tasks from database (defaults to root tasks)
aipartnerupflow tasks list

# List with user filter
aipartnerupflow tasks list --user-id my-user

# Filter by status
aipartnerupflow tasks list --status completed

# Show all tasks including children
aipartnerupflow tasks list --all-tasks

# Limit number of results and pagination
aipartnerupflow tasks list --limit 50 --offset 0
```

#### Get Task Details

```bash
# Get details of a specific task
aipartnerupflow tasks get task-123
```

#### Check Task Status

```bash
# Check status of specific tasks
aipartnerupflow tasks status task-123 task-456
```

#### Count Tasks

```bash
# Get task statistics by status from database (default)
aipartnerupflow tasks count

# Count with user filter
aipartnerupflow tasks count --user-id my-user

# Count only root tasks
aipartnerupflow tasks count --root-only

# JSON format output
aipartnerupflow tasks count --format json
```



#### Get Task Tree

```bash
# Get task tree structure starting from a task
aipartnerupflow tasks tree task-123

# If task is a child, returns the root tree
aipartnerupflow tasks tree child-task-456
```

#### Get Child Tasks

```bash
# Get children of a parent task
aipartnerupflow tasks children --parent-id task-123

# Alternative: use --task-id (same as --parent-id)
aipartnerupflow tasks children --task-id task-123
```

### Monitor Tasks

```bash
# Watch specific task (real-time)
aipartnerupflow tasks watch --task-id task-123

# Watch all running tasks
aipartnerupflow tasks watch --all

# Custom update interval
aipartnerupflow tasks watch --task-id task-123 --interval 0.5
```

### Cancel Tasks

```bash
# Cancel single task
aipartnerupflow tasks cancel task-123

# Cancel multiple tasks
aipartnerupflow tasks cancel task-123 task-456 task-789

# Force cancel (immediate stop)
aipartnerupflow tasks cancel task-123 --force
```

### Create Tasks

Create task trees from JSON file or stdin.

```bash
# Create task tree from JSON file
aipartnerupflow tasks create --file tasks.json

# Create task tree from stdin
echo '{"id": "task1", "name": "Task 1", ...}' | aipartnerupflow tasks create --stdin

# File format: single task object or array of tasks
cat > tasks.json << EOF
[
  {
    "id": "task1",
    "name": "Task 1",
    "user_id": "my-user",
    "status": "pending",
    "priority": 1,
    "has_children": false,
    "progress": 0.0
  }
]
EOF
aipartnerupflow tasks create --file tasks.json
```

### Update Tasks

Update task fields (name, status, progress, inputs, params, etc.).

```bash
# Update task name
aipartnerupflow tasks update task-123 --name "New Task Name"

# Update task status and progress
aipartnerupflow tasks update task-123 --status completed --progress 1.0

# Update task inputs (JSON string)
aipartnerupflow tasks update task-123 --inputs '{"key": "value"}'

# Update task params (JSON string)
aipartnerupflow tasks update task-123 --params '{"executor_id": "my_executor"}'

# Update multiple fields
aipartnerupflow tasks update task-123 \
  --name "Updated Name" \
  --status in_progress \
  --progress 0.5 \
  --error "Custom error message"
```

**Note**: Critical fields (`parent_id`, `user_id`, `dependencies`) cannot be updated after task creation.

### Delete Tasks

Delete tasks with validation (only pending tasks can be deleted).

```bash
# Delete a pending task
aipartnerupflow tasks delete task-123

# Force delete (bypasses validation)
aipartnerupflow tasks delete task-123 --force
```

**Deletion Rules:**
- Only tasks in `pending` status can be deleted (unless `--force` is used)
- All child tasks (recursively) must also be in `pending` status
- Tasks with dependencies cannot be deleted (other tasks depend on them)
- When deletion is allowed, all child tasks are automatically deleted

### Copy Tasks

Create a copy of a task tree for re-execution. This is useful for retrying failed tasks or re-running completed tasks.

```bash
# Copy a task tree (basic usage, minimal mode)
aipartnerupflow tasks copy task-123

# Copy and save to file
aipartnerupflow tasks copy task-123 --output /path/to/copied_task.json

# Copy with children (also copy each direct child task with its dependencies)
aipartnerupflow tasks copy task-123 --children

# Copy with full mode (copies complete tree from root)
aipartnerupflow tasks copy task-123 --copy-mode full

# Copy with custom mode (copy only specified tasks)
aipartnerupflow tasks copy task-123 \
  --copy-mode custom \
  --custom-task-ids task-123,task-child-456

# Copy with custom mode and include children recursively
aipartnerupflow tasks copy task-123 \
  --copy-mode custom \
  --custom-task-ids task-123,task-child-456 \
  --custom-include-children

# Preview copy without saving to database (returns task array)
aipartnerupflow tasks copy task-123 --dry-run

# Copy with reset fields (reset specific fields during copy)
aipartnerupflow tasks copy task-123 --reset-fields status,progress
```

**Copy Modes:**
- `minimal` (default): Copies minimal subtree (original_task + children + dependents). All copied tasks are marked as pending for re-execution.
- `full`: Copies complete tree from root. Tasks that need re-execution are marked as pending, unrelated successful tasks are marked as completed with preserved token_usage.
- `custom`: Copies only specified tasks (requires `--custom-task-ids`). Useful for selective copying of specific tasks in a tree.

**What gets copied:**
- The original task and all its children (depending on mode and parameters)
- All tasks that depend on the original task (including transitive dependencies)
- Automatically handles failed leaf nodes (filters out pending dependents)
- Task structure (parent-child relationships)
- Task definitions (name, inputs, schemas, params, dependencies)

**What happens:**
- New task IDs (UUIDs) are generated for all copied tasks
- All execution fields are reset (status="pending", progress=0.0, result=null) unless `--reset-fields` is specified
- The original task's `has_copy` flag is set to `true` (when not using `--dry-run`)
- Copied tasks are linked to the original via `original_task_id` field
- Dependencies correctly reference new task IDs within the copied tree

**Use cases:**
```bash
# 1. Original task failed - retry with copy
aipartnerupflow tasks status task-123
# Status: failed

# 2. Copy the task tree
aipartnerupflow tasks copy task-123
# Returns: new_task_id (e.g., task-copy-xyz-789)

# 3. Execute the copied task
aipartnerupflow run flow --tasks '[{"id": "task-copy-xyz-789", ...}]'

# Preview copy before saving (useful for validation)
aipartnerupflow tasks copy task-123 --dry-run --output preview.json

# Copy specific tasks only (custom mode)
aipartnerupflow tasks copy task-123 \
  --copy-mode custom \
  --custom-task-ids task-123,task-child-456
```

### Examples Data Management ⚠️ DEPRECATED

> **Note:** The `examples` command has been removed from aipartnerupflow core library.
> 
> **Migration:** For demo task initialization, please use the **aipartnerupflow-demo** project instead.
> The aipartnerupflow-demo project provides:
> - Complete demo tasks for all executors
> - Per-user demo task initialization
> - Demo task validation against executor schemas
> 
> See [aipartnerupflow-demo](https://github.com/aipartnerup/aipartnerupflow-demo) for more information.

The `aipartnerupflow examples init` command is no longer available. Demo task initialization has been moved to the separate aipartnerupflow-demo project to keep the core library focused on orchestration functionality.

### API Server Management

```bash
# Start API server (foreground, default: A2A protocol)
aipartnerupflow serve start --port 8000

# Start API server with A2A protocol (explicit)
aipartnerupflow serve start --port 8000 --protocol a2a

# Start API server with MCP protocol
aipartnerupflow serve start --port 8000 --protocol mcp

# Start with auto-reload (development)
aipartnerupflow serve start --port 8000 --reload

# Start daemon (background service, default: A2A protocol)
aipartnerupflow daemon start --port 8000

# Start daemon with MCP protocol
aipartnerupflow daemon start --port 8000 --protocol mcp

# Check daemon status
aipartnerupflow daemon status

# Stop daemon
aipartnerupflow daemon stop

# View daemon logs
aipartnerupflow daemon logs
```

**Protocol Selection:**
- `--protocol` / `-P`: Specify protocol to use (`a2a` or `mcp`)
- Default: `a2a` (A2A Protocol Server)
- Supported protocols:
  - `a2a`: A2A Protocol Server (default)
  - `mcp`: MCP (Model Context Protocol) Server

## Database Configuration

### Default: DuckDB (Embedded, Zero Config)

CLI uses DuckDB by default - no configuration needed:

```bash
# Just use CLI - database is created automatically
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'
```

Database file location: `~/.aipartnerup/data/aipartnerupflow.duckdb` (or configured path)

### Optional: PostgreSQL

If you want to use PostgreSQL (for production or shared access):

```bash
# Set environment variable
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/aipartnerupflow"

# Use CLI as normal - it will connect to PostgreSQL
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'
```

**Note**: Both CLI and API will use the same database connection string, so they share data automatically.

## Task Format: Standard vs Legacy

### Standard Mode (Recommended)

**Format**: Tasks JSON array (list of task objects)

```json
[
  {
    "id": "task1",
    "name": "Task 1",
    "user_id": "user123",
    "schemas": {
      "method": "system_info_executor"  // Executor ID registered via @executor_register()
    },
    "inputs": {
      "resource": "cpu"
    },
    "parent_id": null,  // null for root tasks
    "priority": 1,
    "status": "pending"
  }
]
```

**Features**:
- ✅ Supports task trees (parent-child relationships)
- ✅ Supports multiple unrelated tasks (CLI groups by root)
- ✅ Same format as API
- ✅ Flexible and extensible

### Legacy Mode (Backward Compatible)

**Format**: Executor ID + Inputs

```bash
aipartnerupflow run flow executor_id --inputs '{"key": "value"}'
```

**Features**:
- ✅ Simple for single executor execution
- ✅ Backward compatible
- ❌ Limited to single executor
- ❌ Cannot execute task trees or multiple tasks

**Recommendation**: Use standard mode (`--tasks`) for new code.

## Multiple Unrelated Tasks

### Understanding the Limitation

`TaskExecutor.execute_tasks()` only supports **single root task tree**. If you pass multiple unrelated tasks (multiple tasks with `parent_id=None`), TaskExecutor will only process the first root task.

### CLI Solution

CLI automatically handles this by:
1. **Detecting multiple root tasks**: Identifies tasks with `parent_id=None`
2. **Grouping by root**: Groups tasks into separate task trees
3. **Executing separately**: Calls `TaskExecutor.execute_tasks()` for each group
4. **Collecting results**: Returns combined results

### Example

```bash
# Multiple unrelated tasks (2 root tasks)
aipartnerupflow run flow --tasks '[
  {"id": "task1", "name": "Get CPU Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}},
  {"id": "task2", "name": "Get Memory Info", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "memory"}}
]'

# CLI output:
# Found 2 unrelated task groups, executing separately...
# Executing task group 1/2...
# Executing task group 2/2...
# Result: {
#   "status": "completed",
#   "task_groups": 2,
#   "root_task_ids": ["task1", "task2"],
#   "results": [...]
# }
```

## Common Questions

### Q: Do I need to start API server to use CLI?

**A: No.** CLI works independently. It directly accesses the database, so no API server is required.

### Q: Can CLI and API run at the same time?

**A: Yes.** They share the same database, so you can:
- Execute tasks via CLI
- Query tasks via API
- Or vice versa

### Q: How does CLI query task status?

**A: Direct database access.** CLI uses `TaskRepository` to query the database directly, not through API.

### Q: Can I use CLI to query tasks created by API?

**A: Yes.** Since they share the same database, CLI can query any task created by API, and vice versa.

### Q: What's the difference between CLI and API?

| Feature | CLI | API |
|---------|-----|-----|
| **Execution** | Direct via TaskExecutor | Via HTTP/A2A protocol |
| **Query** | Direct database access | Via HTTP endpoints |
| **Setup** | No server needed | Requires server |
| **Remote Access** | No (local only) | Yes (HTTP) |
| **A2A Protocol** | No | Yes |
| **Speed** | Fast (direct DB) | Slightly slower (HTTP overhead) |
| **Use Case** | Local dev, scripts | Production, remote access |

### Q: How do I know if a task is running?

**A: Use TaskTracker (in-memory) + Database:**

```bash
# Check task status from database
aipartnerupflow tasks list  # Shows tasks from database

# Check full status from database (includes completed/failed tasks)
aipartnerupflow tasks status task-123  # Shows full details from DB
```

### Q: Can I cancel a task started via API using CLI?

**A: Yes.** Since they share the same database:

```bash
# Task started via API
curl -X POST http://localhost:8000/api/tasks -d '...'

# Cancel via CLI
aipartnerupflow tasks cancel <task_id>
```

## Best Practices

### 1. Development Workflow

```bash
# Use CLI for quick testing
aipartnerupflow run flow --tasks '[{"id": "task1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'

# Use API server for integration testing
aipartnerupflow serve start --reload
# Then test API endpoints
```

### 2. Production Deployment

```bash
# Option A: CLI only (for automation/scripts)
# No server needed, just use CLI commands

# Option B: API server (for remote access)
# Start with A2A protocol (default)
aipartnerupflow daemon start --port 8000
# Or start with MCP protocol
aipartnerupflow daemon start --port 8000 --protocol mcp
# Then use HTTP API, A2A protocol, or MCP protocol
```

### 3. Monitoring

```bash
# For single task
aipartnerupflow tasks watch --task-id task-123

# For all tasks
aipartnerupflow tasks watch --all

# For specific user
aipartnerupflow tasks list --user-id my-user
```

### 4. Error Handling

```bash
# Check task status after execution
aipartnerupflow tasks status <task_id>

# If failed, check error message
# Error is stored in task.error field

# Cancel stuck tasks
aipartnerupflow tasks cancel <task_id> --force
```

## Troubleshooting

### Problem: "Task not found"

**Solution**: Check if task ID is correct:
```bash
aipartnerupflow tasks list  # See all running tasks
aipartnerupflow tasks status <task_id>  # Check specific task
```

### Problem: "Database connection error"

**Solution**: Check database configuration:
```bash
# For DuckDB (default), no config needed
# For PostgreSQL, check DATABASE_URL environment variable
echo $DATABASE_URL
```

### Problem: "Task is stuck"

**Solution**: Cancel and restart:
```bash
aipartnerupflow tasks cancel <task_id> --force
aipartnerupflow run flow <batch_id> --inputs '...'
```

### Problem: "Cannot query task status"

**Solution**: Ensure database is accessible:
```bash
# Check if database file exists (DuckDB)
ls ~/.aipartnerup/data/aipartnerupflow.duckdb

# Or check PostgreSQL connection
psql $DATABASE_URL -c "SELECT COUNT(*) FROM apflow_tasks;"
```

## Summary

- ✅ **CLI is independent** - No API server required
- ✅ **Direct database access** - Fast and efficient
- ✅ **Shared database** - CLI and API can work together
- ✅ **Full functionality** - Execute, query, monitor, cancel tasks
- ✅ **Production ready** - Can be used in scripts and automation

Use CLI for local development and automation, use API server for production deployment and remote access.

## CLI Extension (Dynamic Plugins)

The `apflow` CLI supports dynamic discovery of subcommands through Python's `entry_points` mechanism. This allows external projects to add their own command groups directly to the main CLI without modifying the core library.

### Unified Entry Point

Users always use the same consistent entry point:
- `aipartnerupflow <your-plugin-name> <command>`
- `apflow <your-plugin-name> <command>`

### Example: Users Extension
If a plugin registers a command group called `users`, a user can simply run:
```bash
apflow users stat
```

For more details on how to develop these extensions, see the [Extending Guide](../development/extending.md#creating-cli-extensions).

