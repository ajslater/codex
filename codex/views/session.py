"""Manage user sessions with appropriate defaults."""
from django.forms import Form

from codex.forms import SortChoice


class SessionMixin:
    """Generic Session Mixin."""

    COMIC_KEY = "comic"
    VIEW_KEY = "view"
    BROWSE_KEY = "browse"

    SESSION_DEFAULTS = {
        VIEW_KEY: {"group": "r", "group_id": 0, "folder": "", "root_path_id": 0},
        COMIC_KEY: {},
        BROWSE_KEY: {
            "filters": [],
            "root_group": "s",
            "sort_by": SortChoice.ALPHANUM.name,
            "sort_reverse": False,
        },
    }

    SINGLE_COMIC_INIT = {"bookmark": 0, "finished": False}

    def get_session(self, session_key):
        """Create or get the view session."""
        return self.request.session.setdefault(
            session_key, self.SESSION_DEFAULTS[session_key]
        )

    def session_set(self, session_key, key, val):
        """Set the session."""
        self.get_session(session_key)[key] = val

    def session_get(self, session_key, key, form=None):
        """Get a value from form, session, or default and write it back."""
        session = self.get_session(session_key)
        val = None
        if form and isinstance(form, Form):
            val = form.cleaned_data.get(key)
        elif form is not None:
            val = form
        if val is None:
            val = session.get(key)
        if val is None:
            val = self.SESSION_DEFAULTS[key]
        session[key] = val
        return val

    def session_form_set(self, session_key, form):
        """Get all the session keys and write them back."""
        for key in self.SESSION_DEFAULTS[session_key].keys():
            self.session_get(session_key, key, form)

    def session_get_comic(self, comic_id):
        """Get comic bookmarks, as they're deep."""
        return self.session_get(self.COMIC_KEY, str(comic_id), self.SINGLE_COMIC_INIT)

    def get_read_comic_ids(self):
        """Get ids of finished comics."""
        read_ids = []
        comics = self.get_session(self.COMIC_KEY)
        if not comics:
            return read_ids
        for key, val in comics.items():
            if val.get("finished"):
                read_ids.append(key)
        return read_ids

    def get_in_progress_comic_ids(self):
        """Get ids of unfinished comics with bookmarks."""
        in_progress_ids = []
        comics = self.get_session(self.COMIC_KEY)
        if not comics:
            return in_progress_ids
        for key, val in comics.items():
            finished = val.get("finished")
            if finished:
                continue
            bookmark = val.get("bookmark")
            if bookmark is not None and bookmark > 0:
                in_progress_ids.append(key)
        return in_progress_ids
