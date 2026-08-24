"""Admin Online Tagging Views."""

import contextlib
import uuid
from dataclasses import fields
from types import MappingProxyType
from typing import Final

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
from codex.views.admin.identifier_parse import parse_identifier_input
from codex.views.admin.tagwrite import FilteredComicPksView

# Boolean scan knobs the request may omit, mapped to the field on the stored
# tagging defaults that supplies the fallback.
_FLAG_DEFAULT_FIELDS: Final = MappingProxyType(
    {
        "delete_original": "delete_original",
        "merge_all_sources": "merge_all_sources",
        "rename": "rename_files",
    }
)


def _configured_sources(defaults: ComicboxTaggingDefaults | None) -> frozenset[str]:
    """Which online sources actually have credentials configured."""
    if not defaults:
        return frozenset()
    sources = set()
    if defaults.metron_key or (defaults.metron_user and defaults.metron_password):
        sources.add("metron")
    if defaults.comicvine_key:
        sources.add("comicvine")
    return frozenset(sources)


class AdminOnlineTagActiveView(AdminAPIView):
    """Return the in-flight online tagging scan id, if any."""

    def get(self, _request):
        """Return the active scan id from the cache."""
        sid = get_active_scan_id() or None
        return Response({"session_id": sid})


def _review_sources_by_pk() -> dict[int, tuple[str, ...]]:
    """Map each comic still awaiting review to the source(s) that prompted."""
    by_pk: dict[int, list[str]] = {}
    for prompt in get_pending_prompts().values():
        pk = prompt.get("pk")
        if pk is None:
            continue
        sources = by_pk.setdefault(pk, [])
        source = prompt.get("source")
        if source and source not in sources:
            sources.append(source)
    return {pk: tuple(sources) for pk, sources in by_pk.items()}


class AdminOnlineTagSnapshotView(AdminAPIView):
    """Return the live (or last-finished) online tagging session snapshot."""

    def get(self, _request):
        """Return the session snapshot, reconciled with current resolutions."""
        snapshot = get_snapshot()
        if snapshot:
            snapshot = overlay_resolutions(
                snapshot, _review_sources_by_pk(), get_resolved_outcomes()
            )
        return Response({"snapshot": snapshot})


class AdminOnlineTagStartView(FilteredComicPksView):
    """Start an online tagging scan."""

    @staticmethod
    def _parse_pinned_ids(
        raw_ids: dict, sources: list, configured: frozenset[str]
    ) -> dict[str, int]:
        """
        Parse the entered per-source identifiers into ``{source: issue_id}``.

        A pinned source is fetched by that issue id instead of searched, so a
        session can mix id retrieval and search. Raises ``ValueError`` with a
        user-facing message.
        """
        entered = {
            source: raw for source, raw in raw_ids.items() if (raw or "").strip()
        }
        if not entered:
            return {}
        if not configured:
            msg = "No online source credentials configured."
            raise ValueError(msg)
        if unselected := sorted(set(entered) - set(sources)):
            msg = f"Pinned id for unselected source(s): {', '.join(unselected)}."
            raise ValueError(msg)
        ids: dict[str, int] = {}
        for source, raw in entered.items():
            if source not in configured:
                msg = f"No {source} credentials configured."
                raise ValueError(msg)
            parsed_source, issue_id = parse_identifier_input(
                raw, source_hint=source, configured_sources=configured
            )
            if parsed_source != source:
                msg = (
                    f"That id is a {parsed_source} id, but it was entered for {source}."
                )
                raise ValueError(msg)
            ids[source] = issue_id
        return ids

    def _comic_pks_error(self, comic_pks: frozenset[int], *, pinned: bool) -> str:
        """Return a user-facing message when the resolved comics are unusable."""
        if not comic_pks:
            if pinned and self.skipped_read_only:
                return "Comic is in a read-only library."
            return "No comics matched."
        # comicbox pins an id per source for one comic; a multi-comic selection
        # has no meaningful single issue to pin.
        if pinned and len(comic_pks) > 1:
            return "Tagging by id requires a single comic."
        return ""

    @staticmethod
    def _resolve_flags(data: dict, defaults: ComicboxTaggingDefaults | None) -> dict:
        """Take each boolean knob from the request, falling back to the defaults."""
        return {
            key: bool(requested)
            if (requested := data.get(key)) is not None
            else bool(defaults and getattr(defaults, default_field))
            for key, default_field in _FLAG_DEFAULT_FIELDS.items()
        }

    def post(self, request):
        """Validate and enqueue a BulkOnlineTagTask."""
        serializer = OnlineTagStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            defaults = None

        try:
            ids = self._parse_pinned_ids(
                data.get("ids") or {}, data["sources"], _configured_sources(defaults)
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        comic_pks = self.resolve_comic_pks(data["collection"], data["pks"])
        if detail := self._comic_pks_error(comic_pks, pinned=bool(ids)):
            return Response({"detail": detail}, status=400)

        session_id = str(uuid.uuid4())
        task = BulkOnlineTagTask(
            comic_pks=comic_pks,
            session_id=session_id,
            sources=tuple(data["sources"]),
            mode=data["mode"],
            prompts_mode=data["prompts_mode"],
            ids=ids,
            **self._resolve_flags(data, defaults),
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


def _resume_task_params(resume: dict) -> dict:
    """
    Sanitize a stored resume descriptor into ``BulkOnlineTagTask`` kwargs.

    ``sources`` round-trips through JSON as a list; the task wants a tuple, and
    the pinned ``ids`` want int values. A resume descriptor persists to a
    file-based cache, so one written by an older Codex may carry keys a task
    field no longer accepts (e.g. the removed ``auto_threshold`` and ``dry_run``
    knobs) — drop unknown keys so resuming across an upgrade rebuilds the task
    instead of raising ``TypeError``.
    """
    params = dict(resume.get("params") or {})
    params["sources"] = tuple(params.get("sources") or ())
    params["ids"] = {
        str(source): int(issue_id)
        for source, issue_id in (params.get("ids") or {}).items()
    }
    valid_fields = {f.name for f in fields(BulkOnlineTagTask)}
    return {k: v for k, v in params.items() if k in valid_fields}


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

        session_id = str(uuid.uuid4())
        task = BulkOnlineTagTask(
            comic_pks=frozenset(remaining),
            session_id=session_id,
            **_resume_task_params(resume),
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
