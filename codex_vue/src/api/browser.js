import ReconnectingWebSocket from "reconnecting-websocket";

import { ajax } from "./base";

const BROWSE_BASE = "/browse";

const debug = process.env.NODE_ENV !== "production";

const getBrowseOpened = ({ group, pk }) => {
  return ajax("get", `${BROWSE_BASE}/${group}/${pk}`);
};

const getBrowseObjects = ({ group, pk, settings }) => {
  return ajax("put", `${BROWSE_BASE}/${group}/${pk}`, settings);
};

const setMarkRead = ({ group, pk, finished }) => {
  return ajax("patch", `${BROWSE_BASE}/${group}/${pk}/mark_read`, {
    finished,
  });
};

// websocket only used for the browser now.
export const getSocket = () => {
  let socket_proto = "ws";
  if (window.location.protocol === "https:") {
    socket_proto += "s";
  }
  const socket_uri = `${socket_proto}://${location.host}`;
  return new ReconnectingWebSocket(socket_uri, undefined, {
    debug,
  });
};

export default {
  getBrowseOpened,
  getBrowseObjects,
  setMarkRead,
  getSocket,
};
