"""JSON-native projection of declared Python values.

``to_jsonable`` is the encoder paired with ``dataclass_from_mapping``: a
dataclass projects through its declared fields, and the decoder rebuilds it
from the same declarations. Further value types join through
``to_jsonable.register``.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from functools import singledispatch
from pathlib import Path
from typing import ForwardRef, TypeAlias

from metaclass_registry import AutoRegisterMeta

from .signature_analyzer import signature_analysis_target

JsonScalar: TypeAlias = str | int | float | bool | None
# Recursive aliases retain this declaration's namespace when imported by
# dataclasses; get_type_hints evaluates the reference in this module.
_JSON_VALUE_REFERENCE = ForwardRef("JsonValue", module=__name__)
JsonValue: TypeAlias = (
    JsonScalar
    | Mapping[str, _JSON_VALUE_REFERENCE]
    | tuple[_JSON_VALUE_REFERENCE, ...]
    | list[_JSON_VALUE_REFERENCE]
)
JsonObject: TypeAlias = Mapping[str, JsonValue]


def _jsonable_dataclass(value: object) -> JsonValue:
    """Project fields without ``asdict`` deep-copying immutable containers."""

    return {
        declared_field.name: to_jsonable(getattr(value, declared_field.name))
        for declared_field in fields(value)
    }


@singledispatch
def to_jsonable(value: object) -> JsonValue:
    """Project dataclasses and registered values into JSON-native data."""

    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable_dataclass(value)
    raise TypeError(f"Value is not JSON-serializable: {type(value).__name__}")


@to_jsonable.register(Mapping)
def _jsonable_mapping(value: Mapping) -> JsonValue:
    return {str(to_jsonable(key)): to_jsonable(item) for key, item in value.items()}


@to_jsonable.register(tuple)
@to_jsonable.register(list)
@to_jsonable.register(set)
@to_jsonable.register(frozenset)
def _jsonable_sequence(value) -> JsonValue:
    return [to_jsonable(item) for item in value]


@to_jsonable.register(Callable)
def _jsonable_callable(value: Callable[..., object]) -> JsonValue:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable_dataclass(value)
    target = signature_analysis_target(value)
    module = inspect.getmodule(target)
    module_name = type(target).__module__ if module is None else module.__name__
    if inspect.isfunction(target) or inspect.ismethod(target) or inspect.isclass(target):
        qualname = target.__qualname__
    else:
        qualname = type(target).__qualname__
    return {
        "kind": "callable",
        "name": qualname.rsplit(".", 1)[-1],
        "module": module_name,
        "qualname": qualname,
        "import_path": f"{module_name}.{qualname}",
    }


@to_jsonable.register(AutoRegisterMeta)
def _jsonable_registered_type(value: AutoRegisterMeta) -> JsonValue:
    key_attribute = value.__registry_key__
    declaring_owner = next(
        (owner for owner in value.__mro__ if key_attribute in vars(owner)),
        None,
    )
    if declaring_owner is None:
        raise TypeError(
            f"Registered type {value.__qualname__} has no declared " f"{key_attribute!r} key."
        )
    key = vars(declaring_owner)[key_attribute]
    if key is None:
        raise TypeError(f"Registered type {value.__qualname__} has no registry key.")
    return to_jsonable(key)


@to_jsonable.register(Enum)
def _jsonable_enum(value: Enum) -> JsonValue:
    return to_jsonable(value.value)


@to_jsonable.register(Path)
def _jsonable_path(value: Path) -> JsonValue:
    return str(value)


@to_jsonable.register(type(None))
@to_jsonable.register(str)
@to_jsonable.register(int)
@to_jsonable.register(float)
@to_jsonable.register(bool)
def _jsonable_scalar(value) -> JsonValue:
    return value
