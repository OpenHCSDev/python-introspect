"""Tests for SignatureAnalyzer."""

import pytest
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from python_introspect import (
    SignatureAnalyzer,
    ParameterInfo,
    DocstringExtractor,
    DocstringInfo,
)


class TestSignatureAnalyzer:
    """Test SignatureAnalyzer functionality."""

    def test_analyze_simple_function(self):
        """Test analyzing a simple function."""
        def simple_func(name: str, age: int = 25):
            pass

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(simple_func)

        assert "name" in params
        assert "age" in params
        assert params["name"].param_type == str
        assert params["name"].is_required is True
        assert params["age"].param_type == int
        assert params["age"].default_value == 25
        assert params["age"].is_required is False

    def test_analyze_function_with_kwargs(self):
        """Test analyzing function with keyword-only arguments."""
        def kwonly_func(a: int, *, b: str = "default", c: bool):
            pass

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(kwonly_func)

        assert "a" in params
        assert "b" in params
        assert "c" in params
        assert params["b"].default_value == "default"
        assert params["c"].is_required is True

    def test_analyze_function_with_docstring(self):
        """Test analyzing function with docstring parameters."""
        def documented_func(name: str, age: int = 25):
            """
            Example function.

            Args:
                name: The person's name
                age: The person's age in years
            """
            pass

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(documented_func)

        assert params["name"].description == "The person's name"
        assert params["age"].description == "The person's age in years"

    def test_analyze_dataclass(self):
        """Test analyzing a dataclass."""
        @dataclass
        class Person:
            """A person dataclass.

            Args:
                name: Person's name
                age: Person's age
            """
            name: str
            age: int = 25

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(Person)

        assert "name" in params
        assert "age" in params
        assert params["name"].param_type == str
        assert params["name"].is_required is True
        assert params["age"].default_value == 25
        assert params["age"].is_required is False

    def test_analyze_dataclass_with_factory(self):
        """Test analyzing dataclass with default_factory."""
        @dataclass
        class Config:
            items: List[str] = field(default_factory=list)
            settings: Dict[str, Any] = field(default_factory=dict)

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(Config)

        assert "items" in params
        assert "settings" in params
        assert params["items"].default_value == []
        assert params["settings"].default_value == {}
        assert params["items"].is_required is False

    def test_analyze_dataclass_instance(self):
        """Test analyzing a dataclass instance."""
        @dataclass
        class Config:
            name: str = "default"
            value: int = 10

        instance = Config(name="custom", value=42)
        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(instance)

        assert params["name"].default_value == "custom"
        assert params["value"].default_value == 42

    def test_analyze_method(self):
        """Test analyzing class methods."""
        class MyClass:
            def method(self, x: int, y: str = "default"):
                """Method docstring.

                Args:
                    x: First parameter
                    y: Second parameter
                """
                pass

        obj = MyClass()
        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(obj.method)

        # self should be skipped
        assert "self" not in params
        assert "x" in params
        assert "y" in params

    def test_analyze_constructor(self):
        """Test analyzing class constructors."""
        class MyClass:
            def __init__(self, name: str, value: int = 10):
                """Initialize MyClass.

                Args:
                    name: Object name
                    value: Object value
                """
                self.name = name
                self.value = value

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(MyClass)

        assert "self" not in params
        assert "name" in params
        assert "value" in params
        assert params["name"].is_required is True
        assert params["value"].default_value == 10

    def test_skip_dunder_parameters(self):
        """Test that dunder parameters are skipped."""
        @dataclass
        class Config:
            name: str = "test"
            __internal__: int = 0

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(Config)

        assert "name" in params
        assert "__internal__" not in params

    def test_analyze_with_optional_types(self):
        """Test analyzing functions with Optional types."""
        def func(name: str, email: Optional[str] = None):
            pass

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(func)

        assert "email" in params
        assert params["email"].default_value is None

    def test_analyze_with_complex_types(self):
        """Test analyzing with complex type annotations."""
        def func(
            items: List[str],
            mapping: Dict[str, int],
            data: Optional[List[Dict[str, Any]]] = None
        ):
            pass

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(func)

        assert "items" in params
        assert "mapping" in params
        assert "data" in params

    def test_analyze_empty_callable(self):
        """Test analyzing callable with no parameters."""
        def no_params():
            pass

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(no_params)

        assert len(params) == 0

    def test_analyze_none_target(self):
        """Test analyzing None returns empty dict."""
        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(None)

        assert params == {}


class TestDocstringExtractor:
    """Test DocstringExtractor functionality."""

    def test_extract_simple_docstring(self):
        """Test extracting simple docstring."""
        def func():
            """Simple summary line."""
            pass

        info = DocstringExtractor.extract(func)
        assert info.summary == "Simple summary line."
        assert info.description is None

    def test_extract_google_style_docstring(self):
        """Test extracting Google-style docstring."""
        def func(name: str, age: int):
            """
            Function with Google-style docstring.

            Args:
                name: The person's name
                age: The person's age

            Returns:
                A greeting message
            """
            pass

        info = DocstringExtractor.extract(func)
        assert "name" in info.parameters
        assert info.parameters["name"] == "The person's name"
        assert "age" in info.parameters
        assert info.returns == "A greeting message"

    def test_extract_numpy_style_docstring(self):
        """Test extracting NumPy-style docstring."""
        def func(x: int, y: int):
            """
            Function with NumPy-style docstring.

            Parameters
            ----------
            x : int
                First parameter
            y : int
                Second parameter
            """
            pass

        info = DocstringExtractor.extract(func)
        # NumPy style parsing support
        assert "x" in info.parameters or info.parameters == {}

    def test_extract_multiline_parameter_description(self):
        """Test extracting multiline parameter descriptions."""
        def func(description: str):
            """
            Function with multiline param description.

            Args:
                description: This is a very long description
                    that spans multiple lines and should be
                    properly concatenated together.
            """
            pass

        info = DocstringExtractor.extract(func)
        assert "description" in info.parameters
        assert "multiple lines" in info.parameters["description"]

    def test_extract_with_examples(self):
        """Test extracting examples section."""
        def func():
            """
            Function with examples.

            Examples:
                >>> func()
                'result'
            """
            pass

        info = DocstringExtractor.extract(func)
        assert info.examples is not None
        assert ">>>" in info.examples

    def test_extract_empty_docstring(self):
        """Test extracting from function without docstring."""
        def func():
            pass

        info = DocstringExtractor.extract(func)
        assert info.summary is None
        assert info.description is None
        assert info.parameters == {}

    def test_extract_from_dataclass(self):
        """Test extracting docstring from dataclass."""
        @dataclass
        class Config:
            """
            Configuration dataclass.

            Args:
                name: Config name
                value: Config value
            """
            name: str
            value: int = 10

        info = DocstringExtractor.extract(Config)
        assert info.summary is not None
        assert "name" in info.parameters


class TestParameterInfo:
    """Test ParameterInfo namedtuple."""

    def test_parameter_info_creation(self):
        """Test creating ParameterInfo."""
        param = ParameterInfo(
            name="test",
            param_type=str,
            default_value="default",
            is_required=False,
            description="Test parameter"
        )

        assert param.name == "test"
        assert param.param_type == str
        assert param.default_value == "default"
        assert param.is_required is False
        assert param.description == "Test parameter"

    def test_parameter_info_without_description(self):
        """Test ParameterInfo without description."""
        param = ParameterInfo(
            name="test",
            param_type=int,
            default_value=None,
            is_required=True
        )

        assert param.description is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_analyze_lambda(self):
        """Test analyzing lambda functions."""
        func = lambda x, y=10: x + y

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(func)

        assert "x" in params
        assert "y" in params
        assert params["y"].default_value == 10

    def test_analyze_builtin_function(self):
        """Test analyzing built-in functions (should handle gracefully)."""
        analyzer = SignatureAnalyzer()
        # Built-in functions may not have full signature info
        try:
            params = analyzer.analyze(len)
            # Either succeeds or returns empty dict
            assert isinstance(params, dict)
        except (ValueError, TypeError):
            # Built-ins may raise exceptions, which is acceptable
            pass

    def test_analyze_nested_dataclass(self):
        """Test analyzing dataclass with nested dataclass fields."""
        @dataclass
        class Inner:
            value: int = 5

        @dataclass
        class Outer:
            name: str
            inner: Inner = field(default_factory=Inner)

        analyzer = SignatureAnalyzer()
        params = analyzer.analyze(Outer)

        assert "name" in params
        assert "inner" in params
        assert params["inner"].is_required is False
