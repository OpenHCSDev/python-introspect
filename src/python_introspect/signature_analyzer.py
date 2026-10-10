# File: python_introspect/signature_analyzer.py
"""
Signature analysis with extensible type resolution.

This module provides pure Python introspection with a plugin architecture
for framework-specific extensions. Register namespace providers and type
resolvers to extend functionality without modifying this code.
"""

import ast
import inspect
import sys
import linecache
from functools import lru_cache
import dataclasses
import re
from abc import ABC, abstractmethod
from typing import Annotated, Any, Dict, Callable, get_type_hints, NamedTuple, Union, Optional, Type, List, ClassVar, Tuple, get_args, get_origin, Iterable
from weakref import WeakKeyDictionary

from dataclasses import dataclass, field

from metaclass_registry import AutoRegisterMeta
from .annotation_types import optional_member_type
from .docstring_annotations import infer_parameter_annotation

# =============================================================================
# PLUGIN REGISTRY - Allows frameworks to extend type resolution
# =============================================================================

# Namespace providers: functions that return Dict[str, Any] for get_type_hints()
# Used to resolve forward references supplied by host frameworks.
_namespace_providers: List[Callable[[], Dict[str, Any]]] = []

# Type resolvers: functions that map types to their "real" types
# e.g., framework proxy types -> their public dataclass types
_type_resolvers: List[Callable[[type], Optional[type]]] = []
_signature_analysis_targets: WeakKeyDictionary[object, Callable] = WeakKeyDictionary()
_signature_analysis_targets_by_id: Dict[int, tuple[object, Callable]] = {}


def register_namespace_provider(provider: Callable[[], Dict[str, Any]]) -> None:
    """Register a namespace provider for forward reference resolution.

    The provider function should return a dict of names to types/values
    that will be available during get_type_hints() resolution.

    Example:
        register_namespace_provider(lambda: {'MyClass': MyClass, 'MyEnum': MyEnum})
    """
    _namespace_providers.append(provider)


def register_type_resolver(resolver: Callable[[type], Optional[type]]) -> None:
    """Register a type resolver for lazy/proxy type unwrapping.

    The resolver function should return the resolved type if it can handle
    the input type, or None to defer to other resolvers.

    Example:
        def resolve_lazy(t):
            return lazy_to_base.get(t)
        register_type_resolver(resolve_lazy)
    """
    _type_resolvers.append(resolver)


def set_signature_analysis_target(wrapper: object, target: Callable) -> None:
    """Declare the callable that should be inspected for wrapper parameters."""
    if not callable(target):
        raise TypeError(
            "signature analysis target must be callable, "
            f"got {type(target).__name__}."
        )
    try:
        _signature_analysis_targets[wrapper] = target
    except TypeError:
        _signature_analysis_targets_by_id[id(wrapper)] = (wrapper, target)


def signature_analysis_target(target: Callable) -> Callable:
    """Return the callable that owns user-facing signature metadata."""
    current = target
    seen: set[int] = set()
    while True:
        current_id = id(current)
        if current_id in seen:
            raise RuntimeError("signature analysis target declarations contain a cycle.")
        seen.add(current_id)
        try:
            projected = _signature_analysis_targets.get(current)
        except TypeError:
            projected = None
        if projected is None:
            fallback_record = _signature_analysis_targets_by_id.get(current_id)
            if fallback_record is not None and fallback_record[0] is current:
                projected = fallback_record[1]
        if projected is None:
            return current
        current = projected


def _get_extended_namespace() -> Dict[str, Any]:
    """Get combined namespace from all registered providers."""
    result: Dict[str, Any] = {}
    for provider in _namespace_providers:
        try:
            result.update(provider())
        except Exception:
            pass  # Ignore providers that fail
    return result


def _resolve_type(t: type) -> type:
    """Resolve a type through registered resolvers, returning the unwrapped type."""
    for resolver in _type_resolvers:
        resolved = resolver(t)
        if resolved is not None:
            return resolved
    return t  # No resolver handled it, return as-is


def _parameter_annotation_help(annotation: Any) -> tuple[Any, Optional[str]]:
    """Return the base annotation and optional user help from Annotated metadata."""
    if get_origin(annotation) is not Annotated:
        return annotation, None
    args = get_args(annotation)
    description = next(
        (item.strip() for item in args[1:] if isinstance(item, str) and item.strip()),
        None,
    )
    return args[0], description


@dataclass(frozen=True)
class AnalysisConstants:
    """Constants for signature analysis to eliminate magic strings."""
    INIT_METHOD_SUFFIX: str = ".__init__"
    SELF_PARAM: str = "self"
    CLS_PARAM: str = "cls"
    DUNDER_PREFIX: str = "__"
    DUNDER_SUFFIX: str = "__"


# Create constants instance for use throughout the module
CONSTANTS = AnalysisConstants()


@dataclass(frozen=True, init=False, eq=False)
class ParameterInfo:
    """Admitted parameter values with presentation derived from their declaration.

    Callable descriptions remain concrete because they can determine inferred
    types. Dataclass descriptions are requested independently of value admission.
    """

    name: str
    param_type: type
    default_value: Any
    is_required: bool
    _description: Optional[str]
    _description_owner: Optional[type]

    def __init__(
        self, name: str, param_type: type, default_value: Any, is_required: bool,
        description: Optional[str] = None, *, description_owner: Optional[type] = None,
    ):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "param_type", param_type)
        object.__setattr__(self, "default_value", default_value)
        object.__setattr__(self, "is_required", is_required)
        object.__setattr__(self, "_description", description)
        object.__setattr__(self, "_description_owner", description_owner)

    @property
    def description(self) -> Optional[str]:
        if self._description_owner is not None:
            SignatureAnalyzer._materialize_dataclass_descriptions(self._description_owner, self)
        return self._description

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ParameterInfo):
            return NotImplemented
        return (
            self.name, self.param_type, self.default_value, self.is_required, self.description,
        ) == (
            other.name, other.param_type, other.default_value, other.is_required, other.description,
        )

    def __hash__(self) -> int:
        return hash((self.name, self.param_type, self.default_value, self.is_required, self.description))

    def _replace(self, **changes: Any) -> "ParameterInfo":
        """Replace declared fields through the same public parameter owner."""
        values = dict(
            name=self.name, param_type=self.param_type,
            default_value=self.default_value, is_required=self.is_required,
            description=self._description,
        )
        unknown = changes.keys() - values.keys()
        if unknown:
            raise ValueError(f"Got unexpected field names: {sorted(unknown)!r}")
        owner = self._description_owner
        if "description" in changes:
            owner = None
        elif "name" in changes and changes["name"] != self.name:
            # A renamed field keeps the original declaration's help, rather
            # than querying a different field in the same source class.
            values["description"] = self.description
            owner = None
        values.update(changes)
        return type(self)(**values, description_owner=owner)


class DocstringInfo(NamedTuple):
    """Information extracted from a docstring."""
    summary: Optional[str] = None  # First line or brief description
    description: Optional[str] = None  # Full description
    parameters: Optional[Dict[str, str]] = None  # Parameter name -> description mapping (None = empty)
    returns: Optional[str] = None  # Return value description
    examples: Optional[str] = None  # Usage examples

    @property
    def parameters_dict(self) -> Dict[str, str]:
        """Get parameters as a dict, never None."""
        return self.parameters if self.parameters is not None else {}


@dataclass
class DocstringParseState:
    """Mutable parse state shared by docstring section handlers."""

    summary: Optional[str] = None
    description_lines: List[str] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    returns: Optional[str] = None
    examples: Optional[str] = None
    current_params: Tuple[str, ...] = ()
    current_param_lines: List[str] = field(default_factory=list)

    def finalize_current_param(self) -> None:
        """Commit the active parameter description, if one is being parsed."""
        if self.current_params and self.current_param_lines:
            description = "\n".join(self.current_param_lines).strip()
            self.parameters.update(
                (parameter_name, description)
                for parameter_name in self.current_params
            )

    def reset_current_param(self) -> None:
        """Clear parameter continuation state after a section transition."""
        self.current_params = ()
        self.current_param_lines = []

    def transition_to(self, section: "DocstringSection") -> "DocstringSection":
        """Finalize parameter state before changing active section."""
        self.finalize_current_param()
        self.reset_current_param()
        return section

    def to_info(self) -> DocstringInfo:
        """Build the immutable public docstring projection."""
        self.finalize_current_param()
        description = "\n".join(self.description_lines).strip()
        if description == self.summary or description == "":
            description = None
        if any((self.summary, description, self.parameters, self.returns, self.examples)):
            return DocstringInfo(
                summary=self.summary,
                description=description,
                parameters=self.parameters if self.parameters else {},
                returns=self.returns,
                examples=self.examples,
            )
        return DocstringInfo(parameters={})


class DocstringSection(ABC, metaclass=AutoRegisterMeta):
    """Nominal docstring section family used by the parser orchestration."""

    __registry_key__ = "section_name"
    __skip_if_no_key__ = True

    section_name: ClassVar[Optional[str]] = None
    colon_headers: ClassVar[Tuple[str, ...]] = ()
    numpy_headers: ClassVar[Tuple[str, ...]] = ()

    @classmethod
    def initial(cls) -> "DocstringSection":
        """Return the starting section for a docstring."""
        return cls.__registry__[DescriptionDocstringSection.section_name]()

    @classmethod
    def section_for_header(
        cls,
        line: str,
        next_line: Optional[str],
    ) -> Optional["DocstringSection"]:
        """Return the section selected by this line, if it is a header."""
        normalized = line.lower()
        numpy_separator_follows = (
            next_line is not None and next_line.strip().startswith("-")
        )
        for section_cls in cls.__registry__.values():
            section = section_cls()
            if normalized in section.colon_headers:
                return section
            if numpy_separator_follows and normalized in section.numpy_headers:
                return section
        return None

    @abstractmethod
    def consume(
        self,
        state: DocstringParseState,
        original_line: str,
        line: str,
    ) -> None:
        """Consume a non-header line inside this section."""


class DescriptionDocstringSection(DocstringSection):
    """Free-form summary and description text."""

    section_name = "description"

    def consume(
        self,
        state: DocstringParseState,
        original_line: str,
        line: str,
    ) -> None:
        if not state.summary and line:
            state.summary = line
        else:
            state.description_lines.append(original_line)


class ParametersDocstringSection(DocstringSection):
    """Parameter definition section."""

    section_name = "parameters"
    colon_headers = (
        "args:",
        "arguments:",
        "parameters:",
        "additional parameters:",
    )
    numpy_headers = ("args", "arguments", "parameters", "additional parameters")
    parameter_declaration_pattern = re.compile(
        r"^(?:"
        r":param\s+(?P<sphinx_name>\w+)"
        r"|[-•*]\s*(?P<bullet_names>\w+(?:\s*,\s*\w+)*)"
        r"|(?P<plain_names>\w+(?:\s*,\s*\w+)*)"
        r")\s*:\s*(?P<description>.+)$"
    )

    def consume(
        self,
        state: DocstringParseState,
        original_line: str,
        line: str,
    ) -> None:
        declaration = self.parameter_declaration_pattern.fullmatch(line)
        if declaration is not None:
            state.finalize_current_param()
            declared_names = next(
                value
                for value in (
                    declaration.group("sphinx_name"),
                    declaration.group("bullet_names"),
                    declaration.group("plain_names"),
                )
                if value is not None
            )
            state.current_params = tuple(
                name.strip() for name in declared_names.split(",")
            )
            state.current_param_lines = [
                declaration.group("description").strip()
            ]
        elif state.current_params and (
            original_line.startswith("    ") or original_line.startswith("\t")
        ):
            state.current_param_lines.append(line)
        elif not line:
            state.finalize_current_param()
            state.reset_current_param()
        elif state.current_params:
            state.current_param_lines.append(line)
        else:
            state.parameters.update(DocstringExtractor._parse_inline_parameters(line))

class ReturnsDocstringSection(DocstringSection):
    """Return value section."""

    section_name = "returns"
    colon_headers = ("returns:", "return:")
    numpy_headers = ("returns", "return")

    def consume(
        self,
        state: DocstringParseState,
        original_line: str,
        line: str,
    ) -> None:
        if state.returns is None:
            state.returns = line
        else:
            state.returns += "\n" + line


class ExamplesDocstringSection(DocstringSection):
    """Example usage section."""

    section_name = "examples"
    colon_headers = ("examples:", "example:")
    numpy_headers = ("examples", "example")

    def consume(
        self,
        state: DocstringParseState,
        original_line: str,
        line: str,
    ) -> None:
        if state.examples is None:
            state.examples = line
        else:
            state.examples += "\n" + line


class ParameterSkipPolicy(ABC, metaclass=AutoRegisterMeta):
    """Nominal policy family for parameters excluded from public analysis."""

    __registry_key__ = "policy_name"
    __skip_if_no_key__ = True

    policy_name: ClassVar[Optional[str]] = None

    @classmethod
    def should_skip(cls, param_name: str) -> bool:
        """Return whether any registered policy excludes this parameter."""
        return any(policy_cls().matches(param_name) for policy_cls in cls.__registry__.values())

    @abstractmethod
    def matches(self, param_name: str) -> bool:
        """Return whether this policy excludes a parameter name."""


class BoundReceiverParameterSkipPolicy(ParameterSkipPolicy):
    """Skip implicit instance/class receiver parameters."""

    policy_name = "bound_receiver"
    receiver_names: ClassVar[Tuple[str, ...]] = (
        CONSTANTS.SELF_PARAM,
        CONSTANTS.CLS_PARAM,
    )

    def matches(self, param_name: str) -> bool:
        return param_name in self.receiver_names


class DunderParameterSkipPolicy(ParameterSkipPolicy):
    """Skip reserved dunder parameters."""

    policy_name = "dunder"

    def matches(self, param_name: str) -> bool:
        return (
            param_name.startswith(CONSTANTS.DUNDER_PREFIX)
            and param_name.endswith(CONSTANTS.DUNDER_SUFFIX)
        )


class DocstringExtractor:
    """Extract structured information from docstrings."""

    @staticmethod
    def extract(target: Union[Callable, type]) -> DocstringInfo:
        """Extract docstring information from function or class.

        Args:
            target: Function, method, or class to extract docstring from

        Returns:
            DocstringInfo with parsed docstring components
        """
        if not target:
            return DocstringInfo(parameters={})

        # ENHANCEMENT: Handle lazy dataclasses by extracting from their base class
        actual_target = DocstringExtractor._resolve_lazy_target(target)

        docstring = inspect.getdoc(actual_target)
        if not docstring:
            return DocstringInfo(parameters={})

        return DocstringExtractor._parse_docstring(docstring)

    @staticmethod
    def _resolve_lazy_target(target: Union[Callable, type]) -> Union[Callable, type]:
        """Resolve a proxy type through the registered type authority."""
        if not inspect.isclass(target):
            return target
        return _resolve_type(target)

    @staticmethod
    def _parse_docstring(docstring: str) -> DocstringInfo:
        """Parse a docstring into structured components with improved multiline support.

        Supports multiple docstring formats:
        - Google style (Args:, Returns:, Examples:)
        - NumPy style (Parameters, Returns, Examples)
        - Sphinx style (:param name:, :returns:)
        - Simple format (just description)

        Uses improved parsing for multiline parameter descriptions that continues
        until a blank line or new parameter/section is encountered.
        """
        lines = docstring.strip().split('\n')
        state = DocstringParseState()
        current_section = DocstringSection.initial()

        for i, line_value in enumerate(lines):
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            header_section = DocstringSection.section_for_header(
                line_value.strip(),
                next_line,
            )
            if header_section is not None:
                current_section = state.transition_to(header_section)
                continue

            if line_value.strip().startswith("---"):
                continue

            original_line = line_value
            line = line_value.strip()
            current_section.consume(state, original_line, line)

        return state.to_info()

    @staticmethod
    def _parse_inline_parameters(line: str) -> Dict[str, str]:
        """Parse parameters from a single line containing multiple parameter definitions.

        Handles formats like:
        - "input_image: Image Input image to process. footprint: Image Structuring element..."
        - "param1: type1 description1. param2: type2 description2."
        """
        parameters = {}

        import re

        # Strategy: Use a flexible pattern that works with the pyclesperanto format
        # Pattern matches: param_name: everything up to the next param_name: or end of string
        param_pattern = r'(\w+):\s*([^:]*?)(?=\s+\w+:|$)'
        matches = re.findall(param_pattern, line)

        for param_name, param_desc in matches:
            if param_desc.strip():
                # Clean up the description (remove trailing periods, extra whitespace)
                clean_desc = param_desc.strip().rstrip('.')
                parameters[param_name] = clean_desc

        return parameters


class OriginalParameterSource(ABC, metaclass=AutoRegisterMeta):
    """Nominal source family for recovering wrapper-owned original parameters."""

    __registry_key__ = "source_name"
    __skip_if_no_key__ = True

    source_name: ClassVar[Optional[str]] = None

    @classmethod
    def extract_for(cls, callable_obj: Callable) -> Dict[str, ParameterInfo]:
        """Return original parameters from the first source that can recover them."""
        for source_cls in cls.__registry__.values():
            params = source_cls().extract(callable_obj)
            if params:
                return params
        return {}

    @abstractmethod
    def extract(self, callable_obj: Callable) -> Optional[Dict[str, ParameterInfo]]:
        """Return recovered parameters, or None if this source does not apply."""


class DeclaredSignatureAnalysisTargetSource(OriginalParameterSource):
    """Recover parameters from an explicit signature-analysis target."""

    source_name = "declared_signature_analysis_target"

    def extract(self, callable_obj: Callable) -> Optional[Dict[str, ParameterInfo]]:
        projected = signature_analysis_target(callable_obj)
        if projected is callable_obj:
            return None
        return EnableableParameterOverlay(
            owner=callable_obj,
            parameters=SignatureAnalyzer._analyze_callable(projected),
        ).parameters_with_owner_fields()


@dataclass(frozen=True)
class EnableableParameterOverlay:
    """Overlay signature metadata owned by a wrapper callable."""

    owner: Callable
    parameters: Dict[str, ParameterInfo]

    def parameters_with_owner_fields(self) -> Dict[str, ParameterInfo]:
        from python_introspect.enableable import Enableable, is_enableable

        parameters = self._parameters_with_owner_annotations()
        parameter_name = Enableable.require_parameter_name()
        if not is_enableable(self.owner):
            return parameters
        declaration = SignatureAnalyzer.analyze(Enableable)[parameter_name]
        existing = parameters.get(parameter_name)
        if existing is not None:
            if existing.description:
                return parameters
            return {
                **parameters,
                parameter_name: existing._replace(
                    description=declaration.description,
                ),
            }
        return {
            **parameters,
            parameter_name: ParameterInfo(
                name=parameter_name,
                param_type=Enableable.annotation_type(),
                default_value=Enableable.default_value(),
                is_required=False,
                description=declaration.description,
            ),
        }

    def _parameters_with_owner_annotations(self) -> Dict[str, ParameterInfo]:
        """Retain help metadata on wrapper-only ``Annotated`` parameters."""

        signature = inspect.signature(self.owner)
        try:
            annotations = get_type_hints(self.owner, include_extras=True)
        except Exception:
            annotations = inspect.get_annotations(self.owner, eval_str=False)
        parameters = dict(self.parameters)
        for name, parameter in signature.parameters.items():
            annotation = annotations.get(name, parameter.annotation)
            parameter_type, description = _parameter_annotation_help(annotation)
            if not description:
                continue
            existing = parameters.get(name)
            if existing is not None:
                if not existing.description:
                    parameters[name] = existing._replace(description=description)
                continue
            parameters[name] = ParameterInfo(
                name=name,
                param_type=parameter_type,
                default_value=(
                    None
                    if parameter.default is inspect.Parameter.empty
                    else parameter.default
                ),
                is_required=parameter.default is inspect.Parameter.empty,
                description=description,
            )
        return parameters


class WrappedCallableParameterSource(OriginalParameterSource):
    """Recover parameters from functools-style wrapped callables."""

    source_name = "wrapped_callable"

    def extract(self, callable_obj: Callable) -> Optional[Dict[str, ParameterInfo]]:
        unwrapped = inspect.unwrap(callable_obj)
        if unwrapped is callable_obj:
            return None
        return SignatureAnalyzer._analyze_callable(unwrapped)


class ClosureCallableParameterSource(OriginalParameterSource):
    """Recover parameters from non-variadic callables captured in closures."""

    source_name = "closure_callable"

    def extract(self, callable_obj: Callable) -> Optional[Dict[str, ParameterInfo]]:
        if not inspect.isfunction(callable_obj) or not callable_obj.__closure__:
            return None
        for cell in callable_obj.__closure__:
            candidate = cell.cell_contents
            if not callable(candidate):
                continue
            try:
                candidate_sig = inspect.signature(candidate)
            except Exception:
                continue
            if any(
                param.kind == inspect.Parameter.VAR_KEYWORD
                for param in candidate_sig.parameters.values()
            ):
                continue
            return SignatureAnalyzer._analyze_callable(candidate)
        return None


@dataclass(frozen=True)
class CallableAnalysisContext:
    """Authoritative callable analysis projection for signature extraction."""

    target: Callable
    signature: inspect.Signature
    globalns: Dict[str, Any]
    annotations: Dict[str, Any]
    display_name: str

    @classmethod
    def from_callable(cls, callable_obj: Callable) -> "CallableAnalysisContext":
        """Create the public analysis context for a callable."""
        target = signature_analysis_target(callable_obj)
        extended_ns = _get_extended_namespace()
        globalns = dict(extended_ns)
        for namespace_target in cls.annotation_namespace_targets(target):
            module = inspect.getmodule(namespace_target)
            if module is not None:
                globalns.update(vars(module))
            if inspect.isfunction(namespace_target):
                globalns.update(namespace_target.__globals__)

        return cls(
            target=target,
            signature=inspect.signature(target),
            globalns=globalns,
            annotations=inspect.get_annotations(target, eval_str=False),
            display_name=cls.display_name_for(target),
        )

    @staticmethod
    def display_name_for(target: Callable) -> str:
        """Return a stable human-readable callable name without structural probes."""
        if inspect.isfunction(target) or inspect.ismethod(target):
            return target.__qualname__
        if inspect.isclass(target):
            return target.__qualname__
        return type(target).__name__

    @staticmethod
    def annotation_namespace_targets(target: Callable) -> Tuple[Callable, ...]:
        """Return runtime-to-declaration callables whose namespaces own annotations."""

        unwrapped = inspect.unwrap(target)
        if unwrapped is target:
            return (target,)
        # ``functools.wraps`` copies the declaration's annotation strings onto a
        # wrapper whose runtime globals belong to the decorator module.  Merge
        # outward so the unwrapped declaration, which authored those strings,
        # has final authority over colliding names.
        return (target, unwrapped)

    def type_hints(self) -> Dict[str, Any]:
        """Resolve type hints using the context-owned namespace."""
        return get_type_hints(
            self.target,
            globalns=self.globalns,
            include_extras=True,
        )


def _class_node_for_qualname(tree: ast.AST, qualname: str) -> Optional[ast.ClassDef]:
    """Return the class statement whose qualified name is ``qualname``.

    Function bodies contribute ``<locals>`` exactly as ``__qualname__`` does.
    """
    pending = [(node, ()) for node in reversed(getattr(tree, 'body', ()))]
    while pending:
        node, scope = pending.pop()
        if isinstance(node, ast.ClassDef):
            node_scope = (*scope, node.name)
            if '.'.join(node_scope) == qualname:
                return node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node_scope = (*scope, node.name, '<locals>')
        else:
            node_scope = scope
        pending.extend((child, node_scope) for child in reversed(list(ast.iter_child_nodes(node))))
    return None


class ClassSourceDeclaration(NamedTuple):
    """Immutable located class source and its source-only documentation views."""

    source: str
    inline_docs: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...]

    @classmethod
    def from_block(cls, source: str, tree: ast.AST, first_line: int = 1) -> "ClassSourceDeclaration":
        # The public extractor historically parses the selected block without
        # dedenting. Keep nested/local blocks' empty inline-documentation view.
        first = next((line for line in source.splitlines() if line.strip()), '')
        if first[:1].isspace():
            return cls(source, ())
        source_lines = source.split('\n')
        declarations = []
        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef):
                continue
            field_docs = {}

            # Method 1: Look for field assignments followed by string literals (next line)
            for i, node in enumerate(class_node.body):
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    field_name = node.target.id

                    # Check if the next node is a string literal (documentation)
                    if i + 1 < len(class_node.body):
                        next_node = class_node.body[i + 1]
                        if isinstance(next_node, ast.Expr):
                            if isinstance(next_node.value, ast.Constant) and isinstance(next_node.value.value, str):
                                field_docs[field_name] = next_node.value.value.strip()
                                continue

                    # Method 2: Check for inline comments on the same line
                    # Get the line number of the field definition
                    field_line_num = node.lineno - first_line
                    if 0 <= field_line_num < len(source_lines):
                        line = source_lines[field_line_num]

                        # Look for string literals in comments on the same line
                        # Pattern: field: type = value  # """Documentation"""
                        comment_match = re.search(r'#\s*["\']([^"\']+)["\']', line)
                        if comment_match:
                            field_docs[field_name] = comment_match.group(1).strip()
                            continue

                        # Look for triple-quoted strings on the same line
                        # Pattern: field: type = value  """Documentation"""
                        triple_quote_match = re.search(r'"""([^"]+)"""|\'\'\'([^\']+)\'\'\'', line)
                        if triple_quote_match:
                            doc_text = triple_quote_match.group(1) or triple_quote_match.group(2)
                            field_docs[field_name] = doc_text.strip()

            declarations.append((class_node.name, tuple(field_docs.items())))
        return cls(source, tuple(declarations))

    def field_documentation(self, class_name: str) -> Dict[str, str]:
        """Return a fresh view selected by the caller's current public name."""
        for name, entries in self.inline_docs:
            if name == class_name:
                return dict(entries)
        return {}


class SignatureAnalyzer:
    """Universal analyzer for extracting parameter information from any target."""

    # Class-level cache for field documentation to avoid re-parsing
    _field_docs_cache = {}

    # Class-level cache for dataclass analysis results to avoid expensive AST parsing
    _dataclass_analysis_cache = {}
    
    @staticmethod
    def analyze(target: Union[Callable, Type, object], skip_first_param: Optional[bool] = None) -> Dict[str, ParameterInfo]:
        """Extract parameter information from any target: function, constructor, dataclass, or instance.

        Args:
            target: Function, constructor, dataclass type, or dataclass instance
            skip_first_param: Whether to skip the first parameter (after self/cls).
                            If None, auto-detects based on context:
                            - False for step constructors (all params are configuration)
                            - True for image processing functions (first param is image data)

        Returns:
            Dict mapping parameter names to ParameterInfo
        """
        if not target:
            return {}

        # Dispatch based on target type
        if inspect.isclass(target):
            if dataclasses.is_dataclass(target):
                return SignatureAnalyzer._analyze_dataclass(target)
            else:
                # Try to analyze constructor
                return SignatureAnalyzer._analyze_callable(target.__init__, skip_first_param)
        elif dataclasses.is_dataclass(target):
            # Instance of dataclass
            return SignatureAnalyzer._analyze_dataclass_instance(target)
        else:
            # Function, method, or other callable
            return SignatureAnalyzer._analyze_callable(target, skip_first_param)
    
    @staticmethod
    def _analyze_callable(callable_obj: Callable, skip_first_param: Optional[bool] = None) -> Dict[str, ParameterInfo]:
        """Extract parameter information from callable signature.

        Args:
            callable_obj: The callable to analyze
            skip_first_param: Whether to skip the first parameter (after self/cls).
                            If None, auto-detects based on context.
        """
        analysis_owner = callable_obj
        context = CallableAnalysisContext.from_callable(callable_obj)
        callable_obj = context.target
        sig = context.signature

        import logging
        logger = logging.getLogger(__name__)
        callable_name = context.display_name

        try:
            type_hints = context.type_hints()
            logger.debug(f"🔍 SIG ANALYZER: get_type_hints succeeded for {callable_name}: {type_hints}")
        except (NameError, AttributeError):
            type_hints = context.annotations
            logger.debug(f"🔍 SIG ANALYZER: Fell back to annotations for {callable_name}: {type_hints}")
        except Exception as ex:
            # For any other type hint resolution errors, fall back to annotations.
            type_hints = context.annotations
            logger.debug(f"🔍 SIG ANALYZER: Exception {ex}, fell back to __annotations__ for {callable_name}: {type_hints}")

        # Extract docstring information (with fallback for robustness)
        try:
            docstring_info = DocstringExtractor.extract(callable_obj)
        except:
            docstring_info = None

        if not docstring_info:
            docstring_info = DocstringInfo()

        parameters = {}
        param_list = list(sig.parameters.items())

        # Determine skip behavior: explicit parameter overrides auto-detection
        should_skip_first_param = (
            skip_first_param if skip_first_param is not None
            else SignatureAnalyzer._should_skip_first_parameter(callable_obj)
        )

        first_param_after_self_skipped = False

        for i, (param_name, param) in enumerate(param_list):
            if ParameterSkipPolicy.should_skip(param_name):
                continue

            # Skip first parameter for image processing functions only
            if should_skip_first_param and not first_param_after_self_skipped:
                first_param_after_self_skipped = True
                continue

            # Handle **kwargs parameters - try to extract original function signature
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                # Try to find the original function if this is a wrapper
                original_params = SignatureAnalyzer._extract_original_parameters(callable_obj)
                if original_params:
                    parameters.update(original_params)
                continue 

            from typing import Any
            default_value = param.default if param.default != inspect.Parameter.empty else None
            is_required = param.default == inspect.Parameter.empty

            # Get parameter description from docstring
            param_description = (
                docstring_info.parameters.get(param_name)
                if docstring_info and docstring_info.parameters
                else None
            )
            if param_description is None:
                annotation = type_hints.get(param_name, param.annotation)
                _base_annotation, annotation_description = _parameter_annotation_help(
                    annotation
                )
                param_description = annotation_description

            annotation = type_hints.get(param_name, param.annotation)
            if annotation is inspect.Parameter.empty:
                annotation = infer_parameter_annotation(param, param_description)
            param_type, _annotation_description = _parameter_annotation_help(annotation)

            parameters[param_name] = ParameterInfo(
                name=param_name,
                param_type=param_type,
                default_value=default_value,
                is_required=is_required,
                description=param_description
            )

        return EnableableParameterOverlay(
            owner=analysis_owner,
            parameters=parameters,
        ).parameters_with_owner_fields()

    @staticmethod
    def _should_skip_first_parameter(callable_obj: Callable) -> bool:
        """
        Determine if the first parameter should be skipped for any callable.

        Universal logic that works with any object:
        - Constructors (__init__ methods): don't skip (all params are configuration)
        - Regular functions: don't skip (by default, analyze all parameters)

        Note: This was originally designed for image processing functions where the
        first parameter is typically the input image. For general-purpose use,
        we default to NOT skipping parameters unless explicitly requested via
        skip_first_param parameter.
        """
        # By default, don't skip any parameters for general-purpose introspection
        return False

    @staticmethod
    def _extract_original_parameters(callable_obj: Callable) -> Dict[str, ParameterInfo]:
        """
        Extract parameters from the original function if this is a wrapper with **kwargs.

        This handles wrappers with explicit metadata, functools wrapping, or
        closure-owned original callables.
        """
        try:
            return OriginalParameterSource.extract_for(callable_obj)

        except Exception:
            return {}

    @staticmethod
    def _analyze_dataclass(dataclass_type: type) -> Dict[str, ParameterInfo]:
        """Extract parameter information from dataclass fields."""
        import logging
        logger = logging.getLogger(__name__)

        # PERFORMANCE: Check cache first to avoid expensive AST parsing
        # Use the class object itself as the key (classes are hashable and have stable identity)
        cache_key = dataclass_type
        if cache_key in SignatureAnalyzer._dataclass_analysis_cache:
            logger.debug(f"✅ CACHE HIT for {dataclass_type.__name__} (id={id(dataclass_type)})")
            return SignatureAnalyzer._dataclass_analysis_cache[cache_key]

        logger.debug(f"❌ CACHE MISS for {dataclass_type.__name__} (id={id(dataclass_type)}), cache has {len(SignatureAnalyzer._dataclass_analysis_cache)} entries")

        try:
            # Try to get type hints, fall back to __annotations__ if resolution fails
            try:
                type_hints = get_type_hints(dataclass_type, include_extras=True)
            except Exception:
                type_hints = inspect.get_annotations(dataclass_type, eval_str=False)

            parameters = {}

            for field in dataclasses.fields(dataclass_type):
                # Skip dunder fields (internal/reserved fields)
                if field.name.startswith(CONSTANTS.DUNDER_PREFIX) and field.name.endswith(CONSTANTS.DUNDER_SUFFIX):
                    continue

                param_type = type_hints.get(field.name, str)

                # Get default value
                if field.default != dataclasses.MISSING:
                    default_value = field.default
                    is_required = False
                elif field.default_factory != dataclasses.MISSING:
                    default_value = field.default_factory()
                    is_required = False
                else:
                    default_value = None
                    is_required = True

                parameters[field.name] = ParameterInfo(
                    name=field.name,
                    param_type=param_type,
                    default_value=default_value,
                    is_required=is_required,
                    description_owner=dataclass_type,
                )

            # PERFORMANCE: Cache the result to avoid re-parsing
            SignatureAnalyzer._dataclass_analysis_cache[cache_key] = parameters
            return parameters

        except Exception:
            # Return empty dict on error (don't cache errors)
            return {}

    @staticmethod
    def _materialize_dataclass_descriptions(dataclass_type: type, requested: ParameterInfo) -> None:
        """Fill presentation on the existing admitted declarations, once requested.

        Presentation extraction errors no longer discard usable value/type
        declarations. They yield absent help, matching the existing help fallback.
        """
        parameters = SignatureAnalyzer._dataclass_analysis_cache.get(dataclass_type, {})
        admitted = parameters.get(requested.name)
        if admitted is not None and admitted is not requested:
            object.__setattr__(requested, "_description", admitted.description)
            object.__setattr__(requested, "_description_owner", None)
            return
        if admitted is not requested:
            parameters = {requested.name: requested}
        pending = [info for info in parameters.values() if info._description_owner is not None]
        if not pending:
            return
        try:
            docstring_info = DocstringExtractor.extract(dataclass_type)
            inline_docs = SignatureAnalyzer._extract_inline_field_docs(dataclass_type)
            field_type_docs = SignatureAnalyzer._extract_field_type_docs(dataclass_type)
            descriptions = {}
            for field in dataclasses.fields(dataclass_type):
                if field.name not in parameters:
                    continue
                if 'description' in field.metadata:
                    description = field.metadata['description']
                elif field.name in inline_docs:
                    description = inline_docs[field.name]
                elif field.name in field_type_docs:
                    description = field_type_docs[field.name]
                elif field.name in docstring_info.parameters_dict:
                    description = docstring_info.parameters_dict[field.name]
                else:
                    description = SignatureAnalyzer.extract_field_documentation(dataclass_type, field.name)
                descriptions[field.name] = description
        except Exception:
            descriptions = {}
        for info in pending:
            object.__setattr__(info, "_description", descriptions.get(info.name))
            object.__setattr__(info, "_description_owner", None)

    @staticmethod
    def prepare_dataclass_declarations(declarations: Iterable[type]) -> None:
        """Prepare source facts for declared schemas without resolving values.

        MRO, raw annotations and declared dataclass defaults expose schema
        relationships. Unresolved strings/ForwardRefs remain live for analysis;
        factories, namespace providers and type resolvers are never invoked.
        """
        pending = list(declarations)
        visited = set()
        while pending:
            declaration = pending.pop()
            if not inspect.isclass(declaration) or declaration in visited:
                continue
            visited.add(declaration)
            if declaration is object:
                continue
            if not dataclasses.is_dataclass(declaration):
                continue
            SignatureAnalyzer._extract_inline_field_docs(declaration)
            pending.extend(
                base for base in inspect.getmro(declaration)[1:]
                if dataclasses.is_dataclass(base)
            )
            for declared_field in dataclasses.fields(declaration):
                field_types = [declared_field.type]
                while field_types:
                    field_type = field_types.pop()
                    if inspect.isclass(field_type) and dataclasses.is_dataclass(field_type):
                        pending.append(field_type)
                    field_types.extend(get_args(field_type))
                if dataclasses.is_dataclass(declared_field.default):
                    default = declared_field.default
                    pending.append(default if inspect.isclass(default) else type(default))
                factory = declared_field.default_factory
                if inspect.isclass(factory) and dataclasses.is_dataclass(factory):
                    pending.append(factory)

    @staticmethod
    def prepare_dataclass_declaration(dataclass_type: type) -> None:
        """Prepare one declaration's source closure without evaluating defaults."""
        SignatureAnalyzer.prepare_dataclass_declarations((dataclass_type,))

    @staticmethod
    def _dataclass_source(dataclass_type: type) -> ClassSourceDeclaration:
        """Read current loader source, deriving its class block by immutable content."""
        # Python 3.13+ locates class source from __firstlineno__ directly;
        # its native locator does not perform the repeated module AST traversal.
        if sys.version_info >= (3, 13):
            source = inspect.getsource(dataclass_type)
            if source[:1].isspace():
                return ClassSourceDeclaration(source, ())
            tree = SignatureAnalyzer._module_source_tree(source)
            class_node = next((node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)), None)
            if class_node is None:
                return ClassSourceDeclaration(source, ())
            return SignatureAnalyzer._qualified_class_source(source, class_node.name)
        target = inspect.unwrap(dataclass_type)
        if not inspect.isclass(target):
            source = inspect.getsource(target)
            return ClassSourceDeclaration.from_block(source, SignatureAnalyzer._module_source_tree(source))
        file = inspect.getsourcefile(target)
        if file:
            linecache.checkcache(file)
        else:
            file = inspect.getfile(target)
            if not (file.startswith('<') and file.endswith('>')):
                raise OSError('source code not available')
        module = inspect.getmodule(target, file)
        lines = linecache.getlines(file, module.__dict__) if module else linecache.getlines(file)
        if not lines:
            raise OSError('could not get source code')
        source = SignatureAnalyzer._qualified_class_source(''.join(lines), target.__qualname__)
        if source is None:
            raise OSError('could not find class definition')
        return source

    @staticmethod
    @lru_cache(maxsize=32)
    def _module_source_tree(source: str) -> ast.AST:
        """Parse current immutable module bytes once; never expose the retained AST."""
        return ast.parse(source)

    @staticmethod
    @lru_cache(maxsize=256)
    def _qualified_class_source(source: str, qualname: str) -> Optional[ClassSourceDeclaration]:
        """Use Python's qualified class/decorator locator on current source content."""
        tree = SignatureAnalyzer._module_source_tree(source)
        class_node = _class_node_for_qualname(tree, qualname)
        if class_node is None:
            return None
        first_line = min([class_node.lineno, *(decorator.lineno for decorator in class_node.decorator_list)])
        lines = source.splitlines(keepends=True)
        block = ''.join(inspect.getblock(lines[first_line - 1:]))
        return ClassSourceDeclaration.from_block(block, class_node, first_line)

    @staticmethod
    def _extract_inline_field_docs(dataclass_type: type) -> Dict[str, str]:
        """Extract inline field documentation strings using AST parsing.

        This handles multiple patterns used for field documentation:

        Pattern 1 - Next line string literal:
        @dataclass
        class Config:
            field_name: str = "default"
            '''Field description here.'''

        Pattern 2 - Same line string literal (less common):
        @dataclass
        class Config:
            field_name: str = "default"  # '''Field description'''

        Pattern 3 - Traditional docstring parameters (handled by DocstringExtractor):
        @dataclass
        class Config:
            '''
            Args:
                field_name: Field description here.
            '''
            field_name: str = "default"
        """
        try:
            try:
                declaration = SignatureAnalyzer._dataclass_source(dataclass_type)
            except (OSError, TypeError):
                source_file = inspect.getfile(dataclass_type)
                with open(source_file, 'r', encoding='utf-8') as source_stream:
                    source = SignatureAnalyzer._extract_class_source_from_file(
                        source_stream.read(), dataclass_type.__name__
                    )
                if not source:
                    return {}
                declaration = SignatureAnalyzer._qualified_class_source(source, dataclass_type.__name__)
                if declaration is None:
                    return {}
            return declaration.field_documentation(dataclass_type.__name__)
        except Exception:
            # Preserve the extractor's unavailable/unparsable-source boundary.
            return {}

    @staticmethod
    def _extract_field_type_docs(dataclass_type: type) -> Dict[str, str]:
        """Extract field documentation from field types for decorator-modified dataclasses.

        This handles cases where dataclasses have been modified by decorators (like @auto_create_decorator)
        that inject fields from other dataclasses. In such cases, the AST parsing of the main class
        won't find documentation for the injected fields, so we need to extract documentation from
        the field types themselves.

        For example, a decorated config may inject a field whose type is another
        dataclass. We extract that dataclass docstring for the field description.
        """
        try:
            import dataclasses

            field_type_docs = {}

            # Get all dataclass fields
            if not dataclasses.is_dataclass(dataclass_type):
                return {}

            fields = dataclasses.fields(dataclass_type)
            type_hints = get_type_hints(dataclass_type, include_extras=True)

            for field in fields:
                # Check if this field's type is a dataclass
                field_type = type_hints.get(field.name, field.type)

                optional_type = optional_member_type(field_type)
                if optional_type is not None:
                    field_type = optional_type

                # If the field type is a dataclass, extract its docstring as field documentation
                if dataclasses.is_dataclass(field_type):
                    # ENHANCEMENT: Resolve lazy dataclasses to their base classes for documentation
                    resolved_field_type = _resolve_type(field_type)

                    docstring_info = DocstringExtractor.extract(resolved_field_type)
                    if docstring_info.summary:
                        field_type_docs[field.name] = docstring_info.summary
                    elif docstring_info.description:
                        # Use first line of description if no summary
                        first_line = docstring_info.description.split('\n')[0].strip()
                        if first_line:
                            field_type_docs[field.name] = first_line

            return field_type_docs

        except Exception:
            # Return empty dict if extraction fails
            return {}

    @staticmethod
    def _extract_class_source_from_file(file_content: str, class_name: str) -> Optional[str]:
        """Extract the source code for a specific class from a file.

        This method is used when inspect.getsource() fails (e.g., for decorator-modified classes)
        to extract the class definition directly from the source file.

        Args:
            file_content: The content of the source file
            class_name: The name of the class to extract

        Returns:
            The source code for the class, or None if not found
        """
        try:
            lines = file_content.split('\n')
            class_lines = []
            in_class = False
            class_indent = 0

            for line in lines:
                # Look for the class definition
                if line.strip().startswith(f'class {class_name}'):
                    in_class = True
                    class_indent = len(line) - len(line.lstrip())
                    class_lines.append(line)
                elif in_class:
                    # Check if we've reached the end of the class
                    if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                        # Non-indented line that's not empty - end of class
                        break
                    elif line.strip() and len(line) - len(line.lstrip()) <= class_indent:
                        # Line at same or less indentation than class - end of class
                        break
                    else:
                        # Still inside the class
                        class_lines.append(line)

            if class_lines:
                return '\n'.join(class_lines)
            return None

        except Exception:
            return None

    @staticmethod
    def extract_field_documentation(dataclass_type: type, field_name: str) -> Optional[str]:
        """Extract documentation for a specific field from a dataclass.

        This method tries multiple approaches to find documentation for a specific field:
        1. Inline field documentation (AST parsing)
        2. Field type documentation (for nested dataclasses)
        3. Docstring parameters
        4. Field metadata

        Args:
            dataclass_type: The dataclass type containing the field
            field_name: Name of the field to get documentation for

        Returns:
            Field documentation string, or None if not found
        """
        try:
            import dataclasses

            if not dataclasses.is_dataclass(dataclass_type):
                return None

            # ENHANCEMENT: Resolve lazy dataclasses to their base classes
            # Frameworks can register explicit proxy-to-public type resolvers.
            resolved_type = _resolve_type(dataclass_type)

            # Check cache first for performance
            cache_key = (resolved_type.__name__, resolved_type.__module__)
            if cache_key not in SignatureAnalyzer._field_docs_cache:
                # Extract all field documentation for this dataclass and cache it
                SignatureAnalyzer._field_docs_cache[cache_key] = SignatureAnalyzer._extract_all_field_docs(resolved_type)

            cached_docs = SignatureAnalyzer._field_docs_cache[cache_key]
            if field_name in cached_docs:
                return cached_docs[field_name]

            return None

        except Exception:
            return None

    def _extract_all_field_docs(dataclass_type: type) -> Dict[str, str]:
        """Extract all field documentation for a dataclass and return as a dictionary.

        This method combines all documentation extraction approaches and caches the results.

        Args:
            dataclass_type: The dataclass type to extract documentation from

        Returns:
            Dictionary mapping field names to their documentation
        """
        all_docs = {}

        try:
            import dataclasses

            # Try inline field documentation first
            inline_docs = SignatureAnalyzer._extract_inline_field_docs(dataclass_type)
            all_docs.update(inline_docs)

            # Try field type documentation (for nested dataclasses)
            field_type_docs = SignatureAnalyzer._extract_field_type_docs(dataclass_type)
            for field_name, doc in field_type_docs.items():
                if field_name not in all_docs:  # Don't overwrite inline docs
                    all_docs[field_name] = doc

            # Try docstring parameters
            docstring_info = DocstringExtractor.extract(dataclass_type)
            if docstring_info.parameters:
                for field_name, doc in docstring_info.parameters.items():
                    if field_name not in all_docs:  # Don't overwrite previous docs
                        all_docs[field_name] = doc

            # Try field metadata
            fields = dataclasses.fields(dataclass_type)
            for field in fields:
                if field.name not in all_docs:  # Don't overwrite previous docs
                    if 'description' in field.metadata:
                        all_docs[field.name] = field.metadata['description']

            # ENHANCEMENT: Try inheritance - check parent classes for missing field documentation
            for field in fields:
                if field.name not in all_docs:  # Only for fields still missing documentation
                    # Walk up the inheritance chain
                    for base_class in inspect.getmro(dataclass_type)[1:]:
                        if base_class == object:
                            continue
                        if dataclasses.is_dataclass(base_class):
                            # Check if this base class has the field with documentation
                            try:
                                base_fields = dataclasses.fields(base_class)
                                base_field_names = [f.name for f in base_fields]
                                if field.name in base_field_names:
                                    # Try to get documentation from the base class
                                    inherited_doc = SignatureAnalyzer.extract_field_documentation(base_class, field.name)
                                    if inherited_doc:
                                        all_docs[field.name] = inherited_doc
                                        break  # Found documentation, stop looking
                            except Exception:
                                continue  # Try next base class

        except Exception:
            pass  # Return whatever we managed to extract

        return all_docs

    @staticmethod
    def extract_field_documentation_from_context(field_name: str, context_types: list[type]) -> Optional[str]:
        """Extract field documentation by searching through multiple dataclass types.

        This method is useful when you don't know exactly which dataclass contains
        a field, but you have a list of candidate types to search through.

        Args:
            field_name: Name of the field to get documentation for
            context_types: List of dataclass types to search through

        Returns:
            Field documentation string, or None if not found
        """
        for dataclass_type in context_types:
            if dataclass_type:
                doc = SignatureAnalyzer.extract_field_documentation(dataclass_type, field_name)
                if doc:
                    return doc
        return None

    @staticmethod
    def _analyze_dataclass_instance(instance: object) -> Dict[str, ParameterInfo]:
        """Extract parameter information from a dataclass instance.

        Defaults come from the dataclass type, not from current instance values.
        Instance values are caller-owned current state, not signature defaults.
        """
        try:
            return SignatureAnalyzer._analyze_dataclass(type(instance))

        except Exception:
            return {}

    # Duplicate method removed - using the fixed version above
