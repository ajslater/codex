"""Admin endpoint: snapshot the user-data sidecar from the main DB."""

from __future__ import annotations

from rest_framework.response import Response

from codex.user_data.dump import snapshot_sidecar
from codex.views.admin.auth import AdminAPIView


class AdminDumpUserDataView(AdminAPIView):
    """Write a fresh dated, compressed user-data sidecar backup."""

    def post(self, *_args, **_kwargs) -> Response:
        """Run the snapshot synchronously and return per-table counts."""
        counts = snapshot_sidecar()
        total = sum(counts.values())
        return Response({"written": counts, "total": total})
