"""Reader get Arcs methods."""

from codex.models import AdminFlag
from codex.util import max_none
from codex.views.const import (
    FOLDER_GROUP,
    STORY_ARC_GROUP,
)
from codex.views.reader.books import ReaderBooksView


class ReaderArcsView(ReaderBooksView):
    """Reader get Arcs methods."""

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)

    def _get_group_arc(self, book, attr, browser_arc_group, arcs, max_mtime):
        """Append the volume arc."""
        if browser_arc_group == attr[0]:
            return max_mtime
        group = getattr(book, attr, None)
        if not group:
            return max_mtime

        _, arc_pks = self.get_group_pks_from_breadcrumbs([group])
        if group.pk not in arc_pks:
            arc_pks = (group.pk,)
        arcs.append(
            {
                "group": attr[0],
                "pks": arc_pks,
                "name": group.name,
                "mtime": group.updated_at,
            }
        )
        return max_none(max_mtime, group.updated_at)

    def _get_folder_arc(self, book, browser_arc_group, arcs, max_mtime):
        """Append the folder arc."""
        efv_flag = (
            AdminFlag.objects.only("on")
            .get(key=AdminFlag.FlagChoices.FOLDER_VIEW.value)
            .on
        )
        if not efv_flag or browser_arc_group == FOLDER_GROUP:
            return max_mtime

        folder = book.parent_folder
        arcs.append(
            {
                "group": FOLDER_GROUP,
                "pks": (folder.pk,),
                "name": folder.name,
                "mtime": folder.updated_at,
            }
        )
        return max_none(max_mtime, folder.updated_at)

    def _get_story_arcs(self, book, browser_arc, arcs, max_mtime):
        """Append the story arcs."""
        if browser_arc.get("group") == STORY_ARC_GROUP:
            browser_arc_pks = frozenset(browser_arc.get("pks", ()))
        else:
            browser_arc_pks = frozenset()

        for san in book.story_arc_numbers.all().order_by("story_arc__name"):
            sa = san.story_arc
            if not browser_arc_pks or sa.pk not in browser_arc_pks:
                arc = {
                    "group": "a",
                    "pks": (sa.pk,),
                    "name": sa.name,
                    "mtime": sa.updated_at,
                }
                arcs.append(arc)
                max_mtime = max_none(max_mtime, sa.updated_at)
        return max_mtime

    def get_arcs(self, book):
        """Get all series/folder/story arcs."""
        arcs = []
        max_mtime = None

        if browser_arc := self.params.get("browser_arc", {}):
            arcs.append(browser_arc)
            browser_arc_mtime = browser_arc.get("mtime")
            max_mtime = max_none(max_mtime, browser_arc_mtime)

        browser_arc_group = browser_arc.get("group", "")
        max_mtime = self._get_group_arc(
            book, "series", browser_arc_group, arcs, max_mtime
        )
        max_mtime = self._get_group_arc(
            book, "volume", browser_arc_group, arcs, max_mtime
        )
        max_mtime = self._get_folder_arc(book, browser_arc_group, arcs, max_mtime)
        max_mtime = self._get_story_arcs(book, browser_arc, arcs, max_mtime)

        return arcs, max_mtime
