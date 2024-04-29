"""Common view constants."""

from types import MappingProxyType

FALSY = {None, "", "false", "0", False}
GROUP_NAME_MAP = MappingProxyType(
    {"p": "publisher", "i": "imprint", "s": "series", "v": "volume"}
)
