import API from "@/api/v1/notify";

const MIN_SCAN_WAIT = 5 * 1000;
const MAX_SCAN_WAIT = 10 * 1000;
const SCAN_WAIT_DELTA = MAX_SCAN_WAIT - MIN_SCAN_WAIT;

export const NOTIFY_STATES = {
  OFF: 0,
  CHECK: 1,
  SCANNING: 2,
  FAILED: 3,
  DISMISSED: 4,
};

const state = {
  notify: "OFF",
};

const mutations = {
  setNotify: (state, data) => {
    state.notify = data;
  },
};

const STICKY_STATES = new Set([NOTIFY_STATES.DISMISSED, NOTIFY_STATES.FAILED]);

const notifyCheck = (commit, state) => {
  if (STICKY_STATES.has(state.notify)) {
    // If we have a sticky notification keep it.
    return;
  }

  API.getScanInProgress()
    .then((response) => {
      const data = response.data;
      let notify;
      if (data.scanInProgress) {
        notify = NOTIFY_STATES.SCANNING;
      } else {
        notify = NOTIFY_STATES.OFF;
      }
      if (STICKY_STATES.has(state.notify)) {
        // If we received a sticky notification in the mean time, keep it.
        return;
      }
      commit("setNotify", notify);
      if (state.notify != NOTIFY_STATES.SCANNING) {
        // If we're not scanning don't keep checking.
        return;
      }

      // polite client thundering herd control
      const wait = Math.floor(Math.random() * SCAN_WAIT_DELTA + MIN_SCAN_WAIT);
      return setTimeout(async () => {
        return notifyCheck(commit, state);
      }, wait);
    })
    .catch((error) => {
      console.error(error);
      return console.warn("notifyCheck() Response", error.response);
    });
};

const SUBSCRIBE_MESSAGES = {
  admin: JSON.stringify({
    type: "subscribe",
    register: true,
    admin: true,
  }),
  user: JSON.stringify({ type: "subscribe", register: true }),
  unsub: JSON.stringify({ type: "subscribe", register: false }),
};

const actions = {
  setNotify({ commit, state }, data) {
    commit("setNotify", data);
    notifyCheck(commit, state);
  },
  subscribe({ rootGetters }) {
    // This is sort of irregular but works
    const ws = this._vm.$socket;
    if (!ws || ws.readyState != 1) {
      console.debug("No ready socket. Not subscribing to notifications.");
      return;
    }
    const isAdmin = rootGetters["auth/isAdmin"];
    const isOpenToSee = rootGetters["auth/isOpenToSee"];
    if (isAdmin) {
      console.debug("subscribing to admin notifications.");
      ws.send(SUBSCRIBE_MESSAGES.admin);
    } else if (isOpenToSee) {
      console.debug("subscribing to notifications.");
      ws.send(SUBSCRIBE_MESSAGES.user);
    } else {
      console.debug("unsubscribing from notifications");
      ws.send(SUBSCRIBE_MESSAGES.unsub);
    }
  },
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
};
