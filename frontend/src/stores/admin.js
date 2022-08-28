import { defineStore } from "pinia";

import API from "@/api/v3/admin";
import { useAuthStore } from "@/stores/auth";

export const useAdminStore = defineStore("admin", {
  state: () => ({
    librarianStatuses: [],
    failedImports: false,
  }),
  getters: {
    isUserAdmin() {
      const authStore = useAuthStore();
      return authStore.isUserAdmin;
    },
  },
  actions: {
    setFailedImports(data) {
      if (!this.isUserAdmin) {
        data = false;
      }
      this.failedImports = data;
    },
    async loadLibrarianStatuses() {
      if (!this.isUserAdmin) {
        this.librarianStatuses = [];
        return;
      }
      await API.getLibrarianStatuses()
        .then((response) => {
          this.librarianStatuses = response.data;
          return true;
        })
        .catch((error) => {
          console.log.warn(error);
        });
    },
  },
});
