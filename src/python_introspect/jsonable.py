"""JSON-native projection of declared Python values.

``to_jsonable`` is the encoder paired with ``dataclass_from_mapping``: a
dataclass projects through its declared fields, and the decoder rebuilds it
from the same declarations. Further value types join through
``to_jsonable.register``.

A class registered in an ``AutoRegisterMeta`` family travels as its registry
key; ``registered_class_from_key`` is the inverse the decoder uses for fields
annotated ``type[Family]``. A family whose boundary spelling is not its
registry (for example one resolved through an active subset) registers its own
decoder on its metaclass.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from functools import singledispatch
from pathlib import Path
from typing import ForwardRef, TypeAlias

from metaclass_registry import AutoRegisterMeta

from .choices import AnnotationChoices
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


@singledispatch
def registered_class_from_key(family: type, key: JsonValue) -> type:
    """Return the member of ``family`` that ``to_jsonable`` spells as ``key``.

    Dispatches on the family's metaclass, mirroring how ``to_jsonable``
    dispatches a registered class on its metaclass.
    """

    raise TypeError(
        f"{family.__qualname__} is not a registered family; "
        f"cannot decode {key!r} into one of its classes."
    )


def _json_key(registered_key: object) -> JsonValue:
    """A registry key as ``to_jsonable`` spells it; scalar keys are their own spelling.

    Decoding reads scalar keys directly so it never runs the encoder.
    """

    if isinstance(registered_key, (str, int, float, bool)):
        return registered_key
    return to_jsonable(registered_key)


@registered_class_from_key.register(AutoRegisterMeta)
def _registered_class_from_registry(family: AutoRegisterMeta, key: JsonValue) -> type:
    keys_by_member = {
        member: _json_key(registered_key)
        for registered_key, member in family.__registry__.items()
        if issubclass(member, family)
    }
    matches = [member for member, member_key in keys_by_member.items() if member_key == key]
    if len(matches) != 1:
        raise ValueError(
            f"{key!r} is not a registered {family.__qualname__}; "
            f"registered: {sorted(map(str, keys_by_member.values()))}."
        )
    return matches[0]


@dataclass(frozen=True)
class RegisteredClassChoices(AnnotationChoices):
    """A field holding one class of a registered family.

    The choices are the family's registered members in registration order, each
    labelled by its JSON spelling (its registry key).
    """

    family: AutoRegisterMeta

    def choices(self) -> tuple[object, ...]:
        return tuple(
            member
            for member in self.family.__registry__.values()
            if issubclass(member, self.family)
        )

    def label(self, choice: object) -> str:
        return str(to_jsonable(choice))

    def __get_pydantic_core_schema__(self, source_type, handler):
        """Let pydantic accept a member or its registry key and emit the key."""

        from pydantic_core import core_schema

        def member(value: object) -> type:
            if isinstance(value, type):
                if issubclass(value, self.family):
                    return value
                raise ValueError(f"{value!r} is not a {self.family.__qualname__}.")
            return registered_class_from_key(self.family, value)

        return core_schema.no_info_plain_validator_function(
            member,
            ref=f"{self.family.__module__}.{self.family.__qualname__}",
            json_schema_input_schema=core_schema.literal_schema(
                [to_jsonable(choice) for choice in self.choices()]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(to_jsonable),
        )

    def __get_pydantic_json_schema__(self, core_schema, handler):
        """Publish the family as a named string enum of its registry keys."""

        description = (self.family.__doc__ or "").strip().split("\n\n")[0]
        schema = {
            "enum": [to_jsonable(choice) for choice in self.choices()],
            "title": self.family.__name__,
            "type": "string",
        }
        if description:
            schema["description"] = " ".join(description.split())
        reference = handler(core_schema)
        definition = handler.resolve_ref_schema(reference)
        definition.clear()
        definition.update(schema)
        return reference


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
