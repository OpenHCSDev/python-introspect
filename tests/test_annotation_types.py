from enum import Enum
from typing import Annotated, Optional

from python_introspect import (
    enum_member_type,
    get_enum_from_list,
    is_list_of_enums,
    is_union_type,
    make_optional,
    optional_member_type,
    resolve_annotated,
    resolve_optional,
)


class Mode(Enum):
    FIRST = "first"
    SECOND = "second"


def test_optional_operations_derive_from_the_annotation() -> None:
    annotated = Annotated[int, "units"]
    optional = make_optional(annotated)

    assert is_union_type(optional)
    assert optional_member_type(optional) == annotated
    assert resolve_optional(optional) == annotated
    assert make_optional(optional) == optional


def test_multi_member_union_is_not_misclassified_as_simple_optional() -> None:
    assert optional_member_type(str | int | None) is None


def test_annotated_resolution_preserves_the_owned_declaration() -> None:
    assert resolve_annotated(Annotated[str | None, "help"]) == (str | None)
    assert resolve_annotated(str) is str


def test_enum_operations_derive_from_the_annotation() -> None:
    assert enum_member_type(Mode) is Mode
    assert enum_member_type(Optional[Mode]) is Mode
    assert enum_member_type(Mode | str) is None
    assert is_list_of_enums(list[Mode])
    assert get_enum_from_list(list[Mode]) is Mode
    assert get_enum_from_list(list[str]) is None
