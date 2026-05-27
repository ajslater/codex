"""
v4 WebSocket typed message shapes.

The v3 wire format sends bare strings (``"LIBRARY"``, ``"COVERS"``,
etc.) and the frontend infers what to refetch. v4 ships JSON
envelopes ``{type, ...payload}`` so clients can route by ``type`` and
read payload fields directly. Eventually broadcasters emit these
shapes natively; until then :class:`V4NotifierConsumer` translates v3
events on the wire (see ``v4_consumers.py``).
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


def v3_to_v4_payload(text: str) -> dict[str, Any]:
    """
    Translate a bare v3 notification string to a v4 typed payload.

    The v3 broadcaster doesn't carry ``mtime`` or ``scope`` data, so
    the translated payload leaves those fields ``null``/empty. The
    frontend still has to issue its mtime probe for now — see Phase 6
    in ``tasks/api-v4.md`` for the follow-up that updates the
    broadcasters to populate scope/mtime natively.
    """
    type_ = V3_TYPE_MAP.get(text, "unknown")
    payload: dict[str, Any] = {"type": type_}
    if type_ == "unknown":
        payload["v3"] = text
        return payload
    if type_ == "library.changed":
        payload["mtime"] = None
        payload["scope"] = {}
    elif type_ == "covers.changed":
        payload["scope"] = {}
    return payload
