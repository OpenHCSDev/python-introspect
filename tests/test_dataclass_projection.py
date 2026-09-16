from dataclasses import dataclass
from enum import Enum
from collections.abc import Sequence

import pytest

from python_introspect import dataclass_from_mapping, project_dataclass


class Mode(Enum):
    IPC = "ipc"
    TCP = "tcp"


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    mode: Mode | None = None


@dataclass(frozen=True)
class Envelope:
    connection: Connection
    started_at: float


@dataclass(frozen=True)
class StoredEnvelope:
    connection: Connection
    started_at: float
    path: str


@dataclass(frozen=True)
class UntypedTupleEnvelope:
    values: tuple


@dataclass(frozen=True)
class RecursiveSequenceNode:
    name: str
    children: Sequence["RecursiveSequenceNode"] = ()


@dataclass(frozen=True)
class SequenceEnvelope:
    nodes: Sequence[RecursiveSequenceNode]


@pytest.mark.parametrize("container", (list, tuple))
def test_dataclass_mapping_recurses_from_abstract_sequence_annotations(container):
    result = dataclass_from_mapping(
        SequenceEnvelope,
        {
            "nodes": container([{"name": "parent", "children": [{"name": "child"}]}]),
        },
    )
    assert result == SequenceEnvelope(
        (RecursiveSequenceNode("parent", (RecursiveSequenceNode("child"),)),)
    )


@pytest.mark.parametrize(
    "value", ("text", b"bytes", bytearray(b"bytes"), {"name": "mapping"}, 7)
)
def test_dataclass_mapping_sequence_rejects_non_array_values(value):
    with pytest.raises(TypeError, match="must be an array"):
        dataclass_from_mapping(SequenceEnvelope, {"nodes": value})


def test_dataclass_mapping_recursive_sequence_rejects_unknown_fields_and_wrong_elements():
    with pytest.raises(ValueError, match="undeclared.*extra"):
        dataclass_from_mapping(
            SequenceEnvelope,
            {
                "nodes": [
                    {"name": "parent", "children": [{"name": "child", "extra": 1}]}
                ]
            },
        )
    with pytest.raises(TypeError, match="must be an object"):
        dataclass_from_mapping(SequenceEnvelope, {"nodes": [42]})


def test_dataclass_mapping_abstract_sequence_preserves_typed_members():
    node = RecursiveSequenceNode("typed")
    assert dataclass_from_mapping(
        SequenceEnvelope, {"nodes": [node]}
    ) == SequenceEnvelope((node,))


def test_dataclass_mapping_uses_nested_types_as_the_schema() -> None:
    result = dataclass_from_mapping(
        Envelope,
        {
            "connection": {
                "host": "localhost",
                "port": 7888,
                "mode": "ipc",
            },
            "started_at": 1,
        },
    )

    assert result == Envelope(
        connection=Connection(
            host="localhost",
            port=7888,
            mode=Mode.IPC,
        ),
        started_at=1.0,
    )


def test_dataclass_mapping_rejects_missing_and_undeclared_fields() -> None:
    with pytest.raises(ValueError, match="missing required field"):
        dataclass_from_mapping(Envelope, {"started_at": 1.0})

    with pytest.raises(ValueError, match="undeclared field"):
        dataclass_from_mapping(
            Connection,
            {"host": "localhost", "port": 7888, "extra": True},
        )

    with pytest.raises(ValueError, match="must be one of.*ipc.*tcp"):
        dataclass_from_mapping(
            Connection,
            {"host": "localhost", "port": 7888, "mode": "invalid"},
        )

    with pytest.raises(TypeError, match="field names must be strings"):
        dataclass_from_mapping(Connection, {1: "localhost"})


def test_dataclass_mapping_preserves_bare_tuple_values() -> None:
    result = dataclass_from_mapping(UntypedTupleEnvelope, {"values": [1, "two"]})

    assert result.values == (1, "two")


def test_dataclass_projection_derives_shared_fields_from_both_declarations() -> None:
    source = Envelope(
        connection=Connection("localhost", 7888, Mode.TCP),
        started_at=2.0,
    )

    result = project_dataclass(StoredEnvelope, source, path="/tmp/bridge.json")

    assert result == StoredEnvelope(
        connection=source.connection,
        started_at=2.0,
        path="/tmp/bridge.json",
    )


def test_dataclass_mapping_union_projection_does_not_use_member_order() -> None:
    @dataclass(frozen=True)
    class NumericValue:
        value: float | int

    assert dataclass_from_mapping(NumericValue, {"value": 1}).value == 1
    assert type(dataclass_from_mapping(NumericValue, {"value": 1}).value) is int


def test_dataclass_mapping_rejects_ambiguous_structured_unions() -> None:
    @dataclass(frozen=True)
    class Left:
        value: int

    @dataclass(frozen=True)
    class Right:
        value: int

    @dataclass(frozen=True)
    class Envelope:
        payload: Left | Right

    with pytest.raises(TypeError, match="ambiguously matches multiple members"):
        dataclass_from_mapping(Envelope, {"payload": {"value": 1}})
