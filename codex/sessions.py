"""
Session store that carries a visitor's data across login.

Django's ``login()`` calls ``request.session.cycle_key()``, which creates
a new session row and deletes the old one through the ORM. The settings
and bookmark tables hang off ``Session`` with ``cascade_if_user_null``,
so every anonymous row owned by the old key used to be deleted before
``user_logged_in`` fired, and nothing was left to adopt.

:class:`SessionStore` re-points those rows to the new key between the
``create()`` and the ``delete()``. The ``user_logged_in`` receiver in
:mod:`codex.signals.login` then adopts them into the user.

The cache key prefix and the ``Session`` model are the ``cached_db``
backend's own, so sessions issued before this store keep working.
"""

from typing import override

from asgiref.sync import sync_to_async
from django.contrib.sessions.backends.cached_db import (
    SessionStore as CachedDBSessionStore,
)
from django.db import DatabaseError, transaction
from loguru import logger


def repoint_session_rows(old_key: str, new_key: str) -> None:
    """
    Move the rows a session owns from ``old_key`` to ``new_key``.

    Named browser rows (saved views) are left behind on purpose: they
    stay cascade-deleted with the old session. ``new_key`` was just
    created and owns nothing, so the bulk updates cannot collide with
    the per-session unique constraints.

    A failure is logged and swallowed: losing visitor settings is
    better than failing the login.
    """
    # Lazy imports: the session engine module is imported by Django's
    # session machinery, which must not drag the codex models in early.
    from codex.models.bookmark import Bookmark
    from codex.models.settings import SettingsBrowser, SettingsReader

    try:
        with transaction.atomic():
            SettingsBrowser.objects.filter(session_id=old_key, name="").update(
                session_id=new_key
            )
            SettingsReader.objects.filter(session_id=old_key).update(session_id=new_key)
            Bookmark.objects.filter(session_id=old_key).update(session_id=new_key)
    except DatabaseError:
        logger.exception("Could not move session settings and bookmarks to new key")


class SessionStore(CachedDBSessionStore):
    """``cached_db`` session store that keeps owned rows on ``cycle_key``."""

    @override
    def cycle_key(self) -> None:
        """Create a new key, move the old key's rows to it, drop the old key."""
        data = self._session  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
        key = self.session_key
        self.create()
        self._session_cache = data
        if key:
            if self.session_key:
                repoint_session_rows(key, self.session_key)
            self.delete(key)

    # django-stubs lags Django's async session API, hence the ignores.
    async def acycle_key(self) -> None:
        """Async :meth:`cycle_key`."""
        data = await self._aget_session()  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
        key = self.session_key
        await self.acreate()  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
        self._session_cache = data
        if key:
            if self.session_key:
                await sync_to_async(repoint_session_rows)(key, self.session_key)
            await self.adelete(key)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
