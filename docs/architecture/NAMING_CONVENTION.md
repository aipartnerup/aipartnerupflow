# Naming Convention: extensions/ vs examples/

## Overview

This document clarifies the distinction between `extensions/` and `examples/` directories in the aipartnerupflow project.

## Directory Purposes

### 1. `extensions/` - Framework Extensions

**Purpose**: Framework-provided, production-ready optional extensions

**Characteristics**:
- ✅ Production-grade implementations
- ✅ Full test coverage
- ✅ Maintained by framework maintainers
- ✅ Can have heavy dependencies
- ✅ Installed via extras: `[crewai]`, `[stdio]`
- ✅ Direct use in production
- ✅ Registered through `ExtensionRegistry` system

**Examples**:
- `extensions/crewai/` - CrewAI executor (LLM tasks)
- `extensions/stdio/` - Stdio executor (local command execution)

**Location**: `src/aipartnerupflow/extensions/`

### 2. `examples/` - Learning Templates

**Purpose**: Example implementations for learning and quick start

**Characteristics**:
- ✅ Simple, easy to understand
- ✅ Minimal dependencies
- ✅ Learning and documentation purposes
- ✅ Users copy and customize for their own use
- ✅ Installed via: `[examples]` extra

**Examples**:
- `examples/crews/` - Example CrewManager implementations
- `examples/flows/` - Example task flows
- `examples/tasks/` - Example custom ExecutableTask implementations

**Location**: `src/aipartnerupflow/examples/`

**NOT for**: Production use (users should create their own)

## Comparison Table

| Aspect | extensions/ | examples/ |
|--------|-------------|-----------|
| **Purpose** | Production-ready extensions | Learning templates |
| **Maintainer** | Framework maintainers | Framework maintainers |
| **Quality** | Production-grade, fully tested | Simple examples |
| **Dependencies** | Can be heavy | Minimal |
| **Installation** | `[crewai]`, `[stdio]`, etc. | `[examples]` |
| **Usage** | Direct use in production | Copy and customize |
| **Registration** | Auto-registered via `@extension_register` | Not registered |
| **Example** | CrewManager, StdioExecutor | Example crew, example flow |
| **Status** | ✅ Implemented | ✅ Current |

## Key Distinction

- **`extensions/`** = "What the framework provides for you to use"
- **`examples/`** = "How to implement your own"

## Extension System

All extensions in `extensions/` must:
1. Implement `ExecutableTask` interface (or extend `BaseTask`)
2. Use `@extension_register()` decorator for auto-registration
3. Be registered in `ExtensionRegistry` by unique ID
4. Follow the unified extension system architecture

See [EXTENSION_REGISTRY_DESIGN.md](EXTENSION_REGISTRY_DESIGN.md) for details.

## Summary

- **`extensions/`**: Framework-provided, production-ready executors (CrewAI, Stdio, etc.)
- **`examples/`**: Learning templates (copy and customize)

The distinction is clear:
- Use `extensions/` for production-ready, reusable components
- Use `examples/` for learning and reference implementations
