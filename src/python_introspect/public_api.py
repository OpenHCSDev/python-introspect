"""Module public surfaces derived from what a module declares."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from importlib import import_module
from inspect import isclass, isfunction
from types import ModuleType
from typing import Any


def declared_public_names(
    module_globals: Mapping[str, object],
    *,
    constant_prefixes: Iterable[str] = (),
    excluded_names: Iterable[str] = (),
    extra_names: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return public names declared by the module represented by globals()."""
    module_name = module_globals["__name__"]
    prefixes = tuple(constant_prefixes)
    excluded = set(excluded_names)
    declared_names = tuple(
        name
        for name, value in module_globals.items()
        if name not in excluded
        if is_declared_public_name(
            module_name,
            name,
            value,
            constant_prefixes=prefixes,
        )
    )
    return declared_names + tuple(name for name in extra_names if name not in excluded)


def exported_public_names(
    module_globals: Mapping[str, object],
    *,
    excluded_names: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return public re-export names declared by explicit module imports."""
    excluded = set(excluded_names)
    return tuple(
        name
        for name, value in module_globals.items()
        if not name.startswith("_")
        if name not in excluded
        if not isinstance(value, ModuleType)
    )


def public_names_from_objects(*objects: Any, extra_names: Iterable[str] = ()) -> tuple[str, ...]:
    """Return public names from exported object identities plus explicit aliases."""
    return tuple(item if isinstance(item, str) else item.__name__ for item in objects) + tuple(
        extra_names
    )


def is_declared_public_name(
    module_name: str,
    name: str,
    value: object,
    *,
    constant_prefixes: tuple[str, ...] = (),
) -> bool:
    """Return whether a global is a public module declaration."""
    if name.startswith("_"):
        return False
    if name.isupper():
        return any(name.startswith(prefix) for prefix in constant_prefixes)
    return (isclass(value) or isfunction(value)) and value.__module__ == module_name


def lazy_exports(
    module_globals: dict[str, object],
    exports: Mapping[str, Iterable[str]],
) -> tuple[str, ...]:
    """Install PEP 562 ``__getattr__``/``__dir__`` resolving names on first access.

    ``exports`` maps each owning module path (absolute, or relative to the
    package whose ``globals()`` are passed) to the names it supplies. A name is
    imported from its owner on first access and cached in the module globals.
    Returns the exported names in declaration order, for ``__all__``.
    """

    module_name = module_globals["__name__"]
    package = module_globals.get("__package__") or module_name
    owners: dict[str, str] = {}
    for owner, names in exports.items():
        for name in names:
            if name in owners:
                raise ValueError(
                    f"{module_name} lazy export {name!r} is declared by both "
                    f"{owners[name]!r} and {owner!r}."
                )
            owners[name] = owner

    def __getattr__(name: str) -> object:
        if name not in owners:
            raise AttributeError(f"module {module_name!r} has no attribute {name!r}")
        value = getattr(import_module(owners[name], package), name)
        module_globals[name] = value
        return value

    def __dir__() -> list[str]:
        return sorted(set(module_globals) | set(owners))

    module_globals["__getattr__"] = __getattr__
    module_globals["__dir__"] = __dir__
    return tuple(owners)
