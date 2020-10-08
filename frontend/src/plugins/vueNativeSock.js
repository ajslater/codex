import store from "@/store";

export const SOCKET_OPTIONS = {
  connectManually: true, // So the ONOPEN message occurs after store is created
  reconnection: true,
  store: store,
};

export default {
  SOCKET_OPTIONS,
};
