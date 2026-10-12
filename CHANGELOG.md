# Changelog

0.2.2 is the first 0.2.x release published to PyPI. The 0.2.0 and 0.2.1 tags exist in git, but their publish runs were cancelled, so upgrading from PyPI goes straight from 0.1.16 to 0.2.2. The notes below cover every change in that jump.

## 0.3.0

Changed (the stored form of some fields changes; there is no reader for the old form):
- A dataclass field whose declared type admits several classes is stored as `{tag: fields}`, and `dataclass_from_mapping` reads the class from the tag. Before, the member of a union was guessed from which fields were present: two members with the same fields could not be told apart and the stored value did not say which class it was. Three declarations form such a family (`MemberFamily.declared_by`): a union with two or more dataclass members (other arms such as `None` or `str` stay untagged), an abstract dataclass (its concrete subclasses are the members), and a class whose metaclass is `AutoRegisterMeta`. The tag is the member's registry key when it is registered, so it survives a module move or a rename; otherwise it is the class name. The rule holds inside `tuple`, `list`, `Sequence`, `Mapping`, optional and `Annotated` declarations.
- An unknown tag is a `ValueError` naming the known members. A value whose class is not a member of the declared family is a `TypeError` when encoding. Two members with the same tag are a `TypeError`.
- `to_jsonable` reads the declared field types of every dataclass it encodes, so those annotations must resolve at run time (a name imported only under `TYPE_CHECKING` no longer encodes).

## 0.2.8

Added:
- `RegisteredClassChoices` validates in pydantic: a field annotated with it accepts a member class or its registry key, serializes to the key, and publishes the keys as a JSON-schema enum, so pydantic-built tool schemas (for example MCP) accept family-valued fields.

## 0.2.7

Added:
- `dataclass_from_mapping` decodes a field annotated `type[Family]`, where `Family` is an `AutoRegisterMeta` family, from the registry key that `to_jsonable` writes for the class. A key outside the family fails loudly. Decoding goes through `registered_class_from_key`, which dispatches on the family's metaclass, so a family whose boundary spelling is not its registry key registers its own decoder.
- `RegisteredClassChoices(family)`: the `AnnotationChoices` of a field holding one class of a registered family, labelled by registry key.

## 0.2.6

Added:
- `FieldLabel`: `Annotated` metadata declaring the display label of a field whose name does not read well to users, and `declared_field_label` to read it. Form and table builders derive every other label from the field name.

## 0.2.5

Fixed:
- Inline field documentation (a string literal under a dataclass field) is extracted again on Python 3.13 and later. Class source lookup used `inspect._ClassFinder`, a private helper that Python 3.13 removed, so every dataclass came back with no field help. Classes are now located by qualified name from the module AST directly. CI now tests Python 3.13.

## 0.2.4

Fixed:
- `dataclass_from_mapping` and `validate_annotated_dataclass` no longer raise `RecursionError` on Python 3.10 for fields declared with a recursive type alias such as `V = str | list["V"] | dict[str, "V"]`. Since 0.2.1, nested type strings were expanded on 3.10 with no stop, so a self-reference expanded forever. Expansion now stops at a self-reference and leaves it as a `ForwardRef`, which is what `get_type_hints` returns on Python 3.11 and later, so the decoder sees the same declaration on every version.

## 0.2.3

Added:
- `AnnotationChoices`: `Annotated` metadata declaring the finite values a field may hold. Annotation validation checks each value (or each item of a sequence value) against the declared choices, and `declared_annotation_choices` finds the declaration through `Annotated`, `Optional` and homogeneous containers for form builders; `enum_input_values` returns choice labels.
- `type[X]` annotations are validated: the value must be a class and a subclass of `X`.

## 0.2.2

Added:
- `to_jsonable`, with the `JsonValue`, `JsonObject` and `JsonScalar` aliases. It is the JSON-native encoder paired with `dataclass_from_mapping`: dataclasses are encoded by their declared fields, along with mappings, sequences, enums, paths (`str(path)`), callables (by import identity) and `AutoRegisterMeta` types (by registry key). More types can be added with `to_jsonable.register`.
- Module public-surface helpers: `declared_public_names`, `exported_public_names`, `public_names_from_objects` and `is_declared_public_name`.
- `lazy_exports(globals(), {owner_module: names})`. It installs a PEP 562 `__getattr__`/`__dir__` pair and returns the exported names for `__all__`.

## 0.2.1 (tagged, not published)

- Recursive sequence declarations now resolve on Python 3.10.
- Release readiness is now derived from the declared project metadata.

## 0.2.0 (tagged, not published)

- Breaking: `UnifiedParameterInfo` was removed. Dataclass presentation is now derived from the canonical parameter declarations.
- Immutable declaration docs are now prepared through the existing source cache.
