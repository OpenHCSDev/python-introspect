from dataclasses import dataclass, fields
from typing import Annotated, get_type_hints

from python_introspect import FieldLabel, declared_field_label


@dataclass(frozen=True)
class _Row:
    labelled: Annotated[int, FieldLabel("Shown Name")] = 0
    plain: int = 0


def test_declared_field_label_reads_annotated_metadata_only():
    hints = get_type_hints(_Row, include_extras=True)
    labels = {field.name: declared_field_label(hints[field.name]) for field in fields(_Row)}

    assert labels == {"labelled": "Shown Name", "plain": None}
