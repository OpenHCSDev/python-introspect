Extension points
================

Host packages can extend type resolution and declare wrapper metadata without
teaching python-introspect about concrete frameworks. Registration is
process-local and should happen during host initialization.

Forward-reference namespaces
----------------------------

Register a provider when annotations contain names that are not available in
the inspected callable's normal globals:

.. code-block:: python

   from python_introspect import register_namespace_provider

   class ImageConfig:
       pass

   register_namespace_provider(lambda: {"ImageConfig": ImageConfig})

Providers return a name-to-object mapping used by type-hint resolution.

Proxy type resolution
---------------------

A type resolver maps an application proxy type to the public type whose fields
should be inspected. Return ``None`` when a resolver does not own the input:

.. code-block:: python

   from python_introspect import register_type_resolver

   def resolve_proxy(candidate):
       public_type = getattr(candidate, "public_type", None)
       return public_type if isinstance(public_type, type) else None

   register_type_resolver(resolve_proxy)

Wrapper declarations
--------------------

When a runtime wrapper should expose another callable's user-facing signature,
declare that ownership explicitly:

.. code-block:: python

   from python_introspect import (
       UnifiedParameterAnalyzer,
       set_parameter_exclusions,
       set_signature_analysis_target,
   )

   def operation(image, *, runtime_context=None):
       return image

   def wrapper(*args, **kwargs):
       return operation(*args, **kwargs)

   set_signature_analysis_target(wrapper, operation)
   set_parameter_exclusions(wrapper, {"runtime_context"})
   visible = UnifiedParameterAnalyzer.analyze(wrapper)

``set_signature_analysis_target`` declares which callable owns signature
metadata. Projection is chained: if a wrapper targets an adapter that targets an
authored callable, ``signature_analysis_target()`` returns the authored callable.
A cycle in those declarations raises ``RuntimeError`` instead of selecting an
arbitrary member.

``set_parameter_exclusions`` replaces the explicit exclusion set on one target;
``add_parameter_exclusions`` extends it without discarding earlier declarations.
``UnifiedParameterAnalyzer`` combines those declaration-owned exclusions with
its per-call ``exclude_params`` argument. ``SignatureAnalyzer`` intentionally
does not apply presentation exclusions; it remains the underlying signature and
help projection. These declarations avoid copied signatures and manually
synchronized field lists.

Help projection
---------------

``SignatureAnalyzer`` obtains parameter help from standard docstring sections
and from the first non-empty string in ``typing.Annotated`` metadata. Both
Google-style ``Additional Parameters:`` and NumPy-style ``Additional
Parameters`` are parsed as parameter sections, so wrappers can document optional
or dynamically exposed parameters without a separate help table. A docstring
description takes precedence over ``Annotated`` help for the same parameter.

For a declared wrapper target, source parameters come from the terminal target.
String help on wrapper-only ``Annotated`` parameters is then overlaid by name.
This preserves wrapper-owned presentation metadata without changing which
callable owns the base signature.

Nominal enablement
------------------

Dataclass configurations can inherit ``Enableable``. Callables can instead be
branded with ``mark_enableable``; branded callables must already declare the
``enabled`` parameter, because branding does not wrap or change call behavior.

When an enableable wrapper projects another callable, the generic
``EnableableParameterOverlay`` retains the target parameters and adds the
nominal ``Enableable.enabled`` declaration when absent. If the target already
has that parameter, its value/type remain authoritative and only missing help
may be filled. Hosts should use this overlay rather than redeclaring an enabled
field or copying it into each wrapper signature model.
