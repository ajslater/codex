import API from "@/api/v3/auth";

const state = {
  user: undefined,
  errors: [],
  success: undefined,
  adminFlags: {
    enableRegistration: undefined,
    enableNonUsers: undefined,
  },
};

const mutations = {
  setAdminFlags: (state, adminFlags) => {
    state.adminFlags = adminFlags;
  },
  setUser: (state, user) => {
    state.user = user;
  },
  setErrors: (state, axiosError) => {
    if (!axiosError) {
      state.errors = [];
      return;
    }
    const data = axiosError.response.data;
    let errors = [];
    for (const val of Object.values(data)) {
      if (val) {
        errors = Array.isArray(val) ? [...errors, ...val] : [...errors, val];
      }
    }
    if (errors.length === 0) {
      errors = ["Unknown error"];
    }
    state.errors = errors;
  },
  setSuccess: (state, success) => {
    state.success = success;
  },
};

const getters = {
  isAdmin: (state) => {
    return state.user && (state.user.isStaff || state.user.isSuperuser);
  },
  isOpenToSee: (state) => {
    return Boolean(state.user || state.adminFlags.enableNonUsers);
  },
  isLoggedIn: (state) => {
    return Boolean(state.user);
  },
};

const actions = {
  async setTimezone() {
    await API.setTimezone().catch((error) => {
      console.error(error);
    });
  },
  async getAdminFlags({ commit }) {
    await API.getAdminFlags()
      .then((response) => {
        return commit("setAdminFlags", response.data);
      })
      .catch((error) => {
        console.error(error);
      });
  },
  async register({ commit, dispatch }, credentials) {
    await API.register(credentials)
      .then(() => {
        return dispatch("login", credentials);
      })
      .catch((error) => {
        commit("setErrors", error);
      });
  },
  async login({ commit, dispatch }, credentials) {
    await API.login(credentials)
      .then(() => {
        return dispatch("getProfile");
      })
      .catch((error) => {
        commit("setErrors", error);
      });
  },
  async getProfile({ commit }) {
    return API.getProfile()
      .then((response) => {
        return commit("setUser", response.data);
      })
      .catch((error) => {
        console.debug(error);
      });
  },
  logout({ commit }) {
    API.logout()
      .then(() => {
        return commit("setUser");
      })
      .catch((error) => {
        console.error(error);
      });
  },
  async changePassword({ commit, dispatch, state }, credentials) {
    const username = state.user.username;
    const password = credentials.password;
    commit("setErrors");
    commit("setSuccess", "");
    await API.changePassword(credentials)
      .then((response) => {
        const success = response.data.detail;
        commit("setSuccess", success);
        const changedCredentials = {
          username: username,
          password: password,
        };
        return dispatch("login", changedCredentials);
      })
      .catch((error) => {
        commit("setErrors", error);
      });
  },
  clearErrors({ commit }) {
    commit("setErrors");
    commit("setSuccess", "");
  },
};

export default {
  namespaced: true,
  state,
  mutations,
  getters,
  actions,
};
