API reference
=============

The canonical public surface is ``python_introspect.__all__``. Applications
should import these names from ``python_introspect`` rather than internal
modules.

.. automodule:: python_introspect
   :members:
   :exclude-members: register_type_resolver
   :member-order: bysource

.. py:function:: register_type_resolver(resolver)

   Register a process-local resolver that maps an application proxy type to its
   public type. A resolver returns ``None`` when it does not own the candidate.
