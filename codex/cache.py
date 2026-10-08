"""
Cache backends.

Django's ``FileBasedCache`` treats a corrupt cache file as fatal: a
truncated zlib stream or a partial pickle bubbles up as ``zlib.error``
or ``pickle.UnpicklingError``, which then crashes whatever query
happened to fall on that key. A corrupt entry is rare but inevitable
(a write killed mid-flush leaves a file Django can't decompress) and
the right behaviour is just "treat it as a miss".

An intact entry can be just as unreadable after an upgrade. A pickle
names the module and class of every object in it, so an entry written
before a dependency was dropped raises ``ModuleNotFoundError`` on load,
and one naming a since-removed class raises ``AttributeError``. Codex
2.5.3 pickled comicbox's numpy cover scores into pending online-tag
prompts; 2.5.4 ships without numpy, and every read of those prompts
returned a 500.

``ResilientFileBasedCache`` catches those errors, deletes the bad file,
and reports a miss so the caller continues with the underlying query
instead of returning a 500 to the user.

It also no-ops ``validate_key``: the base class checks every key for
memcached compatibility (no spaces / control chars / length > 250)
and emits a ``CacheKeyWarning`` for violators. Codex hashes-and-pickles
to disk; the FS layer accepts arbitrary keys, so the memcached
portability warnings are noise. Cachalot in particular composes keys
from query plans that include tuples (``(127, 128)``) which trip the
warning on every browse / cover request.
"""

import zlib
from pickle import UnpicklingError
from typing import override

from django.core.cache import caches
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.filebased import FileBasedCache
from django.utils.connection import ConnectionProxy
from loguru import logger

_UNREADABLE_CACHE_ERRORS: tuple[type[BaseException], ...] = (
    zlib.error,
    UnpicklingError,
    EOFError,
    # A stale pickle: its module (ModuleNotFoundError) or class is gone.
    ImportError,
    AttributeError,
)


class ResilientFileBasedCache(FileBasedCache):
    """Cache backend that tolerates unreadable cache entries."""

    def _discard_unreadable(self, fname: str, exc: BaseException) -> None:
        # Warn rather than debug: the tagging cache holds pending prompts and
        # tag-write errors, and an admin whose queue just emptied should be
        # able to find out why.
        logger.warning(f"Discarded unreadable cache file {fname}: {exc!r}")
        self._delete(fname)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]

    @override
    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default=default, version=version)
        except _UNREADABLE_CACHE_ERRORS as exc:
            fname = self._key_to_file(key, version)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._discard_unreadable(fname, exc)
            return default

    @override
    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().touch(key, timeout=timeout, version=version)
        except _UNREADABLE_CACHE_ERRORS as exc:
            fname = self._key_to_file(key, version)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._discard_unreadable(fname, exc)
            return False

    @override
    def validate_key(self, key):
        """No-op key validation — see module docstring."""


# Per-thread connection to the dedicated "tagging" cache, mirroring
# ``django.core.cache.cache``. Durable tagging state (pending online-tag
# prompts, tag-write errors) lives here because the default cache is
# ``cache.clear()``-ed broadly (import finish, Library/Group CRUD,
# startup) and Django's file-based clear ignores key prefixes.
# django-stubs omits CacheHandler's BaseConnectionHandler base.
tagging_cache = ConnectionProxy(caches, "tagging")  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
