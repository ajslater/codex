"""API keys: named, revocable, hashed credentials for apps and devices."""

import hashlib
import secrets
from datetime import timedelta
from typing import Final, override

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    ForeignKey,
    Model,
    Q,
    QuerySet,
    UniqueConstraint,
)
from django.utils import timezone
from loguru import logger

from codex.choices.api_key import CREATABLE_SCOPES, ApiKeyScope
from codex.choices.limits import API_KEY_NAME_MAX_LENGTH
from codex.models.base import BaseModel
from codex.models.choices import max_choices_len

__all__ = ("RevokedApiKey", "UserApiKey")

# 32 symbols, so each character carries 5 bits. Lowercase letters and digits
# without 0/o and 1/l, which read alike on e-ink. The key is typed on e-reader
# keyboards and KOReader hashes exactly what was typed, so the key has no
# dashes and no mixed case.
API_KEY_ALPHABET: Final = "abcdefghijkmnpqrstuvwxyz23456789"
API_KEY_LENGTH: Final = 20  # 100 bits.
API_KEY_PREFIX_LENGTH: Final = 4
API_KEYS_PER_SCOPE_MAX: Final = 32
# ``last_used_at`` is written at most this often per key, so streaming OPDS
# pages does not take the SQLite write lock on every request.
LAST_USED_RESOLUTION: Final = timedelta(hours=1)


_API_KEY_CHARS: Final = frozenset(API_KEY_ALPHABET)
# A DRF token, migrated to a universal key: 20 random bytes as lowercase hex.
_TOKEN_LENGTH: Final = 40
_TOKEN_CHARS: Final = frozenset("0123456789abcdef")


def generate_api_key() -> str:
    """Return a new random API key."""
    return "".join(secrets.choice(API_KEY_ALPHABET) for _ in range(API_KEY_LENGTH))


def is_api_key_shaped(secret: str) -> bool:
    """
    Whether ``secret`` could be a key: a generated one or a migrated token.

    Anything else is a password, which must never reach the fast-hash key
    lookup or a cache key derived from it.
    """
    match len(secret):
        case length if length == API_KEY_LENGTH:
            return set(secret) <= _API_KEY_CHARS
        case length if length == _TOKEN_LENGTH:
            return set(secret) <= _TOKEN_CHARS
        case _:
            return False


def api_key_digest(key: str) -> str:
    """
    Return the SHA-256 hex digest that Basic and Bearer lookups use.

    A generated key is 100 random bits and a migrated bearer token 160, so
    an unsalted fast hash is enough: there is no dictionary to attack.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def api_key_kosync_digest(key: str) -> str:
    """Return the MD5 hex digest KOReader sends as ``x-auth-key``."""
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()


class UserApiKey(BaseModel):
    """
    An API key: a named credential for one app or device.

    Its :attr:`scope` says where it logs in (see :mod:`codex.choices.api_key`).
    The plain key is shown once on creation and never stored; only its hashes
    are. ``name`` is free text the user typed and ``prefix`` is part of a
    credential: neither may ever be reported by telemetry.
    """

    user = ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="api_keys"
    )
    name = CharField(max_length=API_KEY_NAME_MAX_LENGTH)
    scope = CharField(
        max_length=max_choices_len(ApiKeyScope),
        choices=ApiKeyScope.choices,
        default=ApiKeyScope.DEVICE,
    )
    prefix = CharField(max_length=API_KEY_PREFIX_LENGTH)
    digest = CharField(max_length=64, unique=True)
    kosync_digest = CharField(max_length=32, db_index=True)
    last_used_at = DateTimeField(null=True, default=None)

    class Meta(BaseModel.Meta):
        """A user cannot have two keys with the same name."""

        verbose_name = "API key"
        constraints = (
            UniqueConstraint(
                fields=("user", "name"), name="unique_userapikey_user_name"
            ),
        )

    @override
    def __repr__(self) -> str:
        return f"<UserApiKey pk={self.pk} scope={self.scope}>"

    @classmethod
    def _create(cls, user, name: str, scope: str, key: str) -> "UserApiKey":
        return cls.objects.create(
            user=user,
            name=name,
            scope=scope,
            prefix=key[:API_KEY_PREFIX_LENGTH],
            digest=api_key_digest(key),
            kosync_digest=api_key_kosync_digest(key),
        )

    @classmethod
    def create_for_user(
        cls, user, name: str, scope: str = ApiKeyScope.DEVICE.value
    ) -> tuple["UserApiKey", str]:
        """
        Create a key and return it with the plain key, the only time it exists.

        Raises ``ValidationError`` for a scope nobody can make, or when the
        user already has :data:`API_KEYS_PER_SCOPE_MAX` keys of the scope.
        """
        if scope not in CREATABLE_SCOPES:
            reason = f"{ApiKeyScope(scope).label} keys cannot be created."
            raise ValidationError(reason)
        if cls.objects.filter(user=user, scope=scope).count() >= API_KEYS_PER_SCOPE_MAX:
            label = ApiKeyScope(scope).label.lower()
            reason = f"A user can have at most {API_KEYS_PER_SCOPE_MAX} {label} keys."
            raise ValidationError(reason)
        key = generate_api_key()
        return cls._create(user, name, scope, key), key

    def touch(self) -> None:
        """
        Record use, at most once per :data:`LAST_USED_RESOLUTION`.

        A queryset ``update`` rather than ``save``: it leaves ``updated_at``
        alone and writes one column. Cachalot invalidates only the queries
        that read this table, which are the key lookups themselves.

        Best-effort: this is a write on a read path, so a database that is
        locked by a long librarian write skips it rather than failing the
        request. Conditional: a value another request stored after this
        row was loaded is not overwritten.
        """
        now = timezone.now()
        if self.last_used_at and now - self.last_used_at < LAST_USED_RESOLUTION:
            return
        stale = Q(last_used_at__isnull=True) | Q(
            last_used_at__lt=now - LAST_USED_RESOLUTION
        )
        try:
            with transaction.atomic():
                type(self).objects.filter(stale, pk=self.pk).update(last_used_at=now)
        except DatabaseError as exc:
            logger.debug(f"API key last use not recorded: {exc}")
            return
        self.last_used_at = now


class RevokedApiKey(Model):
    """
    A revoked key's tombstone, so a backup restore cannot bring it back.

    Only the key's SHA-256 digest is kept: never the key, its name or its
    prefix. Written by :func:`revoke_api_keys`, which every revoke goes
    through. Deleting a user cascades to their keys without tombstones: a
    restore brings the whole account back, password included, so its keys
    come back with it.
    """

    digest = CharField(max_length=64, unique=True)
    revoked_at = DateTimeField(auto_now_add=True)

    class Meta:
        """Admin name."""

        verbose_name = "revoked API key"

    @override
    def __str__(self) -> str:
        """Name the row, never its digest."""
        return f"revoked API key {self.pk}"


def revoke_api_keys(keys: QuerySet[UserApiKey]) -> int:
    """
    Delete ``keys``, leaving a tombstone for each. Return how many went.

    Only the keys tombstoned are deleted, so a key made while this runs is
    neither deleted nor tombstoned.
    """
    with transaction.atomic():
        digests = tuple(keys.values_list("digest", flat=True))
        if not digests:
            return 0
        RevokedApiKey.objects.bulk_create(
            (RevokedApiKey(digest=digest) for digest in digests),
            ignore_conflicts=True,
        )
        deleted, _ = UserApiKey.objects.filter(digest__in=digests).delete()
    return deleted
