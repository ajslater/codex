"""Online tagging status types."""

from abc import ABC

from codex.librarian.status import Status


class OnlineTagStatus(Status, ABC):
    """Online tagging statii base."""


class OnlineLookupStatus(OnlineTagStatus):
    """Online tag lookup progress."""

    CODE = "OTG"
    ITEM_NAME = "online tags"
    VERB = "Look up"
    _verbed = "Looked up"


class OnlinePromptStatus(OnlineTagStatus):
    """Prompts awaiting admin resolution."""

    CODE = "OTP"
    ITEM_NAME = "prompts pending"
    VERB = "Await"
    _verbed = "Resolved"
    SINGLE = True


ONLINETAG_STATII = (OnlineLookupStatus, OnlinePromptStatus)
