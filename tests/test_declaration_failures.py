"""Broken declarations fail at the existing analysis owner, not as empty forms."""

from dataclasses import dataclass, field

import pytest

from python_introspect import UnifiedParameterAnalyzer, register_type_resolver, resolve_declared_type
from python_introspect.signature_analyzer import SignatureAnalyzer


def test_recursive_declaration_resolves_before_module_binding():
    @dataclass
    class Recursive:
        child: "Recursive | None" = None

    parameters = UnifiedParameterAnalyzer.analyze(Recursive)
    assert parameters["child"].param_type == Recursive | None
    assert parameters["child"].default_value is None
    assert not parameters["child"].is_required
    assert UnifiedParameterAnalyzer.analyze(Recursive) is parameters


def test_unknown_annotation_raises_without_caching_an_empty_form():
    @dataclass
    class Broken:
        value: "MissingDeclaration"

    with pytest.raises(NameError, match="MissingDeclaration"):
        UnifiedParameterAnalyzer.analyze(Broken)
    assert Broken not in SignatureAnalyzer._dataclass_analysis_cache


def test_default_factory_exception_identity_is_not_hidden():
    error = RuntimeError("declared factory failed")

    def fail():
        raise error

    @dataclass
    class BrokenFactory:
        value: int = field(default_factory=fail)

    with pytest.raises(RuntimeError) as raised:
        UnifiedParameterAnalyzer.analyze(BrokenFactory)
    assert raised.value is error
    assert BrokenFactory not in SignatureAnalyzer._dataclass_analysis_cache


def test_public_declared_type_resolver_uses_the_registered_owner():
    class Declared:
        pass

    class Generated:
        pass

    register_type_resolver(lambda candidate: Declared if candidate is Generated else None)
    assert resolve_declared_type(Generated) is Declared
    assert resolve_declared_type(Declared) is Declared
