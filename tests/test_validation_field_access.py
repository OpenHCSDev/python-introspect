"""Annotation validation consumes the field owner's public value semantics."""
from dataclasses import dataclass

import pytest

from python_introspect import (
    AnnotatedDataclassValidationMixin, DataclassPostInit, validate_annotated_dataclass,
)


DEFERRED = object()


@dataclass
class EffectiveValue(AnnotatedDataclassValidationMixin):
    value: int

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        return 7 if name == "value" and value is DEFERRED else value


def test_validation_reads_effective_values_without_rewriting_storage():
    instance = EffectiveValue(DEFERRED)
    assert instance.value == 7
    assert object.__getattribute__(instance, "value") is DEFERRED
    validate_annotated_dataclass(instance)


@pytest.mark.parametrize("value", [None, "invalid", False])
def test_literal_null_and_invalid_concrete_values_are_not_masked(value):
    with pytest.raises(TypeError, match="must be int"):
        EffectiveValue(value)


def test_field_descriptor_failure_propagates_its_original_identity():
    failure = RuntimeError("field accessor failed")

    @dataclass
    class FailedRead(AnnotatedDataclassValidationMixin):
        value: int

        def __getattribute__(self, name):
            if name == "value":
                raise failure
            return object.__getattribute__(self, name)

    with pytest.raises(RuntimeError) as raised:
        FailedRead(3)
    assert raised.value is failure


def test_validator_cooperates_with_the_next_post_init_capability():
    events = []

    class PrepareValue(DataclassPostInit):
        def __post_init__(self):
            events.append("prepare")
            self.value = int(self.value)
            super().__post_init__()

    @dataclass
    class PreparedValue(AnnotatedDataclassValidationMixin, PrepareValue):
        value: int
        label: str = "ok"

    assert PreparedValue("7").value == 7
    assert events == ["prepare"]
    with pytest.raises(TypeError, match="label must be str"):
        PreparedValue("7", label=None)
    assert events == ["prepare", "prepare"]
