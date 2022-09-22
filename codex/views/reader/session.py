"""Reader session view."""
from codex.serializers.reader import ReaderSettingsSerializer
from codex.views.session import ReaderSessionViewBase, SessionViewBase


class ReaderSessionView(ReaderSessionViewBase, SessionViewBase):
    """Get Reader Settings."""

    serializer_class = ReaderSettingsSerializer  # type: ignore
