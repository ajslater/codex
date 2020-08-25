import API from "@/api/metadata";

const state = {
  comic: undefined,
};

const getters = {};

const mutations = {
  setComicMetadata(state, md) {
    state.comic = md;
  },
};

const actions = {
  async comicMetadataOpened({ commit }, pk) {
    // Set the metadata store.
    const response = await API.getComicMetadata(pk);
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
