# python-introspect

Extensible analysis of callable signatures, dataclass fields, type hints, and
docstrings, plus signature-derived callable declaration projection.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
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

Use ``callable_declaration_kwargs`` when declaration identity should omit
keyword arguments equal to their signature defaults. The caller supplies value
equality so array, lazy, or other framework-specific values keep their owning
semantics.

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

### Parameter declarations in 0.2

`UnifiedParameterAnalyzer` now returns the original `ParameterInfo` declarations
from `SignatureAnalyzer`. `UnifiedParameterInfo`, its `source_type` tag, and
`analyze_nested` were removed. Use `analyze` and the declared `param_type` for
parameter topology.

`ParameterInfo` retains its five public fields, constructor and `_replace`
operation, and is now a frozen declaration rather than a tuple. Tuple unpacking
and NamedTuple helpers are no longer supported. Dataclass descriptions are
derived on first help access; value/default overlays preserve that deferred
source, and renaming preserves the original field's help. Callable descriptions
still participate eagerly in inferred parameter types. A presentation extraction
error yields absent help without discarding valid types/defaults. Factory errors
remain uncached and retryable.
