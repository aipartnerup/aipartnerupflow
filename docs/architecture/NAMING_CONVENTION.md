# Naming Convention: features/ vs examples/ vs extensions/

## Current Issue

**Problem**: `ext/` is currently used for examples, but:
- `ext/` typically means "extensions" (extended features/plugins)  
- Current content is actually "examples" (learning templates)
- Creates confusion with `features/` (core optional features)

## Clear Distinctions

### 1. `features/` - Core Optional Features

**Purpose**: Framework-provided, production-ready optional features

**Characteristics**:
- ✅ Production-grade implementations
- ✅ Full test coverage
- ✅ Maintained by framework maintainers
- ✅ Can have heavy dependencies
- ✅ Installed via extras: `[crewai]`, `[http]`
- ✅ Direct use in production

**Examples**:
- `features/crewai/` - CrewAI executor (LLM tasks)
- `features/http_executor/` - HTTP executor (remote API calls)
- `features/shell_executor/` - Shell command executor (future)

### 2. `examples/` - Learning Templates (Rename from `ext/`)

**Purpose**: Example implementations for learning and quick start

**Characteristics**:
- ✅ Simple, easy to understand
- ✅ Minimal dependencies
- ✅ Learning and documentation purposes
- ✅ Users copy and customize for their own use
- ✅ Installed via: `[examples]` extra

**Examples**:
- `examples/crews/` - Example CrewManager implementations
- `examples/batches/` - Example BatchManager implementations
- `examples/tasks/` - Example custom ExecutableTask implementations

**NOT for**: Production use (users should create their own)

### 3. `extensions/` - Third-party Extensions (Future, optional)

**Purpose**: Extended functionality, plugins, or third-party integrations

**Characteristics**:
- 🔮 Future functionality
- 🔮 May be maintained by community
- 🔮 Optional installations
- 🔮 Can be separate packages: `aipartnerupflow-ext-openai`
- 🔮 Extend framework capabilities

**Potential Examples** (if implemented):
- `extensions/openai/` - OpenAI-specific integrations
- `extensions/aws/` - AWS service integrations
- `extensions/slack/` - Slack notification extensions

**Note**: Currently not implemented. Reserved for future extensibility.

## Comparison Table

| Aspect | features/ | examples/ | extensions/ (future) |
|--------|-----------|-----------|---------------------|
| **Purpose** | Core optional features | Learning templates | Third-party plugins |
| **Maintainer** | Framework maintainers | Framework maintainers | Community/third-party |
| **Quality** | Production-grade | Simple examples | Varies |
| **Dependencies** | Can be heavy | Minimal | Varies |
| **Installation** | `[crewai]`, `[http]` | `[examples]` | Separate packages |
| **Usage** | Direct use in production | Copy and customize | Extend framework |
| **Example** | CrewManager | Example crew | OpenAI plugin |
| **Status** | ✅ Implemented | ✅ Current (as ext/) | 🔮 Future |

## Recommended Changes

### Immediate: Rename `ext/` → `examples/`

**Reasons**:
1. ✅ **Clearer naming**: `examples/` is self-explanatory
2. ✅ **Industry convention**: Most projects use `examples/` for example code
3. ✅ **Reserves naming space**: Keeps `ext/` or `extensions/` free for future plugin system
4. ✅ **Better discoverability**: Users naturally look for `examples/` directory

**Changes needed**:
1. Rename `src/aipartnerupflow/ext/` → `src/aipartnerupflow/examples/`
2. Update `pyproject.toml`: `ext` → `examples` in optional-dependencies
3. Update `[all]` extra: `ext` → `examples`
4. Update all documentation (README, ARCHITECTURE, DEVELOPMENT, etc.)

### Future: Use `extensions/` for plugin system (if needed)

If we want to support extensions in the future, use `extensions/` directory or separate packages.

## Summary

- **`features/`**: Framework-provided, production-ready executors (CrewAI, HTTP, etc.)
- **`examples/`**: Learning templates (rename from `ext/`)
- **`extensions/`**: Future third-party plugins/extensions (reserved for future)

The key distinction:
- **`features/`** = "What the framework provides for you to use"
- **`examples/`** = "How to implement your own"
- **`extensions/`** = "How others extend the framework" (future)

