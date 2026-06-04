"""
WebSocket typed message shapes.

The wire ships JSON envelopes ``{type, mtime, scope, ...}`` so
clients can route by ``type`` and read scope+mtime directly — no
extra ``loadMtimes()`` probe after a ``library.changed`` notification.

Broadcaster sites enrich :class:`codex.librarian.notifier.tasks.NotifierTask`
with ``mtime``/``scope`` when known; the channel-layer event
plumbing in :func:`codex.librarian.notifier.notifierd.NotifierThread._send_task`
forwards both fields onto the wire dict that
:class:`codex.websockets.consumers.NotifierConsumer` reads.
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
    Notifications.USERS.value: WebsocketMessages.USERS_CHANGED,
}

# Event types that carry ``mtime`` + ``scope`` enrichment on the wire.
# ``task.progress`` and ``tag-session.prompt`` are excluded — they ship
# their own payload shapes.
_ENRICHED_TYPES = frozenset(
    {
        WebsocketMessages.ADMIN_FLAGS_CHANGED,
        WebsocketMessages.BOOKMARK_CHANGED,
        WebsocketMessages.COVERS_CHANGED,
        WebsocketMessages.FAILED_IMPORTS_CHANGED,
        WebsocketMessages.GROUPS_CHANGED,
        WebsocketMessages.LIBRARY_CHANGED,
        WebsocketMessages.USERS_CHANGED,
    }
)


def typed_payload(
    text: str,
    mtime: int | None = None,
    scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a typed payload from a notification string + optional enrichment.

    Unknown ``text`` (no mapping entry) returns
    ``{type: "unknown", raw: text}`` so the frontend can log without
    crashing. ``mtime`` and ``scope`` are emitted only for event
    types that carry them; absent fields are ``null``/``{}``.
    """
    type_ = NOTIFICATION_TYPE_MAP.get(text, "unknown")
    payload: dict[str, Any] = {"type": type_}
    if type_ == "unknown":
        payload["raw"] = text
        return payload
    if type_ in _ENRICHED_TYPES:
        payload["mtime"] = mtime
        payload["scope"] = dict(scope) if scope else {}
    return payload
