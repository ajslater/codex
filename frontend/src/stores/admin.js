import { defineStore } from "pinia";

import API from "@/api/v3/admin";
import { useAuthStore } from "@/stores/auth";

const warnError = (error) => console.warn(error);

const vuetifyItems = (items, textAttr) => {
  const result = [];
  for (const item of items) {
    const pk = "pk" in item ? item.pk : item.id;
    result.push({ value: +pk, text: item[textAttr] });
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
    const pk = item.pk || item.id;
    map[pk] = item[key];
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
    flags: [],
    folderPicker: {
      root: undefined,
      folders: [],
    },
    form: {
      errors: [],
      success: "",
    },
    isSettingsDrawerOpen: true,
  }),
  getters: {
    isUserAdmin() {
      const authStore = useAuthStore();
      return authStore.isUserAdmin;
    },
    groupMap() {
      return itemMap(this.groups, "name");
    },
    userMap() {
      return itemMap(this.users, "username");
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
    clearErrors() {
      this.$patch((state) => {
        state.form.errors = [];
        state.form.success = "";
      });
    },
    setErrors(axiosError) {
      let errors = [];
      if (!axiosError) {
        this.errors = errors;
        return;
      }
      if (axiosError.response && axiosError.response.data) {
        const data = axiosError.response.data;
        for (const val of Object.values(data)) {
          if (val) {
            errors = Array.isArray(val)
              ? [...errors, ...val]
              : [...errors, val];
          }
        }
      } else {
        console.warn("Unable to parse error", axiosError);
      }
      if (errors.length === 0) {
        errors = ["Unknown error"];
      }
      this.form.errors = errors;
    },
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
          this[stateField] = response.data;
          return true;
        })
        .catch(warnError);
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
        .catch(this.setErrors);
    },
    async createRow(table, data) {
      if (!this.isUserAdmin) {
        return false;
      }
      this.clearErrors();
      const apiFn = "create" + table;
      await API[apiFn](data)
        .then(() => {
          return this.loadTable(table);
        })
        .catch(this.setErrors);
    },
    async updateRow(table, pk, data) {
      if (!this.isUserAdmin) {
        return false;
      }
      this.clearErrors();
      const apiFn = "update" + table;
      await API[apiFn](pk, data)
        .then(() => {
          return this.loadTable(table);
        })
        .catch(this.setErrors);
    },
    async changeUserPassword(pk, data) {
      if (!this.isUserAdmin) {
        return false;
      }
      this.clearErrors();
      await API.changeUserPassword(pk, data)
        .then((response) => {
          this.form.success = response.data.detail;
          return true;
        })
        .catch(this.setErrors);
    },
    async deleteRow(table, pk) {
      if (!this.isUserAdmin) {
        return false;
      }
      this.clearErrors();
      const apiFn = "delete" + table;
      await API[apiFn](pk)
        .then(() => {
          return this.loadTable(table);
        })
        .catch(this.setErrors);
    },
    async librarianTask(task, text, library_id) {
      if (!this.isUserAdmin) {
        return false;
      }
      await API.librarianTask(task, library_id)
        .then(() => (this.form.success = text))
        .catch(this.setErrors);
    },
  },
});
