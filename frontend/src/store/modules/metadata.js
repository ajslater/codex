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
