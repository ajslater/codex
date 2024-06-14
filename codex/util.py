"""Utility functions."""


def max_none(*args):
    """None aware math.max."""
    max_arg = None
    for arg in args:
        if max_arg is None:
            max_arg = arg
        elif arg is not None:
            max_arg = max(max_arg, arg)
    return max_arg
