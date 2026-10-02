import pytest

from observability import traced_operation


def test_traced_operation_returns_span():
    with traced_operation(
        "test.operation",
        component="unit-test",
    ) as span:
        assert span is not None


def test_traced_operation_preserves_exception():
    with pytest.raises(RuntimeError):
        with traced_operation("test.failure"):
            raise RuntimeError("boom")