import { defineStore } from "pinia";

import API from "@/api/v3/common";

export const useCommonStore = defineStore("common", {
  state: () => ({
    versions: {
      // This is injected by vite define
      installed: CODEX_PACKAGE_VERSION, // eslint-disable-line no-undef
      latest: undefined,
    },
    timestamp: Date.now(),
  }),
  actions: {
    async loadVersions() {
      await API.getVersions(this.timestamp)
        .then((response) => {
          const data = response.data;
          return (this.versions = data);
        })
        .catch((error) => {
          return console.error(error);
        });
    },
    downloadIOSPWAFix(href, fileName) {
      API.downloadIOSPWAFix(href, fileName);
    },
  },
});
