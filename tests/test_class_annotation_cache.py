"""A class's resolved annotations are a fact about the class: resolved once, kept read-only."""

from dataclasses import dataclass

import pytest

from python_introspect.annotation_types import resolved_class_annotations


def test_class_annotations_resolve_once_per_class_and_read_only() -> None:
    """Every validated instance asks for its class's annotations: they are resolved once
    and kept for the class, read-only."""

    @dataclass
    class Declared:
        count: int
        names: list[str]

    first = resolved_class_annotations(Declared)
    assert first == {"count": int, "names": list[str]}
    assert resolved_class_annotations(Declared) is first
    with pytest.raises(TypeError):
        first["count"] = str  # type: ignore[index]


def test_a_class_that_does_not_resolve_yet_is_resolved_on_a_later_call() -> None:
    """Nothing is kept for a class whose annotations do not resolve, so a call once the
    name exists resolves it."""

    @dataclass
    class Later:
        value: "NotYetDefined"  # noqa: F821

    with pytest.raises(NameError):
        resolved_class_annotations(Later)
    globals()["NotYetDefined"] = float
    try:
        assert resolved_class_annotations(Later) == {"value": float}
    finally:
        del globals()["NotYetDefined"]
