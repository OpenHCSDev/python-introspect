"""Tests for package initialization and public API."""

import pytest
import python_introspect


class TestPackageImports:
    """Test package-level imports."""

    def test_version_available(self):
        """Test that __version__ is available."""
        assert hasattr(python_introspect, "__version__")
        assert isinstance(python_introspect.__version__, str)
        assert python_introspect.__version__ == "0.1.0"

    def test_signature_analyzer_import(self):
        """Test SignatureAnalyzer is importable."""
        assert hasattr(python_introspect, "SignatureAnalyzer")
        from python_introspect import SignatureAnalyzer
        assert SignatureAnalyzer is not None

    def test_parameter_info_import(self):
        """Test ParameterInfo is importable."""
        assert hasattr(python_introspect, "ParameterInfo")
        from python_introspect import ParameterInfo
        assert ParameterInfo is not None

    def test_docstring_info_import(self):
        """Test DocstringInfo is importable."""
        assert hasattr(python_introspect, "DocstringInfo")
        from python_introspect import DocstringInfo
        assert DocstringInfo is not None

    def test_docstring_extractor_import(self):
        """Test DocstringExtractor is importable."""
        assert hasattr(python_introspect, "DocstringExtractor")
        from python_introspect import DocstringExtractor
        assert DocstringExtractor is not None

    def test_unified_parameter_analyzer_import(self):
        """Test UnifiedParameterAnalyzer is importable."""
        assert hasattr(python_introspect, "UnifiedParameterAnalyzer")
        from python_introspect import UnifiedParameterAnalyzer
        assert UnifiedParameterAnalyzer is not None

    def test_unified_parameter_info_import(self):
        """Test UnifiedParameterInfo is importable."""
        assert hasattr(python_introspect, "UnifiedParameterInfo")
        from python_introspect import UnifiedParameterInfo
        assert UnifiedParameterInfo is not None

    def test_exceptions_import(self):
        """Test all exception classes are importable."""
        from python_introspect import (
            IntrospectionError,
            SignatureAnalysisError,
            DocstringParsingError,
            TypeResolutionError,
        )
        assert IntrospectionError is not None
        assert SignatureAnalysisError is not None
        assert DocstringParsingError is not None
        assert TypeResolutionError is not None


class TestPublicAPI:
    """Test public API completeness."""

    def test_all_exports(self):
        """Test __all__ contains expected exports."""
        expected_exports = [
            "__version__",
            "SignatureAnalyzer",
            "ParameterInfo",
            "DocstringInfo",
            "DocstringExtractor",
            "UnifiedParameterAnalyzer",
            "UnifiedParameterInfo",
            "IntrospectionError",
            "SignatureAnalysisError",
            "DocstringParsingError",
            "TypeResolutionError",
        ]

        for export in expected_exports:
            assert export in python_introspect.__all__

    def test_no_private_exports(self):
        """Test that private names are not in __all__."""
        for name in python_introspect.__all__:
            assert not name.startswith("_") or name == "__version__"

    def test_import_star(self):
        """Test that 'from python_introspect import *' works."""
        # This is a sanity check that __all__ is properly defined
        import python_introspect
        all_names = python_introspect.__all__

        for name in all_names:
            assert hasattr(python_introspect, name)


class TestQuickStart:
    """Test the quick start example from README."""

    def test_readme_example(self):
        """Test the example code from README works."""
        from python_introspect import SignatureAnalyzer

        def example_function(name: str, age: int = 25, *, active: bool = True):
            """
            Example function with parameters.

            Args:
                name: The person's name
                age: The person's age
                active: Whether the person is active
            """
            pass

        # Analyze the function
        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(example_function)

        # Verify it works as documented
        assert "name" in params
        assert "age" in params
        assert "active" in params

        assert params["name"].param_type == str
        assert params["age"].param_type == int
        assert params["age"].default_value == 25
        assert params["active"].param_type == bool
        assert params["active"].default_value is True

        # Verify descriptions are extracted
        assert params["name"].description == "The person's name"
        assert params["age"].description == "The person's age"
        assert params["active"].description == "Whether the person is active"
