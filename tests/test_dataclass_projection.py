from dataclasses import dataclass
from enum import Enum

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
