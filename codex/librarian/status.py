"""Librarian Status."""
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class StatusTypes:
    """Status Type Base Class."""

    @classmethod
    def keys(cls):
        """Return a tuple of non private, non-built-in keys."""
        return (key for key in dir(cls) if not key.startswith("_"))

    @classmethod
    def values(cls):
        """Return a tuple of non private, non-built-in values."""
        return (val for key, val in vars(cls).items() if not key.startswith("_"))

    @classmethod
    def dict(cls):
        """Return a dict of non private, non-built-in tems."""
        return {key: val for key, val in vars(cls).items() if not key.startswith("_")}
