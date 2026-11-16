"""Make API key rows with a known secret, as only a migration or a test may."""

from codex.models.api_key import (
    API_KEY_PREFIX_LENGTH,
    UserApiKey,
    api_key_digest,
    api_key_kosync_digest,
)


def make_api_key(user, name: str, scope: str, secret: str) -> UserApiKey:
    """
    Store ``secret`` as a key of any scope, hashed like a real one.

    ``UserApiKey.create_for_user`` makes only device and stats keys, and
    generates the secret itself; universal keys come only from migrating
    old bearer tokens.
    """
    return UserApiKey.objects.create(
        user=user,
        name=name,
        scope=scope,
        prefix=secret[:API_KEY_PREFIX_LENGTH],
        digest=api_key_digest(secret),
        kosync_digest=api_key_kosync_digest(secret),
    )
