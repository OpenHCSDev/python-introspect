"""Typed annotation inference from callable defaults and docstring declarations."""

from __future__ import annotations

import inspect
import re
from abc import ABC
from collections.abc import Callable, Mapping, Sequence
from functools import reduce
from operator import or_
from typing import Any, ClassVar

from metaclass_registry import AutoRegisterMeta

from .annotation_types import make_optional
from .validation import validate_annotation_value


class DocstringTypeDeclaration(ABC, metaclass=AutoRegisterMeta):
    """Nominal owner for one family of docstring type expressions."""

    __registry_key__ = "declaration_name"
    __skip_if_no_key__ = True

    declaration_name: ClassVar[str | None] = None
    expression_pattern: ClassVar[re.Pattern[str] | None] = None
    annotation: ClassVar[object | None] = None

    @classmethod
    def annotations_for(cls, description: str | None) -> tuple[object, ...]:
        """Return every declaration matched by the parameter's type expression."""

        expression = _type_expression(description)
        if not expression:
            return ()
        annotations = {
            declaration.require_annotation()
            for declaration_type in cls.__registry__.values()
            for declaration in (declaration_type(),)
            if declaration.matches(expression)
        }
        return tuple(sorted(annotations, key=_annotation_sort_key))

    def matches(self, expression: str) -> bool:
        """Return whether this declaration owns a token in ``expression``."""

        pattern = type(self).expression_pattern
        return pattern is not None and pattern.search(expression) is not None

    def require_annotation(self) -> object:
        """Return the annotation owned by this concrete declaration."""

        annotation = type(self).annotation
        if annotation is None:
            raise TypeError(f"{type(self).__name__}.annotation must declare a Python type.")
        return annotation


class BooleanDocstringType(DocstringTypeDeclaration):
    declaration_name = "boolean"
    expression_pattern = re.compile(r"\b(?:bool|boolean|true|false)\b")
    annotation = bool


class IntegerDocstringType(DocstringTypeDeclaration):
    declaration_name = "integer"
    expression_pattern = re.compile(r"\b(?:int|integer|ints|integers)\b")
    annotation = int


class FloatDocstringType(DocstringTypeDeclaration):
    declaration_name = "float"
    expression_pattern = re.compile(r"\b(?:float|double|scalar|scalars|number|numeric)\b")
    annotation = float


class StringDocstringType(DocstringTypeDeclaration):
    declaration_name = "string"
    expression_pattern = re.compile(r"\b(?:str|string|strings)\b")
    annotation = str


class TupleDocstringType(DocstringTypeDeclaration):
    declaration_name = "tuple"
    expression_pattern = re.compile(r"\btuple\b")
    annotation = tuple[Any, ...]


class SequenceDocstringType(DocstringTypeDeclaration):
    declaration_name = "sequence"
    expression_pattern = re.compile(r"\b(?:ndarray|array(?:[_ -]?like)?|sequence|iterable)\b")
    annotation = Sequence[Any]


class ListDocstringType(DocstringTypeDeclaration):
    declaration_name = "list"
    expression_pattern = re.compile(r"\blist\b")
    annotation = list[Any]


class MappingDocstringType(DocstringTypeDeclaration):
    declaration_name = "mapping"
    expression_pattern = re.compile(r"\b(?:dict|dictionary|mapping)\b")
    annotation = Mapping[str, Any]


class CallableDocstringType(DocstringTypeDeclaration):
    declaration_name = "callable"
    expression_pattern = re.compile(r"\b(?:callable|function)\b")
    annotation = Callable[..., Any]


def infer_parameter_annotation(
    parameter: inspect.Parameter,
    description: str | None,
) -> object:
    """Infer one missing annotation from declaration-owned runtime evidence."""

    if parameter.annotation is not inspect.Parameter.empty:
        return parameter.annotation

    documented = DocstringTypeDeclaration.annotations_for(description)
    default = parameter.default
    if default is inspect.Parameter.empty:
        return _union_annotation(documented) if documented else Any
    if default is None:
        inferred = _union_annotation(documented)
        return Any if inferred is Any else make_optional(inferred)
    if documented and any(
        _annotation_accepts_default(annotation, default) for annotation in documented
    ):
        return _union_annotation(documented)
    return type(default)


def _type_expression(description: str | None) -> str:
    """Return the first non-empty docstring line that declares a parameter type."""

    if not description:
        return ""
    expression = next(
        (line.strip().lower() for line in description.splitlines() if line.strip()),
        "",
    )
    return _without_nested_type_arguments(expression)


def _without_nested_type_arguments(expression: str) -> str:
    """Remove bracketed member signatures while retaining their owning type."""

    depth = 0
    projected: list[str] = []
    for character in expression:
        if character == "[":
            depth += 1
            continue
        if character == "]":
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            projected.append(character)
    return "".join(projected)


def _union_annotation(annotations: tuple[object, ...]) -> object:
    if not annotations:
        return Any
    if len(annotations) == 1:
        return annotations[0]
    return reduce(or_, annotations)


def _annotation_accepts_default(annotation: object, default: object) -> bool:
    try:
        validate_annotation_value(annotation, default, path="parameter default")
    except (TypeError, ValueError):
        return False
    return True


def _annotation_sort_key(annotation: object) -> tuple[str, str]:
    origin = getattr(annotation, "__origin__", None)
    owner = origin or annotation
    return (
        str(getattr(owner, "__module__", "")),
        str(getattr(owner, "__qualname__", annotation)),
    )


__all__ = [
    "DocstringTypeDeclaration",
    "infer_parameter_annotation",
]
