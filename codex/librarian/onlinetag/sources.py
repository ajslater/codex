"""
The online tagging sources codex can drive, as one registry.

comicbox names every online source it can search in ``SOURCE_NAMES``. Codex
drives a source only once it is registered here, because driving one takes
more than its name: a column on ``ComicboxTaggingDefaults`` for its key, the
comicbox class whose ``probe()`` tests that key, which of the probe's
rate-limit windows the admin chip shows, and a descriptor in
``frontend/src/components/online-tag/source-labels.js``.

``SUPPORTED_SOURCES`` is comicbox's list filtered to this registry, in
comicbox's order. A source comicbox adds before codex registers it is
therefore inert: never offered, refused by validation, and never handed
another source's credentials.

The Django settings import this module (through ``codex.choices.admin``), so
at runtime it imports nothing from codex and no online client package.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from comicbox.config.online.settings import OnlineSourceCredentials
from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP
from comicbox.formats.base.online import SOURCE_NAMES

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from comicbox.formats.base.online.sources.base import OnlineSource
    from comicbox.online_session import OnlineCredentials

# comicbox's display names, keyed by source name ("metron" -> "Metron").
_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {source.value: label for source, label in ID_SOURCE_NAME_MAP.items()}
)


@dataclass(frozen=True, slots=True)
class OnlineTagSource:
    """What codex needs to drive one comicbox online source."""

    #: comicbox's name for the source, as in ``SOURCE_NAMES``.
    name: str
    #: The comicbox module holding the source class and its process-wide
    #: clients (``close_shared_sessions``). Named, not imported: importing it
    #: loads the source's API client package.
    module: str
    #: The ``OnlineSource`` subclass in ``module``.
    class_name: str
    #: The field holding the source's API key. Codex names its columns on
    #: ``ComicboxTaggingDefaults`` after comicbox's ``OnlineCredentials``
    #: fields, so one name reads both.
    key_field: str
    #: The field holding a custom API url, for a source that takes one.
    url_field: str | None
    #: Codex's rate-limit window (a ``RateLimitInfo`` field) -> the probe's
    #: name for it. Only the windows the validation chip can show.
    rate_limit_windows: Mapping[str, str]

    @property
    def label(self) -> str:
        """The display name comicbox gives the source."""
        return _LABELS.get(self.name, self.name)

    @property
    def credential_fields(self) -> tuple[str, ...]:
        """The credential fields this source reads, key first."""
        return (self.key_field, self.url_field) if self.url_field else (self.key_field,)

    def source_class(self) -> type[OnlineSource]:
        """Import and return the comicbox source class."""
        return getattr(import_module(self.module), self.class_name)


_REGISTRY: Final[Mapping[str, OnlineTagSource]] = MappingProxyType(
    {
        source.name: source
        for source in (
            OnlineTagSource(
                name="metron",
                module="comicbox.formats.metron_api.online_source",
                class_name="MetronOnlineSource",
                key_field="metron_key",
                # mokkari hardcodes its endpoint, so a custom url is a no-op.
                url_field=None,
                # Read off the probe response's X-RateLimit-* headers.
                rate_limit_windows=MappingProxyType(
                    {"burst": "burst", "sustained": "daily"}
                ),
            ),
            OnlineTagSource(
                name="comicvine",
                module="comicbox.formats.comicvine_api.online_source",
                class_name="ComicVineOnlineSource",
                key_field="comicvine_key",
                url_field="comicvine_url",
                # Comic Vine's pools are hourly; the chip speaks per-minute
                # and per-day.
                rate_limit_windows=MappingProxyType({}),
            ),
        )
    }
)


def supported_sources(source_names: Iterable[str]) -> tuple[str, ...]:
    """Filter comicbox's source names to the registered ones, in its order."""
    return tuple(name for name in source_names if name in _REGISTRY)


SUPPORTED_SOURCES: Final[tuple[str, ...]] = supported_sources(SOURCE_NAMES)

#: The supported sources' registry entries, in ``SUPPORTED_SOURCES`` order.
SOURCES: Final[Mapping[str, OnlineTagSource]] = MappingProxyType(
    {name: _REGISTRY[name] for name in SUPPORTED_SOURCES}
)

#: Every credential field the supported sources read, in source order.
CREDENTIAL_FIELDS: Final[tuple[str, ...]] = tuple(
    field for source in SOURCES.values() for field in source.credential_fields
)


def configured_sources(holder: object) -> tuple[str, ...]:
    """
    Return the supported sources that have an API key, in comicbox's order.

    ``holder`` is the ``ComicboxTaggingDefaults`` row, comicbox's
    ``OnlineCredentials`` or None; both name a key by the same field. A url
    alone configures nothing, since it cannot authenticate.

    Typed ``object`` because even a ``TYPE_CHECKING`` import of the model
    trips basedpyright's ``reportImportCycles``: this module ->
    ``codex.models`` -> ``codex.models.admin`` -> ``codex.choices.admin`` ->
    this module.
    """
    if holder is None:
        return ()
    return tuple(
        name for name, source in SOURCES.items() if getattr(holder, source.key_field)
    )


def build_credentials(defaults: object) -> OnlineCredentials | None:
    """
    Return comicbox credentials for every supported source.

    ``None`` when no supported source has a key. ``or None``: the encrypted
    fields store an unset value as "", and comicbox's credentials spell unset
    as None. ``defaults`` is the ``ComicboxTaggingDefaults`` row, typed
    ``object`` for the reason ``configured_sources`` gives.
    """
    if not configured_sources(defaults):
        return None
    # Imported here: the session module loads comicbox's source modules, and
    # the Django settings import this one.
    from comicbox.online_session import OnlineCredentials

    return OnlineCredentials(
        **{field: getattr(defaults, field) or None for field in CREDENTIAL_FIELDS}
    )


def source_credentials(
    name: str, credentials: OnlineCredentials
) -> OnlineSourceCredentials:
    """Return one source's slice of ``credentials`` as comicbox's auth for it."""
    source = SOURCES.get(name)
    if source is None:
        # Never another source's key: an unregistered source gets no auth.
        return OnlineSourceCredentials()
    url = getattr(credentials, source.url_field) if source.url_field else None
    return OnlineSourceCredentials(
        key=getattr(credentials, source.key_field) or None, url=url or None
    )
