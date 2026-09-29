import pytest

from similarity import (
    cosine_similarity,
    dot_product,
    normalize,
)


def test_identical_direction():
    assert cosine_similarity([1, 2], [2, 4]) == pytest.approx(1.0)


def test_orthogonal_vectors():
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)


def test_opposite_direction():
    assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)


def test_normalized_dot_equals_cosine():
    a = [3, 4]
    b = [4, 3]

    normalized_a = normalize(a)
    normalized_b = normalize(b)

    assert dot_product(
        normalized_a,
        normalized_b,
    ) == pytest.approx(cosine_similarity(a, b))