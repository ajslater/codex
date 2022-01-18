import API from "@/api/v2/auth";

const state = {
  user: undefined,
  form: {
    usernameErrors: undefined,
    passwordErrors: undefined,
    error: undefined,
  },
  enableRegistration: false,
  enableNonUsers: undefined,
};

const mutations = {
  setRegisterEnabled: (state, data) => {
    state.enableRegistration = data.enableRegistration;
  },
  setUser: (state, value) => {
    let user = value;
    if (user) {
      state.enableNonUsers = user.enableNonUsers;
      if (!user.pk) {
        user = undefined;
      } else {
        delete user.enableNonUsers;
      }
    }
    state.user = user;
  },
  setErrors: (state, data) => {
    state.form.usernameErrors = data.username;
    state.form.passwordErrors = data.password;
    state.form.error = data.detail;
  },
};

const getters = {
  isAdmin: (state) => {
    return state.user && (state.user.is_staff || state.user.is_superuser);
  },
  isOpenToSee: (state) => {
    return Boolean(state.user || state.enableNonUsers);
  },
  isLoggedIn: (state) => {
    return Boolean(state.user);
  },
};

const actions = {
  async loginDialogOpened({ commit }) {
    await API.registerEnabled()
      .then((response) => {
        commit("setRegisterEnabled", response.data);
        return response;
      })
      .catch((error) => {
        console.error(error);
      });
  },
  async register({ commit }, credentials) {
    await API.register(credentials)
      .then((response) => {
        commit("setUser", response.data);
        return response;
      })
      .catch((error) => {
        commit("setErrors", error.response.data);
      });
  },
  async login({ commit }, credentials) {
    await API.login(credentials)
      .then((response) => {
        commit("setUser", response.data);
        return response;
      })
      .catch((error) => {
        commit("setErrors", error.response.data);
      });
  },
  async me({ commit }) {
    await API.me()
      .then((response) => {
        commit("setUser", response.data);
        return response;
      })
      .catch((error) => {
        return console.debug(error.response.data);
      });
  },
  logout({ commit }) {
    API.logout().catch((error) => {
      console.error(error);
    });
    commit("setUser");
  },
};

export default {
  namespaced: true,
  state,
  mutations,
  getters,
  actions,
};
