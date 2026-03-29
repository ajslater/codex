"""OPDS Browser mixins."""

from abc import ABC

from codex.models.settings import ClientChoices
from codex.views.opds.auth import OPDSAuthMixin


class OPDSSettingsMixin(OPDSAuthMixin, ABC):
    """OPDS View isolates OPDS settings data."""

    CLIENT = ClientChoices.OPDS
    BROWSER_CLIENT = ClientChoices.OPDS


class OPDSBrowserSettingsMixin(OPDSSettingsMixin):
    """OPDS Browser Settings Mixin."""
