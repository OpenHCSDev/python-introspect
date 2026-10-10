"""The encoder and decoder agree on every declared value family."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pytest
from metaclass_registry import AutoRegisterMeta

from python_introspect import (
    JsonObject,
    JsonValue,
    dataclass_from_mapping,
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
        "path": "/plates/a",
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
        (Path("a/b"), "a/b"),
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
