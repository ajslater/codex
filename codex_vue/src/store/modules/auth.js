import API from "@/api/auth";

const state = {
  user: undefined,
  form: {
    usernameErrors: undefined,
    passwordErrors: undefined,
    error: undefined,
  },
  enableRegistration: false,
  adminURL: "",
};

const mutations = {
  setRegisterEnabled: (state, data) => {
    state.enableRegistration = data.enableRegistration;
  },
  setLoginInfo: (state, user) => {
    state.adminURL = user.adminURL;
    if (user) {
      delete user["adminURL"];
    }
    state.user = user;
  },
  setErrors: (state, data) => {
    state.form.usernameErrors = data.username;
    state.form.passwordErrors = data.password;
    state.form.error = data.detail;
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
        commit("setLoginInfo", response.data);
        return response;
      })
      .catch((error) => {
        commit("setErrors", error.response.data);
      });
  },
  async login({ commit }, credentials) {
    await API.login(credentials)
      .then((response) => {
        commit("setLoginInfo", response.data);
        return response;
      })
      .catch((error) => {
        commit("setErrors", error.response.data);
      });
  },
  async me({ commit }) {
    await API.me()
      .then((response) => {
        commit("setLoginInfo", response.data);
        return response;
      })
      .catch((error) => {
        console.log(error.response.data);
      });
  },
  logout({ commit }) {
    API.logout().catch((error) => {
      console.error(error);
    });
    commit("setLoginInfo", undefined);
  },
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
};
