import { ajax } from "./base";

const queueJob = async (task) => {
  return await ajax("post", "/admin/queue_job", { task });
};

const getLibrarianStatuses = () => {
  const ts = Date.now();
  return ajax("get", `/admin/librarian_status?ts=${ts}`);
};

export default {
  getLibrarianStatuses,
  queueJob,
};
