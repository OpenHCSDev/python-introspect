from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Literal

import pytest
from annotated_types import Ge, Gt, Le, MinLen, Predicate

from python_introspect import (
    overlay_non_none_dataclass,
    validate_annotated_dataclass,
)


class Mode(Enum):
    FIRST = "first"
    SECOND = "second"


Port = Annotated[int, Ge(1), Le(65535)]
NonBlankText = Annotated[str, MinLen(1), Predicate(str.strip)]


@dataclass(frozen=True)
class BaseConfig:
    port: Port = 7000
    mode: Mode = Mode.FIRST

    def __post_init__(self) -> None:
        validate_annotated_dataclass(self)


@dataclass(frozen=True)
class ChildConfig(BaseConfig):
    timeout_seconds: Annotated[float, Gt(0)] = 1.0
    label: NonBlankText = "worker"


def test_inherited_validation_reads_the_most_derived_declaration() -> None:
    assert ChildConfig(port=8000, timeout_seconds=2).mode is Mode.FIRST

    with pytest.raises(ValueError, match="timeout_seconds must be greater than"):
        ChildConfig(timeout_seconds=0)

    with pytest.raises(ValueError, match="label does not satisfy strip"):
        ChildConfig(label=" ")


def test_validation_rejects_wrong_nominal_types_without_coercion() -> None:
    with pytest.raises(TypeError, match="port must be int"):
        ChildConfig(port=True)

    with pytest.raises(TypeError, match="mode must be Mode"):
        ChildConfig(mode="first")


@dataclass(frozen=True)
class OptionalConfig:
    port: Port | None = None

    def __post_init__(self) -> None:
        validate_annotated_dataclass(self)


def test_nested_annotated_union_preserves_constraints() -> None:
    assert OptionalConfig().port is None
    assert OptionalConfig(port=1).port == 1

    with pytest.raises(ValueError, match="must be at least"):
        OptionalConfig(port=0)


def test_literal_validation_preserves_nominal_identity() -> None:
    @dataclass(frozen=True)
    class LiteralConfig:
        value: Literal[1]

        def __post_init__(self) -> None:
            validate_annotated_dataclass(self)

    assert LiteralConfig(value=1).value == 1
    with pytest.raises(ValueError, match="must be one of"):
        LiteralConfig(value=True)


@dataclass(frozen=True)
class ConnectionSpec:
    host: str = "localhost"
    port: int | None = None
    persistent: bool = True


@dataclass(frozen=True)
class ConnectionFields:
    host: str | None = None
    port: int | None = None
    persistent: bool | None = None
    unrelated: str | None = None


def test_non_none_dataclass_overlay_derives_shared_fields_from_declarations() -> None:
    updated = overlay_non_none_dataclass(
        ConnectionSpec(port=7000),
        ConnectionFields(host="127.0.0.1", persistent=False, unrelated="ignored"),
    )

    assert updated == ConnectionSpec(
        host="127.0.0.1",
        port=7000,
        persistent=False,
    )


def test_non_none_dataclass_overlay_requires_dataclass_instances() -> None:
    with pytest.raises(TypeError, match="requires two dataclass instances"):
        overlay_non_none_dataclass(ConnectionSpec(), {"host": "localhost"})


def test_non_none_dataclass_overlay_validates_the_target_declaration() -> None:
    @dataclass(frozen=True)
    class InvalidConnectionFields:
        host: int | None = None

    with pytest.raises(TypeError, match="ConnectionSpec.host must be str"):
        overlay_non_none_dataclass(
            ConnectionSpec(),
            InvalidConnectionFields(host=7),
        )
