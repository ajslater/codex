// Notifications and websockets
import { API_PREFIX } from "./base";

const getSocketURL = () => {
  let socketProto = "ws";
  if (window.location.protocol === "https:") {
    socketProto += "s";
  }
  return `${socketProto}://${location.host}${API_PREFIX}/ws`;
};
export const SOCKET_URL = getSocketURL(); // THIS MUST export itself

export default {
  SOCKET_URL,
};
