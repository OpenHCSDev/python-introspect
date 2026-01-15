---
title: 'python-introspect: Unified Callable Introspection for Functions, Dataclasses, and Type Hints'
tags:
  - Python
  - introspection
  - type hints
  - dataclasses
  - code generation
authors:
  - name: Tristan Simas
    orcid: 0000-0002-6526-3149
    affiliation: 1
affiliations:
  - name: McGill University
    index: 1
date: 15 January 2026
bibliography: paper.bib
---

# Summary

`python-introspect` provides a unified API for analyzing callables: functions, methods, dataclasses, and callable objects. The key insight: **all callables have parameters**. A function has parameters in its signature. A dataclass has parameters in its fields. A class has parameters in its `__init__`. A callable object has parameters in its `__call__`.

```python
from python_introspect import UnifiedParameterAnalyzer

analyzer = UnifiedParameterAnalyzer()

# All of these return the same ParameterInfo structure
params_func = analyzer.analyze(my_function)
params_dataclass = analyzer.analyze(MyDataclass)
params_class = analyzer.analyze(MyClass)
params_callable = analyzer.analyze(my_callable_object)
```

This enables form generation, API documentation, and dynamic UI creation from any callable without special-casing each type.

# Statement of Need

Python's introspection capabilities are scattered: `inspect.signature()` for functions, `dataclasses.fields()` for dataclasses, `typing.get_type_hints()` for type hints. Each has different APIs, different error handling, and different edge cases.

Applications that generate UIs from callables (like `pyqt-reactor`) must handle all these cases. Without `python-introspect`, this requires ~200 lines of boilerplate per application.

# Software Design

**Unified Parameter Analyzer**: Detects callable type (function, dataclass, class, callable object) and dispatches to the appropriate analyzer. Returns a consistent `ParameterInfo` structure for all types:

```python
@dataclass
class ParameterInfo(NamedTuple):
    name: str
    param_type: type
    default_value: Any
    is_required: bool
    description: Optional[str] = None
```

**Docstring Extraction**: Parses Google, NumPy, and Sphinx-style docstrings to extract parameter descriptions. Integrates with parameter analysis to provide complete documentation:

```python
def gaussian_filter(image, sigma=1.0, preserve_range=False):
    """Apply Gaussian filter.

    Args:
        image: Input image array
        sigma: Standard deviation of the Gaussian kernel
        preserve_range: Whether to preserve the input range
    """
    pass

# Analyzer extracts both signature and docstring descriptions
params = analyzer.analyze(gaussian_filter)
# params[1].description == "Standard deviation of the Gaussian kernel"
```

**Type Hint Resolution**: Handles forward references, generic types, and optional types. Resolves type hints in the context of the callable's module.

# Research Application

`python-introspect` powers form generation in `pyqt-reactor`, enabling the GUI to generate parameter forms from any function signature without special-casing each type. A user can register any Python function as a pipeline step, and the GUI automatically generates a form with proper type validation and docstring-based help text.

# References

