"""Notification messages."""

from enum import Enum, StrEnum


class Notifications(Enum):
    """Websocket Notifications."""

    ADMIN_FLAGS = "ADMIN_FLAGS_CHANGED"
    BOOKMARK = "BOOKMARK_CHANGED"
    COVERS = "COVERS_CHANGED"
    FAILED_IMPORTS = "FAILED_IMPORTS"
    GROUPS = "GROUPS_CHANGED"
    LIBRARY = "LIBRARY_CHANGED"
    LIBRARIAN_STATUS = "LIBRARIAN_STATUS"
    ONLINE_TAG_PROMPT = "ONLINE_TAG_PROMPT"
    USERS = "USERS_CHANGED"


class WebsocketMessages(StrEnum):
    """
    v4 typed WebSocket ``type`` values.

    Single source of truth for both the backend bridge map
    (:data:`codex.websockets.payloads.NOTIFICATION_TYPE_MAP`) and the
    frontend dispatch table (``frontend/src/api/v4/notify.js``), which
    imports the generated ``websocket-messages.json``. Member names are
    the JS keys; member values are the wire ``type`` strings.
    """

    ADMIN_FLAGS_CHANGED = "admin.flags.changed"
    BOOKMARK_CHANGED = "bookmark.changed"
    COVERS_CHANGED = "covers.changed"
    FAILED_IMPORTS_CHANGED = "failed-imports.changed"
    GROUPS_CHANGED = "groups.changed"
    LIBRARY_CHANGED = "library.changed"
    TAG_SESSION_PROMPT = "tag-session.prompt"
    TASK_PROGRESS = "task.progress"
    USERS_CHANGED = "users.changed"
