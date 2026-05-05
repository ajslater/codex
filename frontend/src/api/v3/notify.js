// Notifications and websockets
export const WS_PATH = `${globalThis.CODEX.API_V3_PATH}ws`;
function getSocketURL() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${window.location.host}${WS_PATH}`;
  console.debug("[socket] Connecting...");
  return url;
}
export const WS_URL = getSocketURL(); // This MUST export itself
