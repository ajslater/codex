// Common store functions
import { defineStore } from "pinia";

import API from "@/api/v3/common";

const ERROR_KEYS = [
  "detail",
  "oldPassword",
  "password",
  "username",
  "passwordConfirm",
  "path",
];
Object.freeze(ERROR_KEYS);

const getErrors = (xiorError) => {
  let errors = [];
  if (xiorError && xiorError.response && xiorError.response.data) {
    let data = xiorError.response.data;
    for (const key of ERROR_KEYS) {
      if (key in data) {
        data = data[key];
        break;
      }
    }
    errors = Array.isArray(data) ? data.flat() : [data];
  } else {
    console.warn("Unable to parse error", xiorError);
  }
  if (errors.length === 0) {
    errors = ["Unknown error"];
  }
  return errors;
};

export const useCommonStore = defineStore("common", {
  state: () => ({
    form: {
      errors: [],
      success: "",
    },
    versions: {
      // This is injected by vite define

      installed: CODEX_PACKAGE_VERSION,
      latest: undefined,
    },
    timestamp: Date.now(),
    isSettingsDrawerOpen: false,
    opdsURLs: undefined,
  }),
  actions: {
    async loadVersions() {
      await API.getVersions(this.timestamp)
        .then((response) => {
          const data = response.data;
          this.versions = data;
          return this.versions;
        })
        .catch(console.error);
    },
    setErrors(xiorError) {
      const errors = getErrors(xiorError);
      this.$patch((state) => {
        state.form.errors = errors;
        state.form.success = "";
      });
    },
    setSuccess(success) {
      this.$patch((state) => {
        state.form.errors = [];
        state.form.success = success;
      });
    },
    clearErrors() {
      this.$patch((state) => {
        state.form.errors = [];
        state.form.success = "";
      });
    },
    setTimestamp() {
      this.timestamp = Date.now();
    },
    setSettingsDrawerOpen(value) {
      this.isSettingsDrawerOpen = value;
    },
    async loadOPDSURLs() {
      if (this.opdsURLs) {
        return;
      }
      await API.getOPDSURLs()
        .then((response) => {
          this.opdsURLs = Object.freeze({ ...response.data });
          return this.opdsURLs;
        })
        .catch(console.error);
    },
  },
});
