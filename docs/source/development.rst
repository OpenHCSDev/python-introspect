Development and documentation
=============================

Install the package with development and documentation dependencies from the
repository root:

.. code-block:: bash

   python -m pip install -e ".[dev,docs]"

Run the package checks before opening a pull request:

.. code-block:: bash

   python -m pytest tests -v
   ruff check src tests
   black --check src tests
   mypy src/python_introspect --ignore-missing-imports

Documentation lives in ``docs/source``. Build it from the repository root with
fresh state and warnings treated as errors:

.. code-block:: bash

   python -m sphinx -E -W --keep-going -b html docs/source docs/build/html

The `documentation workflow
<https://github.com/OpenHCSDev/python-introspect/actions/workflows/docs.yml>`_
is the maintained CI definition. See the `repository
<https://github.com/OpenHCSDev/python-introspect>`_ for current tests and the
`issue tracker <https://github.com/OpenHCSDev/python-introspect/issues>`_ for
bug reports.
