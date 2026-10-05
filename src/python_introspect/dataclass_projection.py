"""Dataclass construction and projection derived from declared annotations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Literal,
    TypeVar,
    get_args,
    get_origin,
)

from .annotation_types import is_union_type, resolved_class_annotations
from .validation import validate_annotated_dataclass, validate_annotation_value

DataclassT = TypeVar("DataclassT")


def dataclass_from_mapping(
    target_type: type[DataclassT],
    values: Mapping[str, object],
) -> DataclassT:
    """Construct declared init fields and verify supplied constructor-owned fields.

    Non-init fields belong to the dataclass's defaults or post-init behavior,
    not the input mapping. If supplied, they must agree with that owner.
    """

    if not isinstance(target_type, type) or not is_dataclass(target_type):
        raise TypeError(
            "dataclass_from_mapping requires a dataclass type; " f"got {target_type!r}."
        )
    if not isinstance(values, Mapping):
        raise TypeError("dataclass_from_mapping requires a mapping.")
    non_text_keys = tuple(key for key in values if not isinstance(key, str))
    if non_text_keys:
        raise TypeError(
            f"{target_type.__name__} field names must be strings; "
            f"got {non_text_keys!r}."
        )

    declared_fields = fields(target_type)
    declared_names = {declared_field.name for declared_field in declared_fields}
    extras = tuple(sorted(set(values) - declared_names))
    if extras:
        raise ValueError(
            f"{target_type.__name__} received undeclared field(s): {', '.join(extras)}."
        )

    annotations = resolved_class_annotations(target_type)
    decoded_values: dict[str, object] = {}
    missing: list[str] = []
    for declared_field in declared_fields:
        if declared_field.name not in values:
            if (
                declared_field.init
                and declared_field.default is MISSING
                and declared_field.default_factory is MISSING
            ):
                missing.append(declared_field.name)
            continue
        annotation = annotations.get(declared_field.name, declared_field.type)
        decoded_values[declared_field.name] = _mapping_value_for_annotation(
            annotation,
            values[declared_field.name],
            path=f"{target_type.__name__}.{declared_field.name}",
        )
    if missing:
        raise ValueError(
            f"{target_type.__name__} is missing required field(s): {', '.join(missing)}."
        )

    result = target_type(
        **{
            declared_field.name: decoded_values[declared_field.name]
            for declared_field in declared_fields
            if declared_field.init and declared_field.name in decoded_values
        }
    )
    validate_annotated_dataclass(result)
    for declared_field in declared_fields:
        if not declared_field.init and declared_field.name in decoded_values:
            if decoded_values[declared_field.name] != object.__getattribute__(
                result, declared_field.name
            ):
                raise ValueError(
                    f"{target_type.__name__}.{declared_field.name} disagrees with "
                    "its constructed value."
                )
    return result


def project_dataclass(
    target_type: type[DataclassT],
    source: object,
    **overrides: object,
) -> DataclassT:
    """Project shared declared fields from one dataclass into another."""

    if not isinstance(target_type, type) or not is_dataclass(target_type):
        raise TypeError(
            "project_dataclass requires a dataclass target type; "
            f"got {target_type!r}."
        )
    if not is_dataclass(source) or isinstance(source, type):
        raise TypeError("project_dataclass requires a dataclass source instance.")

    target_fields = tuple(
        declared_field for declared_field in fields(target_type) if declared_field.init
    )
    target_names = {declared_field.name for declared_field in target_fields}
    invalid_overrides = tuple(sorted(set(overrides) - target_names))
    if invalid_overrides:
        raise ValueError(
            f"{target_type.__name__} received undeclared override(s): "
            f"{', '.join(invalid_overrides)}."
        )

    source_values = {
        declared_field.name: object.__getattribute__(source, declared_field.name)
        for declared_field in fields(source)
    }
    constructor_values = {
        declared_field.name: source_values[declared_field.name]
        for declared_field in target_fields
        if declared_field.name in source_values
    }
    constructor_values.update(overrides)
    result = target_type(**constructor_values)
    validate_annotated_dataclass(result)
    return result


def _mapping_value_for_annotation(
    annotation: object,
    value: object,
    *,
    path: str,
) -> object:
    origin = get_origin(annotation)
    if origin is Annotated:
        base_type = get_args(annotation)[0]
        converted = _mapping_value_for_annotation(base_type, value, path=path)
        validate_annotation_value(annotation, converted, path=path)
        return converted
    if annotation is Any:
        return value
    if annotation is tuple:
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"{path} must be an array.")
        return tuple(value)
    if is_union_type(annotation):
        successes: list[object] = []
        errors: list[Exception] = []
        for member_type in get_args(annotation):
            try:
                converted = _mapping_value_for_annotation(
                    member_type,
                    value,
                    path=path,
                )
                validate_annotation_value(member_type, converted, path=path)
            except (TypeError, ValueError) as error:
                errors.append(error)
                continue
            successes.append(converted)
        if len(successes) == 1:
            return successes[0]
        exact_matches = tuple(
            converted for converted in successes if type(converted) is type(value)
        )
        if len(exact_matches) == 1:
            return exact_matches[0]
        if successes:
            raise TypeError(
                f"{path} ambiguously matches multiple members of {annotation!r}."
            )
        value_errors = tuple(error for error in errors if isinstance(error, ValueError))
        if len(value_errors) == 1:
            raise value_errors[0]
        if value_errors:
            details = "; ".join(str(error) for error in value_errors)
            raise ValueError(
                f"{path} does not match any constrained union member: {details}"
            )
        detail = f" Last error: {errors[-1]}" if errors else ""
        raise TypeError(f"{path} does not match its declared union.{detail}") from (
            errors[-1] if errors else None
        )
    if origin is Literal:
        validate_annotation_value(annotation, value, path=path)
        return value
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"{path} must be an array.")
        member_types = get_args(annotation)
        if not member_types:
            return tuple(value)
        if len(member_types) == 2 and member_types[1] is Ellipsis:
            return tuple(
                _mapping_value_for_annotation(
                    member_types[0],
                    item,
                    path=f"{path}[{index}]",
                )
                for index, item in enumerate(value)
            )
        if member_types and len(value) != len(member_types):
            raise ValueError(
                f"{path} must contain {len(member_types)} item(s); got {len(value)}."
            )
        return tuple(
            _mapping_value_for_annotation(
                member_type,
                item,
                path=f"{path}[{index}]",
            )
            for index, (member_type, item) in enumerate(zip(member_types, value))
        )
    if origin in {list, Sequence}:
        if (origin is list and not isinstance(value, list)) or (
            origin is Sequence
            and (
                not isinstance(value, Sequence)
                or isinstance(value, (str, bytes, bytearray))
            )
        ):
            raise TypeError(f"{path} must be an array.")
        member_types = get_args(annotation)
        if not member_types:
            return list(value) if origin is list else tuple(value)
        converted = [
            _mapping_value_for_annotation(
                member_types[0],
                item,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
        return converted if origin is list else tuple(converted)
    if origin in {dict, Mapping}:
        if not isinstance(value, Mapping):
            raise TypeError(f"{path} must be an object.")
        member_types = get_args(annotation)
        if len(member_types) != 2:
            return dict(value)
        key_type, item_type = member_types
        return {
            _mapping_value_for_annotation(
                key_type,
                key,
                path=f"{path}.key",
            ): _mapping_value_for_annotation(
                item_type,
                item,
                path=f"{path}[{key!r}]",
            )
            for key, item in value.items()
        }
    if annotation is type(None):
        if value is not None:
            raise TypeError(f"{path} must be null.")
        return None
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if isinstance(value, annotation):
            return value
        try:
            return annotation(value)
        except ValueError as error:
            choices = tuple(member.value for member in annotation)
            raise ValueError(
                f"{path} must be one of {choices!r}; got {value!r}."
            ) from error
    if isinstance(annotation, type) and is_dataclass(annotation):
        if isinstance(value, annotation):
            return value
        if not isinstance(value, Mapping):
            raise TypeError(f"{path} must be an object.")
        return dataclass_from_mapping(annotation, value)
    if annotation is Path:
        if isinstance(value, Path):
            return value
        if not isinstance(value, str):
            raise TypeError(f"{path} must be a path string.")
        return Path(value)
    if annotation is float and type(value) is int:
        return float(value)
    validate_annotation_value(annotation, value, path=path)
    return value
