import API from "@/api/v2/admin";

const state = {
  librarianStatuses: [],
  failedImports: [],
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
}

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
  fetchFailedImports({ commit, rootGetters }) {
    if (isNotAdmin(rootGetters)) {
      return commit("setFailedImports", []);
    }
    API.getFailedImports()
      .then((response) => {
        return commit("setFailedImports", response.data);
      })
      .catch((error) => {
        return console.warn(error);
      });
  },
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
};
