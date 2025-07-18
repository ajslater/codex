"""Utility functions."""

from collections.abc import Mapping


def max_none(*args):
    """None aware math.max."""
    return max(filter(None.__ne__, args), default=None)  # ty: ignore[no-matching-overload]


def mapping_to_dict(data):
    """Convert nested Mapping objects to dicts."""
    if isinstance(data, Mapping):
        return {key: mapping_to_dict(value) for key, value in data.items()}
    if isinstance(data, list | tuple | frozenset | set):
        return type(data)(mapping_to_dict(item) for item in data)
    return data


def flatten(seq: tuple | list | frozenset | set):
    """Flatten sequence."""
    flattened = []
    for item in seq:
        if isinstance(item, tuple | list | set | frozenset):
            # To make recursive, instead of list could call flatten again
            flattened.extend(list(item))
        else:
            flattened.append(item)
    return seq.__class__(tuple(flattened))
