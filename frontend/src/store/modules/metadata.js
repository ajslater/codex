import API from "@/api/v1/metadata";

const state = {
  comic: undefined,
};

const getters = {};

const mutations = {
  setComicMetadata(state, md) {
    state.comic = Object.freeze(md);
  },
};

const actions = {
  async comicMetadataOpened({ commit }, { group, pk }) {
    // Set the metadata store.
    commit("setComicMetadata", null);
    const response = await API.getComicMetadata(group, pk);
    commit("setComicMetadata", response.data);
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
