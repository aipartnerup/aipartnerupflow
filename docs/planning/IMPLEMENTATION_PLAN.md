# Architecture Implementation Plan

**Status**: Design phase - Implementation tasks based on latest architecture design

This document outlines the implementation plan to align the codebase with the latest architecture design. The project is currently in the design phase, with some code already written, and this plan details the steps needed to implement the designed architecture.

## Current Issues

1. **core/** contains CrewManager and BatchManager which depend on CrewAI
   - These should be optional features, not core
   - Core should only contain task orchestration specifications

2. **ext/** purpose is unclear
   - Currently only has example_flow.py
   - Should contain predefined example tasks, flows, crews

3. **CrewAI dependency in core**
   - crewai[tools] is in core dependencies
   - Should be in optional [crewai] extra

## New Architecture

### Core (pip install aipartnerupflow)

**Pure task orchestration framework - no CrewAI dependency**

```
aipartnerupflow/
├── execution/      # Task orchestration specifications (CORE)
│   ├── task_manager.py
│   └── streaming_callbacks.py
├── interfaces/     # Core interfaces
│   ├── plugin.py   # ExecutableTask, BaseTask
│   └── storage.py  # TaskStorage
├── storage/        # Storage implementation
└── utils/          # Utilities
```

### Optional Features

#### [crewai] - CrewAI LLM Task Support
```
features/crewai/
├── __init__.py
├── crew_manager.py  # CrewManager (moved from core/)
└── types.py         # CrewManagerState (moved from core/types.py)
```

#### [batch] - Batch Task Orchestration
```
features/batch/
├── __init__.py
├── batch_manager.py  # BatchManager (moved from core/)
└── types.py          # BatchState (moved from core/types.py)
```

**Note**: [batch] depends on [crewai] because BatchManager uses CrewManager

#### [examples] - Predefined Examples
```
examples/
├── crews/           # Example crews
│   └── example_crew.py
├── flows/           # Example batches
│   └── example_batch.py
└── tasks/           # Example custom tasks
    └── example_task.py
```

#### [api] - A2A Protocol Server
```
api/                 # A2A Protocol Server (A2A Protocol is the standard)
```

#### [cli] - CLI Tools
```
cli/                 # Command-line interface
```

## Implementation Steps

**Goal**: Implement the designed architecture from the current codebase state.

The following steps need to be executed to align the code with the architecture design documented in [ARCHITECTURE.md](../architecture/ARCHITECTURE.md).

### Phase 1: Move CrewAI to Features

1. Create `features/crewai/` directory structure
2. Move `core/crew_manager.py` → `features/crewai/crew_manager.py`
3. Move `core/batch_manager.py` → `features/crewai/batch_manager.py` (batch is part of crewai feature)
4. Split `core/types.py` → `features/crewai/types.py` (consolidate CrewManagerState and BatchState)
5. Move `services/task_planner.py` to `features/templates/` (template feature)

### Phase 2: Update Dependencies

5. Update `pyproject.toml`:
   - Remove `crewai[tools]` and `crewai-tools` from core dependencies
   - Add `crewai = ["crewai[tools]>=0.152.0", "crewai-tools>=0.59.0"]` to optional-dependencies
   - Note: `batch` is no longer separate - it's included in `crewai`

### Phase 3: Update Imports

6. Delete empty `src/aipartnerupflow/core/` directory (core modules are at top level)
7. Create `src/aipartnerupflow/features/crewai/__init__.py`:
   - Export CrewManager, BatchManager, and related types
8. Update `src/aipartnerupflow/__init__.py`:
   - Remove CrewManager, BatchManager imports (they're optional features now)
   - Add note that they're available via `from aipartnerupflow.features.crewai import ...`

### Phase 4: Rename ext/ to examples/

9. Rename `src/aipartnerupflow/ext/` → `src/aipartnerupflow/examples/`
10. Update `pyproject.toml`: `ext` → `examples` in optional-dependencies
11. Update all documentation references: `ext/` → `examples/`, `[ext]` → `[examples]`

### Phase 5: Update All References

12. Update all code imports:
   - `from aipartnerupflow.core import ...` → `from aipartnerupflow.features.crewai import ...` (if needed)
   - `from aipartnerupflow.ext import ...` → `from aipartnerupflow.examples import ...`
13. Update tests to use new import paths
14. Update API executor and other modules that reference these classes

## Installation Strategy

```bash
# Core only (pure orchestration framework)
pip install aipartnerupflow

# Core + CrewAI support
pip install aipartnerupflow[crewai]

# Core + CrewAI + Batch support
pip install aipartnerupflow[batch]  # includes crewai

# Core + Examples
pip install aipartnerupflow[examples]

# Full installation
pip install aipartnerupflow[all]  # includes crewai, examples, api, cli, postgres
```

