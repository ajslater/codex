import API from "@/api/v2/notify";

const MIN_NOTIFY_CHECK_WAIT = 5 * 1000;
const MAX_NOTIFY_CHECK_WAIT = 10 * 1000;
const NOTIFY_CHECK_WAIT_DELTA = MAX_NOTIFY_CHECK_WAIT - MIN_NOTIFY_CHECK_WAIT;

export const NOTIFY_STATES = {
  OFF: 1,
  CHECK: 2,
  LIBRARY_UPDATING: 3,
  FAILED: 4,
  DISMISSED: 5,
};

const state = {
  notify: NOTIFY_STATES.OFF,
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
  API.getUpdateInProgress()
    .then((response) => {
      const data = response.data;
      let notify;
      notify = data.updateInProgress
        ? NOTIFY_STATES.LIBRARY_UPDATING
        : NOTIFY_STATES.OFF;
      if (STICKY_STATES.has(state.notify)) {
        // If we received a sticky notification in the mean time, keep it.
        return;
      }
      commit("setNotify", notify);
      if (state.notify != NOTIFY_STATES.LIBRARY_UPDATING) {
        // If we're not updating don't keep checking.
        return;
      }

      // polite client thundering herd control
      const wait = Math.floor(
        Math.random() * NOTIFY_CHECK_WAIT_DELTA + MIN_NOTIFY_CHECK_WAIT
      );
      return setTimeout(async () => {
        return notifyCheck(commit, state);
      }, wait);
    })
    .catch((error) => {
      return console.warn(error);
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
  notifyChanged({ commit, state }, data) {
    commit("setNotify", data);
    notifyCheck(commit, state);
  },
  subscribe({ rootGetters }) {
    const ws = this._vm.$socket;
    if (!ws || ws.readyState != 1) {
      console.debug("No ready socket. Not subscribing to notifications.");
      return;
    }
    const isAdmin = rootGetters["auth/isAdmin"];
    if (isAdmin) {
      ws.send(SUBSCRIBE_MESSAGES.admin);
      return;
    }
    const isOpenToSee = rootGetters["auth/isOpenToSee"];
    if (isOpenToSee) {
      ws.send(SUBSCRIBE_MESSAGES.user);
      return;
    }
    // else
    ws.send(SUBSCRIBE_MESSAGES.unsub);
  },
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
};
