import { defineStore } from "pinia";

import API from "@/api/v3/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const warnError = (error) => console.warn(error);

const IRREGULAR_PLURALS = {
  LibrarianStatus: "LibrarianStatuses",
  Library: "Libraries",
};
Object.freeze(IRREGULAR_PLURALS);
export const TABS = ["Users", "Groups", "Libraries", "Flags", "Tasks", "Stats"];
Object.freeze(TABS);

const getTablePlural = (table) => {
  if (table in IRREGULAR_PLURALS) {
    return IRREGULAR_PLURALS[table];
  }
  return table + "s";
};

export const useAdminStore = defineStore("admin", {
  state: () => ({
    librarianStatuses: [],
    unseenFailedImports: false,
    users: [],
    groups: [],
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
    async loadTable(table) {
      if (!this.isUserAdmin) {
        return false;
      }
      const pluralTable = getTablePlural(table);
      const apiFn = "get" + pluralTable;
      await API[apiFn]()
        .then((response) => {
          const stateField =
            pluralTable.charAt(0).toLowerCase() + pluralTable.slice(1);
          if (Array.isArray(response.data)) {
            this[stateField] = response.data;
            return true;
          } else {
            console.warn(stateField, "response not an array");
            return false;
          }
        })
        .catch(warnError);
    },
    loadTables(tables) {
      for (const table of tables) {
        this.loadTable(table);
      }
    },
    async loadFolders(path, showHidden) {
      if (!this.isUserAdmin) {
        return false;
      }
      await API.getFolders(path, showHidden)
        .then((response) => {
          this.folderPicker = response.data;
          return true;
        })
        .catch(useCommonStore().setErrors);
    },
    async clearFolders(root) {
      if (!this.isUserAdmin) {
        return false;
      }
      this.folderPicker = { root, folders: [""] };
    },
    async createRow(table, data) {
      if (!this.isUserAdmin) {
        return false;
      }
      const apiFn = "create" + table;
      const commonStore = useCommonStore();
      await API[apiFn](data)
        .then(() => {
          commonStore.clearErrors();
          return this.loadTable(table);
        })
        .catch(commonStore.setErrors);
    },
    async updateRow(table, pk, data) {
      if (!this.isUserAdmin) {
        return false;
      }
      const apiFn = "update" + table;
      const commonStore = useCommonStore();
      await API[apiFn](pk, data)
        .then(() => {
          commonStore.clearErrors();
          return this.loadTable(table);
        })
        .catch(commonStore.setErrors);
    },
    async changeUserPassword(pk, data) {
      if (!this.isUserAdmin) {
        return false;
      }
      const commonStore = useCommonStore();
      await API.changeUserPassword(pk, data)
        .then((response) => {
          commonStore.setSuccess(response.data.detail);
          return true;
        })
        .catch(commonStore.setErrors);
    },
    async deleteRow(table, pk) {
      if (!this.isUserAdmin) {
        return false;
      }
      const apiFn = "delete" + table;
      const commonStore = useCommonStore();
      await API[apiFn](pk)
        .then(() => {
          commonStore.clearErrors();
          return this.loadTable(table);
        })
        .catch(commonStore.setErrors);
    },
    async librarianTask(task, text, libraryId) {
      if (!this.isUserAdmin) {
        return false;
      }
      const commonStore = useCommonStore();
      await API.postLibrarianTask({ task, libraryId })
        .then(() => commonStore.setSuccess(text))
        .catch(commonStore.setErrors);
    },
    nameSet(rows, nameKey, oldRow, dupeCheck) {
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
      await API.getStats()
        .then((response) => {
          this.stats = response.data;
          return true;
        })
        .catch(console.warn);
    },
    async updateAPIKey() {
      await API.updateAPIKey()
        .then(() => {
          return true;
        })
        .catch(console.warn);
    },
  },
});
