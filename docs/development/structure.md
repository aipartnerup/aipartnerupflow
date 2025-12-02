# Documentation Structure

## Organization

Documentation is organized into the following categories:

```
docs/
├── README.md                    # Documentation index
├── structure.md                 # This file - documentation structure overview
├── getting-started/             # Getting started guides
│   ├── installation.md         # Installation instructions
│   ├── quick-start.md          # 5-minute quick start guide
│   └── examples.md             # Quick examples
├── guides/                      # User guides (merged usage + user-guide)
│   ├── task-orchestration.md   # Task orchestration guide
│   ├── custom-tasks.md         # Custom tasks creation guide
│   ├── cli.md                  # CLI usage documentation
│   └── api-server.md           # API server setup and usage guide
├── api/                         # API reference documentation
│   ├── python.md               # Python library API reference
│   └── http.md                 # HTTP API reference (A2A Protocol Server)
├── examples/                    # Code examples and tutorials
│   ├── basic_task.md           # Basic task examples and common patterns
│   └── task-tree.md            # Task tree examples with dependencies
├── architecture/                # Architecture and design documents
│   ├── overview.md             # System architecture and design principles
│   ├── directory-structure.md  # Directory structure and naming conventions
│   ├── naming-convention.md    # Naming conventions for extensions
│   ├── extension-registry-design.md  # Extension registry design (Protocol-based)
│   └── configuration.md        # Database table configuration
└── development/                 # Development guides
    ├── setup.md                # Development setup guide for contributors
    ├── extending.md             # Guide for extending the framework
    ├── contributing.md         # Contribution guidelines and process
    ├── design/                  # Design documents for specific features
    │   ├── cli-design.md       # CLI design and implementation
    │   └── aggregate-results-design.md  # Aggregate results executor design
    └── planning/               # Planning documents (historical reference)
        ├── implementation-plan.md  # Architecture implementation plan (completed)
        └── task-tree-dependent-validation.md  # Task tree validation planning
```

## Root Directory Files

These files remain in the root directory for visibility:

- **README.md** - Main user guide and quick start (must be in root for GitHub/PyPI)
- **CHANGELOG.md** - Version history and changes (standard location)
- **LICENSE** - License file (standard location)

## Documentation Categories

### Getting Started (`docs/getting-started/`)

Quick start guides and tutorials for new users.

**Purpose**: Help users get started quickly with the framework

**Contents**:
- Installation instructions
- Quick start guide (5-minute tutorial)
- Basic examples

### Guides (`docs/guides/`)

Comprehensive user guides for using aipartnerupflow.

**Purpose**: Detailed guides for using library features and tools

**Contents**:
- Task orchestration concepts and patterns
- Custom task creation and implementation
- CLI commands and workflows
- API server setup and configuration

**Note**: This directory merges the previous `usage/` (tool usage) and `user-guide/` (library features) directories for better organization.

### API Reference (`docs/api/`)

Complete API reference documentation.

**Purpose**: Detailed API documentation for all interfaces

**Contents**:
- **Python API** (`python.md`): Core Python library API reference (TaskManager, ExecutableTask, TaskTreeNode, etc.)
- **HTTP API** (`http.md`): A2A Protocol Server HTTP API reference

### Examples (`docs/examples/`)

Code examples and tutorials demonstrating common use cases and patterns.

**Purpose**: Practical examples to help users understand and apply the framework

**Contents**:
- Basic task examples
- Task tree examples with dependencies
- Common patterns and use cases

### Architecture (`docs/architecture/`)

Detailed technical documentation about system design, architecture decisions, and design patterns.

**Purpose**: Deep dive into system architecture and design

**Contents**:
- System architecture overview
- Directory structure and organization
- Naming conventions
- Extension registry design
- Configuration options

### Development (`docs/development/`)

Guides for developers contributing to the project.

**Purpose**: Information for contributors and framework extenders

**Contents**:
- Development setup and workflow
- Extending the framework (custom executors, extensions, hooks)
- Contribution guidelines and process
- Design documents for specific features
- Planning documents (historical reference)

**Subdirectories**:
- `design/`: Design documents for specific features
- `planning/`: Historical planning documents (completed implementations)

## Structure Rationale

This structure follows industry-standard patterns from popular open-source projects:

- **FastAPI**: Tutorials → User Guide → Advanced → API Reference
- **Django**: Getting Started → Topics → How-to → API Reference
- **LangChain**: Getting Started → Modules → Use Cases → API

**Key improvements from previous structure**:
1. Reduced from 11 top-level directories to 6
2. Merged related content (`usage/` + `user-guide/` → `guides/`)
3. Unified API documentation (Python + HTTP → `api/`)
4. Consolidated configuration into architecture
5. Organized development docs with subdirectories
6. Removed empty directories

## Navigation Flow

Typical user journey through the documentation:

1. **New Users**: `getting-started/` → `guides/` → `examples/`
2. **API Users**: `api/` → `examples/`
3. **Framework Extenders**: `guides/custom-tasks.md` → `development/extending.md` → `architecture/`
4. **Contributors**: `development/setup.md` → `development/contributing.md` → `architecture/`
