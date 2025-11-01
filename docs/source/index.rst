.. python-introspect documentation master file

Welcome to python-introspect's documentation!
==============================================

**python-introspect** is a pure Python introspection toolkit for function signatures,
dataclasses, and type hints. It provides powerful utilities for analyzing Python code
structures at runtime.

Features
--------

* **Function Signature Analysis**: Deep inspection of function parameters, return types, and annotations
* **Dataclass Introspection**: Extract and analyze dataclass fields and metadata
* **Type Hint Processing**: Work with Python's type hints and annotations
* **Pure Python**: No external dependencies required
* **Comprehensive**: Handles complex signatures including kwargs, varargs, and nested types

Quick Start
-----------

Install the package:

.. code-block:: bash

   pip install python-introspect

Basic usage:

.. code-block:: python

   from python_introspect import SignatureAnalyzer

   def example_function(a: int, b: str = "default") -> bool:
       """Example function."""
       return True

   analyzer = SignatureAnalyzer(example_function)
   print(analyzer.get_parameter_info())

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
