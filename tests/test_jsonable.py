"""The encoder and decoder agree on every declared value family."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePath
from typing import Annotated

import pytest
from metaclass_registry import AutoRegisterMeta

from python_introspect import (
    JsonObject,
    JsonValue,
    RegisteredClassChoices,
    dataclass_from_mapping,
    registered_class_from_key,
    to_jsonable,
)


class Mode(Enum):
    IPC = "ipc"
    TCP = "tcp"


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    mode: Mode


@dataclass(frozen=True)
class Record:
    endpoint: Endpoint
    path: Path
    tags: tuple[str, ...]
    weights: dict[str, float]
    payload: JsonObject
    extra: JsonValue = None
    optional_endpoint: Endpoint | None = None
    values: list[JsonValue] = field(default_factory=list)


def sample_record() -> Record:
    return Record(
        endpoint=Endpoint(host="localhost", port=7777, mode=Mode.TCP),
        path=Path("/plates/a"),
        tags=("x", "y"),
        weights={"a": 0.5},
        payload={"nested": [1, {"deep": None}], "flag": True, "ratio": 1.5},
        extra=["a", 2],
        optional_endpoint=None,
        values=[1, "two", {"three": [3]}],
    )


def test_dataclass_round_trips_through_declared_fields():
    record = sample_record()
    encoded = to_jsonable(record)

    assert encoded == {
        "endpoint": {"host": "localhost", "port": 7777, "mode": "tcp"},
        "path": str(PurePath("/plates/a")),
        "tags": ["x", "y"],
        "weights": {"a": 0.5},
        "payload": {"nested": [1, {"deep": None}], "flag": True, "ratio": 1.5},
        "extra": ["a", 2],
        "optional_endpoint": None,
        "values": [1, "two", {"three": [3]}],
    }
    assert dataclass_from_mapping(Record, encoded) == record


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("text", "text"),
        (3, 3),
        (2.5, 2.5),
        (True, True),
        (Mode.IPC, "ipc"),
        (Path("a/b"), str(PurePath("a/b"))),
        ((1, 2), [1, 2]),
        (frozenset({1}), [1]),
        ({Mode.TCP: (1,)}, {"tcp": [1]}),
    ],
)
def test_value_families_project_to_json_native_data(value, expected):
    assert to_jsonable(value) == expected


def test_callables_project_to_import_identity():
    assert to_jsonable(sample_record) == {
        "kind": "callable",
        "name": "sample_record",
        "module": __name__,
        "qualname": "sample_record",
        "import_path": f"{__name__}.sample_record",
    }


def test_registered_types_project_to_their_registry_key():
    class Family(metaclass=AutoRegisterMeta):
        __registry_key__ = "family_key"
        family_key = None

    class Member(Family):
        family_key = Mode.TCP

    assert to_jsonable(Member) == "tcp"
    with pytest.raises(TypeError, match="has no registry key"):
        to_jsonable(Family)


def test_unregistered_values_are_rejected():
    with pytest.raises(TypeError, match="not JSON-serializable: object"):
        to_jsonable(object())


def test_new_value_family_joins_by_registration():
    class Celsius:
        def __init__(self, degrees: float) -> None:
            self.degrees = degrees

    @to_jsonable.register(Celsius)
    def _celsius(value: Celsius) -> JsonValue:
        return {"celsius": value.degrees}

    assert to_jsonable({"t": Celsius(21.0)}) == {"t": {"celsius": 21.0}}


class Shape(metaclass=AutoRegisterMeta):
    __registry_key__ = "shape_name"
    __skip_if_no_key__ = True
    shape_name = None


class Circle(Shape):
    shape_name = "circle"


class Square(Shape):
    shape_name = "square"


class Unrelated(metaclass=AutoRegisterMeta):
    __registry_key__ = "shape_name"
    __skip_if_no_key__ = True
    shape_name = None


class Triangle(Unrelated):
    shape_name = "triangle"


@dataclass(frozen=True)
class Drawing:
    shape: type[Shape]
    outline: type[Shape] | None = None
    layers: tuple[type[Shape], ...] = ()


class AliasMeta(AutoRegisterMeta):
    """A family whose boundary spelling is not its registry key."""


class Colour(metaclass=AliasMeta):
    __registry_key__ = "colour_name"
    __skip_if_no_key__ = True
    colour_name = None


class Red(Colour):
    colour_name = "red"


@registered_class_from_key.register(AliasMeta)
def _colour_from_alias(family: AliasMeta, key: JsonValue) -> type:
    return {"r": Red}[key]


@dataclass(frozen=True)
class Paint:
    colour: type[Colour]


def test_registered_classes_round_trip_through_their_registry_key():
    drawing = Drawing(shape=Circle, outline=Square, layers=(Square, Circle))
    encoded = to_jsonable(drawing)

    assert encoded == {"shape": "circle", "outline": "square", "layers": ["square", "circle"]}
    assert dataclass_from_mapping(Drawing, encoded) == drawing
    assert dataclass_from_mapping(Drawing, {"shape": Square}).shape is Square


def test_registered_class_keys_decode_only_within_their_family():
    with pytest.raises(ValueError, match="'triangle' is not a registered Shape"):
        dataclass_from_mapping(Drawing, {"shape": "triangle"})
    with pytest.raises(TypeError, match="must be a subclass of Shape"):
        dataclass_from_mapping(Drawing, {"shape": Triangle})


def test_family_with_its_own_spelling_registers_a_decoder_on_its_metaclass():
    assert dataclass_from_mapping(Paint, {"colour": "r"}).colour is Red


def test_registered_class_choices_list_members_by_their_key():
    choices = RegisteredClassChoices(Shape)

    assert choices.choices() == (Circle, Square)
    assert [choices.label(choice) for choice in choices.choices()] == ["circle", "square"]
    assert choices.choice_for_label("square") is Square
    assert choices == RegisteredClassChoices(Shape)


def test_registered_class_choices_validate_keys_in_pydantic():
    pydantic = pytest.importorskip("pydantic")
    adapter = pydantic.TypeAdapter(Annotated[type[Shape], RegisteredClassChoices(Shape)])

    assert adapter.validate_python("square") is Square
    assert adapter.validate_python(Circle) is Circle
    assert adapter.dump_python(Square, mode="json") == "square"
    assert adapter.json_schema() == {"enum": ["circle", "square"], "title": "Shape", "type": "string"}
    with pytest.raises(pydantic.ValidationError):
        adapter.validate_python("triangle")
    with pytest.raises(pydantic.ValidationError):
        adapter.validate_python(Triangle)
