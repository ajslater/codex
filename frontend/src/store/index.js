import Vue from "vue";
import Vuex from "vuex";

import auth from "./modules/auth";
import browser from "./modules/browser";
import metadata from "./modules/metadata";
import notify from "./modules/notify";
import reader from "./modules/reader";
import socket from "./socket";

Vue.use(Vuex);

const debug = process.env.NODE_ENV !== "production";

// vue-native-websockets doesn't put socket stuff in its own module :/
const state = {
  socket: socket.state,
};

const mutations = {
  ...socket.mutations,
};

const actions = {};
const modules = { auth, browser, metadata, notify, reader };

export default new Vuex.Store({
  state,
  mutations,
  actions,
  modules,
  strict: debug,
});
