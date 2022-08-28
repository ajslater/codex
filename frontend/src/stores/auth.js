import { defineStore } from "pinia";

import API from "@/api/v3/auth";
export const useAuthStore = defineStore("auth", {
  state: () => ({
    adminFlags: {
      enableRegistration: undefined,
      enableNonUsers: undefined,
    },
    user: undefined,
    errors: [],
    success: undefined,
  }),
  getters: {
    isCodexViewable() {
      return Boolean(this.user || this.adminFlags.enableNonUsers);
    },
    isUserAdmin() {
      return this.user && (this.user.isStaff || this.user.isSuperuser);
    },
  },
  actions: {
    setErrors(axiosError) {
      let errors = [];
      if (!axiosError) {
        this.errors = errors;
        return;
      }
      const data = axiosError.response.data;
      for (const val of Object.values(data)) {
        if (val) {
          errors = Array.isArray(val) ? [...errors, ...val] : [...errors, val];
        }
      }
      if (errors.length === 0) {
        errors = ["Unknown error"];
      }
      this.errors = errors;
    },
    async loadAdminFlags() {
      await API.getAdminFlags()
        .then((response) => {
          this.adminFlags = response.data;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    async loadProfile() {
      return API.getProfile()
        .then((response) => {
          this.user = response.data;
          return true;
        })
        .catch((error) => {
          console.debug(error);
        });
    },
    async login(credentials) {
      await API.login(credentials)
        .then(() => {
          return this.loadProfile();
        })
        .catch((error) => {
          this.setErrors(error);
        });
    },
    async register(credentials) {
      await API.register(credentials)
        .then(() => {
          return this.login(credentials);
        })
        .catch((error) => {
          this.setErrors(error);
        });
    },
    logout() {
      API.logout()
        .then(() => {
          this.user = undefined;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    clearErrors() {
      this.$patch((state) => {
        state.errors = [];
        state.success = "";
      });
    },
    async changePassword(credentials) {
      const username = this.user.username;
      const password = credentials.password;
      this.clearErrors();
      await API.changePassword(credentials)
        .then((response) => {
          this.success = response.data.detail;
          const changedCredentials = {
            username: username,
            password: password,
          };
          return this.login(changedCredentials);
        })
        .catch((error) => {
          this.setErrors(error);
        });
    },
    async setTimezone() {
      await API.setTimezone().catch((error) => {
        console.error(error);
      });
    },
  },
});
