import { HTTP } from "./base";

const downloadIOSPWAFix = (href, fileName) => {
  // iOS has a download bug inside PWAs. The user is trapped in the
  // download screen and cannot return to the app.
  // https://developer.apple.com/forums/thread/95911
  // This works around that by creating temporary blob link which
  // makes the PWA display browser back controls
  HTTP.get(href, { responseType: "blob" })
    .then((response) => {
      const link = document.createElement("a");
      const blob = new Blob([response.data], {
        type: "application/octet-stream",
      });
      link.href = window.URL.createObjectURL(blob);
      link.download = fileName;
      link.click();
      return window.URL.revokeObjectURL(response.data);
    })
    .catch(console.warn);
};

export const getReaderBasePath = (pk) => {
  return `${window.CODEX.API_V3_PATH}c/${pk}`;
};

const getVersions = (ts) => {
  return HTTP.get(`/version?ts=${ts}`);
};

export default {
  downloadIOSPWAFix,
  getReaderBasePath,
  getVersions,
};
