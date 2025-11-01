# python-introspect

**Pure Python introspection toolkit for function signatures, dataclasses, and type hints**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/trissim/python-introspect/actions/workflows/ci.yml/badge.svg)](https://github.com/trissim/python-introspect/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/python-introspect.svg)](https://badge.fury.io/py/python-introspect)

## Features

- 🔍 **Function/Method Signature Analysis** - Extract parameter info from any callable
- 📦 **Dataclass Field Extraction** - Analyze dataclass fields and types
- 📝 **Docstring Parsing** - Extract and parse docstrings (Google, NumPy, Sphinx styles)
- 🏷️ **Type Hint Resolution** - Resolve complex type hints and annotations
- 🎯 **Unified API** - Single interface for all parameter sources
- 🚀 **Pure Python** - No external dependencies, pure stdlib

## Installation

```bash
pip install python-introspect
```

## Quick Start

```python
from python_introspect import SignatureAnalyzer

def example_function(name: str, age: int = 25, *, active: bool = True):
    """
    Example function with parameters.
    
    Args:
        name: The person's name
        age: The person's age
        active: Whether the person is active
    """
    pass

# Analyze the function
analyzer = SignatureAnalyzer()
params = analyzer.analyze_function(example_function)

for param in params:
    print(f"{param.name}: {param.annotation} = {param.default}")
```

## Use Cases

- **Form Generation** - Generate UI forms from function signatures
- **API Documentation** - Auto-generate API docs from code
- **Configuration Validation** - Validate config against function parameters
- **Dynamic UI** - Build dynamic UIs based on function signatures
- **Parameter Analysis** - Analyze and validate function parameters

## Documentation

Full documentation available at: https://github.com/trissim/python-introspect

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/trissim/python-introspect.git
cd python-introspect

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=python_introspect --cov-report=term --cov-report=html

# Run linting and formatting checks
ruff check src/ tests/
black --check src/ tests/
mypy src/python_introspect/
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Credits

Developed by Tristan Simas as part of the OpenHCS project.
