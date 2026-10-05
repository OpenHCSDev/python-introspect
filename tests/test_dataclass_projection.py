from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Annotated, Literal
from collections.abc import Sequence

import pytest

from python_introspect import (
    dataclass_from_mapping,
    project_dataclass,
    validate_annotated_dataclass,
)


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


@dataclass(frozen=True)
class ConnectionWithSummary(Connection):
    summary: tuple[str, int] = field(init=False)
    effective_mode: Mode = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", (self.host, self.port))
        object.__setattr__(self, "effective_mode", self.mode or Mode.IPC)


@dataclass(frozen=True, slots=True)
class DerivedDefaults:
    count: int
    label: str = field(init=False, default="counter")
    connections: list[Connection] = field(init=False, default_factory=list)


@dataclass(frozen=True)
class DerivedEnvelope:
    connection: ConnectionWithSummary


def test_dataclass_mapping_verifies_inherited_post_init_fields() -> None:
    original = ConnectionWithSummary("localhost", 7888, Mode.TCP)
    values = asdict(original)
    values.update(mode="tcp", effective_mode="tcp", summary=["localhost", 7888])
    assert dataclass_from_mapping(ConnectionWithSummary, values) == original
    assert dataclass_from_mapping(
        ConnectionWithSummary, {"host": "localhost", "port": 7888}
    ) == ConnectionWithSummary("localhost", 7888)


@pytest.mark.parametrize(
    "overrides,error_type,match",
    (
        ({"summary": ["elsewhere", 7888]}, ValueError, "summary.*disagrees"),
        ({"effective_mode": "tcp"}, ValueError, "effective_mode.*disagrees"),
        ({"summary": ["localhost", True]}, TypeError, "must be int"),
        ({"effective_mode": "invalid"}, ValueError, "must be one of"),
        ({"extra": 1}, ValueError, "undeclared.*extra"),
    ),
)
def test_dataclass_mapping_cannot_override_derived_owner(overrides, error_type, match):
    values = {"host": "localhost", "port": 7888, **overrides}
    with pytest.raises(error_type, match=match):
        dataclass_from_mapping(ConnectionWithSummary, values)


def test_dataclass_mapping_verifies_non_init_defaults_and_nested_derived_fields() -> None:
    original = DerivedDefaults(3)
    assert dataclass_from_mapping(DerivedDefaults, asdict(original)) == original
    assert dataclass_from_mapping(DerivedDefaults, {"count": 3}) == original
    with pytest.raises(ValueError, match="connections.*disagrees"):
        dataclass_from_mapping(
            DerivedDefaults,
            {"count": 3, "connections": [{"host": "localhost", "port": 7888}]},
        )
    values = {
        "connection": {
            "host": "localhost", "port": 7888,
            "summary": ["localhost", 7888], "effective_mode": "ipc",
        }
    }
    assert dataclass_from_mapping(DerivedEnvelope, values) == DerivedEnvelope(
        ConnectionWithSummary("localhost", 7888)
    )
    values["connection"]["effective_mode"] = "tcp"
    with pytest.raises(ValueError, match="effective_mode.*disagrees"):
        dataclass_from_mapping(DerivedEnvelope, values)


def test_dataclass_mapping_derived_defaults_do_not_supply_missing_init_fields() -> None:
    with pytest.raises(ValueError, match="missing required field.*count"):
        dataclass_from_mapping(DerivedDefaults, {"label": "counter"})


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


@dataclass(frozen=True)
class AnnotatedSequenceEnvelope:
    nodes: Annotated[Sequence["RecursiveSequenceNode"], "display text"]
    state: Literal["unresolved_name"] = "unresolved_name"


def test_nested_resolution_preserves_annotation_metadata_and_literal_values():
    result = dataclass_from_mapping(
        AnnotatedSequenceEnvelope, {"nodes": [{"name": "child"}]}
    )
    assert result == AnnotatedSequenceEnvelope((RecursiveSequenceNode("child"),))
    with pytest.raises(TypeError, match=r"children\[0\]"):
        validate_annotated_dataclass(RecursiveSequenceNode("parent", ({"name": "child"},)))


def test_inherited_nested_types_use_the_declaring_module_namespace(monkeypatch):
    import sys
    from types import ModuleType

    base_module = ModuleType("sequence_base_declaration")
    child_module = ModuleType("sequence_child_declaration")
    monkeypatch.setitem(sys.modules, base_module.__name__, base_module)
    monkeypatch.setitem(sys.modules, child_module.__name__, child_module)
    exec(
        'from dataclasses import dataclass\nfrom collections.abc import Sequence\n'
        '@dataclass\nclass Leaf:\n    name: str\n'
        '@dataclass\nclass Base:\n    children: Sequence["Leaf"]\n',
        vars(base_module),
    )
    exec(
        'from sequence_base_declaration import Base\n'
        'Leaf = int\nclass Child(Base):\n    pass\n',
        vars(child_module),
    )
    result = dataclass_from_mapping(child_module.Child, {"children": [{"name": "child"}]})
    assert isinstance(result.children[0], base_module.Leaf)
