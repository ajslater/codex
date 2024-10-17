"""Utility functions."""

from collections.abc import Mapping


def max_none(*args):
    """None aware math.max."""
    max_arg = None
    for arg in args:
        if max_arg is None:
            max_arg = arg
        elif arg is not None:
            max_arg = max(max_arg, arg)
    return max_arg


def mapping_to_dict(data):
    """Convert nested Mapping objects to dicts."""
    if isinstance(data, Mapping):
        return {key: mapping_to_dict(value) for key, value in data.items()}
    if isinstance(data, list | tuple | frozenset | set):
        return [mapping_to_dict(item) for item in data]
    return data
