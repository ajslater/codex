import API from "@/api/v2/group";

const state = {
  md: undefined,
};

const getters = {};

const mutations = {
  setMetadata(state, md) {
    state.md = Object.seal(md);
  },
};

const actions = {
  async metadataOpened({ commit }, { group, pk }) {
    // Set the metadata store.
    commit("setMetadata", null);
    const response = await API.getMetadata(group, pk);
    commit("setMetadata", response.data);
  },
  metadataClosed({ commit }) {
    commit("setMetadata", null);
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
