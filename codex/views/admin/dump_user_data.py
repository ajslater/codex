"""Admin endpoint: snapshot the user-data sidecar from the main DB."""

from __future__ import annotations

from rest_framework.response import Response

from codex.user_data.dump import dump_user_data
from codex.views.admin.auth import AdminAPIView


class AdminDumpUserDataView(AdminAPIView):
    """Replace the user-data sidecar with a fresh snapshot."""

    def post(self, *_args, **_kwargs) -> Response:
        """Run the dump synchronously and return per-table counts."""
        counts = dump_user_data()
        total = sum(counts.values())
        return Response({"written": counts, "total": total})
