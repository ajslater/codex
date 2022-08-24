import { HTTP } from "./base";

const queueJob = async (task) => {
  return await HTTP.post("/admin/queue_job", { task });
};

const getLibrarianStatuses = () => {
  const ts = Date.now();
  return HTTP.get(`/admin/librarian_status?ts=${ts}`);
};

export default {
  getLibrarianStatuses,
  queueJob,
};
