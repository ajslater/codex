import { HTTP } from "./base";

const getVersions = () => {
  return HTTP.get("/version");
};

export default {
  getVersions,
};
