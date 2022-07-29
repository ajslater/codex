import { ajax, ROOT_PATH } from "./base";
const ADMIN_URL = `${ROOT_PATH}admin/`;

const queueJob = async (task) => {
  return await ajax("post", "/admin/queue_job", { task });
};

const getLibrarianStatuses = () => {
  const ts = Date.now();
  return ajax("get", `/admin/librarian_status?ts=${ts}`);
};

export default {
  ADMIN_URL,
  getLibrarianStatuses,
  queueJob,
};
