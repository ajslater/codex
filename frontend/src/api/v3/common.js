import { HTTP } from "./base";

const downloadIOSPWAFix = (href, fileName) => {
  HTTP.get(href, { responseType: "blob" })
    .then((response) => {
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(response.data);
      link.download = fileName;
      link.click();
      return true;
    })
    .catch((error) => console.warn(error));
};

const getVersions = () => {
  return HTTP.get("/version");
};

export default {
  downloadIOSPWAFix,
  getVersions,
};
