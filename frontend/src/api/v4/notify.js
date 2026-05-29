/*
 * v4 WebSocket message shapes — see codex/websockets/payloads.py
 * for the backend-side source of truth and tasks/api-v4.md for the
 * design rationale.
 *
 * Stores migrate to this module by switching the WebSocket URL to
 * WS_URL_V4 and routing on ``payload.type`` instead of bare string
 * equality. The dispatch table below names every known type so a
 * regression (e.g. a renamed type) shows up as an unknown branch
 * rather than a silent miss. Unmapped notifications arrive as
 * ``{type: "unknown", raw: "<original string>"}`` so the default
 * branch can log them without crashing.
 *
 * Path is hardcoded for the same reason as the rest of the v4 client
 * (see frontend/src/api/v4/README.md): one mount point, fixed.
 */

const WS_PATH = "/api/v4/ws";

export const WS_URL_V4 = (() => {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}${WS_PATH}`;
})();

export const MESSAGE_TYPES = Object.freeze({
  ADMIN_FLAGS_CHANGED: "admin.flags.changed",
  BOOKMARK_CHANGED: "bookmark.changed",
  COVERS_CHANGED: "covers.changed",
  FAILED_IMPORTS_CHANGED: "failed-imports.changed",
  GROUPS_CHANGED: "groups.changed",
  LIBRARY_CHANGED: "library.changed",
  SESSION_ENDED: "session.ended",
  TAG_SESSION_PROMPT: "tag-session.prompt",
  TASK_PROGRESS: "task.progress",
  USERS_CHANGED: "users.changed",
});

/*
 * Parse a wire message into a v4 typed payload. The backend always
 * sends JSON for /api/v4/ws; this still tolerates the edge case
 * (e.g. heartbeat echoes) by returning null instead of throwing.
 */
export function parseV4Message(raw) {
  if (!raw) return undefined;
  try {
    const payload = JSON.parse(raw);
    if (payload && typeof payload === "object" && "type" in payload) {
      return payload;
    }
  } catch {
    /* not JSON — fall through */
  }
  return undefined;
}
