// Notifications and websockets
const getSocketURL = () => {
  let socketProto = "ws";
  if (globalThis.location.protocol === "https:") {
    socketProto += "s";
  }
  return `${socketProto}://${location.host}${globalThis.CODEX.API_V3_PATH}ws`;
};
export const SOCKET_URL = getSocketURL(); // This MUST export itself

export default {
  SOCKET_URL,
};
