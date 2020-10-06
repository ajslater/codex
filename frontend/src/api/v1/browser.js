import ReconnectingWebSocket from "reconnecting-websocket";

import { ajax, API_PREFIX, ROOT_PATH } from "./base";

const BROWSE_BASE = "/browse";
const ADMIN_SUFFIX = "/a";

const debug = process.env.NODE_ENV !== "production";

// REST ENDPOINTS

const getBrowserOpened = ({ group, pk, page }) => {
  return ajax("get", `${BROWSE_BASE}/${group}/${pk}/${page}`);
};

const getBrowserPage = ({ route, settings }) => {
  const { group, pk, page } = route;
  return ajax("put", `${BROWSE_BASE}/${group}/${pk}/${page}`, settings);
};

const getBrowserChoices = ({ group, pk, choice_type }) => {
  return ajax("get", `${BROWSE_BASE}/${group}/${pk}/choices/${choice_type}`);
};

const setMarkRead = ({ group, pk, finished }) => {
  return ajax("patch", `${BROWSE_BASE}/${group}/${pk}/mark_read`, {
    finished,
  });
};

const getScanInProgress = () => {
  return ajax("get", `${BROWSE_BASE}/scan_notify`);
};

// STATIC PATHS

const MISSING_COVER_PATH = `${ROOT_PATH}static/img/missing_cover.png`;
export const getCoverSrc = (coverPath) => {
  if (coverPath == "missing_cover.png") {
    return MISSING_COVER_PATH;
  }
  return `${ROOT_PATH}covers/${coverPath}`;
};

export const FAILED_IMPORT_URL = `${ROOT_PATH}admin/codex/failedimport/`;

// WEBSOCKETS

const WS_URL = `${location.host}${API_PREFIX}/ws`;
const WS_TIMEOUT = 19000;

const keepAlive = (ws) => {
  if (ws.OPEN) {
    // websocket receiver requires json. send the minimal as a ping.
    ws.send("{}");
  }
  setTimeout(() => keepAlive(ws), WS_TIMEOUT);
};

// websocket only used for the browser now.
export const getSocket = (isAdmin) => {
  let socketProto = "ws";
  if (window.location.protocol === "https:") {
    // this should never happen. use a webserver to terminate ssl.t s
    socketProto += "s";
  }
  let socketURI = `${socketProto}://${WS_URL}`;
  if (isAdmin) {
    socketURI += ADMIN_SUFFIX;
  }

  const ws = new ReconnectingWebSocket(socketURI, undefined, {
    debug,
  });
  keepAlive(ws);
  return ws;
};

export default {
  getBrowserOpened,
  getBrowserPage,
  getBrowserChoices,
  getScanInProgress,
  setMarkRead,
  getSocket,
  FAILED_IMPORT_URL,
};
