"""
API key scopes.

Every inbound API credential is one :class:`codex.models.api_key.UserApiKey`
row, and its scope says where it logs in:

* ``device``: OPDS and KOReader sync. What users make for their reader
  apps.
* ``universal``: everywhere, ``/api/v4/`` included. Only the per-user DRF
  bearer tokens of older versions became these, by migration. Nothing
  makes new ones: they work until revoked.
* ``stats``: the admin Stats API. Owned by the admin who made it and only
  while that user is still staff.
"""

from types import MappingProxyType
from typing import Final

from django.db.models.enums import TextChoices


class ApiKeyScope(TextChoices):
    """Where a key logs in."""

    DEVICE = "device", "Device"
    UNIVERSAL = "universal", "Universal"
    STATS = "stats", "Stats"


#: Scopes valid on OPDS and KOReader sync.
READER_SCOPES: Final = frozenset(
    {ApiKeyScope.DEVICE.value, ApiKeyScope.UNIVERSAL.value}
)
#: Scopes valid on every ``/api/v4/`` endpoint.
FULL_API_SCOPES: Final = frozenset({ApiKeyScope.UNIVERSAL.value})
#: Scopes valid on the admin Stats API.
STATS_SCOPES: Final = frozenset({ApiKeyScope.STATS.value})
#: Scopes a user can make. A universal key cannot be made, only migrated.
CREATABLE_SCOPES: Final = (ApiKeyScope.DEVICE.value, ApiKeyScope.STATS.value)
#: The name migrated bearer tokens get. Reserved: no other key may take it.
UNIVERSAL_KEY_NAME: Final = "Universal Token"

#: Scope titles for the client, dumped to ``api-key-scopes.json``.
API_KEY_SCOPE_TITLES: Final = MappingProxyType(
    {scope.value: scope.label for scope in ApiKeyScope}
)
