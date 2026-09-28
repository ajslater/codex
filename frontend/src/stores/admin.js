import { dequal } from "dequal";
import { defineStore } from "pinia";

import * as API from "@/api/v4/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const { TABLES } = API;

const warnError = (error) => console.warn(error);

/*
 * Sticky-cache TTL for admin table reads. Tab-swap navigation
 * inside the admin panel re-fires ``loadTables`` on mount; the
 * previous code refetched every time. With a short window we
 * serve the existing state for redundant reads while still
 * picking up changes from explicit invalidators (CRUD mutations
 * and websocket fan-out both pass ``{ force: true }``).
 */
const DYNAMIC_TTL_MS = 5000;
/*
 * AgeRatingMetron is a static enum lookup; once loaded it never
 * needs refreshing for the session.
 */
const TABLE_TTL_MS = Object.freeze({
  AgeRatingMetron: Infinity,
});
/*
 * Whether data stamped at ``last`` is still inside its sticky-cache
 * window. Never-loaded data (a falsy stamp) is stale, and so is data
 * exactly ``ttl`` old.
 */
export const isFresh = (last, ttl = DYNAMIC_TTL_MS, now = Date.now()) =>
  Boolean(last) && now - last < ttl;
export const TABS = Object.freeze([
  "Users",
  "Groups",
  "Auth",
  "Email",
  "Libraries",
  "Tagging",
  "Custom Covers",
  "Settings",
  "Defaults",
  "Jobs",
  "Restore",
  "Stats",
]);

export const UNRESTRICTED_LABEL = "Adult";

export const useAdminStore = defineStore("admin", {
  state: () => ({
    allLibrarianStatuses: {},
    activeLibrarianStatuses: [],
    users: [],
    groups: [],
    ageRatingMetrons: [],
    libraries: undefined,
    customCovers: [],
    failedImports: [],
    failedImportsSeenAt: "",
    pendingDeletes: [],
    tagWriteErrors: [],
    flags: [],
    folderPicker: {
      rootFolder: undefined,
      folders: [],
    },
    timestamps: {},
    stats: undefined,
    taggingDefaults: undefined,
    emailSettings: undefined,
    oidcSettings: undefined,
    throttleSettings: undefined,
    settingsDefaults: undefined,
    apiKey: "",
    activeTab: "Libraries",
  }),
  getters: {
    isUserAdmin() {
      const authStore = useAuthStore();
      return authStore.isUserAdmin;
    },
    doNormalComicLibrariesExist() {
      return Boolean(this.libraries?.length);
    },
    // A failed-import warning is "unseen" when a failed import is newer than
    // the server-persisted seen marker (empty marker = never cleared, so all
    // count). Drives the hamburger dot + sidebar item; survives reloads.
    hasUnseenFailedImports() {
      if (!this.failedImports?.length) return false;
      if (!this.failedImportsSeenAt) return true;
      const seen = new Date(this.failedImportsSeenAt).getTime();
      return this.failedImports.some(
        (fi) => new Date(fi.createdAt).getTime() > seen,
      );
    },
  },
  actions: {
    /** Guard: returns true and early-exits the caller if not admin. */
    _requireAdmin() {
      return !this.isUserAdmin;
    },
    async loadTable(table, { force = false } = {}) {
      if (this._requireAdmin()) return false;
      const t = TABLES[table];
      /*
       * Sticky-cache gate. Skip if we've loaded this table within
       * the TTL window and the caller didn't explicitly demand a
       * fresh read. CRUD mutations and websocket-driven refetches
       * pass ``{ force: true }`` because they know the data
       * changed underneath us.
       */
      if (!force && isFresh(this.timestamps[table], TABLE_TTL_MS[table])) {
        return true;
      }
      try {
        const response = await t.getAll();
        /*
         * v4 admin viewsets use cursor pagination, so list responses
         * arrive as ``{count?, next, previous, results}`` inside the
         * envelope. Read-only enums (AgeRatingMetron) and the few
         * non-viewset list endpoints still return a bare array — accept
         * both shapes so callers don't need to know which is which.
         */
        const body = response.data;
        let rows;
        if (Array.isArray(body)) {
          rows = body;
        } else if (Array.isArray(body?.results)) {
          rows = body.results;
        }
        if (rows === undefined) {
          console.warn(t.stateField, "response shape unrecognized");
          return;
        }
        this[t.stateField] = rows;
        this.timestamps[table] = Date.now();
      } catch (error) {
        warnError(error);
      }
    },
    async loadTables(tables, options) {
      if (this._requireAdmin()) return false;
      /*
       * ``Promise.all`` so every fetch runs concurrently and the
       * returned promise resolves only once they've all settled.
       * Previously this was a fire-and-forget for-loop: callers
       * that awaited it received a synchronous ``undefined`` and
       * could observe an admin tab's state mid-load (some tables
       * populated, some still empty), which presented as flicker.
       */
      return await Promise.all(
        tables.map((table) => this.loadTable(table, options)),
      );
    },
    async loadFolders(path, showHidden) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        const response = await API.getFolders(path, showHidden);
        this.folderPicker = response.data;
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async clearFolders(rootFolder) {
      if (this._requireAdmin()) return false;
      this.folderPicker = { rootFolder, folders: [""] };
    },
    /*
     * createRow and updateRow resolve true when the row saved and false when
     * it didn't, so a dialog can stay open to show the server's field errors.
     */
    async createRow(table, data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        await TABLES[table].create(data);
        commonStore.clearErrors();
        await this.loadTable(table, { force: true });
        return true;
      } catch (error) {
        commonStore.setErrors(error);
        return false;
      }
    },
    async updateRow(table, pk, data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        await TABLES[table].update(pk, data);
        commonStore.clearErrors();
        await this.loadTable(table, { force: true });
        return true;
      } catch (error) {
        commonStore.setErrors(error);
        return false;
      }
    },
    async changeUserPassword(pk, data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        const response = await API.changeUserPassword(pk, data);
        commonStore.setSuccess(response.data.detail);
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async sendUserVerificationEmail(pk) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        const response = await API.sendUserVerificationEmail(pk);
        commonStore.setSuccess(response.data.detail);
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async deleteRow(table, pk) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        await TABLES[table].destroy(pk);
        commonStore.clearErrors();
        await this.loadTable(table, { force: true });
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async librarianTask(task, text, libraryId) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        await API.postLibrarianTask({ task, libraryId });
        commonStore.setSuccess(text);
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    /*
     * Names already taken, for the ``$notIn`` rules.
     *
     * A fast local pre-check, not the authority. ``loadTable`` reads
     * only ``body.results`` and never follows ``next``, so with a page
     * size of 200 a duplicate on row 201 is not in here. The server is
     * authoritative -- ``username``, ``Group.name`` and ``Library.path``
     * are all ``unique=True`` and ModelSerializer attaches the
     * UniqueValidator automatically -- and its answer now renders on
     * the field that caused it.
     */
    nameSet(rows, nameKey, oldRow, dupeCheck) {
      if (this._requireAdmin()) return false;
      const names = new Set();
      if (rows) {
        for (const obj of rows) {
          if (!dupeCheck || !oldRow || obj[nameKey] !== oldRow[nameKey]) {
            names.add(obj[nameKey]);
          }
        }
      }
      return names;
    },
    async loadStats() {
      if (this._requireAdmin()) return false;
      try {
        const response = await API.getStats();
        this.stats = response.data;
      } catch (error) {
        console.warn(error);
      }
    },
    async loadAllStatuses() {
      if (this._requireAdmin()) return false;
      try {
        const response = await API.getAllLibrarianStatuses();
        if (Array.isArray(response.data)) {
          const next = {};
          for (const status of response.data) {
            next[status.statusType] = status;
          }
          this._patchAllLibrarianStatuses(next);
        }
      } catch (error) {
        console.warn(error);
      }
    },
    _patchAllLibrarianStatuses(next) {
      /*
       * Diff-based update. The previous code reassigned
       * ``allLibrarianStatuses`` to a brand-new object on every
       * poll, forcing every computed/watcher subscribing to the
       * map (job-tab progress bars, status-list rows) to
       * re-evaluate even when nothing actually moved. The
       * websocket-driven LIBRARIAN_STATUS fan-out can fire many
       * times a second during an active import, so this
       * dominated job-tab render time.
       *
       * Mutate keys in place: Pinia's reactivity then notifies
       * only watchers that touch the specific keys we changed.
       */
      const current = this.allLibrarianStatuses;
      // Remove keys that vanished from the latest payload.
      for (const key of Object.keys(current)) {
        if (!Object.hasOwn(next, key)) {
          delete current[key];
        }
      }
      // Add or replace keys whose values actually changed.
      for (const [key, value] of Object.entries(next)) {
        if (!dequal(current[key], value)) {
          current[key] = value;
        }
      }
    },
    async loadAPIKey() {
      if (this._requireAdmin()) return false;
      try {
        const response = await API.getAPIKey();
        this.apiKey = response.data?.apiKey ?? "";
      } catch (error) {
        console.warn(error);
      }
    },
    async updateAPIKey() {
      if (this._requireAdmin()) return false;
      try {
        const response = await API.updateAPIKey();
        this.apiKey = response.data?.apiKey ?? this.apiKey;
      } catch (error) {
        console.warn(error);
      }
    },
    async loadTaggingDefaults({ force = false } = {}) {
      if (this._requireAdmin()) return false;
      if (!force && isFresh(this.timestamps.TaggingDefaults)) return true;
      try {
        const response = await API.getTaggingDefaults();
        this.taggingDefaults = response.data;
        this.timestamps.TaggingDefaults = Date.now();
      } catch (error) {
        console.warn(error);
      }
    },
    async updateTaggingDefaults(data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        const response = await API.updateTaggingDefaults(data);
        this.taggingDefaults = response.data;
        this.timestamps.TaggingDefaults = Date.now();
        commonStore.clearErrors();
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async validateTaggingCredentials(data) {
      if (this._requireAdmin()) return;
      const commonStore = useCommonStore();
      try {
        const response = await API.validateTaggingCredentials(data);
        commonStore.clearErrors();
        return response.data.results;
      } catch (error) {
        commonStore.setErrors(error);
        return;
      }
    },
    async loadTagWriteErrors({ force = false } = {}) {
      if (this._requireAdmin()) return false;
      if (!force && isFresh(this.timestamps.TagWriteErrors)) return true;
      try {
        const response = await API.getTagWriteErrors();
        this.tagWriteErrors = Array.isArray(response.data) ? response.data : [];
        this.timestamps.TagWriteErrors = Date.now();
      } catch (error) {
        console.warn(error);
      }
    },
    async clearTagWriteErrors() {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        await API.clearTagWriteErrors();
        this.tagWriteErrors = [];
        this.timestamps.TagWriteErrors = Date.now();
        commonStore.clearErrors();
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async loadFailedImportsSeen() {
      if (this._requireAdmin()) return false;
      try {
        const response = await API.getFailedImportsSeen();
        this.failedImportsSeenAt = response.data?.seenAt ?? "";
      } catch (error) {
        console.warn(error);
      }
    },
    async markFailedImportsSeen() {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      // Persist the "seen" marker so the hamburger dot + sidebar item stay
      // cleared across reloads and sessions. The Libraries-tab table persists;
      // failed imports created after this moment re-activate the warning.
      try {
        const response = await API.markFailedImportsSeen();
        this.failedImportsSeenAt = response.data?.seenAt ?? "";
        commonStore.clearErrors();
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async revivePendingDelete(collection, pk) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        await API.revivePendingDelete(collection, pk);
        commonStore.clearErrors();
        // The websocket tells every other admin session; this one
        // refreshes itself so the row leaves immediately.
        await this.loadTables(["PendingDelete", "Library"], {
          force: true,
        });
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    async loadEmailSettings({ force = false } = {}) {
      if (this._requireAdmin()) return false;
      if (!force && isFresh(this.timestamps.EmailSettings)) return true;
      try {
        const response = await API.getEmailSettings();
        this.emailSettings = response.data;
        this.timestamps.EmailSettings = Date.now();
      } catch (error) {
        console.warn(error);
      }
    },
    async updateEmailSettings(data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        const response = await API.updateEmailSettings(data);
        this.emailSettings = response.data;
        this.timestamps.EmailSettings = Date.now();
        commonStore.clearErrors();
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    /*
     * Trigger a one-shot SMTP send using the supplied overrides on top
     * of the saved EmailSettings row. Returns ``{ok, error?}`` from the
     * server; errors land on the common store too so the form can show
     * field-level validation messages.
     */
    async sendEmailTest(data) {
      if (this._requireAdmin()) return;
      const commonStore = useCommonStore();
      try {
        const response = await API.sendEmailTest(data);
        commonStore.clearErrors();
        return response.data;
      } catch (error) {
        commonStore.setErrors(error);
        return;
      }
    },
    async loadOidcSettings({ force = false } = {}) {
      if (this._requireAdmin()) return false;
      if (!force && isFresh(this.timestamps.OidcSettings)) return true;
      try {
        const response = await API.getOidcSettings();
        this.oidcSettings = response.data;
        this.timestamps.OidcSettings = Date.now();
      } catch (error) {
        console.warn(error);
      }
    },
    async updateOidcSettings(data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        const response = await API.updateOidcSettings(data);
        this.oidcSettings = response.data;
        this.timestamps.OidcSettings = Date.now();
        commonStore.clearErrors();
        // Keep the auth store's public OIDC flags — which drive the
        // "Login with <provider>" button — in sync with the settings
        // just saved, so toggling OIDC on/off is reflected without a
        // manual page reload. OIDCSettings is a singleton (no
        // admin.flags.changed websocket broadcast), so refresh here.
        await useAuthStore().loadAdminFlags();
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    /*
     * Probe the identity provider's discovery document, optionally with
     * a not-yet-saved server URL override. Returns the endpoint report
     * from the server; errors land on the common store too.
     */
    async testOidcConnection(data) {
      if (this._requireAdmin()) return;
      const commonStore = useCommonStore();
      try {
        const response = await API.testOidcConnection(data);
        commonStore.clearErrors();
        return response.data;
      } catch (error) {
        commonStore.setErrors(error);
        return;
      }
    },
    async loadSettingsDefaults({ force = false } = {}) {
      if (this._requireAdmin()) return false;
      if (!force && isFresh(this.timestamps.SettingsDefaults)) return true;
      try {
        const response = await API.getSettingsDefaults();
        this.settingsDefaults = response.data;
        this.timestamps.SettingsDefaults = Date.now();
      } catch (error) {
        console.warn(error);
      }
    },
    /*
     * ``applyToAnonymous`` also moves the existing anonymous sessions still
     * at the old defaults. Resolves to the per-field row counts it moved
     * (``{}`` without the catch-up), or ``undefined`` when the save failed.
     */
    async updateSettingsDefaults(data, { applyToAnonymous = false } = {}) {
      if (this._requireAdmin()) return;
      const commonStore = useCommonStore();
      const body = applyToAnonymous ? { ...data, applyToAnonymous } : data;
      try {
        const response = await API.updateSettingsDefaults(body);
        const { applied, ...settingsDefaults } = response.data;
        this.settingsDefaults = settingsDefaults;
        this.timestamps.SettingsDefaults = Date.now();
        commonStore.clearErrors();
        return applied ?? {};
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    // Never cached: the counts move with every anonymous browse.
    async loadSettingsDefaultsReach() {
      if (this._requireAdmin()) return;
      try {
        const response = await API.getSettingsDefaultsReach();
        return response.data;
      } catch (error) {
        console.warn(error);
      }
    },
    async loadThrottleSettings({ force = false } = {}) {
      if (this._requireAdmin()) return false;
      if (!force && isFresh(this.timestamps.ThrottleSettings)) return true;
      try {
        const response = await API.getThrottleSettings();
        this.throttleSettings = response.data;
        this.timestamps.ThrottleSettings = Date.now();
      } catch (error) {
        console.warn(error);
      }
    },
    async updateThrottleSettings(data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      try {
        const response = await API.updateThrottleSettings(data);
        this.throttleSettings = response.data;
        this.timestamps.ThrottleSettings = Date.now();
        commonStore.clearErrors();
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    /*
     * Snapshot the user-data sidecar from the main DB. Returns
     * ``{ written: {table: count}, total }`` or undefined on failure.
     */
    async dumpUserData() {
      if (this._requireAdmin()) return;
      const commonStore = useCommonStore();
      try {
        const response = await API.postDumpUserData();
        commonStore.clearErrors();
        return response.data;
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
    /*
     * List the user-data sidecar backups available to restore from
     * (newest first). Returns an array of { name, label, size, mtime }
     * or [] on failure.
     */
    async listUserDataBackups() {
      if (this._requireAdmin()) return [];
      const commonStore = useCommonStore();
      try {
        const response = await API.getUserDataBackups();
        commonStore.clearErrors();
        return response.data?.backups ?? [];
      } catch (error) {
        commonStore.setErrors(error);
        return [];
      }
    },
    /*
     * Trigger a sidecar → main-DB restore. ``filename`` selects a specific
     * backup (default: newest). Returns the report payload
     * ({ written, skipped, log_path, unmatched }) or undefined on failure.
     */
    async restoreUserData({ dryRun = false, filename } = {}) {
      if (this._requireAdmin()) return;
      const commonStore = useCommonStore();
      try {
        const response = await API.postRestoreUserData({ dryRun, filename });
        commonStore.clearErrors();
        return response.data;
      } catch (error) {
        commonStore.setErrors(error);
      }
    },
  },
});
