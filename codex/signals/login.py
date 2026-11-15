"""
Adopt a visitor's settings and bookmarks into the user on login.

:class:`codex.sessions.SessionStore` keeps the anonymous rows alive
across ``cycle_key()`` by re-pointing them to the new session key. This
``user_logged_in`` receiver then hands them to the user inside the login
request. The user's own row always wins: an anonymous row whose slot the
user already fills is deleted instead of adopted.
"""

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Model
from loguru import logger

_READER_SCOPE_FIELDS = ("comic_id", "series_id", "folder_id", "story_arc_id")


def _adopt_row(row: Model, fields: dict, *, user_has_slot: bool) -> None:
    """Delete the row if the user already fills its slot, else adopt it."""
    if user_has_slot:
        row.delete()
        return
    try:
        with transaction.atomic():
            for attr, value in fields.items():
                setattr(row, attr, value)
            row.save(update_fields=(*fields, "updated_at"))
    except IntegrityError:
        # Lost a race to a row the user created meanwhile: theirs wins.
        row.delete()


def _adopt_browser(user, session_key: str) -> None:
    """Adopt the default (unnamed) browser rows; the session id is kept."""
    from codex.models.settings import SettingsBrowser

    rows = SettingsBrowser.objects.filter(
        session_id=session_key, user__isnull=True, name=""
    )
    for row in rows:
        has_slot = SettingsBrowser.objects.filter(
            user=user, client=row.client, name=""
        ).exists()
        _adopt_row(row, {"user_id": user.pk}, user_has_slot=has_slot)


def _adopt_reader(user, session_key: str) -> None:
    """Adopt reader rows of every scope; the session is dropped."""
    from codex.models.settings import SettingsReader

    rows = SettingsReader.objects.filter(session_id=session_key, user__isnull=True)
    for row in rows:
        scope = {field: getattr(row, field) for field in _READER_SCOPE_FIELDS}
        has_slot = SettingsReader.objects.filter(
            user=user, client=row.client, **scope
        ).exists()
        _adopt_row(
            row, {"user_id": user.pk, "session_id": None}, user_has_slot=has_slot
        )


def _adopt_bookmarks(user, session_key: str) -> None:
    """Adopt bookmarks; the session is dropped."""
    from codex.models.bookmark import Bookmark

    rows = Bookmark.objects.filter(session_id=session_key, user__isnull=True)
    for row in rows:
        has_slot = Bookmark.objects.filter(user=user, comic_id=row.comic_id).exists()  # pyright: ignore[reportAttributeAccessIssue]
        _adopt_row(
            row, {"user_id": user.pk, "session_id": None}, user_has_slot=has_slot
        )


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
