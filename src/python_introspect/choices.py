"""Finite value sets declared as ``Annotated`` metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated, get_args, get_origin

from .annotation_types import is_union_type


class AnnotationChoices(ABC):
    """``Annotated`` metadata declaring the finite values a field may hold.

    The declaring package owns the choice set, which may be computed when it is
    asked for. Validation checks each value (or each item of a sequence value)
    against it, and form builders render the choices with their labels.
    ``None`` is never a choice: an ``Optional`` annotation admits it separately.
    """

    @abstractmethod
    def choices(self) -> tuple[object, ...]:
        """Return the admissible values in display order."""

    def label(self, choice: object) -> str:
        """Return the display label for one admissible value."""

        return str(choice)

    def labelled_choices(self) -> tuple[tuple[str, object], ...]:
        """Return each label with its value in one enumeration of the choice set."""
        return tuple((self.label(choice), choice) for choice in self.choices())

    def choice_for_label(self, label: str) -> object:
        """Decode one display label back to its admissible value."""
        options = self.labelled_choices()
        for name, choice in options:
            if name == label:
                return choice
        raise ValueError(f"{label!r} is not one of {[name for name, _ in options]}.")

class LabelledChoices(AnnotationChoices):
    """Choices whose source already supplies labels and values together."""

    @abstractmethod
    def labelled_choices(self) -> tuple[tuple[str, object], ...]:
        """Return the source's ordered label/value pairs."""

    def choices(self) -> tuple[object, ...]:
        return tuple(value for _, value in self.labelled_choices())

    def label(self, choice: object) -> str:
        return next(label for label, value in self.labelled_choices() if value == choice)


def declared_annotation_choices(annotation: object) -> AnnotationChoices | None:
    """Return the choice set declared on an annotation.

    The metadata is found through ``Annotated``, ``Optional`` and homogeneous
    containers, mirroring how enum declarations are recognised.
    """

    if get_origin(annotation) is Annotated:
        base, *metadata = get_args(annotation)
        for item in metadata:
            if isinstance(item, AnnotationChoices):
                return item
        return declared_annotation_choices(base)
    members = get_args(annotation)
    if is_union_type(annotation):
        found = [
            choices
            for member in members
            if member is not type(None)
            if (choices := declared_annotation_choices(member)) is not None
        ]
        return found[0] if len(found) == 1 else None
    origin = get_origin(annotation)
    if origin in {list, set, frozenset} and len(members) == 1:
        return declared_annotation_choices(members[0])
    if origin is tuple and len(members) == 2 and members[1] is Ellipsis:
        return declared_annotation_choices(members[0])
    return None
