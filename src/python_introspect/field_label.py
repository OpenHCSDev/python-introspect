"""Display labels declared as ``Annotated`` metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, get_args, get_origin


@dataclass(frozen=True, slots=True)
class FieldLabel:
    """Display label for a field whose name does not read well to users.

    Declared as ``Annotated[T, FieldLabel("...")]``. Interfaces derive every
    other label from the field name and every tooltip from the field docstring.
    """

    text: str


def declared_field_label(annotation: object) -> str | None:
    """Return the label declared on an ``Annotated`` annotation, if any."""

    if get_origin(annotation) is not Annotated:
        return None
    _base, *metadata = get_args(annotation)
    for item in metadata:
        if isinstance(item, FieldLabel):
            return item.text
    return None
