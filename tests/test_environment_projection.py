from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated

import pytest

from python_introspect import (
    EnvironmentVariable,
    overlay_dataclass_from_environment,
)


class Mode(Enum):
    IPC = "ipc"
    TCP = "tcp"


@dataclass(frozen=True)
class EnvironmentConfig:
    host: Annotated[str, EnvironmentVariable("EXAMPLE_HOST")] = "localhost"
    port: Annotated[int | None, EnvironmentVariable("EXAMPLE_PORT")] = None
    enabled: Annotated[bool, EnvironmentVariable("EXAMPLE_ENABLED")] = True
    mode: Annotated[Mode | None, EnvironmentVariable("EXAMPLE_MODE")] = None
    path: Annotated[
        Path | None,
        EnvironmentVariable("EXAMPLE_PATH", clear_on_empty=True),
    ] = Path("/default")
    untouched: int = 7


def test_environment_projection_uses_annotations_as_schema() -> None:
    result = overlay_dataclass_from_environment(
        EnvironmentConfig(),
        {
            "EXAMPLE_HOST": "127.0.0.1",
            "EXAMPLE_PORT": "7888",
            "EXAMPLE_ENABLED": "false",
            "EXAMPLE_MODE": "ipc",
            "EXAMPLE_PATH": "/tmp/bridge",
        },
    )

    assert result == EnvironmentConfig(
        host="127.0.0.1",
        port=7888,
        enabled=False,
        mode=Mode.IPC,
        path=Path("/tmp/bridge"),
    )


def test_environment_projection_distinguishes_empty_default_and_clear() -> None:
    result = overlay_dataclass_from_environment(
        EnvironmentConfig(),
        {
            "EXAMPLE_HOST": "",
            "EXAMPLE_PATH": "",
        },
    )

    assert result.host == "localhost"
    assert result.path is None


def test_environment_projection_rejects_values_against_declared_types() -> None:
    with pytest.raises(ValueError, match="EXAMPLE_MODE must be one of"):
        overlay_dataclass_from_environment(
            EnvironmentConfig(),
            {"EXAMPLE_MODE": "invalid"},
        )

    with pytest.raises(ValueError, match="EXAMPLE_ENABLED must be a boolean"):
        overlay_dataclass_from_environment(
            EnvironmentConfig(),
            {"EXAMPLE_ENABLED": "sometimes"},
        )

    with pytest.raises(TypeError, match="EXAMPLE_PORT must be text"):
        overlay_dataclass_from_environment(
            EnvironmentConfig(),
            {"EXAMPLE_PORT": 7888},
        )


def test_environment_projection_rejects_ambiguous_text_unions() -> None:
    @dataclass(frozen=True)
    class AmbiguousEnvironmentConfig:
        value: Annotated[
            str | int,
            EnvironmentVariable("EXAMPLE_AMBIGUOUS"),
        ] = "default"

    with pytest.raises(TypeError, match="cannot populate ambiguous union"):
        overlay_dataclass_from_environment(
            AmbiguousEnvironmentConfig(),
            {"EXAMPLE_AMBIGUOUS": "7"},
        )


def test_environment_variable_binding_validates_its_own_types() -> None:
    with pytest.raises(TypeError, match="EnvironmentVariable.name must be str"):
        EnvironmentVariable(7)
