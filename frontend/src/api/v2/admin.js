import { ajax, ROOT_PATH } from "./base";
const ADMIN_URL = `${ROOT_PATH}admin/`;

const poll = () => {
  return ajax("post", `/poll`);
};

export default {
  ADMIN_URL,
  poll,
};
