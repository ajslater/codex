"""Admin doctor view."""

from adrf.mixins import get_data
from channels.db import database_sync_to_async
from rest_framework.response import Response

from codex.doctor import problem_count, run_doctor
from codex.serializers.admin.doctor import DoctorReportSerializer
from codex.views.admin.auth import AsyncAdminGenericAPIView


class AdminDoctorView(AsyncAdminGenericAPIView):
    """GET: comicbox's doctor report for this install."""

    serializer_class = DoctorReportSerializer

    async def get(self, *_args, **_kwargs) -> Response:
        """Run the doctor and serialize its rows."""
        # About a second: a RAR extraction subprocess, config files,
        # package metadata and a few library queries. Off the event loop
        # and off the one thread every sync view shares; channels'
        # wrapper closes the connection the executor thread opened.
        report = await database_sync_to_async(run_doctor, thread_sensitive=False)()
        obj = {
            "header": report.header,
            "results": report.results,
            "problems": problem_count(report),
        }
        serializer = self.get_serializer(obj)
        return Response(await get_data(serializer))
