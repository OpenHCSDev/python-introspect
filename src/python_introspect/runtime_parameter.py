"""Nominal declarations for runtime-supplied callable parameters."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import ClassVar


class RuntimeParameterDeclarationABC(ABC):
    """Semantic owner for one parameter supplied by runtime infrastructure."""

    preserve_for_execution: ClassVar[bool] = False
    is_semantic_control: ClassVar[bool] = False

    @classmethod
    @abstractmethod
    def require_parameter_name(cls) -> str:
        """Return the public callable parameter name."""

    @classmethod
    @abstractmethod
    def parameter(cls) -> inspect.Parameter:
        """Return the complete callable signature parameter declaration."""

    @classmethod
    def validated_parameter(cls) -> inspect.Parameter:
        """Return the parameter after proving its nominal declaration is coherent."""

        parameter = cls.parameter()
        if not isinstance(parameter, inspect.Parameter):
            raise TypeError(f"{cls.__name__}.parameter() must return inspect.Parameter.")
        parameter_name = cls.require_parameter_name()
        if not isinstance(parameter_name, str) or not parameter_name.strip():
            raise TypeError(
                f"{cls.__name__}.require_parameter_name() must return a non-empty string."
            )
        if parameter.name != parameter_name:
            raise TypeError(
                f"{cls.__name__}.parameter() name {parameter.name!r} does not "
                f"match require_parameter_name() {parameter_name!r}."
            )
        return parameter

    @classmethod
    def require_declaration_type(
        cls,
        candidate: object,
        *,
        boundary: str,
    ) -> type[RuntimeParameterDeclarationABC]:
        """Require one nominal runtime-parameter declaration type."""

        if not isinstance(candidate, type) or not issubclass(candidate, cls):
            raise TypeError(
                f"{boundary} must contain {cls.__name__} subclasses, got {candidate!r}."
            )
        candidate.validated_parameter()
        return candidate

    @classmethod
    def require_declaration_types(
        cls,
        candidates: Iterable[object],
        *,
        boundary: str,
    ) -> tuple[type[RuntimeParameterDeclarationABC], ...]:
        """Require coherent declarations with unique public parameter names."""

        declarations: list[type[RuntimeParameterDeclarationABC]] = []
        seen_names: set[str] = set()
        for candidate in candidates:
            declaration = cls.require_declaration_type(candidate, boundary=boundary)
            parameter_name = declaration.require_parameter_name()
            if parameter_name in seen_names:
                raise ValueError(
                    f"{boundary} declares duplicate runtime parameter {parameter_name!r}."
                )
            declarations.append(declaration)
            seen_names.add(parameter_name)
        return tuple(declarations)


__all__ = ("RuntimeParameterDeclarationABC",)
