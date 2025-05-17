"""Utility functions."""

from collections.abc import Mapping


def max_none(*args):
    """None aware math.max."""
    return max(filter(None.__ne__, args), default=None)


def mapping_to_dict(data):
    """Convert nested Mapping objects to dicts."""
    if isinstance(data, Mapping):
        return {key: mapping_to_dict(value) for key, value in data.items()}
    if isinstance(data, list | tuple | frozenset | set):
        return [mapping_to_dict(item) for item in data]
    return data
