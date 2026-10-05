# Recursive abstract sequence declarations on Python 3.10

Issue #13 reproduced using standalone CPython 3.10.22, with the actual unchanged decoder on merged main 43cdbf3: 3 failed, 29 passed across existing decoder/validation controls. The three failures were nested Sequence list/tuple reconstruction and unknown child-field rejection. The runtime was unpacked into a private maintenance packet; shared installed Python-introspect 0.2.0 and OpenHCS dependencies were not changed.

The annotation_types owner completes unresolved nested type strings after standard get_type_hints, using the declaring class/module namespace. Decoder and dataclass validator consume that same declaration. Literal values and Annotated metadata remain values; inherited fields use the original declaring module. No version-specific escape, private typing API, annotation cache, or duplicate decoder is added.

Receiving: full existing package suite plus two boundary controls, **145 PASS on CPython 3.10.22 and 145 PASS on CPython 3.12**. The added controls preserve Annotated/Literal metadata, direct nested-type validation, and inherited declarations across modules with conflicting names. Local raw logs: external-ready-cleanup-v1/pi310-red.log, pi310-green.log, pi312-green.log. Existing unrelated Ruff UP007 and SIM102 findings are not claimed repaired.

Version 0.2.1 is a distinct patch declaration; v0.2.0 remains immutable. This PR does not publish wheels or change the shared installed environment.
