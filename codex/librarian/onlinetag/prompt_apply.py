"""
Apply an admin's answer to a deferred online-tagging match prompt.

Answering is fully decoupled from the scan that raised the question: the
deferred-prompt fingerprint is deterministic across processes, so this builds
a *fresh* comicbox session and replays the pick into it. A scan may still be
running, may have finished hours ago, or may have been a different daemon
entirely.

One prompt is one *question*, not one comic. Comicbox fingerprints a prompt at
series level so a single pick answers a whole run, which means an answer here
usually has several comics to write:

- The **representative** — the comic whose candidates were scored and rendered
  in the review dialog — is pinned straight to the chosen candidate's issue id
  and fetched by it, never re-searched.
- Its **followers**, the other issues of that series, share the *volume* and
  not the issue. Each replays its own lookup with the pick preloaded, so
  comicbox re-maps it onto whichever of that comic's candidates carries the
  chosen volume.
- When the pick names no volume there is nothing to transfer, so the followers
  go back in the queue for an answer of their own rather than being written
  from another issue's match.

Split out of :mod:`~codex.librarian.onlinetag.session_manager`, which owns the
scan; this owns what happens after one.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from comicbox.exceptions import ComicboxError
from comicbox.online_session import MatchMode, OnlineSession

from codex.librarian.notifier.tasks import (
    ONLINE_TAG_PROMPT_TASK,
    TAG_WRITE_ERRORS_CHANGED_TASK,
)
from codex.librarian.onlinetag.explicit_id import fetch_tags_by_explicit_id
from codex.librarian.onlinetag.session_cache import add_pending_prompts, prompt_comics
from codex.librarian.onlinetag.session_state import serialize_prompt
from codex.librarian.scribe.tagwrite_errors import add_tag_write_error
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models.comic import Comic

if TYPE_CHECKING:
    from collections.abc import Callable
    from multiprocessing import Queue
    from typing import Literal

    from comicbox.online_session import OnlineCredentials
    from loguru._logger import Logger

#: (action, payload, chosen_volume_id) — the admin's answer as the review
#: dialog sends it, carried together because every step needs all three.
Resolution = tuple[str, Any, int | None]


def comic_prompt(prompt: dict[str, Any], comic: dict[str, Any]) -> dict[str, Any]:
    """
    Narrow a series-level prompt to one of the comics it answers for.

    The apply path works one comic at a time, and the steps it hands the
    prompt to read ``pk`` / ``path`` off it — a re-queue after a drifted
    replay most of all, which must name the comic that drifted rather than the
    series' representative.
    """
    return {
        **prompt,
        "pk": comic["pk"],
        "path": comic.get("path") or "",
        "comics": [dict(comic)],
    }


class PromptApplier:
    """Write an answered match prompt to every comic it speaks for."""

    def __init__(
        self,
        log: Logger,
        librarian_queue: Queue,
        build_credentials: Callable[[], OnlineCredentials | None],
    ) -> None:
        """Wire the applier to its log, queue, and credential source."""
        self.log = log
        self.librarian_queue = librarian_queue
        self._build_credentials = build_credentials

    def apply(
        self,
        prompt: dict[str, Any],
        action: str,
        payload: Any,
        chosen_volume_id: int | None,
    ) -> None:
        """Apply the admin's pick to every comic this one question answers for."""
        comics = prompt_comics(prompt)
        source = prompt.get("source") or ""
        if not comics or not source:
            self.log.warning("Online tag: prompt missing comic reference; skipping.")
            return
        credentials = self._build_credentials()
        if not credentials:
            self.log.warning("Online tag: no credentials for prompt resolution.")
            return
        representative, *followers = comics
        resolution = (action, payload, chosen_volume_id)
        self._apply_to_representative(prompt, representative, resolution, credentials)
        if not followers:
            return
        if action == "choose" and chosen_volume_id is not None:
            self._apply_to_followers(prompt, followers, resolution, credentials)
        else:
            self._requeue_untransferable(prompt, followers)

    def _apply_to_representative(
        self,
        prompt: dict[str, Any],
        comic: dict[str, Any],
        resolution: Resolution,
        credentials: OnlineCredentials,
    ) -> None:
        """Apply the pick to the comic whose candidates the admin looked at."""
        action, payload, chosen_volume_id = resolution
        pk = comic["pk"]
        path_str = self._refresh_comic_path(pk, comic.get("path") or "")
        if not path_str:
            return
        source = prompt.get("source") or ""
        scoped = comic_prompt(prompt, comic)
        action, payload = self._explicit_resolution(prompt, action, payload)
        # A concrete pick (a candidate with a known issue id) is fetched
        # directly by id — never re-searched. A re-search replay drifts under
        # rate limiting (a different candidate set misses the preloaded
        # fingerprint), which would silently discard the admin's choice and
        # re-queue a fresh, often worse, prompt. Direct id fetch is immune.
        explicit = self._explicit_issue_id(action, payload, source)
        if explicit is not None:
            self._apply_explicit_id(scoped, pk, explicit, path_str, credentials)
        else:
            replay = (action, payload, chosen_volume_id)
            self._apply_replayed_search(scoped, pk, path_str, credentials, replay)

    def _apply_to_followers(
        self,
        prompt: dict[str, Any],
        followers: list[dict[str, Any]],
        resolution: Resolution,
        credentials: OnlineCredentials,
    ) -> None:
        """
        Apply the picked volume to the rest of the series, one lookup each.

        Deliberately NOT the representative's issue id: these are different
        issues of the same series, so what transfers is the volume. Each comic
        replays its own search with the pick preloaded, and comicbox re-maps it
        onto whichever candidate carries that volume. One that no longer finds
        it re-queues a prompt of its own rather than taking a wrong issue.
        """
        count = len(followers)
        self.log.info(
            f"Online tag: applying the pick to {count} more comics of the series."
        )
        for comic in followers:
            pk = comic["pk"]
            path_str = self._refresh_comic_path(pk, comic.get("path") or "")
            if not path_str:
                continue
            self._apply_replayed_search(
                comic_prompt(prompt, comic), pk, path_str, credentials, resolution
            )

    def _requeue_untransferable(
        self, prompt: dict[str, Any], followers: list[dict[str, Any]]
    ) -> None:
        """
        Re-ask for the comics an untransferable pick cannot speak for.

        A pick with no volume id behind it, or a hand-entered issue id, names
        one issue. The other issues of the series were waiting on the same
        question, so they go back in the queue under it — answering again
        peels off one comic at a time rather than writing one issue's match
        onto all of them.
        """
        remaining = {**comic_prompt(prompt, followers[0]), "comics": list(followers)}
        add_pending_prompts({prompt["fingerprint"]: remaining})
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        count = len(followers)
        self.log.info(
            f"Online tag: the pick named no volume; re-queued {count} more comics."
        )

    # --- one comic ------------------------------------------------------

    @staticmethod
    def _explicit_resolution(
        prompt: dict[str, Any], action: str, payload: Any
    ) -> tuple[str, Any]:
        """
        Pin a chosen candidate to its issue id.

        A fresh search may return candidates in a different order, so a bare
        ``choose`` index could select the wrong issue. Re-map the index to the
        candidate's stable ``issue_id`` and apply it as a ``manual`` pick,
        which fetches that exact issue regardless of search ordering.
        """
        if action != "choose":
            return action, payload
        candidates = prompt.get("candidates") or []
        index = payload if isinstance(payload, int) else None
        if index is None or not (0 <= index < len(candidates)):
            return action, payload
        chosen = candidates[index]
        issue_id = chosen.get("issue_id")
        source = chosen.get("source") or prompt.get("source")
        if issue_id and source:
            return "manual", f"{source}:{issue_id}"
        return action, payload

    @staticmethod
    def _explicit_issue_id(
        action: str, payload: Any, default_source: str
    ) -> tuple[str, int] | None:
        """Parse a ``manual`` ``source:issue_id`` payload into (source, id)."""
        if action != "manual" or not isinstance(payload, str):
            return None
        src, sep, id_str = payload.partition(":")
        if not sep:
            return None
        try:
            issue_id = int(id_str)
        except (TypeError, ValueError):
            return None
        return (src or default_source), issue_id

    def _report_apply_failure(self, path_str: str, msg: str) -> None:
        """Log + surface a failed prompt apply in the admin Tagging error panel."""
        self.log.warning(f"Online tag: {msg} ({path_str})")
        add_tag_write_error(path_str, msg)
        self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)

    def _refresh_comic_path(self, pk: int, prompt_path: str) -> str:
        """
        Return the comic's current path, preferring the DB row over the prompt.

        A prompt's serialized path goes stale between deferral and answer —
        most commonly when an earlier write for the same comic ran with
        rename enabled and moved the file. The DB row follows the rename
        (via the write's move import), so it is the fresher reference. A
        missing row means the comic was deleted (or re-imported under a new
        pk after a rename the DB never synced); surface that instead of
        fetching against a dead path.
        """
        comic = Comic.objects.filter(pk=pk).only("path").first()
        if comic:
            return comic.path
        self._report_apply_failure(
            prompt_path, "comic no longer in the database; answer not applied"
        )
        return ""

    def _apply_explicit_id(
        self,
        prompt: dict[str, Any],
        pk: int,
        explicit: tuple[str, int],
        path_str: str,
        credentials: OnlineCredentials,
    ) -> None:
        """Fetch the picked issue by id and enqueue its write (no re-search)."""
        src, issue_id = explicit
        try:
            tags = fetch_tags_by_explicit_id(Path(path_str), src, issue_id, credentials)
        except (ComicboxError, OSError) as exc:
            # The prompt is already consumed, so a swallowed failure would
            # silently discard the admin's pick — put it on the error panel.
            self._report_apply_failure(
                path_str, f"fetching chosen issue {src}:{issue_id} failed: {exc}"
            )
            return
        if tags:
            self._enqueue_resolved_write(prompt, pk, tags, path_str)
        else:
            # The id itself didn't resolve (wrong/unknown issue). Don't re-queue
            # a fresh ambiguous prompt — the admin made an explicit choice.
            self._report_apply_failure(
                path_str, f"chosen issue {src}:{issue_id} did not resolve"
            )

    def _apply_replayed_search(
        self,
        prompt: dict[str, Any],
        pk: int,
        path_str: str,
        credentials: OnlineCredentials,
        resolution: Resolution,
    ) -> None:
        """Re-search and apply a pick that carries no explicit issue id."""
        action, payload, chosen_volume_id = resolution
        source = prompt.get("source") or ""
        # defer_prompts on: the bridged selector consults the preloaded
        # resolution; without it (or a handler) an ambiguous re-search would
        # fall through to comicbox's interactive CLI prompt inside the daemon.
        session = OnlineSession(
            sources=(source,),
            credentials=credentials,
            # The persisted prompt's own "mode" key predates comicbox 5's
            # rename and is codex's cache format, versioned by
            # PROMPT_VERSION; only the comicbox kwarg moved.
            match=MatchMode(prompt.get("mode") or "auto"),
            defer_prompts=True,
        )
        session.preload_resolution(
            prompt["fingerprint"],
            action=cast("Literal['choose', 'skip', 'manual']", action),
            payload=payload,
            chosen_volume_id=chosen_volume_id,
        )
        try:
            tags = self._first_tags(session, Path(path_str))
        except (ComicboxError, OSError) as exc:
            self._report_apply_failure(
                path_str, f"re-applying chosen match failed: {exc}"
            )
            return
        if not tags:
            self._handle_unresolved(prompt, path_str, session)
            return
        self._enqueue_resolved_write(prompt, pk, tags, path_str)

    def _handle_unresolved(
        self, prompt: dict[str, Any], path_str: str, session: OnlineSession
    ) -> None:
        """Log the dead resolution, re-queueing a fresh prompt if it drifted."""
        if self._repersist_drifted_prompt(prompt, session):
            self.log.warning(
                f"Online tag: prompt for {path_str} drifted; queued a fresh one."
            )
        else:
            self.log.warning(f"Online tag: no tags resolved for {path_str}.")

    def _enqueue_resolved_write(
        self, prompt: dict[str, Any], pk: int, tags: dict[str, Any], path_str: str
    ) -> None:
        """Queue the write for a successfully resolved prompt match."""
        write_task = BulkTagWriteTask(
            comic_pks=frozenset({pk}),
            per_comic_patches={pk: tags},
            mode="update",
            formats=tuple(prompt.get("formats") or ("COMIC_INFO",)),
            delete_original=bool(prompt.get("delete_original")),
            rename=bool(prompt.get("rename")),
        )
        self.librarian_queue.put(write_task)
        self.log.info(f"Online tag: applied resolved match for {path_str}.")

    def _repersist_drifted_prompt(
        self, prompt: dict[str, Any], session: OnlineSession
    ) -> bool:
        """
        Re-queue the prompt when the replayed search no longer matches it.

        The deferred-prompt fingerprint embeds the candidate-id set, so a
        re-search returning a different candidate list (source data changed,
        a rate-limited series dropped out) misses the preloaded resolution
        and defers a fresh prompt instead. Persist that fresh prompt — same
        comic, new fingerprint and candidates — so the admin can answer
        again instead of the click dying silently.
        """
        pk = prompt.get("pk")
        if pk is None:
            return False
        formats = tuple(prompt.get("formats") or ("COMIC_INFO",))
        delete_original = bool(prompt.get("delete_original"))
        rename = bool(prompt.get("rename"))
        new = {
            dp.fingerprint: serialize_prompt(
                dp,
                [{"pk": pk, "path": str(dp.path) if dp.path else ""}],
                formats,
                delete_original=delete_original,
                rename=rename,
            )
            for dp in session.deferred_prompts()
        }
        if not new:
            return False
        add_pending_prompts(new)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        return True

    @staticmethod
    def _first_tags(session: OnlineSession, path: Path) -> dict[str, Any] | None:
        """Return the tags from the single re-tagged comic, or None."""
        for result in session.tag_many([path]):
            # Unmatched results still carry the comic's merged existing
            # metadata; writing that would re-write the file with no new
            # information.
            if result.matched and result.tags and not result.error:
                return result.tags
            break
        return None
