# CLI Design Document

## CLI Basic Features

### Core Commands

#### 1. Task Execution (`run`)

**Execute tasks from tasks.json file:**

```bash
# Execute tasks from tasks.json
aipartnerupflow run tasks.json

# Execute with custom inputs
aipartnerupflow run tasks.json --inputs '{"key": "value"}'

# Execute with inputs file
aipartnerupflow run tasks.json --inputs-file inputs.json

# Save output to file
aipartnerupflow run tasks.json --output result.json
```

**Execute batch/crew directly:**

```bash
# Run a batch (requires [crewai])
aipartnerupflow run batch <batch_id> --inputs '{"key": "value"}'

# Run a crew (requires [crewai])
aipartnerupflow run crew <crew_id> --inputs '{"key": "value"}'
```

#### 2. Task Status (`status`)

```bash
# Check task status by ID
aipartnerupflow status <task_id>

# Check task tree status (all tasks in tree)
aipartnerupflow status <task_id> --tree

# List recent tasks
aipartnerupflow status --recent [--limit 10]
```

#### 3. List Resources (`list`)

```bash
# List available batches (requires [crewai])
aipartnerupflow list batches

# List available crews (requires [crewai])
aipartnerupflow list crews

# List custom tasks
aipartnerupflow list tasks

# List all (batches, crews, tasks)
aipartnerupflow list all
```

#### 4. Server Management (`serve`)

```bash
# Start API server
aipartnerupflow serve

# Start with custom host/port
aipartnerupflow serve --host 0.0.0.0 --port 8000

# Start with auto-reload (development)
aipartnerupflow serve --reload

# Start with multiple workers (production)
aipartnerupflow serve --workers 4
```

#### 5. Daemon Management (`daemon`)

```bash
# Start daemon service
aipartnerupflow daemon start

# Stop daemon service
aipartnerupflow daemon stop

# Restart daemon service
aipartnerupflow daemon restart

# Check daemon status
aipartnerupflow daemon status

# View daemon logs
aipartnerupflow daemon logs [--follow]
```

#### 6. Configuration (`config`)

```bash
# Show current configuration
aipartnerupflow config show

# Set configuration value
aipartnerupflow config set <key> <value>

# Initialize configuration file
aipartnerupflow config init

# Validate configuration
aipartnerupflow config validate
```

## tasks.json File Format

### Format 1: Simple Task Tree

```json
{
  "version": "1.0",
  "tasks": [
    {
      "id": "task-1",
      "name": "root_task",
      "user_id": "user_123",
      "priority": 2,
      "dependencies": [],
      "input_data": {"url": "https://example.com"}
    },
    {
      "id": "task-2",
      "name": "web_analyzer",
      "user_id": "user_123",
      "parent_id": "task-1",
      "priority": 1,
      "dependencies": [],
      "input_data": {"url": "https://example.com"}
    }
  ]
}
```

### Format 2: With Task Templates

```json
{
  "version": "1.0",
  "templates": {
    "web_analyzer": {
      "name": "Web Analyzer",
      "description": "Analyze web content",
      "schemas": {
        "type": "object",
        "properties": {
          "url": {"type": "string", "description": "URL to analyze"}
        }
      }
    }
  },
  "tasks": [
    {
      "template": "web_analyzer",
      "id": "task-1",
      "user_id": "user_123",
      "input_data": {"url": "https://example.com"}
    }
  ]
}
```

### Format 3: CrewAI Tasks (requires [crewai])

```json
{
  "version": "1.0",
  "type": "crew",
  "crew": {
    "name": "Analysis Crew",
    "agents": [
      {
        "role": "Analyst",
        "goal": "Analyze data",
        "backstory": "You are a data analyst"
      }
    ],
    "tasks": [
      {
        "description": "Analyze the input data",
        "agent": "Analyst"
      }
    ]
  },
  "inputs": {
    "data": "sample data"
  }
}
```

### Format 4: Batch Tasks (requires [crewai])

```json
{
  "version": "1.0",
  "type": "batch",
  "batch": {
    "id": "my_batch",
    "name": "Batch Analysis",
    "works": {
      "data_collection": {
        "agents": [
          {
            "role": "Collector",
            "goal": "Collect data"
          }
        ],
        "tasks": [
          {
            "description": "Collect data",
            "agent": "Collector"
          }
        ]
      },
      "data_analysis": {
        "agents": [
          {
            "role": "Analyst",
            "goal": "Analyze data"
          }
        ],
        "tasks": [
          {
            "description": "Analyze data",
            "agent": "Analyst"
          }
        ]
      }
    }
  },
  "inputs": {
    "url": "https://example.com"
  }
}
```

## CLI Implementation Structure

```
cli/
├── main.py              # Main CLI entry point
└── commands/
    ├── run.py           # Task execution (tasks.json, batch, crew)
    ├── status.py        # Task status checking
    ├── list.py          # List resources (batches, crews, tasks)
    ├── serve.py         # API server management
    ├── daemon.py        # Daemon service management
    └── config.py        # Configuration management
```

## Implementation Notes

### tasks.json Parser

1. **Detect format**: Check `type` field or structure to determine format
2. **Validate**: Use JSON Schema to validate structure
3. **Convert**: Convert to internal TaskModel format
4. **Execute**: Use TaskManager or appropriate executor

### Error Handling

- Validate tasks.json format before execution
- Provide clear error messages for invalid formats
- Support dry-run mode to validate without execution

### Output Formats

- Default: Pretty-printed JSON to stdout
- File output: Save to specified file
- Streaming: Real-time progress updates (for long-running tasks)

