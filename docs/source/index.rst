python-introspect
=================

``python-introspect`` analyzes callable signatures, dataclass fields, resolved
type hints, and docstrings through one extensible API.

.. toctree::
   :maxdepth: 2

   extensions
   api
   development

Quick start
-----------

.. code-block:: python

   from python_introspect import SignatureAnalyzer

   def example(a: int, b: str = "default") -> bool:
       return bool(a and b)

   parameters = SignatureAnalyzer().analyze(example)
   for name, info in parameters.items():
       print(name, info.param_type, info.default_value, info.is_required)

``SignatureAnalyzer.analyze`` accepts functions, methods, classes, dataclass
types, and instances. Namespace providers and type resolvers let host packages
extend forward-reference and proxy-type handling without modifying the core.

Requirements
------------

Python 3.9 or newer and metaclass-registry.

Public surface
--------------

The primary public types are ``SignatureAnalyzer``, ``ParameterInfo``,
``DocstringExtractor``, ``UnifiedParameterAnalyzer``, and ``Enableable``. The
registration helpers for namespace providers, type resolvers, wrapper targets,
parameter exclusions, and nominal enablement are also public; see :doc:`api`.
