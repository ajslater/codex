"""Device keys: named, revocable per-device credentials for reader apps."""

import hashlib
import secrets
from datetime import timedelta
from typing import Final, override

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    ForeignKey,
    UniqueConstraint,
)
from django.utils import timezone

from codex.models.base import BaseModel

__all__ = ("UserApiKey",)

# 32 symbols, so each character carries 5 bits. Lowercase letters and digits
# without 0/o and 1/l, which read alike on e-ink. The key is typed on e-reader
# keyboards and KOReader hashes exactly what was typed, so the key has no
# dashes and no mixed case.
DEVICE_KEY_ALPHABET: Final = "abcdefghijkmnpqrstuvwxyz23456789"
DEVICE_KEY_LENGTH: Final = 20  # 100 bits.
DEVICE_KEY_PREFIX_LENGTH: Final = 4
DEVICE_KEY_NAME_MAX_LENGTH: Final = 64
DEVICE_KEYS_PER_USER_MAX: Final = 32
# ``last_used_at`` is written at most this often per key, so streaming OPDS
# pages does not take the SQLite write lock on every request.
LAST_USED_RESOLUTION: Final = timedelta(hours=1)


def generate_device_key() -> str:
    """Return a new random device key."""
    return "".join(
        secrets.choice(DEVICE_KEY_ALPHABET) for _ in range(DEVICE_KEY_LENGTH)
    )


def device_key_digest(key: str) -> str:
    """
    Return the SHA-256 hex digest that Basic and Bearer lookups use.

    The key is 100 random bits, so an unsalted fast hash is enough: there is
    no dictionary to attack.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def device_key_kosync_digest(key: str) -> str:
    """Return the MD5 hex digest KOReader sends as ``x-auth-key``."""
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()


class UserApiKey(BaseModel):
    """
    A device key: a named credential for one reader app or device.

    Valid on OPDS and KOReader sync only, never on ``/api/v4/``. The plain
    key is shown once on creation and never stored; only its hashes are.
    ``name`` is free text the user typed and ``prefix`` is part of a
    credential: neither may ever be reported by telemetry.
    """

    user = ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="api_keys"
    )
    name = CharField(max_length=DEVICE_KEY_NAME_MAX_LENGTH)
    prefix = CharField(max_length=DEVICE_KEY_PREFIX_LENGTH)
    digest = CharField(max_length=64, unique=True)
    kosync_digest = CharField(max_length=32, db_index=True)
    last_used_at = DateTimeField(null=True, default=None)

    class Meta(BaseModel.Meta):
        """A user cannot have two keys with the same name."""

        verbose_name = "device key"
        constraints = (
            UniqueConstraint(
                fields=("user", "name"), name="unique_userapikey_user_name"
            ),
        )

    @override
    def __repr__(self) -> str:
        return f"<UserApiKey pk={self.pk}>"

    @classmethod
    def create_for_user(cls, user, name: str) -> tuple["UserApiKey", str]:
        """
        Create a key and return it with the plain key, the only time it exists.

        Raises ``ValidationError`` when the user already has
        :data:`DEVICE_KEYS_PER_USER_MAX` keys.
        """
        if cls.objects.filter(user=user).count() >= DEVICE_KEYS_PER_USER_MAX:
            reason = f"A user can have at most {DEVICE_KEYS_PER_USER_MAX} device keys."
            raise ValidationError(reason)
        key = generate_device_key()
        api_key = cls.objects.create(
            user=user,
            name=name,
            prefix=key[:DEVICE_KEY_PREFIX_LENGTH],
            digest=device_key_digest(key),
            kosync_digest=device_key_kosync_digest(key),
        )
        return api_key, key

    def touch(self) -> None:
        """
        Record use, at most once per :data:`LAST_USED_RESOLUTION`.

        A queryset ``update`` rather than ``save``: it leaves ``updated_at``
        alone and writes one column. Cachalot invalidates only the queries
        that read this table, which are the key lookups themselves.
        """
        now = timezone.now()
        if self.last_used_at and now - self.last_used_at < LAST_USED_RESOLUTION:
            return
        type(self).objects.filter(pk=self.pk).update(last_used_at=now)
        self.last_used_at = now
