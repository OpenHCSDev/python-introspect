"""
python-introspect: Pure Python introspection toolkit

This package provides utilities for introspecting Python functions, methods,
dataclasses, and type hints.
"""

__version__ = "0.1.2"

from .signature_analyzer import (
    SignatureAnalyzer,
    ParameterInfo,
    DocstringInfo,
    DocstringExtractor,
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

__all__ = [
    # Version
    "__version__",
    # Signature analysis
    "SignatureAnalyzer",
    "ParameterInfo",
    "DocstringInfo",
    "DocstringExtractor",
    # Unified analysis
    "UnifiedParameterAnalyzer",
    "UnifiedParameterInfo",
    # Plugin system
    "register_namespace_provider",
    "register_type_resolver",
    # Exceptions
    "IntrospectionError",
    "SignatureAnalysisError",
    "DocstringParsingError",
    "TypeResolutionError",
]
