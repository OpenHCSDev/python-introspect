# Changelog

0.2.2 is the first 0.2.x release published to PyPI. The 0.2.0 and 0.2.1 tags exist in git, but their publish runs were cancelled, so upgrading from PyPI goes straight from 0.1.16 to 0.2.2. The notes below cover every change in that jump.

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
