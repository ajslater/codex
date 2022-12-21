// Common store functions
import { defineStore } from "pinia";

import API from "@/api/v3/common";

const ERROR_KEYS = [
  "detail",
  "oldPassword",
  "password",
  "username",
  "passwordConfirm",
];
Object.freeze(ERROR_KEYS);

const getErrors = (axiosError) => {
  let errors = [];
  if (axiosError && axiosError.response && axiosError.response.data) {
    let data = axiosError.response.data;
    for (const key of ERROR_KEYS) {
      if (key in data) {
        data = data[key];
        break;
      }
    }
    errors = Array.isArray(data) ? data.flat() : [data];
  } else {
    console.warn("Unable to parse error", axiosError);
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
      installed: CODEX_PACKAGE_VERSION, // eslint-disable-line no-undef
      latest: undefined,
    },
    timestamp: Date.now(),
    isSettingsDrawerOpen: false,
  }),
  getters: {
    isMobile: function () {
      // Probably janky mobile detection
      return (
        window.orientation !== undefined ||
        navigator.userAgent.includes("IEMobile")
      );
    },
  },
  actions: {
    async loadVersions() {
      await API.getVersions(this.timestamp)
        .then((response) => {
          const data = response.data;
          return (this.versions = data);
        })
        .catch(console.error);
    },
    downloadIOSPWAFix(href, fileName) {
      API.downloadIOSPWAFix(href, fileName);
    },
    setErrors(axiosError) {
      const errors = getErrors(axiosError);
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
  },
});
