import { ajax, ROOT_PATH } from "./base";
const ADMIN_URL = `${ROOT_PATH}admin/`;

const queueJob = async (task) => {
  return await ajax("post", "/admin/queue_job", { task });
};

export default {
  ADMIN_URL,
  queueJob,
};
