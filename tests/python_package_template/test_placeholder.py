"""Tests for template entrypoint."""


def test_placeholder_function():
    """Test a function in the entrypoint is callable."""
    from python_package_template.placeholder import placeholder_func

    assert placeholder_func() is True
