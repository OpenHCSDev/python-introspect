from enum import Enum
from typing import Annotated, Optional

from python_introspect import (
    coerce_enum_member,
    declared_enum_type,
    enum_import_path,
    enum_input_values,
    enum_member_names,
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


class OptionalMode(Enum):
    ENABLED = "enabled"
    INHERIT = None


class OtherMode(Enum):
    THIRD = "third"


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


def test_enum_schema_operations_follow_the_single_nested_declaration() -> None:
    annotation = Annotated[list[Optional[Mode]], "modes"]

    assert declared_enum_type(annotation) is Mode
    assert enum_input_values(annotation) == ("first", "second")
    assert enum_member_names(annotation) == ("FIRST", "SECOND")
    assert enum_import_path(annotation) == f"{Mode.__module__}.{Mode.__qualname__}"
    assert declared_enum_type(Mode | OtherMode) is None
    assert declared_enum_type(Mode | str) is None
    assert declared_enum_type(tuple[Mode, ...]) is Mode
    assert declared_enum_type(tuple[Mode, str]) is None


def test_enum_input_coercion_accepts_values_and_non_string_member_names() -> None:
    assert coerce_enum_member(OptionalMode, "enabled") is OptionalMode.ENABLED
    assert coerce_enum_member(Optional[OptionalMode], "INHERIT") is OptionalMode.INHERIT
    assert enum_input_values(OptionalMode) == ("enabled", "INHERIT")
