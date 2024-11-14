"""Frontend Choices, Defaults and Messages."""

from types import MappingProxyType

READER_CHOICES = MappingProxyType(
    {
        "fit_to": MappingProxyType(
            {
                "H": "Fit to Height",
                "O": "Original Size",
                "S": "Fit to Screen",
                "W": "Fit to Width",
            }
        ),
        "reading_direction": MappingProxyType(
            {
                "btt": "Bottom to Top",
                "ltr": "Left to Right",
                "rtl": "Right to Left",
                "ttb": "Top to Bottom",
            }
        ),
    }
)
READER_DEFAULTS = MappingProxyType(
    {
        "finish_on_last_page": True,
        "fit_to": "S",
        "reading_direction": "ltr",
        "read_rtl_in_reverse": False,
        "two_pages": False,
    }
)
