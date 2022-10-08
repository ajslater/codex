import { defineStore } from "pinia";

import API from "@/api/v3/auth";
import { useCommonStore } from "@/stores/common";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    adminFlags: {
      enableRegistration: undefined,
      enableNonUsers: undefined,
    },
    user: undefined,
    MIN_PASSWORD_LENGTH: 4,
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
    async loadAdminFlags() {
      await API.getAdminFlags()
        .then((response) => {
          this.adminFlags = response.data;
          return true;
        })
        .catch(console.error);
    },
    async loadProfile() {
      return API.getProfile()
        .then((response) => {
          this.user = response.data;
          return true;
        })
        .catch(console.debug);
    },
    async login(credentials, clear = true) {
      const commonStore = useCommonStore();
      await API.login(credentials)
        .then(() => {
          if (clear) {
            commonStore.clearErrors();
          }
          return this.loadProfile();
        })
        .catch(commonStore.setErrors);
    },
    async register(credentials) {
      const commonStore = useCommonStore();
      await API.register(credentials)
        .then(() => {
          commonStore.clearErrors();
          return this.login(credentials);
        })
        .catch(commonStore.setErrors);
    },
    logout() {
      API.logout()
        .then(() => {
          this.user = undefined;
          return true;
        })
        .catch(console.error);
    },
    async changePassword(credentials) {
      const changedCredentials = {
        username: this.user.username,
        password: credentials.password,
      };
      const commonStore = useCommonStore();
      await API.changePassword(credentials)
        .then((response) => {
          commonStore.setSuccess(response.data.detail);
          return this.login(changedCredentials, false);
        })
        .catch(commonStore.setErrors);
    },
    async setTimezone() {
      await API.setTimezone().catch(console.error);
    },
  },
});
