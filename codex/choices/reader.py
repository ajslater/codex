"""Frontend Choices, Defaults and Messages."""

from types import MappingProxyType

READER_CHOICES = MappingProxyType(
    {
        "FIT_TO": MappingProxyType(
            {
                "S": "Fit to Screen",
                "W": "Fit to Width",
                "H": "Fit to Height",
                "O": "Original Size",
            }
        ),
        "READING_DIRECTION": MappingProxyType(
            {
                "ltr": "Left to Right",
                "rtl": "Right to Left",
                "ttb": "Top to Bottom",
                "btt": "Bottom to Top",
            }
        ),
    }
)
READER_DEFAULTS = MappingProxyType(
    {
        "fit_to": "W",
        "reading_direction": "ltr",
        "two_pages": False,
        "page_transition": True,
        "cache_book": False,
    }
)
