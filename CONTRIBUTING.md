# Contributing to python-introspect

Thank you for your interest in contributing to python-introspect! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/python-introspect.git
   cd python-introspect
   ```

3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/trissim/python-introspect.git
   ```

## Development Setup

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install the package in development mode with dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

This will install:
- pytest and pytest-cov for testing
- ruff for linting
- black for code formatting
- mypy for type checking

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run with coverage report
```bash
pytest tests/ --cov=python_introspect --cov-report=term --cov-report=html
```

View the HTML coverage report by opening `htmlcov/index.html` in your browser.

### Run specific test file
```bash
pytest tests/test_signature_analyzer.py
```

### Run specific test function
```bash
pytest tests/test_signature_analyzer.py::TestSignatureAnalyzer::test_analyze_simple_function
```

### Run with verbose output
```bash
pytest tests/ -v
```

## Code Style

We use automated tools to maintain consistent code style:

### Linting with ruff
```bash
# Check for linting issues
ruff check src/ tests/

# Auto-fix issues where possible
ruff check src/ tests/ --fix
```

### Formatting with black
```bash
# Check formatting
black --check src/ tests/

# Auto-format code
black src/ tests/
```

### Type checking with mypy
```bash
mypy src/python_introspect/
```

### Run all checks
```bash
# Run all quality checks at once
ruff check src/ tests/ && \
black --check src/ tests/ && \
mypy src/python_introspect/ && \
pytest tests/ -v
```

## Code Guidelines

### General Principles

1. **Clarity over cleverness** - Write code that is easy to understand
2. **Document your code** - Use docstrings for all public APIs
3. **Test your code** - Add tests for new features and bug fixes
4. **Follow conventions** - Match the existing code style
5. **Keep it simple** - Avoid unnecessary complexity

### Docstring Style

Use Google-style docstrings:

```python
def analyze_function(func: Callable) -> Dict[str, ParameterInfo]:
    """Extract parameter information from a function.

    Args:
        func: The function to analyze

    Returns:
        Dictionary mapping parameter names to ParameterInfo objects

    Raises:
        SignatureAnalysisError: If function signature cannot be analyzed

    Examples:
        >>> def example(x: int, y: str = "test"):
        ...     pass
        >>> params = analyze_function(example)
        >>> params["x"].param_type
        <class 'int'>
    """
    pass
```

### Type Hints

- Use type hints for all function parameters and return values
- Use `typing` module for complex types (List, Dict, Optional, etc.)
- Keep type hints accurate and up-to-date

### Testing Guidelines

1. **Test coverage** - Aim for high test coverage (>90%)
2. **Test naming** - Use descriptive test names: `test_analyze_function_with_defaults`
3. **Test organization** - Group related tests in classes
4. **Test independence** - Tests should not depend on each other
5. **Edge cases** - Test edge cases and error conditions

## Submitting Changes

### Before Submitting

1. Ensure all tests pass:
   ```bash
   pytest tests/
   ```

2. Ensure code meets style guidelines:
   ```bash
   black src/ tests/
   ruff check src/ tests/
   ```

3. Update documentation if needed

4. Add tests for new features

### Creating a Pull Request

1. Create a new branch for your changes:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. Make your changes and commit them:
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

3. Push to your fork:
   ```bash
   git push origin feature/my-new-feature
   ```

4. Open a Pull Request on GitHub

### Pull Request Guidelines

- **Title**: Use a clear, descriptive title
- **Description**: Explain what changes you made and why
- **Link issues**: Reference any related issues
- **Tests**: Include tests for new functionality
- **Documentation**: Update docs if needed
- **One feature per PR**: Keep PRs focused on a single feature or fix

### Commit Message Format

Use clear, descriptive commit messages:

```
Add feature: support for parsing NumPy-style docstrings

- Implement NumPy docstring parser
- Add tests for NumPy format
- Update documentation with examples
```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the bug
2. **Steps to reproduce**: Minimal code to reproduce the issue
3. **Expected behavior**: What you expected to happen
4. **Actual behavior**: What actually happened
5. **Environment**: Python version, OS, package version
6. **Traceback**: Full error traceback if applicable

Example:

```markdown
## Bug: SignatureAnalyzer fails on dataclasses with factory defaults

### Description
SignatureAnalyzer raises AttributeError when analyzing dataclasses with default_factory.

### Steps to Reproduce
```python
from dataclasses import dataclass, field
from python_introspect import SignatureAnalyzer

@dataclass
class Config:
    items: list = field(default_factory=list)

analyzer = SignatureAnalyzer()
analyzer.analyze(Config)  # Raises AttributeError
```

### Expected Behavior
Should successfully analyze the dataclass and return parameter info.

### Environment
- Python 3.11
- python-introspect 0.1.0
- Ubuntu 22.04
```

### Feature Requests

When requesting features, please include:

1. **Use case**: Describe the problem you're trying to solve
2. **Proposed solution**: How you'd like it to work
3. **Alternatives**: Other approaches you've considered
4. **Additional context**: Any other relevant information

## Development Workflow

### Keeping Your Fork Updated

```bash
# Fetch upstream changes
git fetch upstream

# Merge upstream main into your local main
git checkout main
git merge upstream/main

# Push updates to your fork
git push origin main
```

### Working on Multiple Features

```bash
# Create separate branches for each feature
git checkout -b feature/feature-1
# Work on feature 1...

git checkout main
git checkout -b feature/feature-2
# Work on feature 2...
```

## Questions?

If you have questions about contributing:

1. Check existing issues and discussions
2. Open a new issue with the "question" label
3. Reach out to the maintainers

## License

By contributing to python-introspect, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Thank you for contributing to python-introspect! Your efforts help make this project better for everyone.
