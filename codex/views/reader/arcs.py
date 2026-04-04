"""Reader get Arcs methods."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.models.comic import Comic
from codex.models.functions import JsonGroupArray
from codex.models.named import StoryArc
from codex.util import max_none
from codex.views.const import (
    EPOCH_START,
    STORY_ARC_GROUP,
)
from codex.views.reader.params import ReaderParamsView

if TYPE_CHECKING:
    from collections.abc import Mapping

_COMIC_ARC_FIELD_NAMES = ("series", "volume", "parent_folder")
_STORY_ARC_ONLY = ("name", "ids", "updated_ats")
_UPDATED_ATS_DATE_FORMAT_STR = "%Y-%m-%d %H:%M:%S.%f"


class ReaderArcsView(ReaderParamsView):
    """Reader get Arcs methods."""

    def _get_field_names(self) -> tuple:
        field_names = []
        for field_name in _COMIC_ARC_FIELD_NAMES:
            if field_name == "parent_folder":
                efv_flag = (
                    AdminFlag.objects.only("on")
                    .get(key=AdminFlagChoices.FOLDER_VIEW.value)
                    .on
                )
                if not efv_flag:
                    continue
            else:
                show: Mapping = self.get_from_settings(  # pyright: ignore[reportAssignmentType]
                    "show", browser=True
                )
                group = field_name[0]
                if not show.get(group):
                    continue
            field_names.append(field_name)
        return tuple(field_names)

    @staticmethod
    def _get_group_arc(
        comic: Comic,
        field_name: str,
        arcs: dict,
        max_mtime: int | None,
    ):
        """Append the series, volume, or folder arc from the comic's own FKs."""
        group = getattr(comic, field_name)
        arc_ids = (group.pk,)
        mtime = group.updated_at
        max_mtime = max_none(max_mtime, mtime)

        group_letter = "f" if field_name == "parent_folder" else field_name[0]
        arcs[group_letter] = {arc_ids: {"name": group.name, "mtime": mtime}}
        return max_mtime

    def _get_story_arcs(self, comic: Comic, arcs, max_mtime: int | None):
        """Append the story arcs."""
        qs = StoryArc.objects.filter(storyarcnumber__comic__pk=comic.pk)
        if not qs.exists():
            return max_mtime

        qs = qs.group_by("sort_name")  # pyright: ignore[reportAttributeAccessIssue]
        qs = qs.annotate(
            ids=JsonGroupArray("id", distinct=True, order_by="id"),
            updated_ats=JsonGroupArray(
                "updated_at", distinct=True, order_by="updated_at"
            ),
        )
        qs = qs.order_by("sort_name").only("name")

        arcs[STORY_ARC_GROUP] = {}

        for sa in qs:
            arc = {"name": sa.name}
            ids = tuple(sorted(set(sa.ids)))
            updated_ats = (
                datetime.strptime(ua, _UPDATED_ATS_DATE_FORMAT_STR).replace(tzinfo=UTC)
                for ua in sa.updated_ats
            )
            mtime = max_none(EPOCH_START, *updated_ats)
            arc["mtime"] = mtime
            max_mtime = max_none(max_mtime, mtime)
            arcs[STORY_ARC_GROUP][ids] = arc
        return max_mtime

    def _set_selected_arc(self, arcs) -> None:
        arc = self.params["arc"]
        arc_group = arc["group"]
        requested_arc_ids = arc.get("ids", ())
        arc_id_infos = arcs.get(arc_group)
        all_arc_ids: frozenset[tuple[int, ...]] = (
            frozenset(arc_id_infos.keys()) if arc_id_infos else frozenset()
        )
        arc_ids = ()
        if arc_group == STORY_ARC_GROUP:
            if requested_arc_ids in all_arc_ids:
                arc_ids = requested_arc_ids
            else:
                for arc_ids in all_arc_ids:
                    if requested_arc_ids.intersection(frozenset(arc_ids)):
                        break
        if not arc_ids:
            arc_ids = next(iter(all_arc_ids))
        self._selected_arc_group = arc_group
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
            max_mtime = self._get_group_arc(comic, field_name, arcs, max_mtime)
        max_mtime = self._get_story_arcs(comic, arcs, max_mtime)
        self._set_selected_arc(arcs)
        return arcs, max_mtime
