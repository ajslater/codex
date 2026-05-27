"""
v4 WebSocket typed message shapes.

The v3 wire format sent bare strings (``"LIBRARY"``, ``"COVERS"``,
etc.) and the frontend inferred what to refetch. v4 ships JSON
envelopes ``{type, mtime, scope, ...}`` so clients can route by
``type`` and read scope+mtime directly — no extra ``loadMtimes()``
probe after a ``library.changed`` notification.

Broadcaster sites enrich :class:`codex.librarian.notifier.tasks.NotifierTask`
with ``mtime``/``scope`` when known; the channel-layer event
plumbing in :func:`codex.librarian.notifier.notifierd.NotifierThread._send_task`
forwards both fields onto the wire dict that
:class:`codex.websockets.v4_consumers.V4NotifierConsumer` reads.
"""

from collections.abc import Mapping
from typing import Any

from codex.choices.notifications import Notifications

# v3 plain-string notification → v4 ``type`` key. Anything not in the
# map is forwarded as ``{type: "unknown", v3: "<str>"}`` so the
# frontend can log it without crashing.
V3_TYPE_MAP: Mapping[str, str] = {
    Notifications.ADMIN_FLAGS.value: "admin.flags.changed",
    Notifications.BOOKMARK.value: "bookmark.changed",
    Notifications.COVERS.value: "covers.changed",
    Notifications.FAILED_IMPORTS.value: "failed-imports.changed",
    Notifications.GROUPS.value: "groups.changed",
    Notifications.LIBRARY.value: "library.changed",
    Notifications.LIBRARIAN_STATUS.value: "task.progress",
    Notifications.ONLINE_TAG_PROMPT.value: "tag-session.prompt",
    Notifications.USERS.value: "users.changed",
}

# Event types that always carry an ``mtime`` field on the v4 wire.
# Other types omit it.
_MTIME_TYPES = frozenset(
    {
        "admin.flags.changed",
        "bookmark.changed",
        "covers.changed",
        "failed-imports.changed",
        "groups.changed",
        "library.changed",
        "users.changed",
    }
)

# Event types that always carry a ``scope`` dict on the v4 wire.
# Listed separately from ``_MTIME_TYPES`` because ``task.progress``
# and ``tag-session.prompt`` ship their own payload shapes.
_SCOPE_TYPES = frozenset(
    {
        "admin.flags.changed",
        "bookmark.changed",
        "covers.changed",
        "failed-imports.changed",
        "groups.changed",
        "library.changed",
        "users.changed",
    }
)


def v3_to_v4_payload(
    text: str,
    mtime: int | None = None,
    scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Translate a v3 notification string + enrichment to a typed v4 payload.

    Unknown ``text`` (no mapping entry) returns
    ``{type: "unknown", v3: text}`` so the frontend can log without
    crashing. ``mtime`` and ``scope`` are emitted only for event
    types that carry them; absent fields are ``null``/``{}``.
    """
    type_ = V3_TYPE_MAP.get(text, "unknown")
    payload: dict[str, Any] = {"type": type_}
    if type_ == "unknown":
        payload["v3"] = text
        return payload
    if type_ in _MTIME_TYPES:
        payload["mtime"] = mtime
    if type_ in _SCOPE_TYPES:
        payload["scope"] = dict(scope) if scope else {}
    return payload
