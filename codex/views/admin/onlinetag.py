"""Admin Online Tagging Views."""

import contextlib
import uuid

from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_409_CONFLICT

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.session_cache import (
    get_active_scan_id,
    get_pending_prompts,
)
from codex.librarian.onlinetag.session_snapshot import (
    get_resolved_outcomes,
    get_resume_state,
    get_snapshot,
    overlay_resolutions,
)
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagAbortTask,
    OnlineTagDismissTask,
    OnlineTagPromptResponseTask,
    OnlineTagSkipAllPromptsTask,
)
from codex.models.admin import ComicboxTaggingDefaults
from codex.serializers.admin.tagging import (
    OnlineTagPromptResponseSerializer,
    OnlineTagStartSerializer,
)
from codex.views.admin.auth import AdminAPIView
from codex.views.admin.tagwrite import FilteredComicPksView


class AdminOnlineTagActiveView(AdminAPIView):
    """Return the in-flight online tagging scan id, if any."""

    def get(self, _request):
        """Return the active scan id from the cache."""
        sid = get_active_scan_id() or None
        return Response({"session_id": sid})


class AdminOnlineTagSnapshotView(AdminAPIView):
    """Return the live (or last-finished) online tagging session snapshot."""

    def get(self, _request):
        """Return the session snapshot, reconciled with current resolutions."""
        snapshot = get_snapshot()
        if snapshot:
            review_pks = {p.get("pk") for p in get_pending_prompts().values()}
            snapshot = overlay_resolutions(
                snapshot, review_pks, get_resolved_outcomes()
            )
        return Response({"snapshot": snapshot})


class AdminOnlineTagStartView(FilteredComicPksView):
    """Start an online tagging scan."""

    def post(self, request):
        """Validate and enqueue a BulkOnlineTagTask."""
        serializer = OnlineTagStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comic_pks = self.resolve_comic_pks(data["collection"], data["pks"])
        if not comic_pks:
            return Response({"detail": "No comics matched."}, status=400)

        session_id = str(uuid.uuid4())
        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            defaults = None

        req_delete = data.get("delete_original")
        if req_delete is not None:
            delete_original = req_delete
        else:
            delete_original = bool(defaults and defaults.delete_original)

        req_merge = data.get("merge_all_sources")
        if req_merge is not None:
            merge_all_sources = req_merge
        else:
            merge_all_sources = bool(defaults and defaults.merge_all_sources)

        req_rename = data.get("rename")
        if req_rename is not None:
            rename = req_rename
        else:
            rename = bool(defaults and defaults.rename_files)

        task = BulkOnlineTagTask(
            comic_pks=comic_pks,
            session_id=session_id,
            sources=tuple(data["sources"]),
            mode=data["mode"],
            prompts_mode=data["prompts_mode"],
            auto_threshold=float(data.get("auto_threshold", 0.85)),
            delete_original=delete_original,
            merge_all_sources=merge_all_sources,
            rename=rename,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response(
            {
                "session_id": session_id,
                "comic_count": len(comic_pks),
                "skipped": self.skipped_read_only,
            },
            status=HTTP_202_ACCEPTED,
        )


class AdminOnlineTagAbortView(AdminAPIView):
    """
    Pause the in-flight online tagging scan (DELETE on the tag-session URL).

    Stops the scan between comics; comics already tagged keep their tags and the
    rest are left resumable via the resume descriptor the daemon persists.
    """

    def delete(self, _request, session_id):
        """Enqueue an abort (pause) task for the running scan."""
        LIBRARIAN_QUEUE.put(OnlineTagAbortTask(session_id=session_id))
        return Response({"detail": "Pause signal sent."}, status=HTTP_202_ACCEPTED)


class AdminOnlineTagResumeView(AdminAPIView):
    """Resume a paused/interrupted scan over the comics it never reached."""

    def post(self, _request):
        """Rebuild a scan task from the stored resume descriptor and enqueue it."""
        if get_active_scan_id():
            return Response(
                {"detail": "A tagging scan is already running."},
                status=HTTP_409_CONFLICT,
            )
        resume = get_resume_state()
        remaining = resume.get("remaining_pks") if resume else None
        if not resume or not remaining:
            return Response({"detail": "Nothing to resume."}, status=400)

        params = dict(resume.get("params") or {})
        # sources round-trips through JSON as a list; the task wants a tuple.
        params["sources"] = tuple(params.get("sources") or ())
        session_id = str(uuid.uuid4())
        task = BulkOnlineTagTask(
            comic_pks=frozenset(remaining),
            session_id=session_id,
            **params,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response(
            {"session_id": session_id, "comic_count": len(remaining)},
            status=HTTP_202_ACCEPTED,
        )


class AdminOnlineTagDismissView(AdminAPIView):
    """Clear the status-table snapshot and resume descriptor."""

    def post(self, _request):
        """Enqueue a dismiss task (leaves pending prompts intact)."""
        LIBRARIAN_QUEUE.put(OnlineTagDismissTask())
        return Response({"detail": "Dismiss signal sent."}, status=HTTP_202_ACCEPTED)


class AdminOnlineTagPromptsView(AdminAPIView):
    """List every pending deferred prompt (independent of any running scan)."""

    def get(self, _request):
        """Return all pending prompts from the cache."""
        prompts = list(get_pending_prompts().values())
        return Response({"prompts": prompts})


class AdminOnlineTagPromptResponseView(AdminAPIView):
    """Resolve a single deferred prompt by fingerprint."""

    def post(self, request, fingerprint):
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
            prompt_fingerprint=fingerprint,
            action=data["action"],
            payload=payload,
            chosen_volume_id=chosen_volume_id,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response({"detail": "Prompt response queued."}, status=HTTP_202_ACCEPTED)


class AdminOnlineTagSkipAllPromptsView(AdminAPIView):
    """Skip every pending deferred prompt in one shot."""

    def post(self, _request):
        """Enqueue a skip-all-prompts task."""
        LIBRARIAN_QUEUE.put(OnlineTagSkipAllPromptsTask())
        return Response({"detail": "Skip-all signal sent."}, status=HTTP_202_ACCEPTED)
