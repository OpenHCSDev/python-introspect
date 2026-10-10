from dataclasses import dataclass, field
from typing import Annotated, Optional

import pytest

from python_introspect import (
    AnnotatedDataclassValidationMixin,
    AnnotationChoices,
    AnnotationValidationError,
    declared_annotation_choices,
    enum_input_values,
)


class _Kind:
    pass


class _Alpha(_Kind):
    pass


class _Beta(_Kind):
    pass


class _Other:
    pass


class _KindChoices(AnnotationChoices):
    def choices(self):
        return (_Alpha, _Beta)

    def label(self, choice):
        return choice.__name__.strip("_").lower()


_CHOICES = _KindChoices()


@dataclass(frozen=True)
class _Declared(AnnotatedDataclassValidationMixin):
    kind: Annotated[Optional[type[_Kind]], _CHOICES] = None
    kinds: Annotated[list[type[_Kind]], _CHOICES] = field(default_factory=list)


def test_choices_are_found_through_optional_and_containers():
    assert declared_annotation_choices(Optional[Annotated[list[type[_Kind]], _CHOICES]]) is _CHOICES
    assert declared_annotation_choices(Annotated[Optional[type[_Kind]], _CHOICES]) is _CHOICES
    assert declared_annotation_choices(list[int]) is None
    assert enum_input_values(Annotated[list[type[_Kind]], _CHOICES]) == ("alpha", "beta")
    assert _CHOICES.choice_for_label("beta") is _Beta


def test_validation_admits_only_declared_choices_and_class_bounds():
    _Declared(kind=_Alpha, kinds=[_Beta])
    with pytest.raises(AnnotationValidationError):
        _Declared(kinds=[_Kind])
    with pytest.raises(TypeError):
        _Declared(kind=_Other)
