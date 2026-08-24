"""Tests for nominal runtime-parameter declarations."""

import inspect

import pytest

from python_introspect import RuntimeParameterDeclarationABC


class ExampleRuntimeParameter(RuntimeParameterDeclarationABC):
    @classmethod
    def require_parameter_name(cls) -> str:
        return "runtime_value"

    @classmethod
    def parameter(cls) -> inspect.Parameter:
        return inspect.Parameter(
            cls.require_parameter_name(),
            inspect.Parameter.KEYWORD_ONLY,
            annotation=int,
        )


class StructuralImpostor:
    @classmethod
    def require_parameter_name(cls) -> str:
        return "runtime_value"

    @classmethod
    def parameter(cls) -> inspect.Parameter:
        return inspect.Parameter("runtime_value", inspect.Parameter.KEYWORD_ONLY)


class MismatchedRuntimeParameter(ExampleRuntimeParameter):
    @classmethod
    def parameter(cls) -> inspect.Parameter:
        return inspect.Parameter("different_name", inspect.Parameter.KEYWORD_ONLY)


def test_runtime_parameter_requires_nominal_subclass() -> None:
    with pytest.raises(TypeError, match="RuntimeParameterDeclarationABC subclasses"):
        RuntimeParameterDeclarationABC.require_declaration_type(
            StructuralImpostor,
            boundary="test declarations",
        )


def test_runtime_parameter_requires_matching_declared_name() -> None:
    with pytest.raises(TypeError, match="does not match require_parameter_name"):
        MismatchedRuntimeParameter.validated_parameter()


def test_runtime_parameter_collection_requires_unique_names() -> None:
    with pytest.raises(ValueError, match="duplicate runtime parameter 'runtime_value'"):
        RuntimeParameterDeclarationABC.require_declaration_types(
            (ExampleRuntimeParameter, ExampleRuntimeParameter),
            boundary="test declarations",
        )
