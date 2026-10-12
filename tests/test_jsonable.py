"""The encoder and decoder agree on every declared value family."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
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


# A field whose declared type admits several classes stores {tag: fields}.


@dataclass(frozen=True)
class Left:
    value: int


@dataclass(frozen=True)
class Right:
    value: int


@dataclass(frozen=True)
class Measurement(ABC):
    @abstractmethod
    def unit(self) -> str: ...


@dataclass(frozen=True)
class Length(Measurement):
    amount: float

    def unit(self) -> str:
        return "m"


@dataclass(frozen=True)
class Duration(Measurement):
    amount: float

    def unit(self) -> str:
        return "s"


class Tool(metaclass=AutoRegisterMeta):
    __registry_key__ = "tool_key"
    tool_key = None


@dataclass(frozen=True)
class Hammer(Tool):
    tool_key = "hammer"
    weight: int


@dataclass(frozen=True)
class Saw(Tool):
    tool_key = "saw"
    weight: int


@dataclass(frozen=True)
class Envelope:
    side: Left | Right
    measurement: Measurement
    tool: Tool
    sides: tuple[Left | Right, ...] = ()
    measurements: Mapping[str, Measurement] = field(default_factory=dict)
    spare: Tool | None = None
    note: Left | Right | str | None = None


FAMILY_MEMBERS = (
    ("side", Left(1), {"Left": {"value": 1}}),
    ("side", Right(1), {"Right": {"value": 1}}),
    ("measurement", Length(2.0), {"Length": {"amount": 2.0}}),
    ("measurement", Duration(2.0), {"Duration": {"amount": 2.0}}),
    ("tool", Hammer(3), {"hammer": {"weight": 3}}),
    ("tool", Saw(3), {"saw": {"weight": 3}}),
)


@pytest.mark.parametrize(("field_name", "member", "stored"), FAMILY_MEMBERS)
def test_each_family_member_is_stored_under_its_tag_and_reads_back(field_name, member, stored):
    envelope = replace(Envelope(Left(0), Length(0.0), Hammer(0)), **{field_name: member})
    document = to_jsonable(envelope)

    assert document[field_name] == stored
    decoded = dataclass_from_mapping(Envelope, json.loads(json.dumps(document)))
    assert decoded == envelope
    assert type(getattr(decoded, field_name)) is type(member)


def test_members_with_identical_fields_decode_to_the_class_the_tag_names():
    document = to_jsonable(Envelope(Right(1), Duration(1.0), Saw(1), sides=(Left(1), Right(1))))

    decoded = dataclass_from_mapping(Envelope, document)

    assert [type(side) for side in (decoded.side, *decoded.sides)] == [Right, Left, Right]
    assert type(decoded.measurement) is Duration
    assert type(decoded.tool) is Saw


def test_family_fields_inside_containers_and_optional_fields_carry_the_tag():
    envelope = Envelope(
        Left(1),
        Length(1.0),
        Hammer(1),
        measurements={"wait": Duration(5.0)},
        spare=Saw(2),
        note=Right(7),
    )
    document = to_jsonable(envelope)

    assert document["measurements"] == {"wait": {"Duration": {"amount": 5.0}}}
    assert document["spare"] == {"saw": {"weight": 2}}
    assert document["note"] == {"Right": {"value": 7}}
    assert dataclass_from_mapping(Envelope, document) == envelope
    untagged_arms = replace(envelope, spare=None, note="text")
    assert to_jsonable(untagged_arms)["note"] == "text"
    assert dataclass_from_mapping(Envelope, to_jsonable(untagged_arms)) == untagged_arms


@pytest.mark.parametrize(
    ("field_name", "stored", "known"),
    (
        ("side", {"Middle": {"value": 1}}, r"\['Left', 'Right'\]"),
        ("measurement", {"Mass": {"amount": 1.0}}, r"\['Duration', 'Length'\]"),
        ("tool", {"drill": {"weight": 1}}, r"\['hammer', 'saw'\]"),
    ),
)
def test_unknown_tag_is_an_error_naming_the_known_members(field_name, stored, known):
    document = {**to_jsonable(Envelope(Left(1), Length(1.0), Hammer(1))), field_name: stored}

    with pytest.raises(ValueError, match=f"{next(iter(stored))!r} is not .*{known}"):
        dataclass_from_mapping(Envelope, document)


def test_untagged_fields_are_not_matched_to_a_member_by_their_shape():
    document = to_jsonable(Envelope(Left(1), Length(1.0), Hammer(1)))
    document = {**document, "measurement": {"amount": 1.0}}

    with pytest.raises(ValueError, match="'amount' is not a member of Measurement"):
        dataclass_from_mapping(Envelope, document)
    with pytest.raises(ValueError, match="stored as {tag: fields}"):
        dataclass_from_mapping(Envelope, {**document, "measurement": {"amount": 1.0, "x": 2}})


@dataclass(frozen=True)
class Other:
    value: int


Namesake = dataclass(frozen=True)(type("Left", (), {"__annotations__": {"value": int}}))


@dataclass(frozen=True)
class Pair:
    side: Left | Namesake


def test_a_value_outside_the_declared_family_is_not_encoded():
    with pytest.raises(TypeError, match=r"Other is not a member of Left \| Right"):
        to_jsonable(Envelope(Other(1), Length(1.0), Hammer(1)))


def test_two_members_with_one_tag_are_rejected():
    with pytest.raises(TypeError, match="two members tagged 'Left'"):
        to_jsonable(Pair(Left(1)))


class Probe(metaclass=AutoRegisterMeta):
    __registry_key__ = "depth"
    depth = None


@dataclass(frozen=True)
class DeepProbe(Probe):
    depth = 3
    reach: int


to_jsonable.register(Probe, lambda probe: {"reach": probe.reach, "depth": probe.depth})


@dataclass(frozen=True)
class Survey:
    probe: Probe


def test_a_member_with_its_own_projection_keeps_its_stored_form():
    assert to_jsonable(Survey(DeepProbe(9))) == {"probe": {"reach": 9, "depth": 3}}


@dataclass(frozen=True)
class Unresolved:
    value: NotImportedAtRunTime  # noqa: F821


def test_a_dataclass_whose_field_types_do_not_resolve_is_not_projected():
    with pytest.raises(TypeError, match="Unresolved cannot be projected.*NotImportedAtRunTime"):
        to_jsonable(Unresolved(1))
