import { defineStore } from "pinia";

import API from "@/api/v3/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const warnError = (error) => console.warn(error);

const vuetifyItems = (items, textAttr) => {
  const result = [];
  for (const item of items) {
    result.push({ value: item.pk, title: item[textAttr] });
  }
  return result;
};

const IRREGULAR_PLURALS = {
  LibrarianStatus: "LibrarianStatuses",
  Library: "Libraries",
};

const getTablePlural = (table) => {
  if (table in IRREGULAR_PLURALS) {
    return IRREGULAR_PLURALS[table];
  }
  return table + "s";
};

const itemMap = (items, key) => {
  const map = {};
  for (const item of items) {
    map[item.pk] = item[key];
  }
  return map;
};

export const useAdminStore = defineStore("admin", {
  state: () => ({
    librarianStatuses: [],
    unseenFailedImports: false,
    users: [],
    groups: [],
    libraries: [],
    failedImports: [],
    flags: {},
    folderPicker: {
      root: undefined,
      folders: [],
    },
    stats: undefined,
  }),
  getters: {
    isUserAdmin() {
      const authStore = useAuthStore();
      return authStore.isUserAdmin;
    },
    userMap() {
      return itemMap(this.users, "username");
    },
    groupMap() {
      return itemMap(this.groups, "name");
    },
    libraryMap() {
      return itemMap(this.libraries, "path");
    },
    vuetifyUsers() {
      return vuetifyItems(this.users, "username");
    },
    vuetifyGroups() {
      return vuetifyItems(this.groups, "name");
    },
    vuetifyLibraries() {
      return vuetifyItems(this.libraries, "path");
    },
    librariesExist() {
      return this.libraries && this.libraries.length > 0;
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
    async librarianTask(task, text, library_id) {
      if (!this.isUserAdmin) {
        return false;
      }
      const commonStore = useCommonStore();
      await API.librarianTask(task, library_id)
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
