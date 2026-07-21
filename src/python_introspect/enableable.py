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
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any
from typing import get_type_hints
from weakref import WeakKeyDictionary


_ENABLEABLE_TAG = object()
_enableable_objects: WeakKeyDictionary[Any, object] = WeakKeyDictionary()
_enableable_objects_by_id: dict[int, tuple[Any, object]] = {}


def _remember_enableable(obj: Any) -> None:
    """Record explicit enableable branding without mutating the object."""
    try:
        _enableable_objects[obj] = _ENABLEABLE_TAG
    except TypeError:
        _enableable_objects_by_id[id(obj)] = (obj, _ENABLEABLE_TAG)


def _is_marked_enableable(obj: Any) -> bool:
    """Return whether an object was explicitly branded as enableable."""
    try:
        if _enableable_objects.get(obj) is _ENABLEABLE_TAG:
            return True
    except TypeError:
        pass

    fallback_record = _enableable_objects_by_id.get(id(obj))
    return fallback_record is not None and fallback_record[0] is obj


class EnableableMeta(ABCMeta):
    """Metaclass enabling nominal isinstance checks for branded callables."""

    def __instancecheck__(cls, instance: Any) -> bool:  # type: ignore[override]
        if _is_marked_enableable(instance):
            return True
        return super().__instancecheck__(instance)


@dataclass(frozen=True)
class Enableable(ABC, metaclass=EnableableMeta):
    """Mixin indicating an object participates in enabled semantics."""

    enabled: bool = True
    """Run this callable or configuration when enabled; skip it when disabled."""

    @classmethod
    def callable_field(cls):
        """Return the dataclass field that defines callable enable semantics."""
        return fields(Enableable)[0]

    @classmethod
    def require_parameter_name(cls) -> str:
        return cls.callable_field().name

    @classmethod
    def default_value(cls) -> bool:
        return cls.callable_field().default

    @classmethod
    def annotation_type(cls) -> type[bool]:
        return get_type_hints(Enableable)[cls.require_parameter_name()]

    @classmethod
    def parameter(cls) -> inspect.Parameter:
        return inspect.Parameter(
            cls.require_parameter_name(),
            inspect.Parameter.KEYWORD_ONLY,
            default=cls.default_value(),
            annotation=cls.annotation_type(),
        )

    @classmethod
    def parameter_in(cls, values: Mapping[Any, Any]) -> bool:
        """Return whether a kwargs-like mapping carries the enable parameter."""
        return cls.require_parameter_name() in values

    @classmethod
    def is_parameter_key(cls, key: Any) -> bool:
        """Return whether key names the enable parameter."""
        return key == cls.require_parameter_name()

    @classmethod
    def disabled_in(cls, values: Mapping[Any, Any]) -> bool:
        """Return whether a kwargs-like mapping explicitly disables execution."""
        if not cls.parameter_in(values):
            return False
        return values[cls.require_parameter_name()] is False

    @classmethod
    def without_parameter(cls, values: Mapping[Any, Any]) -> dict[Any, Any]:
        """Return a copy of mapping values without the enable parameter."""
        return {
            key: value
            for key, value in values.items()
            if not cls.is_parameter_key(key)
        }


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
        parameter_name = Enableable.require_parameter_name()
        if parameter_name not in sig.parameters:
            raise TypeError(
                f"Enableable callable {obj!r} must have an '{parameter_name}' parameter"
            )

    _remember_enableable(obj)
    return obj
