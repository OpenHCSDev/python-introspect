"""Unified parameter analysis interface for all parameter sources in OpenHCS TUI.

This module provides a single, consistent interface for analyzing parameters from:
- Functions and methods
- Dataclasses and their fields
- Nested dataclass structures
- Any callable or type with parameters

Replaces the fragmented approach of SignatureAnalyzer vs FieldIntrospector.
"""

import inspect
import dataclasses
from abc import ABC, abstractmethod
from typing import Dict, Union, Callable, Type, Any, Optional, ClassVar
from dataclasses import dataclass
from weakref import WeakKeyDictionary

from metaclass_registry import AutoRegisterMeta

from .signature_analyzer import SignatureAnalyzer, ParameterInfo


_parameter_exclusions: WeakKeyDictionary[object, frozenset[str]] = WeakKeyDictionary()
_parameter_exclusions_by_id: dict[int, tuple[object, frozenset[str]]] = {}


def set_parameter_exclusions(target: object, names: Union[str, list[str], tuple[str, ...], frozenset[str]]) -> None:
    """Declare parameter names hidden from unified parameter analysis."""
    normalized = frozenset((names,) if isinstance(names, str) else tuple(str(name) for name in names))
    try:
        _parameter_exclusions[target] = normalized
    except TypeError:
        _parameter_exclusions_by_id[id(target)] = (target, normalized)


def parameter_exclusions(target: object) -> frozenset[str]:
    """Return parameter names explicitly hidden for a target."""
    try:
        exclusions = _parameter_exclusions.get(target)
    except TypeError:
        exclusions = None
    if exclusions is not None:
        return exclusions

    fallback_record = _parameter_exclusions_by_id.get(id(target))
    if fallback_record is not None and fallback_record[0] is target:
        return fallback_record[1]
    return frozenset()


@dataclass
class UnifiedParameterInfo:
    """Unified parameter information that works for all parameter sources."""
    name: str
    param_type: Type
    default_value: Any
    is_required: bool
    description: Optional[str] = None
    source_type: str = "unknown"  # "function", "dataclass", "nested"
    
    @classmethod
    def from_parameter_info(cls, param_info: ParameterInfo, source_type: str = "function") -> "UnifiedParameterInfo":
        """Convert from existing ParameterInfo to unified format."""
        return cls(
            name=param_info.name,
            param_type=param_info.param_type,
            default_value=param_info.default_value,
            is_required=param_info.is_required,
            description=param_info.description,
            source_type=source_type
        )


class UnifiedParameterTargetAnalyzer(ABC, metaclass=AutoRegisterMeta):
    """Nominal target-kind family for unified parameter analysis."""

    __registry_key__ = "target_kind"
    __skip_if_no_key__ = True

    target_kind: ClassVar[Optional[str]] = None

    @classmethod
    def analyze_target(cls, target: Union[Callable, Type, object]) -> Dict[str, UnifiedParameterInfo]:
        """Analyze a target using the first registered target-kind analyzer."""
        for analyzer_cls in cls.__registry__.values():
            analyzer = analyzer_cls()
            if analyzer.matches(target):
                return analyzer.analyze(target)
        return ObjectInstanceTargetAnalyzer().analyze(target)

    @abstractmethod
    def matches(self, target: Union[Callable, Type, object]) -> bool:
        """Return whether this analyzer owns the target."""

    @abstractmethod
    def analyze(self, target: Union[Callable, Type, object]) -> Dict[str, UnifiedParameterInfo]:
        """Analyze the target."""


class CallableTargetAnalyzer(UnifiedParameterTargetAnalyzer):
    """Analyze functions, methods, and callable objects through SignatureAnalyzer."""

    target_kind = "callable"

    def matches(self, target: Union[Callable, Type, object]) -> bool:
        return callable(target) and not inspect.isclass(target)

    def analyze(self, target: Union[Callable, Type, object]) -> Dict[str, UnifiedParameterInfo]:
        return UnifiedParameterAnalyzer._analyze_callable(target)


class DataclassTypeTargetAnalyzer(UnifiedParameterTargetAnalyzer):
    """Analyze dataclass types."""

    target_kind = "dataclass_type"

    def matches(self, target: Union[Callable, Type, object]) -> bool:
        return inspect.isclass(target) and dataclasses.is_dataclass(target)

    def analyze(self, target: Union[Callable, Type, object]) -> Dict[str, UnifiedParameterInfo]:
        return UnifiedParameterAnalyzer._analyze_dataclass_type(target)


class ClassTargetAnalyzer(UnifiedParameterTargetAnalyzer):
    """Analyze non-dataclass classes through their constructor."""

    target_kind = "class"

    def matches(self, target: Union[Callable, Type, object]) -> bool:
        return inspect.isclass(target)

    def analyze(self, target: Union[Callable, Type, object]) -> Dict[str, UnifiedParameterInfo]:
        return UnifiedParameterAnalyzer._analyze_callable(target.__init__)


class DataclassInstanceTargetAnalyzer(UnifiedParameterTargetAnalyzer):
    """Analyze dataclass instances."""

    target_kind = "dataclass_instance"

    def matches(self, target: Union[Callable, Type, object]) -> bool:
        return dataclasses.is_dataclass(target)

    def analyze(self, target: Union[Callable, Type, object]) -> Dict[str, UnifiedParameterInfo]:
        return UnifiedParameterAnalyzer._analyze_dataclass_instance(target)


class ObjectInstanceTargetAnalyzer(UnifiedParameterTargetAnalyzer):
    """Analyze regular object instances."""

    target_kind = "object_instance"

    def matches(self, target: Union[Callable, Type, object]) -> bool:
        return True

    def analyze(self, target: Union[Callable, Type, object]) -> Dict[str, UnifiedParameterInfo]:
        return UnifiedParameterAnalyzer._analyze_object_instance(target)


class UnifiedParameterAnalyzer:
    """Single interface for analyzing parameters from any source.
    
    This class provides a unified way to extract parameter information
    from functions, dataclasses, and other parameter sources, ensuring
    consistent behavior across the entire application.
    """
    
    @staticmethod
    def analyze(target: Union[Callable, Type, object], exclude_params: Optional[list] = None) -> Dict[str, UnifiedParameterInfo]:
        """Analyze parameters from any source.

        Args:
            target: Function, method, dataclass type, or instance to analyze
            exclude_params: Optional list of parameter names to exclude from analysis

        Returns:
            Dictionary mapping parameter names to UnifiedParameterInfo objects

        Examples:
            # Function analysis
            param_info = UnifiedParameterAnalyzer.analyze(my_function)

            # Dataclass analysis
            param_info = UnifiedParameterAnalyzer.analyze(MyDataclass)

            # Instance analysis
            param_info = UnifiedParameterAnalyzer.analyze(my_instance)

            # Instance analysis with exclusions (e.g., exclude 'func' from FunctionStep)
            param_info = UnifiedParameterAnalyzer.analyze(step_instance, exclude_params=['func'])
        """
        if target is None:
            return {}

        result = UnifiedParameterTargetAnalyzer.analyze_target(target)

        excluded_names = UnifiedParameterAnalyzer._excluded_parameter_names(
            target,
            exclude_params,
        )
        if excluded_names:
            result = {
                name: info
                for name, info in result.items()
                if name not in excluded_names
            }

        return result

    @staticmethod
    def _excluded_parameter_names(
        target: Union[Callable, Type, object],
        exclude_params: Optional[list],
    ) -> frozenset[str]:
        """Return explicit and callable-declared parameter exclusions."""
        names = set(parameter_exclusions(target))
        names.update(exclude_params or [])
        return frozenset(names)
    
    @staticmethod
    def _analyze_callable(callable_obj: Callable) -> Dict[str, UnifiedParameterInfo]:
        """Analyze a callable (function, method, etc.)."""
        # Use existing SignatureAnalyzer for callables
        param_info_dict = SignatureAnalyzer.analyze(callable_obj)

        # Convert to unified format
        unified_params = {}
        for name, param_info in param_info_dict.items():
            unified_params[name] = UnifiedParameterInfo.from_parameter_info(
                param_info,
                source_type="function"
            )

        return unified_params
    
    @staticmethod
    def _analyze_dataclass_type(dataclass_type: Type) -> Dict[str, UnifiedParameterInfo]:
        """Analyze a dataclass type using existing SignatureAnalyzer infrastructure."""
        # CRITICAL FIX: Use existing SignatureAnalyzer._analyze_dataclass method
        # which already handles all the docstring extraction properly
        param_info_dict = SignatureAnalyzer._analyze_dataclass(dataclass_type)

        # Convert to unified format
        unified_params = {}
        for name, param_info in param_info_dict.items():
            unified_params[name] = UnifiedParameterInfo.from_parameter_info(
                param_info,
                source_type="dataclass"
            )

        return unified_params

    @staticmethod
    def _analyze_object_instance(instance: object) -> Dict[str, UnifiedParameterInfo]:
        """Analyze a regular object instance by examining its full inheritance hierarchy.

        For dynamic containers like SimpleNamespace (which use **kwargs in __init__),
        falls back to inspecting __dict__ to discover attributes and their types.

        Args:
            instance: Object instance to analyze
        """
        import logging
        _logger = logging.getLogger(__name__)

        # Use MRO to get all constructor parameters from the inheritance chain
        instance_class = type(instance)
        all_params = {}
        found_kwargs_only = False

        _logger.debug(f"🔧 _analyze_object_instance: instance_class={instance_class.__name__}, MRO={[c.__name__ for c in instance_class.__mro__]}")

        # Traverse MRO from most specific to most general (like dual-axis resolver)
        for cls in instance_class.__mro__:
            if cls == object:
                continue

            # Skip classes without custom __init__
            if cls.__init__ == object.__init__:
                continue

            try:
                # Analyze this class's constructor
                class_params = UnifiedParameterAnalyzer._analyze_callable(cls.__init__)

                # Remove 'self' parameter
                if 'self' in class_params:
                    del class_params['self']

                _logger.debug(f"🔧 _analyze_object_instance: cls={cls.__name__}, class_params after removing self={list(class_params.keys())}")

                # Special handling for *args/**kwargs - if params are only args/kwargs, skip this class
                # This handles dynamic containers like SimpleNamespace(self, /, *args, **kwargs)
                variadic_only = set(class_params.keys()) <= {'args', 'kwargs'}
                if variadic_only and class_params:
                    # This class uses only *args/**kwargs, skip it and use __dict__ fallback
                    found_kwargs_only = True
                    _logger.debug(f"🔧 _analyze_object_instance: cls={cls.__name__} has only variadic params {list(class_params.keys())}, skipping, found_kwargs_only=True")
                    continue

                # Add parameters that haven't been seen yet (most specific wins)
                for param_name, param_info in class_params.items():
                    if param_name not in all_params and param_name != 'kwargs':
                        all_params[param_name] = UnifiedParameterInfo(
                            name=param_name,
                            param_type=param_info.param_type,
                            default_value=param_info.default_value,
                            is_required=param_info.is_required,
                            description=param_info.description,
                            source_type="object_instance"
                        )

            except Exception:
                # Skip classes that can't be analyzed - this is legitimate since some classes
                # in MRO might not have analyzable constructors (e.g., ABC, object)
                continue

        # Fallback for dynamic containers (SimpleNamespace, etc.): inspect __dict__
        # This handles objects that store attrs via **kwargs and have no static signature
        _logger.debug(f"🔧 _analyze_object_instance: after MRO loop, all_params={list(all_params.keys())}, found_kwargs_only={found_kwargs_only}")
        if not all_params and found_kwargs_only:
            instance_values = vars(instance)
            _logger.debug(f"🔧 _analyze_object_instance: FALLBACK triggered, inspecting __dict__={list(instance_values.keys())}")
            for attr_name, attr_value in instance_values.items():
                if attr_name.startswith('_'):
                    continue
                # Infer type from value
                attr_type = type(attr_value) if attr_value is not None else type(None)
                all_params[attr_name] = UnifiedParameterInfo(
                    name=attr_name,
                    param_type=attr_type,
                    default_value=attr_value,
                    is_required=False,
                    description=None,
                    source_type="dynamic_attr"
                )
            _logger.debug(f"🔧 _analyze_object_instance: after fallback, all_params={list(all_params.keys())}")

        return all_params

    @staticmethod
    def _analyze_dataclass_instance(instance: object) -> Dict[str, UnifiedParameterInfo]:
        """Analyze a dataclass instance.

        Uses current instance values as defaults.
        """
        param_info_dict = SignatureAnalyzer.analyze(instance)
        return {
            name: UnifiedParameterInfo.from_parameter_info(
                param_info,
                source_type="dataclass_instance",
            )
            for name, param_info in param_info_dict.items()
        }
    
    @staticmethod
    def analyze_nested(
        target: Union[Callable, Type, object],
        parent_info: Dict[str, UnifiedParameterInfo] = None,
    ) -> Dict[str, UnifiedParameterInfo]:
        """Analyze parameters with nested dataclass support.
        
        This method provides enhanced analysis that can handle nested dataclasses
        and maintain parent context information.
        
        Args:
            target: The target to analyze
            parent_info: Optional parent parameter information for context
            
        Returns:
            Dictionary of unified parameter information with nested support
        """
        base_params = UnifiedParameterAnalyzer.analyze(target)
        
        # For each parameter, check if it's a nested dataclass
        enhanced_params = {}
        for name, param_info in base_params.items():
            enhanced_params[name] = param_info
            
            # If this parameter is a dataclass, mark it as having nested structure
            if dataclasses.is_dataclass(param_info.param_type):
                # Update source type to indicate nesting capability
                enhanced_params[name] = UnifiedParameterInfo(
                    name=param_info.name,
                    param_type=param_info.param_type,
                    default_value=param_info.default_value,
                    is_required=param_info.is_required,
                    description=param_info.description,
                    source_type=f"{param_info.source_type}_nested"
                )
        
        return enhanced_params


# Backward compatibility aliases
# These allow existing code to continue working while migration happens
ParameterAnalyzer = UnifiedParameterAnalyzer
analyze_parameters = UnifiedParameterAnalyzer.analyze
