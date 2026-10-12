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

A dataclass field whose declared type admits several classes (``MemberFamily``:
a union of dataclasses, an abstract dataclass, or a registered class) holds its
value as ``{tag: fields}``. The tag is the member's registry key when its
metaclass registers it and its class name otherwise, so the stored form names
the class instead of leaving the decoder to guess it from the fields present.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence, Set
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from functools import singledispatch
from pathlib import Path
from typing import Annotated, ForwardRef, TypeAlias, get_args, get_origin
from weakref import WeakKeyDictionary

from metaclass_registry import AutoRegisterMeta

from .annotation_types import is_union_type, resolved_class_annotations
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


_FIELD_TYPES_BY_DATACLASS: WeakKeyDictionary[type, Mapping[str, object]] = WeakKeyDictionary()


def _declared_field_types(owner: type) -> Mapping[str, object]:
    if owner not in _FIELD_TYPES_BY_DATACLASS:
        try:
            _FIELD_TYPES_BY_DATACLASS[owner] = resolved_class_annotations(owner)
        except NameError as error:
            raise TypeError(
                f"{owner.__qualname__} cannot be projected: a field type does not resolve "
                f"at run time ({error}). A field's declared type decides its stored form, "
                "so import the name outside TYPE_CHECKING."
            ) from error
    return _FIELD_TYPES_BY_DATACLASS[owner]


def _jsonable_dataclass(value: object) -> JsonValue:
    """Project each field by its declared type, without ``asdict`` deep copies."""

    declared_types = _declared_field_types(type(value))
    return {
        declared_field.name: _jsonable_as_declared(
            declared_types[declared_field.name], getattr(value, declared_field.name)
        )
        for declared_field in fields(value)
    }


def _projects_by_declared_fields(value: object) -> bool:
    """Whether ``to_jsonable`` writes ``value`` as its dataclass fields.

    A type with its own registered projection owns its whole stored form,
    including how that form names the class.
    """

    return (
        is_dataclass(value)
        and not isinstance(value, type)
        and to_jsonable.dispatch(type(value)) in (to_jsonable.registry[object], _jsonable_callable)
    )


def _jsonable_as_declared(annotation: object, value: object) -> JsonValue:
    """Project ``value`` as a field declared ``annotation`` stores it.

    The declaration is followed through optional, annotated and container types
    to the places where it admits several classes; a value there is wrapped in
    its member tag. Everything else projects by its own type.
    """

    if value is None:
        return None
    origin = get_origin(annotation)
    if origin is Annotated:
        return _jsonable_as_declared(get_args(annotation)[0], value)
    family = MemberFamily.declared_by(annotation)
    if family is not None and _projects_by_declared_fields(value):
        return {family.tag_of(type(value)): to_jsonable(value)}
    if is_union_type(annotation):
        arms = tuple(
            arm
            for arm in get_args(annotation)
            if isinstance(runtime_class := get_origin(arm) or arm, type)
            and runtime_class is not type(None)
            and isinstance(value, runtime_class)
        )
        return _jsonable_as_declared(arms[0], value) if len(arms) == 1 else to_jsonable(value)
    item_types = get_args(annotation)
    if (
        isinstance(origin, type)
        and item_types
        and isinstance(value, origin)
        and not isinstance(value, (str, bytes, bytearray))
    ):
        if issubclass(origin, Mapping) and len(item_types) == 2:
            return {
                str(to_jsonable(key)): _jsonable_as_declared(item_types[1], item)
                for key, item in value.items()
            }
        if origin is tuple and Ellipsis not in item_types and len(item_types) == len(value):
            return [
                _jsonable_as_declared(item_type, item) for item_type, item in zip(item_types, value)
            ]
        if issubclass(origin, (Sequence, Set)):
            return [_jsonable_as_declared(item_types[0], item) for item in value]
    return to_jsonable(value)


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
            f"Registered type {value.__qualname__} has no declared {key_attribute!r} key."
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


class MemberFamily(ABC):
    """The classes a declared field type admits, each named by one tag.

    A value of such a field is stored as ``{tag: fields}``. Three declarations
    form a family: a union with two or more dataclass members, an abstract
    dataclass (its concrete subclasses are the members) and a class registered
    by ``AutoRegisterMeta`` (the registry's classes are the members).
    """

    @staticmethod
    def declared_by(annotation: object) -> MemberFamily | None:
        """The family ``annotation`` declares, or None when it names one class."""

        if is_union_type(annotation):
            members = tuple(
                member
                for member in get_args(annotation)
                if isinstance(member, type) and is_dataclass(member)
            )
            return UnionMembers(members) if len(members) > 1 else None
        if isinstance(annotation, AutoRegisterMeta):
            return RegisteredMembers(annotation)
        if (
            isinstance(annotation, type)
            and is_dataclass(annotation)
            and inspect.isabstract(annotation)
        ):
            return ConcreteSubclasses(annotation)
        return None

    @property
    @abstractmethod
    def name(self) -> str:
        """How error messages refer to the family."""

    @abstractmethod
    def members(self) -> tuple[type, ...]:
        """The classes a value of the field may be."""

    def member_tagged(self, tag: str) -> type:
        """The member a stored tag names."""

        members = self._members_by_tag()
        if tag not in members:
            raise ValueError(f"{tag!r} is not a member of {self.name}; members: {sorted(members)}.")
        return members[tag]

    def tag_of(self, member: type) -> str:
        """The tag that names ``member`` in stored data."""

        tags = {known: tag for tag, known in self._members_by_tag().items()}
        if member not in tags:
            raise TypeError(
                f"{member.__qualname__} is not a member of {self.name}; "
                f"members: {sorted(tags.values())}."
            )
        return tags[member]

    def _members_by_tag(self) -> dict[str, type]:
        members: dict[str, type] = {}
        for member in self.members():
            tag = class_tag(member)
            if members.setdefault(tag, member) is not member:
                raise TypeError(
                    f"{self.name} has two members tagged {tag!r}: "
                    f"{members[tag].__qualname__} and {member.__qualname__}."
                )
        return members


def class_tag(member: type) -> str:
    """The tag naming ``member``: its registry key if it is registered, else its name."""

    tag = to_jsonable(member) if isinstance(member, AutoRegisterMeta) else member.__name__
    if not isinstance(tag, str):
        raise TypeError(
            f"{member.__qualname__} has the registry key {tag!r}; a member tag is a string."
        )
    return tag


@dataclass(frozen=True)
class UnionMembers(MemberFamily):
    """The dataclasses listed in a union; its other arms are stored untagged.

    An arm that is itself a family contributes that family's members.
    """

    listed: tuple[type, ...]

    @property
    def name(self) -> str:
        return " | ".join(member.__qualname__ for member in self.listed)

    def members(self) -> tuple[type, ...]:
        members: list[type] = []
        for arm in self.listed:
            family = MemberFamily.declared_by(arm)
            members.extend((arm,) if family is None else family.members())
        return tuple(members)


@dataclass(frozen=True)
class ConcreteSubclasses(MemberFamily):
    """The concrete subclasses of an abstract dataclass, as loaded when asked."""

    base: type

    @property
    def name(self) -> str:
        return self.base.__qualname__

    def members(self) -> tuple[type, ...]:
        found: dict[type, None] = {}
        pending = list(self.base.__subclasses__())
        while pending:
            subclass = pending.pop(0)
            pending.extend(subclass.__subclasses__())
            if not inspect.isabstract(subclass):
                found[subclass] = None
        return tuple(found)


@dataclass(frozen=True)
class RegisteredMembers(ConcreteSubclasses):
    """The classes a registered family's registry holds, tagged by registry key.

    A stored tag is read by ``registered_class_from_key``, so a family with its
    own spelling decodes tags the way it decodes ``type[Family]`` fields.
    """

    def members(self) -> tuple[type, ...]:
        return tuple(
            member for member in self.base.__registry__.values() if issubclass(member, self.base)
        )

    def member_tagged(self, tag: str) -> type:
        return registered_class_from_key(self.base, tag)


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
