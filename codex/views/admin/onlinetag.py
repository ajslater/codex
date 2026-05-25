"""Admin Online Tagging Views."""

import contextlib
import uuid

from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagAbortTask,
    OnlineTagPromptResponseTask,
    OnlineTagSkipAllPromptsTask,
)
from codex.models.admin import ComicboxTaggingDefaults
from codex.serializers.admin.tagging import (
    OnlineTagPromptResponseSerializer,
    OnlineTagStartSerializer,
)
from codex.views.admin.auth import AdminAPIView
from codex.views.admin.tagwrite import _resolve_comic_pks


class AdminOnlineTagActiveView(AdminAPIView):
    """Return the active online tagging session ID, if any."""

    def get(self, _request):
        """Return active session from the database."""
        from codex.models.admin import ComicboxTaggingDefaults

        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            return Response({"session_id": None})
        sid = defaults.active_session_id or None
        return Response({"session_id": sid})


class AdminOnlineTagStartView(AdminAPIView):
    """Start an online tagging session."""

    def post(self, request):
        """Validate and enqueue a BulkOnlineTagTask."""
        serializer = OnlineTagStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comic_pks = _resolve_comic_pks(data["group"], data["pks"])
        if not comic_pks:
            return Response({"detail": "No comics matched."}, status=400)

        session_id = str(uuid.uuid4())
        req_delete = data.get("delete_original")
        if req_delete is not None:
            delete_original = req_delete
        else:
            try:
                defaults = ComicboxTaggingDefaults.objects.get(pk=1)
                delete_original = defaults.delete_original
            except ComicboxTaggingDefaults.DoesNotExist:
                delete_original = False

        task = BulkOnlineTagTask(
            comic_pks=comic_pks,
            session_id=session_id,
            sources=tuple(data["sources"]),
            mode=data["mode"],
            prompts_mode=data["prompts_mode"],
            auto_threshold=float(data.get("auto_threshold", 0.85)),
            delete_original=delete_original,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response(
            {"session_id": session_id, "comic_count": len(comic_pks)},
            status=HTTP_202_ACCEPTED,
        )


class AdminOnlineTagPromptsView(AdminAPIView):
    """List pending prompts for an online tagging session."""

    def get(self, _request, session_id):
        """Return pending prompts from the database."""
        from codex.models.admin import ComicboxTaggingDefaults

        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            return Response({"session_id": session_id, "prompts": []})
        if defaults.active_session_id != session_id:
            return Response({"session_id": session_id, "prompts": []})
        return Response(
            {"session_id": session_id, "prompts": defaults.active_prompts or []}
        )


class AdminOnlineTagPromptResponseView(AdminAPIView):
    """Resolve a single deferred prompt."""

    def post(self, request, session_id, fingerprint):
        """Enqueue a prompt response task."""
        serializer = OnlineTagPromptResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        chosen_volume_id = None
        if data.get("chosen_volume_id"):
            with contextlib.suppress(ValueError):
                chosen_volume_id = int(data["chosen_volume_id"])

        payload = data.get("payload") or None
        if data["action"] == "choose" and payload:
            with contextlib.suppress(ValueError):
                payload = int(payload)

        task = OnlineTagPromptResponseTask(
            session_id=session_id,
            prompt_fingerprint=fingerprint,
            action=data["action"],
            payload=payload,
            chosen_volume_id=chosen_volume_id,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response({"detail": "Prompt response queued."}, status=HTTP_202_ACCEPTED)


class AdminOnlineTagAbortView(AdminAPIView):
    """Abort an online tagging session."""

    def post(self, _request, session_id):
        """Enqueue an abort task."""
        LIBRARIAN_QUEUE.put(OnlineTagAbortTask(session_id=session_id))
        return Response({"detail": "Abort signal sent."}, status=HTTP_202_ACCEPTED)


class AdminOnlineTagSkipAllPromptsView(AdminAPIView):
    """Skip every currently queued prompt for an online tagging session."""

    def post(self, _request, session_id):
        """Enqueue a skip-all-prompts task."""
        LIBRARIAN_QUEUE.put(OnlineTagSkipAllPromptsTask(session_id=session_id))
        return Response({"detail": "Skip-all signal sent."}, status=HTTP_202_ACCEPTED)
