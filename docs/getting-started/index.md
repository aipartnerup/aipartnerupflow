# Getting Started with aipartnerupflow

Welcome to aipartnerupflow! This guide will help you get started quickly, whether you're new to task orchestration or an experienced developer.

## What is aipartnerupflow?

**aipartnerupflow** is a Python framework for orchestrating and executing tasks. Think of it as a conductor for your application's tasks - it manages when tasks run, how they depend on each other, and ensures everything executes in the right order.

### Key Benefits

- **Simple Task Management**: Create, organize, and execute tasks with ease
- **Dependency Handling**: Tasks automatically wait for their dependencies to complete
- **Flexible Execution**: Support for custom tasks, LLM agents (CrewAI), and more
- **Production Ready**: Built-in storage, streaming, and API support
- **Extensible**: Easy to add custom task types and integrations

## Quick Navigation

### 🚀 New to aipartnerupflow?

Start here if you're completely new:

1. **[Core Concepts](concepts.md)** - Learn the fundamental ideas (5 min read)
2. **[Quick Start Guide](quick-start.md)** - Build your first task (10 min)
3. **[First Steps Tutorial](tutorials/tutorial-01-first-steps.md)** - Complete beginner tutorial

### 📚 Already familiar?

Jump to what you need:

- **[Examples](examples.md)** - Copy-paste ready examples
- **[Task Orchestration Guide](../guides/task-orchestration.md)** - Deep dive into task management
- **[Custom Tasks Guide](../guides/custom-tasks.md)** - Create your own task types
- **[API Reference](../api/python.md)** - Complete API documentation

### 🎯 What do you want to do?

**I want to...**

- **Execute simple tasks** → [Quick Start](quick-start.md)
- **Build complex workflows** → [Task Orchestration Guide](../guides/task-orchestration.md)
- **Create custom task types** → [Custom Tasks Guide](../guides/custom-tasks.md)
- **Use LLM agents** → [CrewAI Examples](../examples/basic_task.md#example-4-using-crewai-llm-tasks)
- **Understand the architecture** → [Architecture Overview](../architecture/overview.md)

## Core Concepts at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                    Your Application                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              aipartnerupflow Framework                   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Task 1     │  │   Task 2     │  │   Task 3     │ │
│  │  (Fetch)    │  │  (Process)   │  │  (Save)      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                  │         │
│         └─────────────────┼──────────────────┘         │
│                           │                             │
│                    Dependencies                          │
│              (Task 2 waits for Task 1)                  │
│                                                          │
│              TaskManager orchestrates                   │
│              execution order automatically              │
└─────────────────────────────────────────────────────────┘
```

### The Basics

- **Task**: A unit of work (e.g., "fetch data", "process file", "send email")
- **Task Tree**: A hierarchical structure organizing related tasks
- **Dependencies**: Relationships that control execution order
- **Executor**: The code that actually runs a task
- **TaskManager**: The orchestrator that manages task execution

## Installation

Choose your installation based on what you need:

```bash
# Minimal: Core orchestration only
pip install aipartnerupflow

# With LLM support (CrewAI)
pip install aipartnerupflow[crewai]

# With API server
pip install aipartnerupflow[a2a]

# With CLI tools
pip install aipartnerupflow[cli]

# Everything
pip install aipartnerupflow[all]
```

See [Installation Guide](installation.md) for details.

## Your First 5 Minutes

Here's the fastest way to see aipartnerupflow in action:

```python
from aipartnerupflow import TaskManager, TaskTreeNode, create_session
import asyncio

async def main():
    # 1. Create a database session
    db = create_session()
    
    # 2. Create a task manager
    task_manager = TaskManager(db)
    
    # 3. Create a simple task
    task = await task_manager.task_repository.create_task(
        name="system_info_executor",  # Built-in executor
        user_id="user123",
        inputs={"resource": "cpu"}
    )
    
    # 4. Build and execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # 5. Check the result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Task completed: {result.status}")
    print(f"Result: {result.result}")

asyncio.run(main())
```

**That's it!** You just executed your first task. 

👉 **Next**: Read [Core Concepts](concepts.md) to understand what just happened, or jump to [Quick Start](quick-start.md) for a more detailed walkthrough.

## Learning Paths

### Path 1: Quick Learner (30 minutes)
1. [Core Concepts](concepts.md) (5 min)
2. [Quick Start](quick-start.md) (10 min)
3. [Basic Examples](../examples/basic_task.md) (15 min)

### Path 2: Comprehensive (2 hours)
1. [Core Concepts](concepts.md)
2. [Quick Start](quick-start.md)
3. [First Steps Tutorial](tutorials/tutorial-01-first-steps.md)
4. [Task Trees Tutorial](tutorials/tutorial-02-task-trees.md)
5. [Dependencies Tutorial](tutorials/tutorial-03-dependencies.md)

### Path 3: Professional Developer (4+ hours)
1. Complete Path 2
2. [Custom Tasks Guide](../guides/custom-tasks.md)
3. [Best Practices](../guides/best-practices.md)
4. [API Reference](../api/python.md)
5. [Advanced Topics](../advanced/extending.md)

## Common Questions

**Q: Do I need to know task orchestration?**  
A: No! Start with [Core Concepts](concepts.md) - we explain everything from scratch.

**Q: Can I use this without LLM/AI?**  
A: Yes! The core framework has no AI dependencies. LLM support is optional via `[crewai]`.

**Q: Is this production-ready?**  
A: Yes! It includes storage, error handling, streaming, and API support out of the box.

**Q: How is this different from Celery/Airflow?**  
A: aipartnerupflow focuses on simplicity and flexibility. It's designed for both simple workflows and complex AI agent orchestration.

## Next Steps

- **New to task orchestration?** → Start with [Core Concepts](concepts.md)
- **Ready to code?** → Jump to [Quick Start](quick-start.md)
- **Want examples?** → Check [Examples](examples.md)
- **Need help?** → See [FAQ](../guides/faq.md)

---

**Ready to begin?** → [Start with Core Concepts →](concepts.md)

