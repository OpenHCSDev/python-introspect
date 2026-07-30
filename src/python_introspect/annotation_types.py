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
    members = tuple(
        member for member in get_args(annotation) if member is not type(None)
    )
    if len(members) != 1 or not is_enum_type(members[0]):
        return None
    return members[0]


def is_list_of_enums(annotation: object) -> bool:
    """Return whether the declaration is ``list[SomeEnum]``."""

    members = get_args(annotation)
    return (
        get_origin(annotation) is list
        and len(members) == 1
        and is_enum_type(members[0])
    )


def get_enum_from_list(annotation: object) -> type[Enum] | None:
    """Return the enum type from ``list[SomeEnum]`` when declared."""

    if not is_list_of_enums(annotation):
        return None
    return get_args(annotation)[0]
