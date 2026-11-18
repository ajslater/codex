"""
Adopt a visitor's settings and bookmarks into the user on login.

:class:`codex.sessions.SessionStore` keeps the anonymous rows alive
across ``cycle_key()`` by re-pointing them to the new session key. This
``user_logged_in`` receiver then hands them to the user inside the login
request. The user's own row always wins: an anonymous row whose slot the
user already fills is deleted instead of adopted.
"""

from collections.abc import Mapping

from django.db import DatabaseError, transaction
from django.db.models import Exists, OuterRef, QuerySet, Value
from django.db.models.functions import Coalesce
from loguru import logger

_READER_SCOPE_FIELDS = ("comic_id", "series_id", "folder_id", "story_arc_id")


def _adopt_rows(anonymous: QuerySet, owned: QuerySet, fields: Mapping) -> None:
    """
    Delete the anonymous rows whose slot the user fills; adopt the rest.

    ``owned`` is the user's rows, correlated to an anonymous row's slot.
    Two set-based statements in one transaction. A queryset ``update``
    leaves ``updated_at`` alone, so an adopted bookmark keeps the time it
    was last read, and neither statement touches a row the user owns.
    """
    with transaction.atomic():
        anonymous.filter(Exists(owned)).delete()
        anonymous.update(**fields)


def _adopt_browser(user, session_key: str) -> None:
    """Adopt the default (unnamed) browser rows; the session id is kept."""
    from codex.models.settings import SettingsBrowser

    anonymous = SettingsBrowser.objects.filter(
        session_id=session_key, user__isnull=True, name=""
    )
    owned = SettingsBrowser.objects.filter(
        user=user, client=OuterRef("client"), name=""
    )
    _adopt_rows(anonymous, owned, {"user_id": user.pk})


def _adopt_reader(user, session_key: str) -> None:
    """Adopt reader rows of every scope; the session is dropped."""
    from codex.models.settings import SettingsReader

    anonymous = SettingsReader.objects.filter(session_id=session_key, user__isnull=True)
    # A slot is the client plus every scope column, a null equal to a null
    # (the global row has none set). No row has pk 0.
    owned = SettingsReader.objects.filter(user=user, client=OuterRef("client"))
    for field in _READER_SCOPE_FIELDS:
        alias = f"_slot_{field}"
        owned = owned.alias(**{alias: Coalesce(field, Value(0))}).filter(
            **{alias: Coalesce(OuterRef(field), Value(0))}
        )
    _adopt_rows(anonymous, owned, {"user_id": user.pk, "session_id": None})


def _adopt_bookmarks(user, session_key: str) -> None:
    """Adopt bookmarks; the session is dropped."""
    from codex.models.bookmark import Bookmark

    anonymous = Bookmark.objects.filter(session_id=session_key, user__isnull=True)
    owned = Bookmark.objects.filter(user=user, comic_id=OuterRef("comic_id"))
    _adopt_rows(anonymous, owned, {"user_id": user.pk, "session_id": None})


_ADOPTERS = (_adopt_browser, _adopt_reader, _adopt_bookmarks)


def adopt_session_rows(sender, request, user, **_kwargs) -> None:
    """Adopt the login session's anonymous rows into the user."""
    del sender
    session = getattr(request, "session", None)
    session_key = getattr(session, "session_key", None)
    if not session_key or not getattr(user, "pk", None):
        return
    for adopter in _ADOPTERS:
        try:
            adopter(user, session_key)
        except DatabaseError:
            logger.exception(f"Login settings adoption failed in {adopter.__name__}")
