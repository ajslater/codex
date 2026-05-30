"""Admin endpoints: list and restore user-data sidecar backups."""

from __future__ import annotations

from loguru import logger
from rest_framework import status
from rest_framework.response import Response

from codex.settings import BACKUP_DB_DIR, CONFIG_PATH
from codex.user_data.backups import list_sidecar_backups, resolve_sidecar_backup
from codex.user_data.restore import restore, write_log
from codex.views.admin.auth import AdminAPIView


class AdminUserDataBackupsView(AdminAPIView):
    """List the user-data sidecar backups available to restore from."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return the dated backups (newest first) plus any legacy sidecar."""
        backups = list_sidecar_backups(BACKUP_DB_DIR, CONFIG_PATH)
        return Response({"backups": backups})


class AdminRestoreUserDataView(AdminAPIView):
    """Run the sidecar → main-DB restore and return per-table counts."""

    def post(self, *_args, **_kwargs) -> Response:
        """Trigger a restore (optionally from a chosen backup) and return the report."""
        dry_run = bool(self.request.data.get("dry_run", False))
        filename = self.request.data.get("filename") or None
        sidecar_path = None
        if filename:
            sidecar_path = resolve_sidecar_backup(filename, BACKUP_DB_DIR, CONFIG_PATH)
            if sidecar_path is None:
                return Response(
                    {"detail": f"Unknown backup {filename!r}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        report = restore(sidecar_path=sidecar_path, dry_run=dry_run)
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
