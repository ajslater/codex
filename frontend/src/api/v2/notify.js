// Notifications and websockets
const getSocketURL = () => {
  let socketProto = "ws";
  if (window.location.protocol === "https:") {
    socketProto += "s";
  }
  return `${socketProto}://${location.host}${window.CODEX.API_V2_PATH}/ws`;
};
export const SOCKET_URL = getSocketURL(); // THIS MUST export itself

export default {
  SOCKET_URL,
};
