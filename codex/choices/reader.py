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
        "finish_on_last_page": True,
        "fit_to": "W",
        "reading_direction": "ltr",
        "read_rtl_in_reverse": False,
        "two_pages": False,
        "page_transition": True,
        "last_route": {},
    }
)
