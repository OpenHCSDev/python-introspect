"""
python-introspect: Pure Python introspection toolkit

This package provides utilities for introspecting Python functions, methods,
dataclasses, and type hints.

Extensibility:
    Use register_namespace_provider() and register_type_resolver() to extend
    type resolution for framework-specific types (lazy configs, proxies, etc.)
"""

__version__ = "0.1.7"

from .signature_analyzer import (
    SignatureAnalyzer,
    ParameterInfo,
    DocstringInfo,
    DocstringExtractor,
    # Plugin registration
    register_namespace_provider,
    register_type_resolver,
    set_signature_analysis_target,
    signature_analysis_target,
)
from .unified_parameter_analyzer import (
    UnifiedParameterAnalyzer,
    UnifiedParameterInfo,
    add_parameter_exclusions,
    set_parameter_exclusions,
    parameter_exclusions,
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
)
from .validation import (
    AnnotatedDataclassValidationMixin,
    AnnotationValidationError,
    overlay_non_none_dataclass,
    validate_annotated_dataclass,
    validate_annotation_value,
)
from .dataclass_projection import (
    dataclass_from_mapping,
    project_dataclass,
)
from .environment_projection import (
    EnvironmentVariable,
    overlay_dataclass_from_environment,
)
from .annotation_types import (
    enum_member_type,
    get_enum_from_list,
    is_enum_type,
    is_list_of_enums,
    is_union_type,
    make_optional,
    optional_member_type,
    resolve_annotated,
    resolve_optional,
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
    "set_signature_analysis_target",
    "signature_analysis_target",
    # Unified analysis
    "UnifiedParameterAnalyzer",
    "UnifiedParameterInfo",
    "add_parameter_exclusions",
    "set_parameter_exclusions",
    "parameter_exclusions",
    # Exceptions
    "IntrospectionError",
    "SignatureAnalysisError",
    "DocstringParsingError",
    "TypeResolutionError",
    # Enableable
    "Enableable",
    "is_enableable",
    "mark_enableable",
    # Runtime annotation validation
    "AnnotatedDataclassValidationMixin",
    "AnnotationValidationError",
    "overlay_non_none_dataclass",
    "validate_annotated_dataclass",
    "validate_annotation_value",
    # Dataclass projection
    "dataclass_from_mapping",
    "project_dataclass",
    # Environment projection
    "EnvironmentVariable",
    "overlay_dataclass_from_environment",
    # Annotation type operations
    "enum_member_type",
    "get_enum_from_list",
    "is_enum_type",
    "is_list_of_enums",
    "is_union_type",
    "make_optional",
    "optional_member_type",
    "resolve_annotated",
    "resolve_optional",
]
