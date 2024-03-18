"""Logging Color Formatter."""

import logging
from types import MappingProxyType

from colors import color


class ColorFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors."""

    FORMAT_COLORS = MappingProxyType(
        {
            "CRITICAL": {"fg": "red", "style": "bold"},
            "ERROR": {"fg": "red"},
            "WARNING": {"fg": "yellow"},
            "INFO": {"fg": "green"},
            "DEBUG": {"fg": "black", "style": "bold"},
            "NOTSET": {"fg": "blue"},
        }
    )

    def __init__(self, fmt, **kwargs):
        """Set up the FORMATS dict."""
        super().__init__(**kwargs)
        self.formatters = {}
        for level_name, args in self.FORMAT_COLORS.items():
            levelno = getattr(logging, level_name)
            template = color(fmt, **args)
            formatter = logging.Formatter(fmt=template, **kwargs)
            self.formatters[levelno] = formatter

    def format(self, record):
        """Format each log message."""
        formatter = self.formatters[record.levelno]
        return formatter.format(record)
