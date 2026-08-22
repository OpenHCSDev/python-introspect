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
) -> dict[str, ParameterValue]:
    """Return declared kwargs whose values differ from signature defaults.

    Equality remains caller-owned so frameworks can supply semantics for
    arrays, lazy values, and other values whose ``==`` result is not boolean.
    """

    try:
        defaults = {
            name: parameter.default
            for name, parameter in inspect.signature(func).parameters.items()
            if parameter.default is not inspect.Parameter.empty
        }
    except (TypeError, ValueError):
        defaults = {}
    return {
        name: value
        for name, value in kwargs.items()
        if name not in defaults or not values_equal(value, defaults[name])
    }
