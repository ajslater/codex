"""Views for reading comic books."""

from django.db.models import F, IntegerField, Value
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import AdminFlag, Bookmark, Comic
from codex.serializers.reader import ReaderComicsSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.views.bookmark import BookmarkBaseView
from codex.views.session import BrowserSessionViewBase

LOG = get_logger(__name__)


class ReaderView(BookmarkBaseView):
    """Get info for displaying comic pages."""

    serializer_class = ReaderComicsSerializer

    SETTINGS_ATTRS = ("fit_to", "two_pages", "reading_direction")
    _COMIC_FIELDS = (
        "file_type",
        "issue_number",
        "issue_suffix",
        "page_count",
        "series",
        "volume",
        "reading_direction",
        "updated_at",
    )
    _VALID_ARC_GROUPS = frozenset({"f", "s", "a"})

    def _get_comics_list(self):
        """Get the reader naviation group filter."""
        arc_group = self.params.get("arc_group")

        if arc_group == "a":
            # for story arcs
            rel = "story_arc_numbers__story_arc"
            fields = self._COMIC_FIELDS
            arc_name_rel = "story_arc_numbers__story_arc__name"
            arc_pk_rel = "story_arc_numbers__story_arc__pk"
            arc_index = F("story_arc_numbers__number")
            ordering = ("arc_index", "date", *Comic.ORDERING)
        elif arc_group == self.FOLDER_GROUP:
            # folder mode
            rel = "parent_folder"
            fields = (*self._COMIC_FIELDS, "parent_folder")
            arc_pk_rel = "parent_folder__pk"
            arc_name_rel = "parent_folder__name"
            arc_index = Value(None, IntegerField())
            ordering = ("path", "pk")
        else:
            # browser mode.
            rel = "series"
            fields = self._COMIC_FIELDS
            arc_pk_rel = "series__pk"
            arc_name_rel = "series__name"
            arc_index = Value(None, IntegerField())
            ordering = Comic.ORDERING

        group_acl_filter = self.get_group_acl_filter(Comic)
        arc_pk = self.params.get("arc_pk")
        if not arc_pk:
            rel += "__comic"
            arc_pk = self.kwargs.get("pk")
        nav_filter = {rel: arc_pk}

        qs = (
            Comic.objects.filter(group_acl_filter)
            .filter(**nav_filter)
            .prefetch_related("story_arc_numbers__story_arc")
            .only(*fields)
            .annotate(
                series_name=F("series__name"),
                volume_name=F("volume__name"),
                issue_count=F("volume__issue_count"),
            )
            .annotate(
                arc_pk=F(arc_pk_rel),
                arc_name=F(arc_name_rel),
                arc_index=arc_index,
            )
            .annotate(mtime=F("updated_at"))
        )

        return qs.order_by(*ordering)

    def _append_with_settings(self, book, bookmark_filter):
        """Get bookmarks and filename and append to book list."""
        book.settings = (
            Bookmark.objects.filter(**bookmark_filter, comic=book)
            .only(*self.SETTINGS_ATTRS)
            .first()
        )
        return book

    def _get_book_collection(self):
        """Get the -1, +1 window around the current issue.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.

        Yields 1 to 3 books
        """
        comics = self._get_comics_list()
        bookmark_filter = self.get_bookmark_filter()
        books = {}
        prev_book = None
        pk = self.kwargs.get("pk")
        for index, book in enumerate(comics):
            if books:
                # after match set next comic and break
                books["next"] = self._append_with_settings(book, bookmark_filter)
                break
            if book.pk == pk:
                # first match. set previous and current comic
                if prev_book:
                    books["prev"] = self._append_with_settings(
                        prev_book, bookmark_filter
                    )
                # create extra current book attrs:
                if book.arc_index is None:  # type: ignore
                    book.arc_index = index + 1  # type: ignore
                book.filename = book.filename()  # type: ignore

                books["current"] = self._append_with_settings(book, bookmark_filter)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book
        return books, comics.count()

    def _get_folder_arc(self, book):
        """Create the folder arc."""
        efv_flag = (
            AdminFlag.objects.only("on")
            .get(key=AdminFlag.FlagChoices.FOLDER_VIEW.value)
            .on
        )

        if efv_flag:
            folder_arc = {
                "group": self.FOLDER_GROUP,
                "pk": book.parent_folder.pk,
                "name": book.parent_folder.name,
            }
        else:
            folder_arc = None
        return folder_arc

    def _get_arcs(self, book):
        """Get all series/folder/story arcs."""
        # create top arcs
        folder_arc = self._get_folder_arc(book)
        series_arc = {"group": "s", "pk": book.series.pk, "name": book.series.name}

        # order top arcs
        top_group = self.params.get("top_group")
        if top_group == self.FOLDER_GROUP and folder_arc:
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
        sas = []
        for san in book.story_arc_numbers.all():
            sa = san.story_arc
            arc = {
                "group": "a",
                "pk": sa.pk,
                "name": sa.name,
            }
            sas.append(arc)
        sas = sorted(sas, key=lambda x: x["name"])
        arcs += sas
        return arcs

    def _raise_not_found(self):
        """Raise not found exception."""
        pk = self.kwargs.get("pk")
        detail = {
            "route": reverse("app:start"),
            "reason": f"comic {pk} not found",
            "serializer": ReaderRedirectSerializer,
        }
        raise NotFound(detail=detail)

    def get_object(self):
        """Get the previous and next comics in a group or story arc."""
        # Books
        books, arc_count = self._get_book_collection()

        current = books.get("current")
        if not current:
            self._raise_not_found()

        prev_book = books.get("prev")
        next_book = books.get("next")
        books = {
            "current": current,
            "prev_book": prev_book,
            "next_book": next_book,
        }

        # Arcs
        arcs = self._get_arcs(current)

        arc_group = self.params.get("arc_group")
        arc = {
            "group": arc_group,
            "pk": current.arc_pk,  # type: ignore
            "index": current.arc_index,  # type: ignore
            "count": arc_count,
        }

        return {
            "books": books,
            "arcs": arcs,
            "arc": arc,
        }

    def _parse_params(self):
        data = self.request.GET

        # PARAMS
        session = self.request.session.get(BrowserSessionViewBase.SESSION_KEY, {})
        top_group = session.get("top_group", "s")
        arc_group = data.get("arcGroup")
        if not arc_group:
            arc_group = top_group

        if arc_group not in self._VALID_ARC_GROUPS:
            arc_group = "s"

        arc_pk = data.get("arcPk")
        if arc_pk is not None:
            arc_pk = int(arc_pk)
        elif top_group == "a":
            last_route = session.get("route", {})
            arc_pk = last_route.get("pk")

        params = {
            "arc_group": arc_group,
            "arc_pk": arc_pk,
            "top_group": top_group,
        }
        self.params = params

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "arcGroup", OpenApiTypes.STR, enum=sorted(_VALID_ARC_GROUPS)
            ),
            OpenApiParameter("arcPk", OpenApiTypes.INT),
        ]
    )
    def get(self, *args, **kwargs):
        """Get the book info."""
        self._parse_params()
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
