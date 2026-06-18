"""Admin Tag Write Errors View."""

from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import TAG_WRITE_ERRORS_CHANGED_TASK
from codex.librarian.scribe.tagwrite_errors import (
    clear_tag_write_errors,
    get_tag_write_errors,
)
from codex.views.admin.auth import AdminAPIView


class AdminTagWriteErrorsView(AdminAPIView):
    """Read and clear the collected tag-write errors."""

    def get(self, _request, *_args, **_kwargs) -> Response:
        """
        Return the collected tag-write errors (newest first).

        Returns a bare list: the envelope renderer reserves an ``errors``
        key for DRF error objects, so a ``{"errors": [...]}`` payload would
        be mistaken for an envelope and drop the data.
        """
        return Response(get_tag_write_errors())

    def delete(self, _request, *_args, **_kwargs) -> Response:
        """Clear all collected tag-write errors and notify admins."""
        clear_tag_write_errors()
        # Tell other admin sessions to drop the badge / empty the panel.
        LIBRARIAN_QUEUE.put(TAG_WRITE_ERRORS_CHANGED_TASK)
        return Response({"detail": "Tag write errors cleared."})
