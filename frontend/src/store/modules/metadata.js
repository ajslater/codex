import API from "@/api/v3/browser";

const state = {
  md: undefined,
};

const getters = {};

const mutations = {
  setMetadata(state, md) {
    if (md) {
      md.pk = md.id;
    }
    state.md = Object.seal(md);
  },
};

const actions = {
  async metadataOpened({ commit, rootState }, { group, pk }) {
    // Use the browser's timestamp
    // Set the metadata store.
    const queryParams = {
      ...rootState.browser.settings,
      ts: rootState.browser.timestamp,
      show: rootState.browser.show,
    };
    await API.getMetadata({ group, pk }, queryParams)
      .then((response) => {
        return commit("setMetadata", response.data);
      })
      .catch((error) => {
        console.error(error);
        commit("setMetadata");
      });
  },
  metadataClosed({ commit }) {
    commit("setMetadata");
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
