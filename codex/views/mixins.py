"""Manage user sessions with appropriate defaults."""
from copy import deepcopy

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.utils.cache import get_cache_key
from rest_framework.views import APIView

from codex.models import Comic, UserBookmark
from codex.serializers.webpack import DEFAULTS


class SessionMixin(APIView):
    """Generic Session Mixin."""

    BROWSER_KEY = "browser"
    READER_KEY = "reader"
    KEYS = (BROWSER_KEY, READER_KEY)
    CREDIT_PERSON_UI_FIELD = "creators"

    DYNAMIC_FILTER_DEFAULTS = {
        "characters": [],
        "country": [],
        CREDIT_PERSON_UI_FIELD: [],
        "critical_rating": [],
        "decade": [],
        "format": [],
        "genres": [],
        "language": [],
        "locations": [],
        "maturity_rating": [],
        "read_ltr": [],
        "series_groups": [],
        "story_arcs": [],
        "tags": [],
        "teams": [],
        "user_rating": [],
        "year": [],
    }
    FILTER_ATTRIBUTES = set(DYNAMIC_FILTER_DEFAULTS.keys())
    SESSION_DEFAULTS = {
        BROWSER_KEY: {
            "filters": {
                "bookmark": DEFAULTS["bookmarkFilter"],
                **DYNAMIC_FILTER_DEFAULTS,
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


class UserBookmarkMixin(APIView):
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
            comic = Comic.objects.only("pk", "max_page").get(pk=pk)
        search_kwargs = self._get_user_bookmark_search_kwargs(comic=comic, comic_pk=pk)
        if updates.get("bookmark") == comic.max_page:
            # Auto finish on bookmark last page
            updates["finished"] = True
        defaults = deepcopy(search_kwargs)
        defaults.update(updates)
        UserBookmark.objects.update_or_create(defaults=defaults, **search_kwargs)
        # DRF Request decends from django.http.HttpRequest so it works with duck typing
        #  despite get_cache_key typing specifying WSGIRequest
        ck = get_cache_key(self.request)  # type: ignore
        if ck:
            cache.delete(ck)
