from __future__ import annotations

from operator import attrgetter

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
