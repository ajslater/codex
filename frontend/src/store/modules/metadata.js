import API from "@/api/v2/group";

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
    const ts = rootState.browser.timestamp;
    // Set the metadata store.
    await API.getMetadata({ group, pk }, ts)
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
