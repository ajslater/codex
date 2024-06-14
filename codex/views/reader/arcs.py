"""Reader get Arcs methods."""

from types import MappingProxyType

from codex.models import AdminFlag
from codex.util import max_none
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP
from codex.views.reader.books import ReaderBooksView


class ReaderArcsView(ReaderBooksView):
    """Reader get Arcs methods."""

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self.params: MappingProxyType = MappingProxyType({})

    def _get_group_arc(self, book, attr):
        """Create the volume arc."""
        group = getattr(book, attr, None)
        if not group:
            return None

        _, arc_pks = self.get_group_pks_from_breadcrumbs([group])
        if group.pk not in arc_pks:
            arc_pks = (group.pk,)
        return {
            "group": attr[0],
            "pks": arc_pks,
            "name": group.name,
            "mtime": group.updated_at,
        }

    def _get_folder_arc(self, book):
        """Create the folder arc."""
        efv_flag = (
            AdminFlag.objects.only("on")
            .get(key=AdminFlag.FlagChoices.FOLDER_VIEW.value)
            .on
        )
        if not efv_flag:
            return None

        folder = book.parent_folder
        return {
            "group": FOLDER_GROUP,
            "pks": (folder.pk,),
            "name": folder.name,
            "mtime": folder.updated_at,
        }

    def _get_story_arcs(self, book):
        """Create story arcs."""
        sas = []
        for san in book.story_arc_numbers.all():
            sa = san.story_arc
            arc = {
                "group": "a",
                "pks": (sa.pk,),
                "name": sa.name,
                "mtime": sa.updated_at,
            }
            sas.append(arc)
        return sorted(sas, key=lambda x: x["name"])

    def get_arcs(self, book):
        """Get all series/folder/story arcs."""
        # create top arcs
        arcs = []
        top_group = self.params.get("top_group")
        arc = None
        if series_arc := self._get_group_arc(book, "series"):
            arcs.append(series_arc)
            arc = series_arc
        if volume_arc := self._get_group_arc(book, "volume"):
            arcs.append(volume_arc)
            if not arc:
                arc = volume_arc
        if folder_arc := self._get_folder_arc(book):
            arcs.append(folder_arc)
            if top_group == FOLDER_GROUP:
                arc = folder_arc
        if story_arcs := self._get_story_arcs(book):
            arcs = [*arcs, *story_arcs]
            if top_group == STORY_ARC_GROUP:
                arc = story_arcs[0]

        max_mtime = None
        for arc in arcs:
            max_mtime = max_none(max_mtime, arc["mtime"])
        return arcs, max_mtime
