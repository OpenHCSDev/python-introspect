"""Runtime validation derived from declared Python type annotations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import fields, is_dataclass, replace
from functools import singledispatch
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    get_args,
    get_origin,
    get_type_hints,
    TypeVar,
)

from annotated_types import Ge, Gt, Interval, Le, Len, Lt, MaxLen, MinLen, Predicate
from .annotation_types import is_union_type


class AnnotationValidationError(ValueError):
    """A runtime value violates its authoritative type annotation."""


DataclassT = TypeVar("DataclassT")


def overlay_non_none_dataclass(
    base: DataclassT,
    overlay: object,
) -> DataclassT:
    """Replace declared fields on ``base`` with non-None overlay values.

    Field identity is derived from the two dataclass declarations. Callers do
    not maintain field-name lists or per-field fallback branches.
    """

    if (
        not is_dataclass(base)
        or isinstance(base, type)
        or not is_dataclass(overlay)
        or isinstance(overlay, type)
    ):
        raise TypeError("overlay_non_none_dataclass requires two dataclass instances.")

    overlay_values = {
        declared_field.name: object.__getattribute__(overlay, declared_field.name)
        for declared_field in fields(overlay)
    }
    replacements = {
        declared_field.name: overlay_values[declared_field.name]
        for declared_field in fields(base)
        if declared_field.init
        and declared_field.name in overlay_values
        and overlay_values[declared_field.name] is not None
    }
    result = replace(base, **replacements)
    validate_annotated_dataclass(result)
    return result


def validate_annotated_dataclass(instance: object) -> None:
    """Validate every field from the instance's resolved dataclass annotations."""

    owner_type = type(instance)
    if not is_dataclass(instance) or isinstance(instance, type):
        raise TypeError(
            "validate_annotated_dataclass requires a dataclass instance; "
            f"got {owner_type.__name__}."
        )

    annotations = get_type_hints(owner_type, include_extras=True)
    for declared_field in fields(instance):
        annotation = annotations.get(declared_field.name, declared_field.type)
        value = object.__getattribute__(instance, declared_field.name)
        validate_annotation_value(
            annotation,
            value,
            path=f"{owner_type.__name__}.{declared_field.name}",
        )


def validate_annotation_value(
    annotation: object,
    value: object,
    *,
    path: str,
) -> None:
    """Validate one value against a resolved annotation and its metadata."""

    origin = get_origin(annotation)
    if origin is Annotated:
        base_type, *metadata = get_args(annotation)
        validate_annotation_value(base_type, value, path=path)
        for constraint in metadata:
            _validate_constraint(constraint, value, path)
        return

    if annotation is Any:
        return
    if is_union_type(annotation):
        errors: list[Exception] = []
        for member_type in get_args(annotation):
            try:
                validate_annotation_value(member_type, value, path=path)
            except (TypeError, ValueError) as error:
                errors.append(error)
                continue
            return
        constraint_errors = [
            error for error in errors if isinstance(error, AnnotationValidationError)
        ]
        if constraint_errors:
            raise constraint_errors[-1]
        expected = " | ".join(_annotation_label(member) for member in get_args(annotation))
        raise TypeError(f"{path} must match {expected}; got {type(value).__name__}.") from (
            errors[-1] if errors else None
        )
    if origin is Literal:
        choices = get_args(annotation)
        if not any(
            type(value) is type(choice) and value == choice
            for choice in choices
        ):
            raise AnnotationValidationError(f"{path} must be one of {choices!r}.")
        return
    if origin is tuple:
        _validate_tuple(annotation, value, path)
        return
    if origin in {list, set, frozenset, Sequence, Set}:
        _validate_sequence(annotation, value, path)
        return
    if origin in {dict, Mapping}:
        _validate_mapping(annotation, value, path)
        return
    if origin is ClassVar:
        return
    if annotation is None or annotation is type(None):
        if value is not None:
            raise TypeError(f"{path} must be None; got {type(value).__name__}.")
        return
    if annotation is bool:
        if type(value) is not bool:
            raise TypeError(f"{path} must be bool; got {type(value).__name__}.")
        return
    if annotation is int:
        if type(value) is not int:
            raise TypeError(f"{path} must be int; got {type(value).__name__}.")
        return
    if annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{path} must be float; got {type(value).__name__}.")
        return
    if isinstance(annotation, type) and not isinstance(value, annotation):
        raise TypeError(
            f"{path} must be {_annotation_label(annotation)}; got {type(value).__name__}."
        )


def _validate_tuple(annotation: object, value: object, path: str) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{path} must be tuple; got {type(value).__name__}.")
    members = get_args(annotation)
    if not members:
        return
    if len(members) == 2 and members[1] is Ellipsis:
        for index, item in enumerate(value):
            validate_annotation_value(members[0], item, path=f"{path}[{index}]")
        return
    if len(value) != len(members):
        raise AnnotationValidationError(
            f"{path} must contain {len(members)} items; got {len(value)}."
        )
    for index, (item, member_type) in enumerate(zip(value, members)):
        validate_annotation_value(member_type, item, path=f"{path}[{index}]")


def _validate_sequence(annotation: object, value: object, path: str) -> None:
    origin = get_origin(annotation)
    expected_type = origin if isinstance(origin, type) else Sequence
    if not isinstance(value, expected_type):
        raise TypeError(
            f"{path} must be {_annotation_label(expected_type)}; got {type(value).__name__}."
        )
    members = get_args(annotation)
    if members:
        for index, item in enumerate(value):
            validate_annotation_value(members[0], item, path=f"{path}[{index}]")


def _validate_mapping(annotation: object, value: object, path: str) -> None:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be a mapping; got {type(value).__name__}.")
    members = get_args(annotation)
    if len(members) != 2:
        return
    key_type, item_type = members
    for key, item in value.items():
        validate_annotation_value(key_type, key, path=f"{path}.key")
        validate_annotation_value(item_type, item, path=f"{path}[{key!r}]")


def _annotation_label(annotation: object) -> str:
    return annotation.__name__ if isinstance(annotation, type) else str(annotation)


@singledispatch
def _validate_constraint(metadata: object, value: object, path: str) -> None:
    """Ignore annotation metadata that does not declare a runtime constraint."""


@_validate_constraint.register
def _(metadata: Ge, value: object, path: str) -> None:
    if value < metadata.ge:
        raise AnnotationValidationError(f"{path} must be at least {metadata.ge}.")


@_validate_constraint.register
def _(metadata: Gt, value: object, path: str) -> None:
    if value <= metadata.gt:
        raise AnnotationValidationError(f"{path} must be greater than {metadata.gt}.")


@_validate_constraint.register
def _(metadata: Le, value: object, path: str) -> None:
    if value > metadata.le:
        raise AnnotationValidationError(f"{path} must be at most {metadata.le}.")


@_validate_constraint.register
def _(metadata: Lt, value: object, path: str) -> None:
    if value >= metadata.lt:
        raise AnnotationValidationError(f"{path} must be less than {metadata.lt}.")


@_validate_constraint.register
def _(metadata: MinLen, value: object, path: str) -> None:
    if len(value) < metadata.min_length:
        raise AnnotationValidationError(
            f"{path} must contain at least {metadata.min_length} item(s)."
        )


@_validate_constraint.register
def _(metadata: MaxLen, value: object, path: str) -> None:
    if len(value) > metadata.max_length:
        raise AnnotationValidationError(
            f"{path} must contain at most {metadata.max_length} item(s)."
        )


@_validate_constraint.register
def _(metadata: Predicate, value: object, path: str) -> None:
    if not metadata.func(value):
        raise AnnotationValidationError(f"{path} does not satisfy {metadata.func.__name__}.")


@_validate_constraint.register
def _(metadata: Interval, value: object, path: str) -> None:
    if metadata.ge is not None:
        _validate_constraint(Ge(metadata.ge), value, path)
    if metadata.gt is not None:
        _validate_constraint(Gt(metadata.gt), value, path)
    if metadata.le is not None:
        _validate_constraint(Le(metadata.le), value, path)
    if metadata.lt is not None:
        _validate_constraint(Lt(metadata.lt), value, path)


@_validate_constraint.register
def _(metadata: Len, value: object, path: str) -> None:
    _validate_constraint(MinLen(metadata.min_length), value, path)
    if metadata.max_length is not None:
        _validate_constraint(MaxLen(metadata.max_length), value, path)
