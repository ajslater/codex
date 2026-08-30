"""Reader get Arcs methods."""

from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING

from django.db.models import Max, Q

from codex.choices.admin import AdminFlagChoices
from codex.collection import READER_REPRINT_COLLECTION, Collection
from codex.models import AdminFlag
from codex.models.comic import Comic
from codex.models.functions import JsonGroupArray
from codex.models.named import Reprint, StoryArc
from codex.util import max_none
from codex.views.const import (
    STORY_ARC_COLLECTION,
)
from codex.views.reader.params import ReaderParamsView

if TYPE_CHECKING:
    from collections.abc import Mapping

# Comic FK attribute → the browse collection it represents as a reader arc.
# Drives both the ``show`` gate and the ``arcs`` dict key (collection-valued).
_COMIC_ARC_FIELD_COLLECTIONS = MappingProxyType(
    {
        "series": Collection.SERIES,
        "volume": Collection.VOLUME,
        "parent_folder": Collection.FOLDER,
    }
)
_COMIC_ARC_FIELD_NAMES = tuple(_COMIC_ARC_FIELD_COLLECTIONS)

# Arc collections whose rows are groups rather than a single row, so the
# requested ids may be a stale subset of the current group. Both story
# arcs (grouped by sort_name) and alternate series (grouped by identity)
# accept an intersecting id set as the same arc.
_MULTI_ROW_ARC_COLLECTIONS = frozenset(
    {STORY_ARC_COLLECTION, READER_REPRINT_COLLECTION}
)

# Preference order when the requested arc collection has no arc for this
# comic. Series first: it's the reader's default reading order.
_ARC_COLLECTION_FALLBACK_ORDER = (
    Collection.SERIES,
    Collection.VOLUME,
    Collection.FOLDER,
    STORY_ARC_COLLECTION,
    READER_REPRINT_COLLECTION,
)


class ReaderArcsView(ReaderParamsView):
    """Reader get Arcs methods."""

    def _get_field_names(self) -> tuple:
        # Hoist the per-iteration settings + admin-flag reads outside
        # the loop. Pre-fix: 2 SettingsBrowser queries (one per non-folder
        # iteration) + 1 AdminFlag query. Post-fix: 1 SettingsBrowser
        # query + 1 AdminFlag query (sub-plan 01 #5 / #2).
        show: Mapping = self.get_from_settings("show", browser=True) or {}
        folder_view_allowed: bool = self._reader_folder_view_enabled
        field_names = []
        for field_name, collection in _COMIC_ARC_FIELD_COLLECTIONS.items():
            if field_name == "parent_folder":
                if not folder_view_allowed:
                    continue
            elif not show.get(collection):
                # ``show`` is keyed by collection name now (publishers/…);
                # ``collection`` is the matching ``Collection`` member.
                continue
            field_names.append(field_name)
        return tuple(field_names)

    @cached_property
    def _reader_folder_view_enabled(self) -> bool:
        """
        Per-request cache of the ``folder_view`` admin flag.

        The reader chain doesn't inherit ``SearchFilterView`` (the
        browser/OPDS chain's ``self.admin_flags`` source) — see the
        reader plan's sub-plan 01 #2. A local ``@cached_property`` is
        the smallest equivalent: subsequent accesses within the same
        request are dict lookups, and cachalot still caches the
        underlying SQL across requests.
        """
        return (
            AdminFlag.objects.only("on").get(key=AdminFlagChoices.FOLDER_VIEW.value).on
        )

    @staticmethod
    def _get_collection_arc(
        comic: Comic,
        field_name: str,
        arcs: dict,
        max_mtime: int | None,
    ):
        """Append the series, volume, or folder arc from the comic's own FKs."""
        collection = getattr(comic, field_name)
        arc_ids = (collection.pk,)
        mtime = collection.updated_at
        max_mtime = max_none(max_mtime, mtime)

        arc_collection = _COMIC_ARC_FIELD_COLLECTIONS[field_name]
        arcs[arc_collection] = {arc_ids: {"name": collection.name, "mtime": mtime}}
        return max_mtime

    def _get_story_arcs(self, comic: Comic, arcs, max_mtime: int | None):
        """Append the story arcs."""
        qs = StoryArc.objects.filter(storyarcnumber__comic__pk=comic.pk)
        if not qs.exists():
            return max_mtime

        # ``Max("updated_at")`` returns a single typed datetime per arc
        # via the field's ``from_db_value`` hook — replaces the prior
        # ``JsonGroupArray("updated_at")`` + per-row Python ``strptime``
        # loop (sub-plan 01 #4 / Tier 3 #8). SQLite stores datetimes as
        # ISO strings, so any aggregate that yields a typed datetime
        # bypasses the manual parse.
        qs = qs.group_by("sort_name")  # pyright: ignore[reportAttributeAccessIssue]
        qs = qs.annotate(
            ids=JsonGroupArray("id", distinct=True, order_by="id"),
            mtime=Max("updated_at"),
        )
        qs = qs.order_by("sort_name").only("name")

        arcs[STORY_ARC_COLLECTION] = {}

        for sa in qs:
            ids = tuple(sorted(set(sa.ids)))
            mtime = sa.mtime
            arcs[STORY_ARC_COLLECTION][ids] = {"name": sa.name, "mtime": mtime}
            max_mtime = max_none(max_mtime, mtime)
        return max_mtime

    def _get_reprint_arcs(self, comic: Comic, arcs, max_mtime: int | None):
        """Append the alternate series (ComicInfo AlternateSeries) arcs."""
        # An alternate series is identified by everything but the issue —
        # that's ``Reprint``'s unique key minus ``issue``. Splitting on
        # volume and language keeps a v1 and a v2, or an English and a
        # Spanish edition, from merging into one reading order.
        identities = tuple(
            Reprint.objects.filter(comic__pk=comic.pk)
            .values_list("series_name", "volume_number", "language")
            .distinct()
        )
        if not identities:
            return max_mtime

        identity_filter = Q()
        for series_name, volume_number, language in identities:
            identity_filter |= Q(
                series_name=series_name,
                volume_number=volume_number,
                language=language,
            )

        # Every issue of an alternate series is its own ``Reprint`` row, so
        # the arc handle has to be the whole group's pks, not just this
        # comic's. Keying on one comic's row would make the *next* book
        # report a different id set and silently drop the reading order.
        qs = Reprint.objects.filter(identity_filter)
        qs = qs.group_by("series_name", "volume_number", "language")  # pyright: ignore[reportAttributeAccessIssue]
        qs = qs.annotate(
            ids=JsonGroupArray("id", distinct=True, order_by="id"),
            mtime=Max("updated_at"),
        )
        qs = qs.order_by("series_name", "volume_number", "language")

        arcs[READER_REPRINT_COLLECTION] = {}
        for reprint in qs:
            ids = tuple(sorted(set(reprint.ids)))
            mtime = reprint.mtime
            name = Reprint.compose_name(
                reprint.series_name, reprint.volume_number, "", reprint.language
            )
            arcs[READER_REPRINT_COLLECTION][ids] = {"name": name, "mtime": mtime}
            max_mtime = max_none(max_mtime, mtime)
        return max_mtime

    @staticmethod
    def _fallback_arc_collection(arcs) -> str:
        """Pick a collection this comic actually has an arc for."""
        # The requested collection can be valid yet absent for this comic
        # (an alternate series the comic isn't in, a story arc it lost on
        # re-tag). Reading must still work, so fall back to the most
        # series-like arc available instead of raising.
        for collection in _ARC_COLLECTION_FALLBACK_ORDER:
            if arcs.get(collection):
                return collection
        return next(iter(arcs), "")

    def _set_selected_arc(self, arcs) -> None:
        arc = self.params["arc"]
        arc_collection = arc["collection"]
        requested_arc_ids = arc.get("ids", ())
        if not arcs.get(arc_collection):
            arc_collection = self._fallback_arc_collection(arcs)
        arc_id_infos = arcs.get(arc_collection)
        all_arc_ids: frozenset[tuple[int, ...]] = (
            frozenset(arc_id_infos.keys()) if arc_id_infos else frozenset()
        )
        arc_ids = ()
        if arc_collection in _MULTI_ROW_ARC_COLLECTIONS:
            if requested_arc_ids in all_arc_ids:
                arc_ids = requested_arc_ids
            else:
                # Pre-build the frozenset cast for each candidate once,
                # outside the per-iteration intersection compute (sub-plan 01 #6).
                requested_set = frozenset(requested_arc_ids)
                for candidate in all_arc_ids:
                    if requested_set.intersection(candidate):
                        arc_ids = candidate
                        break
        if not arc_ids and all_arc_ids:
            arc_ids = next(iter(all_arc_ids))
        self._selected_arc_collection = arc_collection
        self._selected_arc_ids = arc_ids

    def get_arcs(self) -> tuple[dict, int | None]:
        """Get all series/folder/story arcs."""
        field_names = self._get_field_names()
        comic_pk = self.kwargs.get("pk")
        comic = (
            Comic.objects.select_related(*field_names)
            .only(*field_names)
            .get(pk=comic_pk)
        )

        arcs = {}
        max_mtime = None
        for field_name in field_names:
            max_mtime = self._get_collection_arc(comic, field_name, arcs, max_mtime)
        max_mtime = self._get_story_arcs(comic, arcs, max_mtime)
        max_mtime = self._get_reprint_arcs(comic, arcs, max_mtime)
        self._set_selected_arc(arcs)
        return arcs, max_mtime
