"""
Cache backends.

Django's ``FileBasedCache`` treats a corrupt cache file as fatal: a
truncated zlib stream or a partial pickle bubbles up as ``zlib.error``
or ``pickle.UnpicklingError``, which then crashes whatever query
happened to fall on that key. A corrupt entry is rare but inevitable
(a write killed mid-flush leaves a file Django can't decompress) and
the right behaviour is just "treat it as a miss".

``ResilientFileBasedCache`` catches those decode errors, deletes the
bad file, and reports a miss so the caller continues with the
underlying query instead of returning a 500 to the user.

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

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.filebased import FileBasedCache
from loguru import logger

_CORRUPT_CACHE_ERRORS: tuple[type[BaseException], ...] = (
    zlib.error,
    UnpicklingError,
    EOFError,
)


class ResilientFileBasedCache(FileBasedCache):
    """Cache backend that tolerates corrupt cache entries."""

    def _discard_corrupt(self, fname: str, exc: BaseException) -> None:
        logger.debug(f"Discarded corrupt cache file {fname}: {exc}")
        self._delete(fname)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]

    @override
    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default=default, version=version)
        except _CORRUPT_CACHE_ERRORS as exc:
            fname = self._key_to_file(key, version)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._discard_corrupt(fname, exc)
            return default

    @override
    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().touch(key, timeout=timeout, version=version)
        except _CORRUPT_CACHE_ERRORS as exc:
            fname = self._key_to_file(key, version)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._discard_corrupt(fname, exc)
            return False

    @override
    def validate_key(self, key):
        """No-op key validation — see module docstring."""
