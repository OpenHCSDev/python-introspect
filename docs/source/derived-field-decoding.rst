Declared derived-field decoding
===============================

The dataclass declaration owns field membership. Its constructor, defaults and
post-init behavior own non-init field values. ``dataclass_from_mapping`` admits
all fields from ``dataclasses.fields`` and decodes supplied values through the
existing annotation decoder. It passes only init fields to the constructor.
Supplied non-init fields must equal the constructed owner's values. It never
assigns supplied values to derived fields. Unknown keys remain errors; omitted
derived fields are computed normally. ``project_dataclass`` remains an init-only
projection, not a wire decoder.

Original failure
----------------

OpenHCS issue 578 observed successful native registration and status readback,
but the normal MCP CLI exited with a decode error. The canonical serializer
emitted ``CustomFunctionRegistrationObservation.outcome``. That declared
``init=False`` field was rejected as undeclared because the shared decoder used
the constructor subset as field membership. OpenHCS PR 579 independently fixes
the visibility of this client rejection. No operation is replayed here.

Ownership and source coverage
-----------------------------

The change starts at dependency main
``ed1e4eb15f7a0bf8315274d3e47858fa2b4372bb``. The existing decoder and annotation
validator remain the only owners. No OpenHCS-specific key list, alternate codec,
raw fallback, outcome branch or field-state copy is introduced. The applicable
refactor-audit patterns are BOUND-1, BOUND-2, BOUND-3 and MEMB-5: derive membership
from declarations and decode once at the boundary.

Before editing, the existing refactor-audit ``Package`` / ``Repository`` AST
loader covered current OpenHCS (687 modules), the dependency (12 modules), and
all eight OpenHCS dependency roots (354 modules). There were zero parse omissions.
This is source evidence, not a complete NRA detector scan or behavioral proof.
The query found the decoder, recursive annotation call and validation owner;
imports/calls in viewer DTOs, UI bridge service, runtime image values, source
provenance, MCP client/server and desktop updater. Existing consumers still use
the same public decoder. Constructor projections, overlay operations and native
post-init derived values retain their existing authority. The receiving version
adds the registration-observation DTO and the declaration-driven client result
decoder; it uses this same dependency entrypoint, not a second decoder.

Annotation resolution uses ``get_type_hints(..., include_extras=True)`` and the
existing recursive converter. Dynamic annotation namespaces are not statically
proved by this AST query. Equality uses the constructed field value's Python
equality contract; this change does not introduce framework-specific array
comparison semantics.

Verification scope
------------------

The focused family exercises inherited/frozen and slotted dataclasses, enum and
tuple conversion, nested derived DTOs, omitted derived fields, factory defaults,
contradictory derived values, invalid annotated values, unknown keys and missing
constructor fields. Verification results and actual OpenHCS receiving acceptance
are recorded separately; dependency tests alone do not establish CLI readiness.

The first focused run passed 37 tests. The first entire dependency run passed
143 tests with one stale test failure: ``test_version_available`` still pinned
0.1.12 although dependency main had already released source version 0.1.15.
That test now checks the canonical PEP 440 version through ``packaging.Version``
instead of adding a third literal version authority. The existing immutable
release action remains responsible for agreement between release metadata,
artifacts and tag; no release assertion is weakened here.

The original saved OpenHCS registration-status reply from PR 567's receiving
attempt decoded as ``registered`` with zero errors and one published source.
Contradictory outcome, boolean outcome and undeclared keys were rejected. This
was a read-only decode of the original canonical receipt, not a registration
replay or a new native runtime. The qualified OpenHCS import unexpectedly peaked
at 7,490,312 KiB; that process exited normally and the integration workers were
informed of the actual cost. It is not a lightweight dependency-only check.
Full client entrypoint acceptance remains separately assigned to PR 579's owner.

After that stale internal-version assertion was migrated, the entire dependency
suite passed: 144 tests in 0.80 seconds using the existing Python 3.12 environment
and this checkout's ``src`` on ``PYTHONPATH``. No environment or installed
package was changed. This is dependency source acceptance plus the real saved
OpenHCS DTO acceptance, not fresh installed-client or registry publication proof.

Release source follows the existing version convention: project metadata and
runtime declaration are advanced together to 0.1.16. Remote 0.1.15 is merged
source but has no public tag or published distribution; the new patch release
includes it. The existing immutable-tag publication workflow remains the
publication owner. A version edit or merged PR is not registry publication.
