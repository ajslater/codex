import API from "@/api/v2/group";

const state = {
  md: undefined,
  timestamp: Date.now(),
};

const getters = {};

const mutations = {
  setMetadata(state, md) {
    state.md = Object.seal(md);
  },
  setTimestamp(state) {
    state.timestamp = Date.now();
  },
};

const actions = {
  async metadataOpened({ commit }, { group, pk }) {
    // Set the metadata store.
    await API.getMetadata(group, pk)
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
