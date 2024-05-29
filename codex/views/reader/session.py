"""Reader session view."""

from types import MappingProxyType

from codex.serializers.choices import DEFAULTS
from codex.serializers.reader import ReaderSettingsSerializer
from codex.views.session import SessionViewBase, SessionViewBaseBase


class ReaderSessionViewBase(SessionViewBaseBase):
    """Reader session base."""

    SESSION_KEY = "reader"  # type: ignore
    SESSION_DEFAULTS = MappingProxyType(
        {
            "fit_to": DEFAULTS["fitTo"],
            "two_pages": False,
            "reading_direction": DEFAULTS["readingDirection"],
        }
    )


class ReaderSessionView(ReaderSessionViewBase, SessionViewBase):
    """Get Reader Settings."""

    serializer_class = ReaderSettingsSerializer  # type: ignore
