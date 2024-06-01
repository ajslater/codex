"""Reader get Arcs methods."""

from types import MappingProxyType

from codex.models import AdminFlag
from codex.util import max_none
from codex.views.const import FOLDER_GROUP
from codex.views.reader.books import ReaderBooksView


class ReaderArcsView(ReaderBooksView):
    """Reader get Arcs methods."""

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self.params: MappingProxyType = MappingProxyType({})

    def _get_folder_arc(self, book):
        """Create the folder arc."""
        efv_flag = (
            AdminFlag.objects.only("on")
            .get(key=AdminFlag.FlagChoices.FOLDER_VIEW.value)
            .on
        )

        if efv_flag:
            folder = book.parent_folder
            folder_arc = {
                "group": FOLDER_GROUP,
                "pks": (folder.pk,),
                "name": folder.name,
                "mtime": folder.updated_at,
            }
        else:
            folder_arc = None
        return folder_arc

    def _get_series_arc(self, book):
        """Create the series arc."""
        series = book.series
        if series:
            arc_pks = self.get_series_pks_from_breadcrumbs()
            if book.series.pk not in arc_pks:
                arc_pks = (book.series.pk,)
            arc = (
                {
                    "group": "s",
                    "pks": arc_pks,
                    "name": series.name,
                    "mtime": series.updated_at,
                }
                if series
                else None
            )
        else:
            arc = None
        return arc

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
        folder_arc = self._get_folder_arc(book)
        series_arc = self._get_series_arc(book)

        # order top arcs
        top_group = self.params.get("top_group")
        if top_group == FOLDER_GROUP and folder_arc:
            arc = folder_arc
            other_arc = series_arc
        else:
            arc = series_arc
            other_arc = folder_arc

        arcs = []
        arcs.append(arc)
        if other_arc:
            arcs.append(other_arc)

        # story arcs
        sas = self._get_story_arcs(book)
        arcs += sas

        max_mtime = None
        for arc in arcs:
            max_mtime = max_none(max_mtime, arc["mtime"])
        return arcs, max_mtime
