import { defineStore } from "pinia";

import API from "@/api/v3/auth";
import { useCommonStore } from "@/stores/common";

/*
 * Don't use router in here, perhaps called to early.
 * Breaks the prod build.
 */
export const useAuthStore = defineStore("auth", {
  state: () => ({
    adminFlags: {
      registration: undefined,
      nonUsers: undefined,
      bannerText: undefined,
      lazyImportMetadata: undefined,
    },
    user: undefined,
    token: undefined,
    MIN_PASSWORD_LENGTH: 4,
    showLoginDialog: false,
    showChangePasswordDialog: false,
    showAuthTokenDialog: false,
  }),
  getters: {
    isAuthorized() {
      return Boolean(this.user || this.adminFlags.nonUsers);
    },
    isAuthChecked() {
      return (
        this.user !== undefined || this.adminFlags.registration !== undefined
      );
    },
    isUserAdmin() {
      return this.user && (this.user.isStaff || this.user.isSuperuser);
    },
    isAuthDialogOpen() {
      return this.showLoginDialog || this.showChangePasswordDialog;
    },
    isBanner(state) {
      return Boolean(state.adminFlags.bannerText);
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
      await API.updatePassword(credentials)
        .then((response) => {
          commonStore.setSuccess(response.data.detail);
          return this.login(changedCredentials, false);
        })
        .catch(commonStore.setErrors);
    },
    async setTimezone() {
      if (this.adminFlags.nonUsers || this.user) {
        await API.updateTimezone().catch(console.error);
      }
    },
    async getToken() {
      await API.getToken()
        .then((response) => (this.token = response.data.token))
        .catch(console.error);
    },
    async updateToken() {
      await API.updateToken()
        .then((response) => (this.token = response.data.token))
        .catch(console.error);
    },
  },
});
