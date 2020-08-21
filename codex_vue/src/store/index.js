import Vue from "vue";
import Vuex from "vuex";

import auth from "./modules/auth";
import browser from "./modules/browser";
import metadata from "./modules/metadata";
import reader from "./modules/reader";

Vue.use(Vuex);

const debug = process.env.NODE_ENV !== "production";

export default new Vuex.Store({
  state: {},
  mutations: {},
  actions: {},
  modules: { auth, browser, metadata, reader },
  strict: debug,
});
