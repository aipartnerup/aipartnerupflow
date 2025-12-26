# Contributing to aipartnerupflow

Thank you for your interest in contributing to aipartnerupflow! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect different viewpoints and experiences

## How to Contribute

### Reporting Bugs

1. **Check existing issues**: Search [GitHub Issues](https://github.com/aipartnerup/aipartnerupflow/issues) to see if the bug is already reported
2. **Create a new issue**: If not found, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (Python version, OS, etc.)
   - Error messages or logs

### Suggesting Features

1. **Check existing discussions**: Search [GitHub Discussions](https://github.com/aipartnerup/aipartnerupflow/discussions)
2. **Create a feature request**: Include:
   - Use case and motivation
   - Proposed solution
   - Alternatives considered
   - Impact on existing code

### Contributing Code

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/my-feature`
3. **Make your changes**
4. **Write/update tests**
5. **Ensure all tests pass**: `pytest`
6. **Update documentation** if needed
7. **Commit your changes**: Follow commit message guidelines
8. **Push to your fork**: `git push origin feature/my-feature`
9. **Create a Pull Request**

## Development Setup

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed setup instructions.

**Quick Setup:**
```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/aipartnerupflow.git
cd aipartnerupflow

# Create virtual environment
python3.10+ -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[all,dev]"

# Run tests
pytest
```

## Code Style

### Python Code

We use:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **mypy** for type checking (optional, not strict)

**Format code:**
```bash
black src/ tests/
ruff check src/ tests/
```

**Configuration:** See `pyproject.toml` for tool settings.

### Code Style Guidelines

1. **Type Hints**: Use type hints for function parameters and return values
   ```python
   async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
       ...
   ```

2. **Docstrings**: Use Google-style docstrings
   ```python
   def my_function(param: str) -> int:
       """
       Brief description.
       
       Args:
           param: Parameter description
       
       Returns:
           Return value description
       """
   ```

3. **Naming Conventions**:
   - Classes: `PascalCase`
   - Functions/Methods: `snake_case`
   - Constants: `UPPER_SNAKE_CASE`
   - Private: Prefix with `_`

4. **Imports**: Organize imports:
   ```python
   # Standard library
   import asyncio
   from typing import Dict, Any
   
   # Third-party
   import aiohttp
   from pydantic import BaseModel
   
   # Local
   from aipartnerupflow import ExecutableTask
   ```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/aipartnerupflow --cov-report=html

# Run specific test file
pytest tests/core/execution/test_task_manager.py

# Run with verbose output
pytest -v
```

### Writing Tests

1. **Test files**: Place in `tests/` directory, mirroring source structure
2. **Test functions**: Prefix with `test_`
3. **Use fixtures**: See `tests/conftest.py` for available fixtures
4. **Async tests**: Use `@pytest.mark.asyncio` for async functions
5. **Test isolation**: Ensure tests don't depend on execution order or side effects from other tests

**Example:**
```python
import pytest
from aipartnerupflow import TaskManager, create_session

@pytest.mark.asyncio
async def test_task_creation():
    """Test task creation"""
    db = create_session()
    task_manager = TaskManager(db)
    
    task = await task_manager.task_repository.create_task(
        name="test_task",
        user_id="test_user"
    )
    
    assert task.id is not None
    assert task.name == "test_task"
```

#### Test Isolation Best Practices

When writing tests that use the extension registry or other global state:

1. **Use `autouse=True` fixtures** to ensure required setup runs before each test:
   ```python
   @pytest.fixture(autouse=True)
   def ensure_executor_registered():
       """Ensure custom executor is registered before each test"""
       from aipartnerupflow.core.extensions import get_registry
       
       registry = get_registry()
       if not registry.is_registered("custom_executor"):
           registry.register(
               extension=CustomExecutor(),
               executor_class=CustomExecutor,
               override=True
           )
       yield
   ```

2. **Skip tests when optional dependencies are unavailable**:
   ```python
   from aipartnerupflow.extensions.llm.llm_executor import LITELLM_AVAILABLE
   
   @pytest.mark.skipif(not LITELLM_AVAILABLE, reason="litellm not installed")
   @pytest.mark.asyncio
   async def test_llm_feature():
       # Test code that requires litellm
       pass
   ```

3. **Clean up after tests** to avoid affecting other tests (fixtures handle this automatically for database sessions)

### Test Coverage

- Aim for high test coverage (>80%)
- Focus on critical paths and edge cases
- Test both success and failure scenarios

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Maintenance tasks

**Examples:**
```
feat(api): Add task cancellation endpoint

Add POST /tasks/cancel endpoint to support task cancellation.
Includes cancellation status tracking and cleanup.

Closes #123
```

```
fix(executor): Handle None inputs gracefully

Previously, None inputs would cause AttributeError.
Now returns empty dict as default.

Fixes #456
```

## Pull Request Process

### Before Submitting

1. **Update CHANGELOG.md**: Add entry under `[Unreleased]`
2. **Update documentation**: If adding features
3. **Run tests**: Ensure all tests pass
4. **Check code style**: Run `black` and `ruff`
5. **Update type hints**: If changing function signatures

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Tests added/updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated checks**: CI will run tests and linting
2. **Code review**: Maintainers will review your PR
3. **Address feedback**: Make requested changes
4. **Merge**: Once approved, maintainers will merge

## Project Structure

```
aipartnerupflow/
├── src/aipartnerupflow/    # Source code
│   ├── core/               # Core framework
│   ├── extensions/          # Extensions (crewai, stdio, etc.)
│   ├── api/                # API server
│   └── cli/                # CLI tools
├── tests/                   # Test suite
├── docs/                    # Documentation
└── scripts/                 # Utility scripts
```

See [DIRECTORY_STRUCTURE.md](../architecture/DIRECTORY_STRUCTURE.md) for details.

## Areas for Contribution

### High Priority

1. **Documentation**: Improve examples, tutorials, API docs
2. **Tests**: Increase test coverage, add integration tests
3. **Examples**: Add more practical examples
4. **Error Messages**: Improve error messages and debugging info

### Feature Areas

1. **New Executors**: Create executors for different use cases
2. **Storage Backends**: Add support for more databases
3. **Monitoring**: Add observability and monitoring features
4. **Performance**: Optimize task execution and storage

### Good First Issues

Look for issues tagged with `good-first-issue` on GitHub.

## Questions?

- **Documentation**: Check [docs/](../README.md)
- **Discussions**: [GitHub Discussions](https://github.com/aipartnerup/aipartnerupflow/discussions)
- **Issues**: [GitHub Issues](https://github.com/aipartnerup/aipartnerupflow/issues)

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 license.

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md (if we create one)
- Acknowledged in release notes for significant contributions
- Thanked in the project README

Thank you for contributing to aipartnerupflow! 🎉

