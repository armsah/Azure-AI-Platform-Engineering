import math


def dot_product(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vectors must have the same dimensions")

    return sum(x * y for x, y in zip(a, b))


def magnitude(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    denominator = magnitude(a) * magnitude(b)

    if denominator == 0:
        raise ValueError("zero vector has no cosine similarity")

    return dot_product(a, b) / denominator


def normalize(vector: list[float]) -> list[float]:
    length = magnitude(vector)

    if length == 0:
        raise ValueError("cannot normalize zero vector")

    return [x / length for x in vector]