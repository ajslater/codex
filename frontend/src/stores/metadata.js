import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import { useBrowserStore } from "@/stores/browser";

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
  }),
  actions: {
    async loadMetadata({ group, pks }) {
      const browserStore = useBrowserStore();
      await API.getMetadata({ group, pks }, browserStore.settings)
        .then((response) => {
          const md = { ...response.data };
          md.loaded = true;
          this.md = md;
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
