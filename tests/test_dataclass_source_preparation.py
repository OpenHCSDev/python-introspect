"""Source preparation must preserve live declarations and first-use values."""
import dataclasses
import importlib.util
import inspect
import linecache
import os
import sys
import types
from typing import Annotated

import pytest
from python_introspect import SignatureAnalyzer


def _load_module(monkeypatch, name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def test_preparation_does_not_run_factories_or_snapshot_annotations():
    calls = []
    current = {"value": 1}

    def first():
        calls.append("first")
        return current["value"]

    def second():
        calls.append("second")
        return []

    @dataclasses.dataclass
    class Declaration:
        value: int = dataclasses.field(default_factory=first)
        values: list = dataclasses.field(default_factory=second)

    SignatureAnalyzer.prepare_dataclass_declaration(Declaration)
    assert calls == []
    current["value"] = 4
    Declaration.__annotations__["value"] = str
    result = SignatureAnalyzer._analyze_dataclass(Declaration)
    assert calls == ["first", "second"]
    assert result["value"].default_value == 4
    assert result["value"].param_type is str
    assert SignatureAnalyzer._analyze_dataclass(Declaration) is result
    assert calls == ["first", "second"]


def test_throwing_factory_stays_uncached_and_retryable():
    calls = []

    def throwing():
        calls.append(1)
        raise RuntimeError("first-use factory")

    @dataclasses.dataclass
    class Declaration:
        value: int = dataclasses.field(default_factory=throwing)

    SignatureAnalyzer.prepare_dataclass_declaration(Declaration)
    assert calls == []
    assert SignatureAnalyzer._analyze_dataclass(Declaration) == {}
    assert Declaration not in SignatureAnalyzer._dataclass_analysis_cache
    assert SignatureAnalyzer._analyze_dataclass(Declaration) == {}
    assert calls == [1, 1]


def test_factory_effects_precede_metadata_and_inherited_documentation():
    metadata = {"description": "before"}

    def factory():
        metadata["description"] = "after"
        Parent.__doc__ = "Args:\n    inherited: after factory"
        return 3

    @dataclasses.dataclass
    class Parent:
        """Args:
            inherited: before factory
        """
        owned: int = dataclasses.field(default_factory=factory, metadata=metadata)
        inherited: int = 1

    @dataclasses.dataclass
    class Child(Parent):
        pass

    SignatureAnalyzer.prepare_dataclass_declaration(Parent)
    SignatureAnalyzer.prepare_dataclass_declaration(Child)
    result = SignatureAnalyzer._analyze_dataclass(Child)
    assert result["owned"].description == "after"
    assert result["inherited"].description == "after factory"


def test_optional_and_required_field_semantics_survive_preparation():
    marker = object()

    @dataclasses.dataclass
    class Declaration:
        required: Annotated[int, marker]
        inherited: int | None = None

    SignatureAnalyzer.prepare_dataclass_declaration(Declaration)
    result = SignatureAnalyzer._analyze_dataclass(Declaration)
    assert result["required"].is_required
    assert result["required"].param_type == Annotated[int, marker]
    assert result["inherited"].default_value is None
    assert not result["inherited"].is_required


def test_source_lookup_uses_qualified_nested_and_decorated_classes(tmp_path, monkeypatch):
    path = tmp_path / "declarations.py"
    path.write_text('''from dataclasses import dataclass

def identity(target):
    return target

@identity
@dataclass
class Outer:
    value: int = 1
    "Outer documentation"
    @dataclass
    class Inner:
        value: int = 2
        "Inner documentation"

def factory():
    @dataclass
    class Inner:
        value: int = 3
        "Local documentation"
    return Inner
''')
    module = _load_module(monkeypatch, "qualified_source_preparation", path)
    for declaration in (module.Outer, module.Outer.Inner, module.factory()):
        SignatureAnalyzer.prepare_dataclass_declaration(declaration)
        assert SignatureAnalyzer._dataclass_source(declaration) == inspect.getsource(declaration)
    # The original inline extractor does not dedent nested blocks before parsing.
    # Source preparation preserves that behavior rather than repairing it here.
    assert SignatureAnalyzer._extract_inline_field_docs(module.Outer.Inner) == {}
    assert SignatureAnalyzer._extract_inline_field_docs(module.factory()) == {}


def test_warmed_lookup_observes_changed_file_content_and_qualname(tmp_path, monkeypatch):
    path = tmp_path / "declarations.py"
    source = '''from dataclasses import dataclass
@dataclass
class First:
    value: int = 1
    "First documentation"
@dataclass
class Second:
    value: int = 2
    "Second documentation"
'''
    path.write_text(source)
    module = _load_module(monkeypatch, "live_source_preparation", path)
    SignatureAnalyzer.prepare_dataclass_declaration(module.First)
    module.First.__qualname__ = "Second"
    assert SignatureAnalyzer._dataclass_source(module.First) == inspect.getsource(module.First)
    module.First.__qualname__ = "First"
    path.write_text(source.replace("First documentation", "Changed documentation"))
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 2))
    assert SignatureAnalyzer._extract_inline_field_docs(module.First) == {"value": "Changed documentation"}


def test_loader_source_is_read_at_original_observation_point(tmp_path, monkeypatch):
    class Loader:
        source = 'from dataclasses import dataclass\n@dataclass\nclass Loaded:\n    value:int=1\n    "Original documentation"\n'

        def get_source(self, name):
            return self.source

    loader = Loader()
    module = types.ModuleType("loader_source_preparation")
    module.__file__ = str(tmp_path / "not_on_disk.py")
    module.__loader__ = loader
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(loader.source, module.__file__, "exec"), module.__dict__)
    SignatureAnalyzer.prepare_dataclass_declaration(module.Loaded)
    loader.source = loader.source.replace("Original documentation", "Current documentation")
    linecache.cache.pop(module.__file__, None)
    assert SignatureAnalyzer._dataclass_source(module.Loaded) == inspect.getsource(module.Loaded)
    assert SignatureAnalyzer._extract_inline_field_docs(module.Loaded) == {"value": "Current documentation"}


def test_generated_type_keeps_original_fallback_without_inventing_source(tmp_path, monkeypatch):
    path = tmp_path / "declarations.py"
    path.write_text('''from dataclasses import dataclass
@dataclass
class Public:
    value: int = 1
    "Public documentation"
''')
    module = _load_module(monkeypatch, "generated_source_preparation", path)
    generated = dataclasses.make_dataclass("Public", [("value", int, 1)])
    generated.__module__ = module.__name__
    generated.__qualname__ = "GeneratedPublic"
    SignatureAnalyzer.prepare_dataclass_declaration(generated)
    assert SignatureAnalyzer._extract_inline_field_docs(generated) == {"value": "Public documentation"}


def test_missing_source_keeps_original_error():
    with pytest.raises(TypeError) as original:
        inspect.getsource(int)
    with pytest.raises(TypeError) as prepared:
        SignatureAnalyzer._dataclass_source(int)
    assert str(prepared.value) == str(original.value)
    SignatureAnalyzer.prepare_dataclass_declaration(int)
    assert SignatureAnalyzer._extract_inline_field_docs(int) == {}
