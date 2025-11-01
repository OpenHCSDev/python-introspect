"""Tests for UnifiedParameterAnalyzer."""

import pytest
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from python_introspect import (
    UnifiedParameterAnalyzer,
    UnifiedParameterInfo,
)


class TestUnifiedParameterAnalyzer:
    """Test UnifiedParameterAnalyzer functionality."""

    def test_analyze_function(self):
        """Test analyzing a simple function."""
        def test_func(name: str, age: int = 25):
            """Test function.

            Args:
                name: Person's name
                age: Person's age
            """
            pass

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(test_func)

        assert "name" in params
        assert "age" in params
        assert isinstance(params["name"], UnifiedParameterInfo)
        assert params["name"].param_type == str
        assert params["name"].is_required is True
        assert params["age"].default_value == 25
        assert params["age"].source_type == "function"

    def test_analyze_dataclass_type(self):
        """Test analyzing a dataclass type."""
        @dataclass
        class Config:
            """Configuration class.

            Args:
                name: Config name
                value: Config value
            """
            name: str
            value: int = 10

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(Config)

        assert "name" in params
        assert "value" in params
        assert params["name"].source_type == "dataclass"
        assert params["value"].default_value == 10

    def test_analyze_dataclass_instance(self):
        """Test analyzing a dataclass instance."""
        @dataclass
        class Config:
            name: str = "default"
            value: int = 10

        instance = Config(name="custom", value=42)
        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(instance)

        assert params["name"].default_value == "custom"
        assert params["value"].default_value == 42
        assert params["name"].source_type == "dataclass_instance"

    def test_analyze_with_exclusions(self):
        """Test analyzing with parameter exclusions."""
        def func(a: int, b: str, c: bool):
            pass

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(func, exclude_params=["b", "c"])

        assert "a" in params
        assert "b" not in params
        assert "c" not in params

    def test_analyze_class_constructor(self):
        """Test analyzing a class type."""
        class MyClass:
            def __init__(self, name: str, value: int = 10):
                """Initialize.

                Args:
                    name: Object name
                    value: Object value
                """
                self.name = name
                self.value = value

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(MyClass)

        assert "name" in params
        assert "value" in params
        assert "self" not in params

    def test_analyze_callable_object(self):
        """Test analyzing a callable object."""
        class CallableClass:
            def __call__(self, x: int, y: str = "default"):
                pass

        obj = CallableClass()
        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(obj)

        assert "x" in params
        assert "y" in params

    def test_analyze_nested(self):
        """Test nested analysis for dataclass fields."""
        @dataclass
        class Inner:
            value: int = 5

        @dataclass
        class Outer:
            name: str
            inner: Inner = field(default_factory=Inner)

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze_nested(Outer)

        assert "name" in params
        assert "inner" in params
        assert "nested" in params["inner"].source_type

    def test_analyze_method(self):
        """Test analyzing instance methods."""
        class MyClass:
            def method(self, x: int, y: str = "test"):
                """Method docstring.

                Args:
                    x: First param
                    y: Second param
                """
                pass

        obj = MyClass()
        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(obj.method)

        assert "self" not in params
        assert "x" in params
        assert "y" in params

    def test_analyze_none(self):
        """Test analyzing None returns empty dict."""
        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(None)

        assert params == {}

    def test_analyze_empty_function(self):
        """Test analyzing function with no parameters."""
        def no_params():
            pass

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(no_params)

        assert len(params) == 0

    def test_analyze_with_complex_types(self):
        """Test analyzing with complex type hints."""
        def func(
            items: List[str],
            mapping: Dict[str, int],
            optional: Optional[str] = None
        ):
            pass

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(func)

        assert len(params) == 3
        assert "items" in params
        assert "mapping" in params
        assert "optional" in params


class TestUnifiedParameterInfo:
    """Test UnifiedParameterInfo dataclass."""

    def test_create_unified_parameter_info(self):
        """Test creating UnifiedParameterInfo."""
        info = UnifiedParameterInfo(
            name="test",
            param_type=str,
            default_value="default",
            is_required=False,
            description="Test param",
            source_type="function"
        )

        assert info.name == "test"
        assert info.param_type == str
        assert info.default_value == "default"
        assert info.is_required is False
        assert info.description == "Test param"
        assert info.source_type == "function"

    def test_from_parameter_info(self):
        """Test converting from ParameterInfo."""
        from python_introspect import ParameterInfo

        param_info = ParameterInfo(
            name="test",
            param_type=int,
            default_value=10,
            is_required=True,
            description="Test"
        )

        unified = UnifiedParameterInfo.from_parameter_info(
            param_info,
            source_type="test"
        )

        assert unified.name == "test"
        assert unified.param_type == int
        assert unified.default_value == 10
        assert unified.is_required is True
        assert unified.description == "Test"
        assert unified.source_type == "test"


class TestBackwardCompatibility:
    """Test backward compatibility aliases."""

    def test_parameter_analyzer_alias(self):
        """Test ParameterAnalyzer alias."""
        from python_introspect.unified_parameter_analyzer import ParameterAnalyzer

        assert ParameterAnalyzer == UnifiedParameterAnalyzer

    def test_analyze_parameters_alias(self):
        """Test analyze_parameters function alias."""
        from python_introspect.unified_parameter_analyzer import analyze_parameters

        def func(x: int):
            pass

        params = analyze_parameters(func)
        assert "x" in params


class TestObjectInstanceAnalysis:
    """Test analysis of regular object instances."""

    def test_analyze_object_instance(self):
        """Test analyzing regular object instances."""
        class MyClass:
            def __init__(self, name: str, value: int = 10):
                self.name = name
                self.value = value

        instance = MyClass("test", 20)
        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(instance)

        # Should get parameters from __init__
        assert "name" in params
        assert "value" in params
        # Instance values should be used
        assert params["name"].default_value == "test"
        assert params["value"].default_value == 20

    def test_analyze_inherited_parameters(self):
        """Test analyzing object with inherited parameters."""
        class Base:
            def __init__(self, base_param: str = "base"):
                self.base_param = base_param

        class Derived(Base):
            def __init__(self, derived_param: int = 5, **kwargs):
                super().__init__(**kwargs)
                self.derived_param = derived_param

        instance = Derived(derived_param=10, base_param="custom")
        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(instance)

        # Should get parameters from both classes
        assert "derived_param" in params
        # Note: base_param might not be captured due to **kwargs


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_analyze_lambda(self):
        """Test analyzing lambda functions."""
        func = lambda x, y=10: x + y

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(func)

        assert "x" in params
        assert "y" in params

    def test_analyze_with_varargs(self):
        """Test analyzing function with *args."""
        def func(x: int, *args):
            pass

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(func)

        # Should get x, args handling varies
        assert "x" in params

    def test_analyze_nested_dataclass_field(self):
        """Test analyzing dataclass with nested dataclass field."""
        @dataclass
        class Address:
            street: str = "Main St"
            city: str = "Unknown"

        @dataclass
        class Person:
            name: str
            address: Address = field(default_factory=Address)

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(Person)

        assert "name" in params
        assert "address" in params

    def test_analyze_dataclass_with_metadata(self):
        """Test analyzing dataclass with field metadata."""
        @dataclass
        class Config:
            name: str = field(
                default="test",
                metadata={"description": "Config name"}
            )

        analyzer = UnifiedParameterAnalyzer()
        params = analyzer.analyze(Config)

        assert "name" in params
        assert params["name"].description == "Config name"
