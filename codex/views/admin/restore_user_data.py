"""Admin endpoint: trigger a user-data sidecar restore."""

from __future__ import annotations

from loguru import logger
from rest_framework.response import Response

from codex.settings import CONFIG_PATH
from codex.user_data.restore import restore, write_log
from codex.views.admin.auth import AdminAPIView


class AdminRestoreUserDataView(AdminAPIView):
    """Run the sidecar → main-DB restore and return per-table counts."""

    def post(self, *_args, **_kwargs) -> Response:
        """Trigger a restore and return the report."""
        dry_run = bool(self.request.data.get("dry_run", False))
        report = restore(dry_run=dry_run)
        log_path = CONFIG_PATH / "restore_user_data.log"
        try:
            write_log(report, log_path)
        except Exception:
            logger.exception("Failed to write restore log")
        return Response(
            {
                "written": report.written,
                "skipped": report.skipped,
                "log_path": str(log_path),
                "unmatched": report.unmatched_log,
            }
        )
