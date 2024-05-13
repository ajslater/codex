"""Views for reading comic books."""

from copy import deepcopy
from types import MappingProxyType

from comicbox.box import Comicbox
from django.db.models import F, IntegerField, Value
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from codex.librarian.importer.tasks import LazyImportComicsTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.models import AdminFlag, Bookmark, Comic
from codex.serializers.reader import ReaderArcSerializer, ReaderComicsSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.views.bookmark import BookmarkBaseView
from codex.views.mixins import SharedAnnotationsMixin
from codex.views.session import BrowserSessionViewBase

LOG = get_logger(__name__)


_MIN_CRUMB_WALKBACK_LEN = 3


class ReaderView(
    BookmarkBaseView,
    BrowserSessionViewBase,
    SharedAnnotationsMixin,
):
    """Get info for displaying comic pages."""

    serializer_class = ReaderComicsSerializer
    input_serializer_class = ReaderArcSerializer

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
    TARGET = "reader"

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self.series_pks: tuple[int, ...] = ()

    def _get_series_pks_from_breadcrumbs(self):
        """Get Multi-Group pks from the breadcrumbs."""
        if self.series_pks:
            return self.series_pks
        breadcrumbs = self.get_from_session("breadcrumbs")
        if breadcrumbs:
            crumb = breadcrumbs[-1]
            crumb_group = crumb.get("group")
            if crumb_group == "v" and len(breadcrumbs) >= _MIN_CRUMB_WALKBACK_LEN:
                crumb = breadcrumbs[-2]
                crumb_group = crumb.get("group")
            if crumb_group == "s":
                self.series_pks = crumb.get("pks", ())

        return self.series_pks

    def _get_reader_arc_pks(
        self, arc, arc_pk_select_related, prefetch_related, arc_pk_rel
    ):
        """Get the nav filter."""
        arc_pks = arc.get("pks", ())
        if not arc_pks:
            comic_pk = self.kwargs["pk"]
            try:
                arc_pk_qs = Comic.objects.filter(pk=comic_pk)
                arc_pk_qs = arc_pk_qs.select_related(*arc_pk_select_related)
                arc_pk_qs = arc_pk_qs.prefetch_related(*prefetch_related)
                arc_pk = arc_pk_qs.values_list(arc_pk_rel, flat=True)[0]
            except IndexError:
                arc_pk = 0

            if arc_pk_rel == "series__pk":
                multi_arc_pks = self._get_series_pks_from_breadcrumbs()
                if not arc_pk or arc_pk in multi_arc_pks:
                    arc_pks = multi_arc_pks
            if not arc_pks:
                arc_pks = (arc_pk,)

        return arc_pks

    def _get_comics_list(self):
        """Get the reader naviation group filter."""
        select_related = ("series", "volume")
        prefetch_related = ()

        arc = self.params.get("arc", {})

        arc_group = arc.get("group", "s")
        if arc_group == "a":
            # for story arcs
            rel = "story_arc_numbers__story_arc"
            fields = self._COMIC_FIELDS
            arc_pk_rel = "story_arc_numbers__story_arc__pk"
            prefetch_related = (*prefetch_related, "story_arc_numbers__story_arc")
            arc_index = F("story_arc_numbers__number")
            ordering = ("arc_index", "date")
            arc_pk_select_related = ()
        elif arc_group == self.FOLDER_GROUP:
            # folder mode
            rel = "parent_folder"
            fields = (*self._COMIC_FIELDS, "parent_folder")
            arc_pk_rel = "parent_folder__pk"
            select_related = (*select_related, "parent_folder")
            arc_index = Value(None, IntegerField())
            ordering = ("path", "pk")
            arc_pk_select_related = ("parent_folder",)
        else:
            # browser mode.
            rel = "series"
            fields = self._COMIC_FIELDS
            arc_pk_rel = "series__pk"
            arc_index = Value(None, IntegerField())
            ordering = ()
            arc_pk_select_related = ("series",)

        arc_pks = self._get_reader_arc_pks(
            arc,
            arc_pk_select_related,
            prefetch_related,
            arc_pk_rel,
        )
        nav_filter = {f"{rel}__in": arc_pks}
        group_acl_filter = self.get_group_acl_filter(Comic)

        qs = (
            Comic.objects.filter(group_acl_filter)
            .filter(**nav_filter)
            .select_related(*select_related)
            .prefetch_related(*prefetch_related)
            .only(*fields)
            .annotate(
                issue_count=F("volume__issue_count"),
            )
            .annotate(
                arc_pk=F(arc_pk_rel),
                arc_index=arc_index,
            )
            .annotate(mtime=F("updated_at"))
        )
        qs = self.annotate_group_names(qs, Comic)
        if arc_group == "s":
            show = deepcopy(self.get_from_session("show"))
            show.pop("p", None)
            show.pop("i", None)
            qs, comic_sort_names = self.alias_sort_names(
                qs, Comic, pks=arc_pks, model_group="i", show=show
            )
            ordering = (
                *comic_sort_names,
                "issue_number",
                "issue_suffix",
                "sort_name",
            )
        return qs.order_by(*ordering), arc_group

    def _append_with_settings(self, book, bookmark_filter):
        """Append bookmark to book list."""
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
        comics, arc_group = self._get_comics_list()
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
                book.filename = book.get_filename()  # type: ignore
                book.arc_group = arc_group
                book.arc_count = comics.count()
                books["current"] = self._append_with_settings(book, bookmark_filter)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book
        return books

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
                "group": self.FOLDER_GROUP,
                "pks": (folder.pk,),
                "name": folder.name,
            }
        else:
            folder_arc = None
        return folder_arc

    def _get_series_arc(self, book):
        """Create the series arc."""
        series = book.series
        if series:
            arc_pks = self._get_series_pks_from_breadcrumbs()
            if book.series.pk not in arc_pks:
                arc_pks = (book.series.pk,)
            arc = (
                {"group": "s", "pks": arc_pks, "name": series.name} if series else None
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
            }
            sas.append(arc)
        return sorted(sas, key=lambda x: x["name"])

    def _get_arcs(self, book):
        """Get all series/folder/story arcs."""
        # create top arcs
        folder_arc = self._get_folder_arc(book)
        series_arc = self._get_series_arc(book)

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
        sas = self._get_story_arcs(book)
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

    @staticmethod
    def _lazy_metadata(current, prev_book, next_book):
        """Get reader metadata from comicbox if it's not in the db."""
        import_pks = set()
        if current and not (current.page_count and current.file_type):
            with Comicbox(current.path) as cb:
                current.file_type = cb.get_file_type()
                current.page_count = cb.get_page_count()
            import_pks.add(current.pk)

        if prev_book and not prev_book.page_count:
            with Comicbox(prev_book.path) as cb:
                prev_book.page_count = cb.get_page_count()
            import_pks.add(prev_book.pk)

        if next_book and not next_book.page_count:
            with Comicbox(next_book.path) as cb:
                next_book.page_count = cb.get_page_count()
            import_pks.add(next_book.pk)

        if import_pks:
            task = LazyImportComicsTask(frozenset(import_pks))
            LIBRARIAN_QUEUE.put(task)

    def get_object(self):
        """Get the previous and next comics in a group or story arc."""
        # Books
        self.last_route = self.get_last_route()
        books = self._get_book_collection()

        current = books.get("current")
        if not current:
            self._raise_not_found()

        prev_book = books.get("prev")
        next_book = books.get("next")
        self._lazy_metadata(current, prev_book, next_book)

        books = {
            "current": current,
            "prev_book": prev_book,
            "next_book": next_book,
        }

        # Arcs
        arcs = self._get_arcs(current)

        arc = self.params.get("arc", {})
        if not arc.get("group"):
            arc["group"] = current.arc_group  # type: ignore
        if not arc.get("pks"):
            arc["pks"] = (current.arc_pk,)  # type: ignore
        arc["index"] = current.arc_index  # type:ignore
        arc["count"] = current.arc_count  # type: ignore
        close_route = self.last_route
        close_route.pop("name", None)

        return {"books": books, "arcs": arcs, "arc": arc, "close_route": close_route}

    def _parse_params(self):
        data = self.request.GET
        # Hack for query_parm parser
        arc_data = MappingProxyType(
            {"group": data.get("arc[group]"), "pks": data.get("arc[pks]")}
        )
        serializer = self.input_serializer_class(data=arc_data)
        arc = {}
        try:
            serializer.is_valid()
            arc = serializer.validated_data
        except ValidationError:
            pass

        # PARAMS
        session = self.request.session.get(BrowserSessionViewBase.SESSION_KEY, {})
        top_group = session.get("top_group", "s")

        # arc.group validation
        # Can't be in the serializer
        arc_group = arc.get("group", "")
        if not arc_group:
            series_pks = self._get_series_pks_from_breadcrumbs()
            if series_pks:
                arc_group = "s"
                arc["pks"] = series_pks
        if not arc_group:
            arc_group = top_group
        if arc_group not in self._VALID_ARC_GROUPS:
            arc_group = None

        params = MappingProxyType(
            {
                "arc": arc,
                "top_group": top_group,
            }
        )
        self.params = params

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "arc[group]", OpenApiTypes.STR, enum=sorted(_VALID_ARC_GROUPS)
            ),
            OpenApiParameter("arc[pks]", OpenApiTypes.STR),
        ]
    )
    def get(self, *args, **kwargs):
        """Get the book info."""
        self._parse_params()
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
