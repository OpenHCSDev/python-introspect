"""Environment overlays derived from dataclass annotations."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Annotated, TypeVar, get_args, get_origin, get_type_hints

from .annotation_types import is_union_type, optional_member_type
from .validation import validate_annotated_dataclass, validate_annotation_value


DataclassT = TypeVar("DataclassT")


@dataclass(frozen=True, slots=True)
class EnvironmentVariable:
    """Bind one declared dataclass field to an environment variable."""

    name: str
    clear_on_empty: bool = False

    def __post_init__(self) -> None:
        validate_annotated_dataclass(self)
        if not self.name:
            raise ValueError("Environment variable names must not be empty.")


def overlay_dataclass_from_environment(
    base: DataclassT,
    environment: Mapping[str, str] | None = None,
) -> DataclassT:
    """Overlay environment-bound fields while preserving the dataclass type."""

    if not is_dataclass(base) or isinstance(base, type):
        raise TypeError("overlay_dataclass_from_environment requires a dataclass instance.")
    source = os.environ if environment is None else environment
    owner_type = type(base)
    annotations = get_type_hints(owner_type, include_extras=True)
    replacements: dict[str, object] = {}
    for declared_field in fields(base):
        if not declared_field.init:
            continue
        annotation = annotations.get(declared_field.name, declared_field.type)
        binding = _environment_binding(annotation)
        if binding is None or binding.name not in source:
            continue
        raw_value = source[binding.name]
        if not isinstance(raw_value, str):
            raise TypeError(
                f"{binding.name} must be text; got {type(raw_value).__name__}."
            )
        if raw_value == "":
            if binding.clear_on_empty:
                replacements[declared_field.name] = None
            continue
        replacements[declared_field.name] = _text_value_for_annotation(
            annotation,
            raw_value,
            path=binding.name,
        )

    result = replace(base, **replacements)
    validate_annotated_dataclass(result)
    return result


def _environment_binding(annotation: object) -> EnvironmentVariable | None:
    if get_origin(annotation) is not Annotated:
        return None
    bindings = tuple(
        metadata
        for metadata in get_args(annotation)[1:]
        if isinstance(metadata, EnvironmentVariable)
    )
    if len(bindings) > 1:
        raise TypeError("A field cannot declare multiple environment variables.")
    return bindings[0] if bindings else None


def _text_value_for_annotation(
    annotation: object,
    value: str,
    *,
    path: str,
) -> object:
    origin = get_origin(annotation)
    if origin is Annotated:
        base_type = get_args(annotation)[0]
        converted = _text_value_for_annotation(base_type, value, path=path)
        validate_annotation_value(annotation, converted, path=path)
        return converted
    if is_union_type(annotation):
        member_type = optional_member_type(annotation)
        if member_type is None:
            raise TypeError(
                f"{path} cannot populate ambiguous union {annotation!r} from text."
            )
        return _text_value_for_annotation(member_type, value, path=path)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        try:
            return annotation(value)
        except ValueError as error:
            choices = tuple(member.value for member in annotation)
            raise ValueError(f"{path} must be one of {choices!r}.") from error
    if annotation is Path:
        return Path(value)
    if annotation is str:
        return value
    if annotation is bool:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"{path} must be a boolean value.")
    if annotation is int:
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(f"{path} must be an integer.") from error
    if annotation is float:
        try:
            return float(value)
        except ValueError as error:
            raise ValueError(f"{path} must be a number.") from error
    raise TypeError(f"{path} cannot populate declared type {annotation!r} from text.")
