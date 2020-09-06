"""Manage user sessions with appropriate defaults."""
from copy import copy
from decimal import Decimal

from django.contrib.sessions.models import Session
from django.db.models import DecimalField
from django.db.models import F
from django.db.models import Q
from django.db.models import Value
from django.db.models.functions import Coalesce

from codex.choices.static import DEFAULTS
from codex.models import Comic
from codex.models import UserBookmark


class SessionMixin:
    """Generic Session Mixin."""

    BROWSE_KEY = "browse"
    READER_KEY = "reader"
    KEYS = (BROWSE_KEY, READER_KEY)

    SESSION_DEFAULTS = {
        BROWSE_KEY: {
            "filters": {
                "bookmark": DEFAULTS["bookmarkFilter"],
                "decade": [],
                "characters": [],
            },
            "root_group": DEFAULTS["rootGroup"],
            "sort_by": DEFAULTS["sort"],
            "sort_reverse": False,
            "show": DEFAULTS["show"],
        },
        READER_KEY: {"defaults": {"fit_to": DEFAULTS["fitTo"], "two_pages": False}},
    }

    def get_session(self, session_key):
        """Create or get the view session."""
        data = self.request.session.setdefault(
            session_key, self.SESSION_DEFAULTS[session_key]
        )

        # Set defaults for each key in case they don't exist.
        for key, value in self.SESSION_DEFAULTS[session_key].items():
            data[key] = self.request.session[session_key].setdefault(key, value)
            if isinstance(value, dict):
                # Just one level. No need for recursion.
                for deep_key, deep_value in self.SESSION_DEFAULTS[session_key][
                    key
                ].items():
                    data[key][deep_key] = self.request.session[session_key][
                        key
                    ].setdefault(deep_key, deep_value)

        return data


class UserBookmarkMixin:
    """Hold user setting for a comic."""

    def _get_user_bookmark_search_kwargs(self, comic=None, comic_pk=None):
        """
        Get the search kwargs for a user's authentication state.

        Comic & Session must be instantiated for create.
        """
        if comic:
            search_kwargs = {"comic": comic}
        else:
            search_kwargs = {"comic__pk": comic_pk}
        if self.request.user.is_authenticated:
            search_kwargs["user"] = self.request.user
        else:
            try:
                session = Session.objects.only("pk", "session_key").get(
                    session_key=self.request.session.session_key
                )
            except Session.DoesNotExist:
                self.request.session.save()
                # This save is for first time users to create a session
                # in the db before looking it up.
                session = Session.objects.get(
                    session_key=self.request.session.session_key
                ).only("pk", "session_key")

            search_kwargs["session"] = session
        return search_kwargs

    def get_user_bookmark(self, pk):
        """Get a user bookmark."""
        search_kwargs = self._get_user_bookmark_search_kwargs(comic_pk=pk)
        try:
            ub = UserBookmark.objects.get(**search_kwargs)
        except UserBookmark.DoesNotExist:
            ub = None
        return ub

    def update_user_bookmark(self, updates, comic=None, pk=None):
        """Update a user bookmark."""
        if comic is None:
            comic = Comic.objects.only("pk").get(pk=pk)
        search_kwargs = self._get_user_bookmark_search_kwargs(comic)
        if updates.get("bookmark") == comic.max_page:
            # Auto finish on bookmark last page
            updates["finished"] = True
        defaults = copy(search_kwargs)
        defaults.update(updates)
        UserBookmark.objects.update_or_create(defaults=defaults, **search_kwargs)

    def get_userbookmark_filter(self, for_comic=False):
        """Get a filter for my session or user defined bookmarks."""
        rel_to_ub = "userbookmark"
        if not for_comic:
            rel_to_ub = "comic__userbookmark"

        if self.request.user.is_authenticated:
            my_bookmarks_kwargs = {f"{rel_to_ub}__user": self.request.user}
        else:
            my_bookmarks_kwargs = {f"{rel_to_ub}__session": self.request.session}
        return Q(**my_bookmarks_kwargs)

    @staticmethod
    def annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from userbookmarks.
        # Requires x_page_count native to comic or aggregated
        queryset = queryset.annotate(
            progress=Coalesce(
                F("bookmark") * Decimal("1.0") / F("x_page_count") * 100,
                Value(0.00),
                output_field=DecimalField(),
            )
        )
        return queryset
