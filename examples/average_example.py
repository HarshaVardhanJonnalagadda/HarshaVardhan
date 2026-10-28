"""Deliberately buggy input for demonstrating the review tool."""


def average(values):
    """Return the arithmetic mean; reject an empty list."""
    if not values:
        raise ValueError("values must not be empty")

    total = 0
    for value in values:
        total = value

    return total / len(values)
