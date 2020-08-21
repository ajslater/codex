"""Base class for the Browse Views."""
import logging

from pathlib import Path
from urllib.parse import quote

from django.http import FileResponse
from django.views.generic import FormView
from django.views.generic import ListView
from django.views.generic import View
from django.views.generic.detail import SingleObjectMixin

from codex.forms import BrowseForm
from codex.forms import FilterChoice
from codex.forms import SortChoice
from codex.library.importer import get_cover_path
from codex.models import Comic
from codex.settings import STATIC_ROOT
from codex.views.session import SessionMixin


LOG = logging.getLogger(__name__)
DEFAULT_COVER_PATH = "codex" / Path(STATIC_ROOT) / "default_cover.png"


class BrowseBaseView(FormView, ListView, SessionMixin):
    """Base class for the Browse Views."""

    template_name = "codex/browse.html"
    form_class = BrowseForm

    def quote(self, path):
        """Urlsafe quote a pathlib path."""
        return quote(str(path), safe="")

    def get_filtered_comics(self):
        """Filter the comics based on the form filters."""
        filters = self.session_get(self.BROWSE_KEY, "filters")

        # Get comics for the direct filters
        comics = Comic.objects.all().filter(deleted_at=None, root_path__deleted_at=None)
        # Apply filters
        for filter in filters:
            if filter == FilterChoice.UNREAD.name:
                read_ids = self.get_read_comic_ids()
                comics = comics.exclude(pk__in=read_ids)
            if filter == FilterChoice.IN_PROGRESS.name:
                in_progress_ids = self.get_in_progress_comic_ids()
                comics = comics.filter(pk__in=in_progress_ids)
        return comics

    def create_order_by(self):
        """Create sorting order_by list for django orm."""
        sort_by = self.session_get(self.BROWSE_KEY, "sort_by")

        if sort_by == SortChoice.DATE.name:
            order_key = "date"
        else:
            order_key = "name"

        sort_reverse = self.session_get(self.BROWSE_KEY, "sort_reverse")
        order_by = [order_key]
        if sort_reverse:
            reversed_order_by = []
            for relation in order_by:
                reversed_order_by.append("-" + relation)
            order_by = reversed_order_by
        return order_key, order_by


class BaseFileView(View):
    """Base class for returning file responses."""

    def file_response(self, path, content_type, as_attachment=False):
        """Open a file as binary and return a file response."""
        fd = open(path, "rb")
        return FileResponse(
            fd,
            content_type=content_type,
            as_attachment=as_attachment,
            filename=path.name,
        )


class ComicCoverView(BaseFileView):
    """Return the cover for the comic."""

    def get(self, request, *args, **kwargs):
        """Get the cover for a comic."""
        pk = self.kwargs.get("pk")
        if pk > 0:
            cover_path = get_cover_path(pk)
        else:
            cover_path = DEFAULT_COVER_PATH
        return self.file_response(cover_path, "image/jpeg")


class ComicDownloadView(BaseFileView, SingleObjectMixin):
    """Return the comic archive file as an attachment."""

    model = Comic

    def get(self, request, *args, **kwargs):
        """Download a comic archive."""
        comic = self.get_object()
        path = Path(comic.path)
        suffix = path.suffix
        if suffix == ".cbr":
            mime_type = "application/vnd.comicbook-rar"
        else:
            mime_type = "application/vnd.comicbook+zip"

        return self.file_response(path, mime_type, as_attachment=True)
