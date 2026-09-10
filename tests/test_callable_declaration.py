from __future__ import annotations

from operator import attrgetter

import pytest

from python_introspect import callable_declaration_kwargs


def sample_function(value, threshold: float = 1.0, enabled: bool = True):
    return value


def test_callable_declaration_kwargs_projects_signature_defaults() -> None:
    kwargs = {
        "threshold": 1,
        "enabled": False,
        "extension_parameter": "preserved",
    }

    declaration = callable_declaration_kwargs(
        sample_function,
        kwargs,
        values_equal=lambda left, right: left == right,
    )

    assert declaration == {
        "enabled": False,
        "extension_parameter": "preserved",
    }


def test_callable_declaration_kwargs_preserves_values_for_opaque_callable() -> None:
    kwargs = {"extension_parameter": "preserved"}

    declaration = callable_declaration_kwargs(
        attrgetter("value"),
        kwargs,
        values_equal=lambda left, right: left == right,
    )

    assert declaration == kwargs


@pytest.mark.parametrize("omit_defaults", [True, False])
def test_signature_order_precedes_extra_keywords_without_mutation(omit_defaults):
    kwargs = {"extra_b": 2, "enabled": False, "threshold": 99.8, "extra_a": 1}
    original = kwargs.copy()
    result = callable_declaration_kwargs(
        sample_function, kwargs, values_equal=lambda a, b: a == b,
        omit_defaults=omit_defaults,
    )
    assert list(result) == ["threshold", "enabled", "extra_b", "extra_a"]
    assert list(kwargs.items()) == list(original.items())
    assert result == kwargs


def test_full_projection_keeps_explicit_defaults_but_does_not_insert_missing():
    result = callable_declaration_kwargs(
        sample_function, {"enabled": True}, values_equal=lambda a, b: a == b,
        omit_defaults=False,
    )
    assert result == {"enabled": True}
