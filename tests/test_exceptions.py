"""Tests for exception classes."""

import pytest
from python_introspect import (
    IntrospectionError,
    SignatureAnalysisError,
    DocstringParsingError,
    TypeResolutionError,
)


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_introspection_error_base(self):
        """Test IntrospectionError is base exception."""
        error = IntrospectionError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_signature_analysis_error_inheritance(self):
        """Test SignatureAnalysisError inherits from IntrospectionError."""
        error = SignatureAnalysisError("signature error")
        assert isinstance(error, IntrospectionError)
        assert isinstance(error, Exception)
        assert str(error) == "signature error"

    def test_docstring_parsing_error_inheritance(self):
        """Test DocstringParsingError inherits from IntrospectionError."""
        error = DocstringParsingError("docstring error")
        assert isinstance(error, IntrospectionError)
        assert isinstance(error, Exception)
        assert str(error) == "docstring error"

    def test_type_resolution_error_inheritance(self):
        """Test TypeResolutionError inherits from IntrospectionError."""
        error = TypeResolutionError("type error")
        assert isinstance(error, IntrospectionError)
        assert isinstance(error, Exception)
        assert str(error) == "type error"


class TestExceptionRaising:
    """Test raising and catching exceptions."""

    def test_raise_introspection_error(self):
        """Test raising IntrospectionError."""
        with pytest.raises(IntrospectionError) as exc_info:
            raise IntrospectionError("test")
        assert str(exc_info.value) == "test"

    def test_catch_specific_exception(self):
        """Test catching specific exception types."""
        with pytest.raises(SignatureAnalysisError):
            raise SignatureAnalysisError("analysis failed")

    def test_catch_base_exception(self):
        """Test catching derived exceptions with base class."""
        with pytest.raises(IntrospectionError):
            raise SignatureAnalysisError("derived exception")

    def test_multiple_exception_types(self):
        """Test multiple exception types can be caught."""
        exceptions = [
            SignatureAnalysisError("sig"),
            DocstringParsingError("doc"),
            TypeResolutionError("type"),
        ]

        for exc in exceptions:
            with pytest.raises(IntrospectionError):
                raise exc


class TestExceptionMessages:
    """Test exception messages and context."""

    def test_exception_with_detailed_message(self):
        """Test exceptions can carry detailed messages."""
        detailed_msg = "Failed to analyze function 'test_func': parameter 'x' has invalid type"
        error = SignatureAnalysisError(detailed_msg)
        assert detailed_msg in str(error)

    def test_exception_with_empty_message(self):
        """Test exceptions can be created with empty messages."""
        error = IntrospectionError("")
        assert str(error) == ""

    def test_exception_repr(self):
        """Test exception representation."""
        error = TypeResolutionError("test error")
        repr_str = repr(error)
        assert "TypeResolutionError" in repr_str
        assert "test error" in repr_str
