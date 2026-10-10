"""Module public surfaces derive from declarations, and lazy exports resolve once."""

from __future__ import annotations

import sys
import types

import pytest

from python_introspect import (
    declared_public_names,
    exported_public_names,
    is_declared_public_name,
    lazy_exports,
    public_names_from_objects,
)


def make_module(name: str, source: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__package__ = name.rpartition(".")[0] or name
    sys.modules[name] = module
    exec(source, module.__dict__)
    return module


@pytest.fixture
def owner_package():
    names = ("lazy_pkg", "lazy_pkg.owner", "lazy_pkg.other")
    package = make_module("lazy_pkg", "")
    package.__path__ = []
    package.__package__ = "lazy_pkg"
    make_module("lazy_pkg.owner", "class Widget: pass\ndef build(): return 1\n")
    make_module("lazy_pkg.other", "VALUE = 7\n")
    yield package
    for name in names:
        sys.modules.pop(name, None)


def test_declared_public_names_follow_module_declarations():
    module = make_module(
        "declaring_module",
        "from pathlib import Path\n"
        "import os\n"
        "class Local: pass\n"
        "def helper(): pass\n"
        "def _private(): pass\n"
        "LIMIT_MAX = 1\n"
        "OTHER = 2\n",
    )
    try:
        assert declared_public_names(
            vars(module), constant_prefixes=("LIMIT_",), extra_names=("alias",)
        ) == ("Local", "helper", "LIMIT_MAX", "alias")
        assert declared_public_names(vars(module), excluded_names=("helper",)) == ("Local",)
        assert "Path" in exported_public_names(vars(module))
        assert "os" not in exported_public_names(vars(module))
        assert not is_declared_public_name("declaring_module", "Path", module.Path)
        assert public_names_from_objects(module.Local, "named", extra_names=("x",)) == (
            "Local",
            "named",
            "x",
        )
    finally:
        sys.modules.pop("declaring_module", None)


def test_lazy_exports_resolve_on_first_access_and_cache(owner_package):
    namespace = vars(owner_package)
    exported = lazy_exports(
        namespace,
        {".owner": ("Widget", "build"), "lazy_pkg.other": ("VALUE",)},
    )

    assert exported == ("Widget", "build", "VALUE")
    assert "Widget" not in namespace
    assert set(exported) <= set(dir(owner_package))
    assert owner_package.Widget is sys.modules["lazy_pkg.owner"].Widget
    assert namespace["Widget"] is owner_package.Widget
    assert owner_package.VALUE == 7
    with pytest.raises(AttributeError, match="has no attribute 'missing'"):
        owner_package.missing


def test_lazy_exports_reject_a_name_owned_twice(owner_package):
    with pytest.raises(ValueError, match="declared by both"):
        lazy_exports(vars(owner_package), {".owner": ("Widget",), ".other": ("Widget",)})


def test_lazy_export_of_an_undeclared_owner_attribute_fails(owner_package):
    lazy_exports(vars(owner_package), {".other": ("Widget",)})
    with pytest.raises(AttributeError):
        owner_package.Widget
