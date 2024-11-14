"""Notification messages."""

from enum import Enum


class Notifications(Enum):
    """Websocket Notifications."""

    ADMIN_FLAGS = "ADMIN_FLAGS_CHANGED"
    BOOKMARK = "BOOKMARK_CHANGED"
    COVERS = "COVERS_CHANGED"
    FAILED_IMPORTS = "FAILED_IMPORTS"
    GROUPS = "GROUPS_CHANGED"
    LIBRARY = "LIBRARY_CHANGED"
    LIBRARIAN_STATUS = "LIBRARIAN_STATUS"
    USERS = "USERS_CHANGED"
