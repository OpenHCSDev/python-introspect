"""Nominal enable semantics as type-safe metadata.

This module provides a single, shared "axis" for objects and callables that
participate in enabled semantics.

Design goals:
- Nominal (not structural): only explicitly branded callables qualify.
- Dataclass-friendly: configs can inherit Enableable to get an enabled field.
- Callable-safe: branded callables must declare an `enabled` parameter.
"""

from __future__ import annotations

import inspect
from abc import ABC, ABCMeta
from dataclasses import dataclass
from typing import Any


ENABLED_FIELD = 'enabled'

_ENABLEABLE_TAG = object()


class EnableableMeta(ABCMeta):
    """Metaclass enabling nominal isinstance checks for branded callables."""

    def __instancecheck__(cls, instance: Any) -> bool:  # type: ignore[override]
        if getattr(instance, '__enableable_tag__', None) is _ENABLEABLE_TAG:
            return True
        return super().__instancecheck__(instance)


@dataclass(frozen=True)
class Enableable(ABC, metaclass=EnableableMeta):
    """Mixin indicating an object participates in enabled semantics."""

    enabled: bool = True


def is_enableable(obj: Any) -> bool:
    """Return True iff obj is nominally Enableable.

    Works for both instances (using isinstance) and classes (using issubclass).
    This is needed because widget creation code needs to check if a type (class)
    is enableable, not just instances.
    """

    # Check if obj is a type/class
    if isinstance(obj, type):
        # obj is a class - check if it's a subclass of Enableable
        try:
            return issubclass(obj, Enableable)
        except TypeError:
            # obj is not a class or is not class-like (e.g., a generic type)
            return False
    else:
        # obj is an instance - use isinstance
        return isinstance(obj, Enableable)


def mark_enableable(obj: Any, *, enabled_default: bool = True) -> Any:
    """Nominally brand an object/callable as Enableable.

    This does not wrap and does not change call semantics.
    """

    _ = enabled_default  # reserved for future: default enabled semantics

    # If we're branding a callable, require the enabled kwarg to exist.
    if callable(obj) and not isinstance(obj, type):
        sig = inspect.signature(obj)
        if ENABLED_FIELD not in sig.parameters:
            raise TypeError(
                f"Enableable callable '{getattr(obj, '__name__', obj)}' must have an '{ENABLED_FIELD}' parameter"
            )

    setattr(obj, '__enableable_tag__', _ENABLEABLE_TAG)
    return obj
