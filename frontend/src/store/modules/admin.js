import API from "@/api/v2/admin";

const state = {
  librarianStatuses: [],
  failedImports: false,
};

const mutations = {
  setLibrarianStatuses: (state, data) => {
    state.librarianStatuses = data;
  },
  setFailedImports: (state, data) => {
    state.failedImports = data;
  },
};

const isNotAdmin = function (rootGetters) {
  return !rootGetters["auth/isAdmin"];
};

const actions = {
  fetchLibrarianStatuses({ commit, rootGetters }) {
    if (isNotAdmin(rootGetters)) {
      return commit("setLibrarianStatuses", []);
    }
    API.getLibrarianStatuses()
      .then((response) => {
        return commit("setLibrarianStatuses", response.data);
      })
      .catch((error) => {
        return console.warn(error);
      });
  },
  setFailedImports({ commit, rootGetters }, data) {
    if (isNotAdmin(rootGetters)) {
      data = false;
    }
    return commit("setFailedImports", data);
  },
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
};
