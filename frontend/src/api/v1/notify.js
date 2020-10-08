// Notifications and websockets
import { ajax, API_PREFIX, ROOT_PATH } from "./base";
import { BROWSE_BASE } from "./browser";

export const FAILED_IMPORT_URL = `${ROOT_PATH}admin/codex/failedimport/`;
const getScanInProgress = () => {
  return ajax("get", `${BROWSE_BASE}/scan_notify`);
};

const getSocketURL = () => {
  let socketProto = "ws";
  if (window.location.protocol === "https:") {
    socketProto += "s";
  }
  return `${socketProto}://${location.host}${API_PREFIX}/ws`;
};
export const SOCKET_URL = getSocketURL();

export default {
  getScanInProgress,
};
