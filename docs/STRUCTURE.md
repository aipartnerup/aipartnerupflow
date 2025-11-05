# Documentation Structure

## Organization

Documentation is organized into the following categories:

```
docs/
├── README.md                    # Documentation index
├── architecture/                # Architecture and design documents
│   ├── ARCHITECTURE.md          # System architecture and design principles
│   ├── DIRECTORY_STRUCTURE.md   # Directory structure and naming conventions
│   ├── NAMING_CONVENTION.md     # Naming conventions for extensions and examples
│   └── EXTENSION_REGISTRY_DESIGN.md  # Extension registry design (Protocol-based)
├── development/                 # Development guides
│   ├── DEVELOPMENT.md          # Development guide for contributors
│   └── CLI_DESIGN.md           # CLI design and implementation
└── planning/                    # Planning and reference documents
    └── IMPLEMENTATION_PLAN.md   # Architecture implementation plan (design phase tasks)
```

## Root Directory Files

These files remain in the root directory for visibility:

- **README.md** - Main user guide and quick start (must be in root for GitHub/PyPI)
- **CHANGELOG.md** - Version history and changes (standard location)
- **LICENSE** - License file (standard location)

## Documentation Categories

### Architecture Documents (`docs/architecture/`)
Detailed technical documentation about system design, architecture decisions, and design patterns.

### Development Documents (`docs/development/`)
Guides for developers contributing to the project.

### Planning Documents (`docs/planning/`)
Planning documents and implementation plans. Currently contains the implementation plan for aligning code with the designed architecture.

