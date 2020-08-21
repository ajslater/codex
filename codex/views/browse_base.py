"""Base class for the Browse Views."""
import logging

from copy import deepcopy
from decimal import Decimal

from django.db.models import Case
from django.db.models import Count
from django.db.models import DecimalField
from django.db.models import F
from django.db.models import FilteredRelation
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import Subquery
from django.db.models import Sum
from django.db.models import Value
from django.db.models import When
from django.http import FileResponse
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView
from django.views.generic import ListView
from django.views.generic import View
from django.views.generic.detail import SingleObjectMixin

from codex.forms import BookmarkFilterChoice
from codex.forms import BookmarkFiltersForm
from codex.forms import BrowseCharacterFilterForm
from codex.forms import BrowseDecadeFilterForm
from codex.forms import BrowseForm
from codex.forms import BrowseGroupForm
from codex.forms import BrowseSortForm
from codex.forms import MarkReadForm
from codex.forms import SortChoice
from codex.models import Comic
from codex.views.session import SessionMixin


LOG = logging.getLogger(__name__)


class BrowseBaseView(FormView, ListView, SessionMixin):
    """Base class for the Browse Views."""

    template_name = "codex/browse.html"
    form_class = BrowseForm
    paginate_by = 21

    def get_unique_name(self, root_path_id, name):
        """
        If an object has a name collision, number it.

        Folder view has a mashed up root folder of many root_paths
        to protect the anonymity of the actual filesystem.
        """
        if self.kwargs.get("pk") is None and name in self.root_view_names:
            name += f" ({root_path_id})"
        self.root_view_names.add(name)
        return name

    def get_userbookmark_filter(self, model_type):
        """Get a filter for my session or user defined bookmarks."""
        if model_type == Comic:
            # This is becuase I use FilteredRelation below
            rel_to_ub = ""
        else:
            rel_to_ub = "comic__"
        rel_to_ub += "userbookmark"

        if self.request.user.is_authenticated:
            my_bookmarks_kwargs = {f"{rel_to_ub}__user": self.request.user}
        else:
            my_bookmarks_kwargs = {
                f"{rel_to_ub}__session__session_key": self.request.session.session_key
            }
        return Q(**my_bookmarks_kwargs)

    def filter_by_bookmark(self, comics):
        """Build bookmark query."""
        bookmark_filter = self.browse_session.get("bookmark_filter", None)
        if bookmark_filter == BookmarkFilterChoice.UNREAD.name:
            comics = comics.exclude(self.ub_filter, userbookmark__finished=True)
        elif bookmark_filter == BookmarkFilterChoice.IN_PROGRESS.name:
            comics = comics.filter(
                self.ub_filter,
                userbookmark__bookmark__gt=0,
                userbookmark__finished=False,
            )
        return comics

    def filter_by_decade(self, comics):
        """
        Buld decade query.

        This query is complicated because integer forms bollox up nulls
        with empty strings, so i gotta use -1 and also you can't search
        for null in an __in filter.
        """
        decades = self.browse_session.get("decade_filter")
        if decades:
            valid_decades = []
            nullq = False
            for decade in decades:
                # Special code for null due to django form weirdness.
                if decade == "-1":
                    nullq = Q(decade__isnull=True)
                else:
                    valid_decades.append(decade)

            if valid_decades:
                vdq = Q(decade__in=valid_decades)
                if nullq:
                    comics = comics.filter(vdq | nullq)
                else:
                    comics = comics.filter(vdq)
            elif nullq:
                comics = comics.filter(nullq)
        return comics

    def filter_by_character(self, comics):
        """Build character query."""
        characters = self.browse_session.get("character_filter")
        if characters:
            comics = comics.filter(characters__in=characters)
        return comics

    def get_filtered_comics(self):
        """Filter the comics based on the form filters."""
        comics = Comic.objects.all()
        self.ub_filter = self.get_userbookmark_filter(None)

        comics = self.filter_by_bookmark(comics)
        comics = self.filter_by_decade(comics)
        comics = self.filter_by_character(comics)

        return comics

    def create_order_by(self):
        """Create sorting order_by list for django orm."""
        sort_by = self.browse_session.get("sort_by")
        if hasattr(SortChoice, sort_by):
            order_key = sort_by
        else:
            order_key = "sort_name"
        sort_reverse = self.browse_session.get("sort_reverse")
        if sort_reverse:
            order_by = "-" + order_key
        else:
            order_by = order_key
        return order_key, order_by

    def annotate_object_list(self, obj_list, comics, model_type):
        """Add annotations for the view and sorting."""
        if model_type == Comic:
            # Bookmark Prefences
            ub_filter = self.get_userbookmark_filter(model_type)
            obj_list = obj_list.annotate(
                my_bookmark=FilteredRelation("userbookmark", condition=ub_filter)
            )
            obj_list = obj_list.annotate(
                fit_to=F("my_bookmark__fit_to"),
                two_pages=F("my_bookmark__two_pages"),
                finished=F("my_bookmark__finished"),
            )
        else:
            # Count children
            child_count = Count("comic__pk", distinct=True, filter=Q(comic__in=comics))
            obj_list = obj_list.annotate(child_count=child_count).filter(
                child_count__gt=0
            )

            # Cover Path
            cover_path_subquery = Subquery(comics.values("cover_path")[:1])
            obj_list = obj_list.annotate(cover_path=cover_path_subquery)

            # Total page_count of children
            page_count = Sum("comic__page_count", filter=Q(comic__in=comics))
            obj_list = obj_list.annotate(page_count=page_count)

        # Pages read
        pages_read = Sum(f"comic__userbookmark__bookmark", filter=self.ub_filter)
        obj_list = obj_list.annotate(pages_read=pages_read)

        # Annotate progress
        obj_list = obj_list.annotate(
            progress=Case(
                When(pages_read=None, then=Value(0)),
                default=F("pages_read") * Decimal("1.0") / F("page_count") * 100,
                output_field=DecimalField(),
            )
        )

        # TODO it might be nice to add get_unique_name here for
        # duplicate comics or folders.
        # obj.root_path.id but only if we can use a set in the
        # template

        return obj_list

    def annotate_and_sort_object_list(self, obj_list, comics, model_type):
        """
        Sort the final object list adding many annotations.

        model_type is neccissary because this gets called twice by folder
        view. once for the comics.
        """
        # Select comics for the children by an outer ref for annotation
        comics_outer_ref = {model_type.__name__.lower(): OuterRef("pk")}
        comics = comics.filter(**comics_outer_ref)
        # Order the decendent comics by the sort argumentst
        comics_order_key, comics_order_by = self.create_order_by()
        comics = comics.order_by(comics_order_by)

        obj_list = self.annotate_object_list(obj_list, comics, model_type)

        # Special sorting annotation for non-name sorting.
        obj_order_key = comics_order_key
        obj_order_by = comics_order_by
        if model_type != Comic and obj_order_key != SortChoice.sort_name.name:
            # If we're not sorting by name annotate a single child
            # comic attribute to sort by.
            sort_subquery = Subquery(comics.values(comics_order_key)[:1])
            if obj_order_key == "created_at":
                # Don't conflict with native container field
                obj_order_key += "child"
                obj_order_by += "child"
            annotate = {obj_order_key: sort_subquery}
            obj_list = obj_list.annotate(**annotate)

        # order the containers by the sort arguments
        obj_list = obj_list.order_by(obj_order_by)

        return obj_list

    def get_forms(self):
        """Get the forms to composite the browse menu."""
        forms = {}
        initial = deepcopy(self.browse_session)
        forms["bookmark"] = BookmarkFiltersForm(initial=initial)
        forms["decade"] = BrowseDecadeFilterForm(initial=initial)
        forms["character"] = BrowseCharacterFilterForm(initial=initial)
        settings = self.browse_session.get("settings")
        forms["group"] = BrowseGroupForm(settings, initial=initial)
        forms["sort"] = BrowseSortForm(initial=initial)

        initial = {"next_url": self.request.get_full_path()}
        forms["mark_read"] = MarkReadForm(initial=initial)
        forms["full_path"] = self.request.get_full_path()
        return forms

    def get_form(self, form_class=None):
        """Overrde FormMixin."""
        if form_class is None:
            form_class = self.get_form_class()
        initial = self.session_get(self.BROWSE_KEY, "settings")
        return form_class(initial, **self.get_form_kwargs())

    def save_session(self):
        """Save session with view params."""
        reader_session = self.get_session(self.READER_KEY)
        reader_session["group"] = self.get_group()
        reader_session["pk"] = self.kwargs.get("pk")
        self.request.session.save()

    def get_common_context(self, context):
        """Set context common to both views."""
        forms = self.get_forms()
        context["forms"] = forms
        return self.get_context_data(**context)

    def main_view(self):
        """Create the view."""
        self.browse_session = self.get_session(self.BROWSE_KEY)
        response = self.redirect_to_correct_view()
        if response:
            return response

        self.object_list = self.get_queryset()

        self.save_session()
        context = self.get_context()
        return self.render_to_response(context)


class ComicDownloadView(View, SingleObjectMixin):
    """Return the comic archive file as an attachment."""

    model = Comic

    def get(self, request, *args, **kwargs):
        """Download a comic archive."""
        try:
            comic = self.get_object()
        except Comic.DoesNotExist:
            pk = kwargs.get("pk")
            LOG.warn(f"Can't downlod comic {pk} that doesn't exist.")
            raise Http404(f"Comic not not found.")

        fd = open(comic.path, "rb")
        return FileResponse(fd, as_attachment=True,)


def redirect_browse_root(request):
    """Redirect to the browse root view."""
    return redirect("browse", group="r", pk=0)
