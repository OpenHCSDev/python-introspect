"""Generic operations derived directly from Python type annotations."""

from __future__ import annotations

import types
from enum import Enum
from typing import Annotated, Union, get_args, get_origin


def is_union_type(annotation: object) -> bool:
    """Return whether ``annotation`` is a typing or PEP 604 union."""

    return get_origin(annotation) in {Union, types.UnionType}


def optional_member_type(annotation: object) -> object | None:
    """Return ``T`` only for the simple optional declaration ``T | None``."""

    if not is_union_type(annotation):
        return None
    members = get_args(annotation)
    if len(members) != 2 or type(None) not in members:
        return None
    return next(member for member in members if member is not type(None))


def make_optional(annotation: object) -> object:
    """Return the same declaration with ``None`` admitted exactly once."""

    if is_union_type(annotation) and type(None) in get_args(annotation):
        return annotation
    return Union[annotation, type(None)]


def resolve_optional(annotation: object) -> object:
    """Resolve an optional declaration to its non-None member declaration."""

    member_type = optional_member_type(annotation)
    return annotation if member_type is None else member_type


def resolve_annotated(annotation: object) -> object:
    """Resolve an ``Annotated[T, ...]`` declaration to its owned type ``T``."""

    if get_origin(annotation) is Annotated:
        return get_args(annotation)[0]
    return annotation


def is_enum_type(annotation: object) -> bool:
    """Return whether the declaration is an enum type."""

    return isinstance(annotation, type) and issubclass(annotation, Enum)


def enum_member_type(annotation: object) -> type[Enum] | None:
    """Return the enum type declared directly or as a simple optional."""

    if is_enum_type(annotation):
        return annotation
    if not is_union_type(annotation):
        return None
    members = tuple(member for member in get_args(annotation) if member is not type(None))
    if len(members) != 1 or not is_enum_type(members[0]):
        return None
    return members[0]


def declared_enum_type(annotation: object) -> type[Enum] | None:
    """Return the enum carried by transparent annotation wrappers.

    Schema and transport projections need to recognise the same enum when it is
    wrapped by ``Annotated``, ``Optional``, or a homogeneous container.  Mixed
    unions and heterogeneous containers admit values outside that enum, so they
    deliberately have no single declared enum owner.
    """

    resolved = resolve_annotated(annotation)
    if is_enum_type(resolved):
        return resolved

    optional_member = optional_member_type(resolved)
    if optional_member is not None:
        return declared_enum_type(optional_member)

    origin = get_origin(resolved)
    members = get_args(resolved)
    if origin in {list, set, frozenset} and len(members) == 1:
        return declared_enum_type(members[0])
    if origin is tuple and len(members) == 2 and members[1] is Ellipsis:
        return declared_enum_type(members[0])

    return None


def enum_input_values(annotation: object) -> tuple[str, ...]:
    """Return declaration-derived string inputs accepted for an enum.

    String-valued members expose their value.  Members whose values are not
    strings expose their name, which keeps JSON and command-line projections
    unambiguous, including enums whose concrete value is ``None``.
    """

    enum_type = declared_enum_type(annotation)
    if enum_type is None:
        return ()
    return tuple(
        member.value if isinstance(member.value, str) else member.name for member in enum_type
    )


def enum_member_names(annotation: object) -> tuple[str, ...]:
    """Return member names for the single enum carried by an annotation."""

    enum_type = declared_enum_type(annotation)
    if enum_type is None:
        return ()
    return tuple(member.name for member in enum_type)


def enum_import_path(annotation: object) -> str | None:
    """Return the import path of the single enum carried by an annotation."""

    enum_type = declared_enum_type(annotation)
    if enum_type is None:
        return None
    return f"{enum_type.__module__}.{enum_type.__qualname__}"


def coerce_enum_member(annotation: object, value: object) -> Enum:
    """Coerce an enum value or declared member name through its annotation."""

    enum_type = declared_enum_type(annotation)
    if enum_type is None:
        raise TypeError(f"Annotation does not declare one enum type: {annotation!r}")
    if isinstance(value, enum_type):
        return value
    for member in enum_type:
        if value == member.value or value == member.name:
            return member
    raise ValueError(f"{value!r} is not a valid {enum_type.__module__}.{enum_type.__name__}")


def is_list_of_enums(annotation: object) -> bool:
    """Return whether the declaration is ``list[SomeEnum]``."""

    members = get_args(annotation)
    return get_origin(annotation) is list and len(members) == 1 and is_enum_type(members[0])


def get_enum_from_list(annotation: object) -> type[Enum] | None:
    """Return the enum type from ``list[SomeEnum]`` when declared."""

    if not is_list_of_enums(annotation):
        return None
    return get_args(annotation)[0]
