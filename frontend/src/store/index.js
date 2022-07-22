import Vue from "vue";
import Vuex from "vuex";

import admin from "./modules/admin";
import auth from "./modules/auth";
import browser from "./modules/browser";
import metadata from "./modules/metadata";
import reader from "./modules/reader";
import socket from "./modules/socket";

Vue.use(Vuex);

const debug = process.env.NODE_ENV !== "production";

// vue-native-websockets doesn't put socket mutations in its own module :/
const mutations = {
  ...socket.mutations,
};

const modules = { admin, auth, browser, metadata, reader, socket };

// eslint-disable-next-line import/no-named-as-default-member
export default new Vuex.Store({
  mutations,
  modules,
  strict: debug,
});
