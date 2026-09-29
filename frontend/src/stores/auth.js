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
      oidcEnabled: undefined,
      oidcProviderName: undefined,
      oidcLoginUrl: undefined,
      oidcLogoutUrl: undefined,
    },
    user: undefined,
    /*
     * Populated by the v4 ``/session`` composite alongside ``user`` +
     * ``adminFlags``. The SPA chrome reads ``version.installed``
     * immediately; ``latest`` feeds the update-available footer and
     * ``dockerHub`` the deprecated-image snackbar.
     */
    version: undefined,
    /*
     * The admin site defaults, ``{browser, reader}``, and their revision.
     * ``/session`` sends them only to a caller who may browse. They seed a
     * view's first paint and feed the runtime table-column, bookmark and
     * reader-scope fallbacks; ``defaultsRev`` changing is what reloads an
     * open view's settings after the admin saves.
     */
    defaults: undefined,
    defaultsRev: undefined,
    token: undefined,
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
    // Absent from the payload means this caller may not browse: clear them.
    _setDefaults({ defaults, defaultsRev }) {
      this.defaults = defaults;
      this.defaultsRev = defaultsRev;
    },
    /*
     * v4 composite boot: one request returns user + adminFlags +
     * permissions + version. Use this on app start; the per-resource
     * loaders below stay around for explicit refreshes after admin
     * mutations (e.g. websocket fan-out of admin.flags.changed).
     */
    async loadSession() {
      try {
        const response = await API.getSession();
        const data = response.data || {};
        const { user, adminFlags, version } = data;
        if (adminFlags) this.adminFlags = adminFlags;
        this.user = user || undefined;
        if (version) this.version = version;
        this._setDefaults(data);
        return true;
      } catch (error) {
        console.error(error);
      }
    },
    async loadAdminFlags() {
      try {
        const response = await API.getSession();
        const data = response.data || {};
        if (data.adminFlags) this.adminFlags = data.adminFlags;
        this._setDefaults(data);
        return true;
      } catch (error) {
        console.error(error);
      }
    },
    async loadProfile() {
      try {
        const response = await API.getProfile();
        this.user = response.data;
        return true;
      } catch (error) {
        console.debug(error);
      }
    },
    async login(credentials, shouldClear = true) {
      const commonStore = useCommonStore();
      try {
        await API.login(credentials);
        if (shouldClear) {
          commonStore.clearErrors();
        }
        await this.loadSession();
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async register(credentials) {
      const commonStore = useCommonStore();
      try {
        await API.register(credentials);
        commonStore.clearErrors();
        await this.login(credentials);
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    /*
     * Full-page navigation, not an XHR: the identity provider's login
     * page must render in the browser, and the chain of redirects
     * ends back at the SPA root with a fresh session cookie. The URL
     * arrives prefix-qualified from the ``/session`` payload.
     */
    loginSSO() {
      const url = this.adminFlags.oidcLoginUrl;
      if (url) {
        location.assign(url);
      }
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
      /*
       * Captured before the local clear: RP-initiated logout also ends
       * the identity-provider session. The URL only exists on payloads
       * for authenticated OIDC-configured sessions.
       */
      const oidcLogoutUrl = this.adminFlags.oidcLogoutUrl;
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
        if (oidcLogoutUrl) {
          // Full-page redirect to end the IdP session; the ensuing
          // reload refreshes the flags on its own.
          location.assign(oidcLogoutUrl);
        } else {
          /*
           * Refresh the public admin flags so the logged-out login
           * screen reflects anything changed during the session — e.g.
           * OIDC toggled off hides the "Login with <provider>" button
           * without a manual page reload.
           */
          await this.loadAdminFlags();
        }
      }
    },
    async changePassword(credentials) {
      const changedCredentials = {
        username: this.user.username,
        password: credentials.password,
      };
      const commonStore = useCommonStore();
      try {
        const response = await API.updatePassword(credentials);
        commonStore.setSuccess(response.data.detail);
        await this.login(changedCredentials, false);
      } catch (error) {
        commonStore.setErrors(error);
      }
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
      try {
        const response = await API.updateProfile(profile);
        this.user = response.data;
        commonStore.clearErrors();
        return true;
      } catch (error) {
        commonStore.setErrors(error);
        return false;
      }
    },
    async sendResetPasswordLink(login) {
      const commonStore = useCommonStore();
      try {
        const response = await API.sendResetPasswordLink(login);
        commonStore.setSuccess(response.data.detail);
        return true;
      } catch (error) {
        commonStore.setErrors(error);
        return false;
      }
    },
    async resetPassword(payload) {
      const commonStore = useCommonStore();
      try {
        const response = await API.resetPassword(payload);
        commonStore.setSuccess(response.data.detail);
        return true;
      } catch (error) {
        commonStore.setErrors(error);
        return false;
      }
    },
    async setTimezone() {
      if (this.adminFlags.nonUsers || this.user) {
        try {
          await API.updateTimezone();
        } catch (error) {
          console.error(error);
        }
      }
    },
    async getToken() {
      try {
        const response = await API.getToken();
        this.token = response.data.token;
      } catch (error) {
        console.error(error);
      }
    },
    async updateToken() {
      try {
        const response = await API.updateToken();
        this.token = response.data.token;
      } catch (error) {
        console.error(error);
      }
    },
  },
});
