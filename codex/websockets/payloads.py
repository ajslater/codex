"""
WebSocket typed message shapes.

The wire ships a minimal ``{type}`` envelope so clients route by
``type``. A notification only signals that a class of thing changed;
the client reacts on its own (probe ``/api/v4/mtime``, reload a table).
Unknown ``type`` strings are forwarded as ``{type: "unknown", raw}`` so
the frontend can log them without crashing.
"""

from collections.abc import Mapping
from typing import Any

from codex.choices.notifications import Notifications, WebsocketMessages

# Plain-string notification → ``type`` key on the typed payload. Anything
# not in the map is forwarded as ``{type: "unknown", raw: "<str>"}`` so
# the frontend can log it without crashing.
NOTIFICATION_TYPE_MAP: Mapping[str, WebsocketMessages] = {
    Notifications.ADMIN_FLAGS.value: WebsocketMessages.ADMIN_FLAGS_CHANGED,
    Notifications.BOOKMARK.value: WebsocketMessages.BOOKMARK_CHANGED,
    Notifications.COVERS.value: WebsocketMessages.COVERS_CHANGED,
    Notifications.FAILED_IMPORTS.value: WebsocketMessages.FAILED_IMPORTS_CHANGED,
    Notifications.GROUPS.value: WebsocketMessages.GROUPS_CHANGED,
    Notifications.LIBRARY.value: WebsocketMessages.LIBRARY_CHANGED,
    Notifications.LIBRARIAN_STATUS.value: WebsocketMessages.TASK_PROGRESS,
    Notifications.ONLINE_TAG_PROMPT.value: WebsocketMessages.TAG_SESSION_PROMPT,
    Notifications.TAG_WRITE_ERRORS.value: WebsocketMessages.TAG_WRITE_ERRORS_CHANGED,
    Notifications.USERS.value: WebsocketMessages.USERS_CHANGED,
}


def typed_payload(text: str) -> dict[str, Any]:
    """
    Build a typed payload from a notification string.

    Unknown ``text`` (no mapping entry) returns
    ``{type: "unknown", raw: text}`` so the frontend can log without
    crashing.
    """
    type_ = NOTIFICATION_TYPE_MAP.get(text, "unknown")
    payload: dict[str, Any] = {"type": type_}
    if type_ == "unknown":
        payload["raw"] = text
    return payload
