"""Declaration projections derived from callable signatures."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import TypeVar


ParameterValue = TypeVar("ParameterValue")


def callable_declaration_kwargs(
    func: Callable,
    kwargs: Mapping[str, ParameterValue],
    *,
    values_equal: Callable[[object, object], bool],
    omit_defaults: bool = True,
) -> dict[str, ParameterValue]:
    """Project supplied kwargs in signature order, optionally omitting defaults.

    Equality remains caller-owned so frameworks can supply semantics for
    arrays, lazy values, and other values whose ``==`` result is not boolean.
    Extra kwargs retain their relative input order after declared parameters.
    Missing parameters are never populated by this projection.
    """

    try:
        parameters = inspect.signature(func).parameters
    except (TypeError, ValueError):
        parameters = {}
    defaults = {
        name: parameter.default
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty
    }
    return {
        name: kwargs[name]
        for name in dict.fromkeys((*parameters, *kwargs))
        if name in kwargs
        and (
            not omit_defaults
            or name not in defaults
            or not values_equal(kwargs[name], defaults[name])
        )
    }
