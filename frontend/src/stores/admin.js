import { dequal } from "dequal";
import { defineStore } from "pinia";

import * as API from "@/api/v3/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const { TABLES } = API;

const warnError = (error) => console.warn(error);

// Sticky-cache TTL for admin table reads. Tab-swap navigation
// inside the admin panel re-fires ``loadTables`` on mount; the
// previous code refetched every time. With a short window we
// serve the existing state for redundant reads while still
// picking up changes from explicit invalidators (CRUD mutations
// and websocket fan-out both pass ``{ force: true }``).
const DYNAMIC_TTL_MS = 5_000;
// AgeRatingMetron is a static enum lookup; once loaded it never
// needs refreshing for the session.
const TABLE_TTL_MS = Object.freeze({
  AgeRatingMetron: Number.POSITIVE_INFINITY,
});
export const TABS = Object.freeze([
  "Users",
  "Groups",
  "Libraries",
  "Flags",
  "Jobs",
  "Stats",
]);

export const UNRESTRICTED_LABEL = "Adult";

export const useAdminStore = defineStore("admin", {
  state: () => ({
    allLibrarianStatuses: {},
    activeLibrarianStatuses: [],
    unseenFailedImports: false,
    users: [],
    groups: [],
    ageRatingMetrons: [],
    libraries: undefined,
    failedImports: [],
    flags: [],
    folderPicker: {
      root: undefined,
      folders: [],
    },
    timestamps: {},
    stats: undefined,
    activeTab: "Libraries",
  }),
  getters: {
    isUserAdmin() {
      const authStore = useAuthStore();
      return authStore.isUserAdmin;
    },
    normalLibraries() {
      const libs = [];
      if (this.libraries) {
        for (const library of this.libraries) {
          if (!library.coversOnly) {
            libs.push(library);
          }
        }
      }
      return libs;
    },
    customCoverLibraries() {
      const libs = [];
      if (this.libraries) {
        for (const library of this.libraries) {
          if (library.coversOnly) {
            libs.push(library);
          }
        }
      }
      return libs;
    },
    doNormalComicLibrariesExist() {
      return Object.keys(this.normalLibraries).length > 0;
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
      // Sticky-cache gate. Skip if we've loaded this table within
      // the TTL window and the caller didn't explicitly demand a
      // fresh read. CRUD mutations and websocket-driven refetches
      // pass ``{ force: true }`` because they know the data
      // changed underneath us.
      if (!force) {
        const ttl = TABLE_TTL_MS[table] ?? DYNAMIC_TTL_MS;
        const last = this.timestamps[table] || 0;
        if (last && Date.now() - last < ttl) {
          return true;
        }
      }
      await t
        .getAll()
        .then((response) => {
          if (Array.isArray(response.data)) {
            this[t.stateField] = response.data;
            this.timestamps[table] = Date.now();
            return true;
          } else {
            console.warn(t.stateField, "response not an array");
            return false;
          }
        })
        .catch(warnError);
    },
    async loadTables(tables, options) {
      if (this._requireAdmin()) return false;
      // ``Promise.all`` so every fetch runs concurrently and the
      // returned promise resolves only once they've all settled.
      // Previously this was a fire-and-forget for-loop: callers
      // that awaited it received a synchronous ``undefined`` and
      // could observe an admin tab's state mid-load (some tables
      // populated, some still empty), which presented as flicker.
      return await Promise.all(
        tables.map((table) => this.loadTable(table, options)),
      );
    },
    async loadFolders(path, showHidden) {
      if (this._requireAdmin()) return false;
      await API.getFolders(path, showHidden)
        .then((response) => {
          this.folderPicker = response.data;
          return true;
        })
        .catch(useCommonStore().setErrors);
    },
    async clearFolders(root) {
      if (this._requireAdmin()) return false;
      this.folderPicker = { root, folders: [""] };
    },
    async createRow(table, data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      await TABLES[table]
        .create(data)
        .then(() => {
          commonStore.clearErrors();
          return this.loadTable(table, { force: true });
        })
        .catch(commonStore.setErrors);
    },
    async updateRow(table, pk, data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      await TABLES[table]
        .update(pk, data)
        .then(() => {
          commonStore.clearErrors();
          return this.loadTable(table, { force: true });
        })
        .catch(commonStore.setErrors);
    },
    async changeUserPassword(pk, data) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      await API.changeUserPassword(pk, data)
        .then((response) => {
          commonStore.setSuccess(response.data.detail);
          return true;
        })
        .catch(commonStore.setErrors);
    },
    async deleteRow(table, pk) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      await TABLES[table]
        .destroy(pk)
        .then(() => {
          commonStore.clearErrors();
          return this.loadTable(table, { force: true });
        })
        .catch(commonStore.setErrors);
    },
    async librarianTask(task, text, libraryId) {
      if (this._requireAdmin()) return false;
      const commonStore = useCommonStore();
      await API.postLibrarianTask({ task, libraryId })
        .then(() => commonStore.setSuccess(text))
        .catch(commonStore.setErrors);
    },
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
      await API.getStats()
        .then((response) => {
          this.stats = response.data;
          return true;
        })
        .catch(console.warn);
    },
    async loadAllStatuses() {
      if (this._requireAdmin()) return false;
      await API.getAllLibrarianStatuses()
        .then((response) => {
          if (Array.isArray(response.data)) {
            const next = {};
            for (const status of response.data) {
              next[status.statusType] = status;
            }
            this._patchAllLibrarianStatuses(next);
          }
          return true;
        })
        .catch(console.warn);
    },
    _patchAllLibrarianStatuses(next) {
      // Diff-based update. The previous code reassigned
      // ``allLibrarianStatuses`` to a brand-new object on every
      // poll, forcing every computed/watcher subscribing to the
      // map (job-tab progress bars, status-list rows) to
      // re-evaluate even when nothing actually moved. The
      // websocket-driven LIBRARIAN_STATUS fan-out can fire many
      // times a second during an active import, so this
      // dominated job-tab render time.
      //
      // Mutate keys in place: Pinia's reactivity then notifies
      // only watchers that touch the specific keys we changed.
      const current = this.allLibrarianStatuses;
      // Remove keys that vanished from the latest payload.
      for (const key of Object.keys(current)) {
        if (!(key in next)) {
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
    async updateAPIKey() {
      if (this._requireAdmin()) return false;
      await API.updateAPIKey()
        .then(() => {
          return true;
        })
        .catch(console.warn);
    },
  },
});
