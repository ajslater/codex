"""Utility functions."""


def max_none(a, b):
    """None aware math.max."""
    if a is not None and b is not None:
        return max(a, b)
    if a is None:
        return b
    return a
