# python-introspect

Extensible analysis of callable signatures, dataclass fields, type hints, and
docstrings.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/python-introspect.svg)](https://badge.fury.io/py/python-introspect)

## Quick start

```python
from python_introspect import SignatureAnalyzer

def resize(image, factor: float = 0.5, *, preserve_range: bool = True):
    """Resize an image.

    Args:
        image: Input image.
        factor: Scale factor.
        preserve_range: Preserve the input intensity range.
    """

parameters = SignatureAnalyzer().analyze(resize)

for name, info in parameters.items():
    print(name, info.param_type, info.default_value, info.is_required)
```

``analyze`` is the unified entry point for functions, methods, classes,
dataclass types, and instances. It returns a mapping of names to
``ParameterInfo`` records.

## Extension points

Use ``register_namespace_provider`` to contribute names used while resolving
forward references and ``register_type_resolver`` to unwrap application proxy
types. Wrappers can declare their user-facing inspection target through the
signature-target helpers in ``python_introspect.signature_analyzer``.

## Installation

```bash
python -m pip install python-introspect
```

The runtime depends on metaclass-registry. Repository and issues:
[OpenHCSDev/python-introspect](https://github.com/OpenHCSDev/python-introspect).

## Documentation

The maintained sources are in [`docs/source`](docs/source). Documentation
changes are checked by the repository's [documentation
workflow](https://github.com/OpenHCSDev/python-introspect/actions/workflows/docs.yml);
the local warnings-as-errors build command is documented in
[`development.rst`](docs/source/development.rst).
