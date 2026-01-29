"""
python-introspect: Pure Python introspection toolkit

This package provides utilities for introspecting Python functions, methods,
dataclasses, and type hints.

Extensibility:
    Use register_namespace_provider() and register_type_resolver() to extend
    type resolution for framework-specific types (lazy configs, proxies, etc.)
"""

__version__ = "0.1.3"

from .signature_analyzer import (
    SignatureAnalyzer,
    ParameterInfo,
    DocstringInfo,
    DocstringExtractor,
    # Plugin registration
    register_namespace_provider,
    register_type_resolver,
)
from .unified_parameter_analyzer import (
    UnifiedParameterAnalyzer,
    UnifiedParameterInfo,
)
from .exceptions import (
    IntrospectionError,
    SignatureAnalysisError,
    DocstringParsingError,
    TypeResolutionError,
)
from .enableable import (
    Enableable,
    is_enableable,
    mark_enableable,
    ENABLED_FIELD,
)

__all__ = [
    # Version
    "__version__",
    # Signature analysis
    "SignatureAnalyzer",
    "ParameterInfo",
    "DocstringInfo",
    "DocstringExtractor",
    # Plugin registration
    "register_namespace_provider",
    "register_type_resolver",
    # Unified analysis
    "UnifiedParameterAnalyzer",
    "UnifiedParameterInfo",
    # Exceptions
    "IntrospectionError",
    "SignatureAnalysisError",
    "DocstringParsingError",
    "TypeResolutionError",
    # Enableable
    "Enableable",
    "is_enableable",
    "mark_enableable",
    "ENABLED_FIELD",
]
