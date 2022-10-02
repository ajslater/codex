import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import { useBrowserStore } from "@/stores/browser";

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
  }),
  actions: {
    async loadMetadata({ group, pk }) {
      const browserStore = useBrowserStore();
      await API.getMetadata({ group, pk }, browserStore.settings)
        .then((response) => {
          this.md = response.data;
          return true;
        })
        .catch((error) => {
          console.error(error);
          this.clearMetadata();
        });
    },
    clearMetadata() {
      this.md = undefined;
    },
  },
});
