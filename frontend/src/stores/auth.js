import { defineStore } from "pinia";

import * as API from "@/api/v4/auth";
import { useCommonStore } from "@/stores/common";
import { useFavoritesStore } from "@/stores/favorites";

/*
 * Don't use router in here, perhaps called to early.
 * Breaks the prod build.
 */
export const useAuthStore = defineStore("auth", {
  state: () => ({
    adminFlags: {
      registration: undefined,
      registerVerification: undefined,
      nonUsers: undefined,
      bannerText: undefined,
      lazyImportMetadata: undefined,
      emailEnabled: undefined,
      remoteUserEnabled: undefined,
    },
    user: undefined,
    /*
     * Populated by the v4 ``/session`` composite alongside ``user`` +
     * ``adminFlags``. The SPA chrome reads ``version.installed``
     * immediately; ``latest`` / ``warning`` show up in the update-
     * available banner.
     */
    version: undefined,
    token: undefined,
    MIN_PASSWORD_LENGTH: 4,
    showLoginDialog: false,
    showChangePasswordDialog: false,
    showProfileDialog: false,
    showAuthTokenDialog: false,
    showResetPasswordRequestDialog: false,
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
      return (
        this.showLoginDialog ||
        this.showChangePasswordDialog ||
        this.showProfileDialog ||
        this.showResetPasswordRequestDialog
      );
    },
    isBanner(state) {
      return Boolean(state.adminFlags.bannerText);
    },
  },
  actions: {
    /*
     * v4 composite boot: one request returns user + adminFlags +
     * permissions + version. Use this on app start; the per-resource
     * loaders below stay around for explicit refreshes after admin
     * mutations (e.g. websocket fan-out of admin.flags.changed).
     */
    async loadSession() {
      try {
        const response = await API.getSession();
        const { user, adminFlags, version } = response.data || {};
        if (adminFlags) this.adminFlags = adminFlags;
        this.user = user || undefined;
        if (version) this.version = version;
        return true;
      } catch (error) {
        console.error(error);
      }
    },
    async loadAdminFlags() {
      try {
        const response = await API.getSession();
        const { adminFlags } = response.data || {};
        if (adminFlags) this.adminFlags = adminFlags;
        return true;
      } catch (error) {
        console.error(error);
      }
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
          return this.loadSession();
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
    async logout() {
      /*
       * The user clicked "log out" — clear client-side state
       * unconditionally so the menu and routes reflect the logged-
       * out state immediately. Surface API errors to the console
       * but don't let them block the local clear; the next
       * server-side request will either succeed against a fresh
       * session or 401 and prompt re-login.
       *
       * ``async`` so callers can ``await`` (they currently fire-
       * and-forget, but the menu's UI feedback would benefit from
       * knowing when the call resolves).
       */
      try {
        await API.logout();
      } catch (error) {
        console.error(error);
      } finally {
        this.user = undefined;
        /*
         * Wipe per-user favorite state so a different account
         * signing in next doesn't see the previous user's stars.
         */
        useFavoritesStore().clear();
      }
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
    /*
     * Update editable user-profile fields (username, email).
     * Only the changed fields are sent; an empty payload short-circuits.
     * On success, refresh the local user state so the menu and any
     * other consumers see the new value without a full reload.
     */
    async updateProfile(profile) {
      if (!profile || Object.keys(profile).length === 0) {
        return true;
      }
      const commonStore = useCommonStore();
      return API.updateProfile(profile)
        .then((response) => {
          this.user = response.data;
          commonStore.clearErrors();
          return true;
        })
        .catch((error) => {
          commonStore.setErrors(error);
          return false;
        });
    },
    async sendResetPasswordLink(login) {
      const commonStore = useCommonStore();
      return API.sendResetPasswordLink(login)
        .then((response) => {
          commonStore.setSuccess(response.data.detail);
          return true;
        })
        .catch((error) => {
          commonStore.setErrors(error);
          return false;
        });
    },
    async resetPassword(payload) {
      const commonStore = useCommonStore();
      return API.resetPassword(payload)
        .then((response) => {
          commonStore.setSuccess(response.data.detail);
          return true;
        })
        .catch((error) => {
          commonStore.setErrors(error);
          return false;
        });
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
