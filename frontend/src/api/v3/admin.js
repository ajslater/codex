import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

// CRUD factory — generates create/getAll/update/destroy for a given admin entity.
const makeAdminCRUD = (entity) => {
  const path = `/admin/${entity}`;
  return {
    create: (data) => HTTP.post(path, data),
    getAll: () => HTTP.get(path, { params: serializeParams() }),
    update: (pk, data) => HTTP.put(`${path}/${pk}/`, data),
    destroy: (pk) => HTTP.delete(`${path}/${pk}/`),
  };
};

const userCRUD = makeAdminCRUD("user");
const groupCRUD = makeAdminCRUD("group");
const libraryCRUD = makeAdminCRUD("library");

// ONE-OFF ENDPOINTS

const changeUserPassword = (pk, data) => {
  return HTTP.put(`/admin/user/${pk}/password`, data);
};

const getFolders = (path, showHidden) => {
  const params = { path, showHidden };
  return HTTP.get("/admin/folders", { params });
};

const getFailedImports = () => {
  const params = serializeParams();
  return HTTP.get("/admin/failed-import", { params });
};

const getFlags = () => {
  const params = serializeParams();
  return HTTP.get("/admin/flag", { params });
};

const updateFlag = (key, data) => {
  return HTTP.put(`/admin/flag/${key}/`, data);
};

const postLibrarianTask = async (data) => {
  return await HTTP.post("/admin/librarian/task", data);
};

const getActiveLibrarianStatuses = () => {
  const params = { ts: Date.now() };
  return HTTP.get("/admin/librarian/status", { params });
};

const getAllLibrarianStatuses = () => {
  const params = { ts: Date.now() };
  return HTTP.get("/admin/librarian/status/all", { params });
};

const getStats = () => {
  const params = { ts: Date.now() };
  return HTTP.get("/admin/stats", { params });
};

const updateAPIKey = async () => {
  return await HTTP.put("/admin/api_key");
};

// Preserve the original function-name keys for dynamic lookup by the admin store
// (e.g. API["create" + table], API["get" + pluralTable]).
export default {
  createUser: userCRUD.create,
  getUsers: userCRUD.getAll,
  updateUser: userCRUD.update,
  deleteUser: userCRUD.destroy,
  changeUserPassword,
  createGroup: groupCRUD.create,
  getGroups: groupCRUD.getAll,
  updateGroup: groupCRUD.update,
  deleteGroup: groupCRUD.destroy,
  createLibrary: libraryCRUD.create,
  getLibraries: libraryCRUD.getAll,
  updateLibrary: libraryCRUD.update,
  deleteLibrary: libraryCRUD.destroy,
  getActiveLibrarianStatuses,
  getAllLibrarianStatuses,
  getFailedImports,
  getFlags,
  getFolders,
  getStats,
  postLibrarianTask,
  updateAPIKey,
  updateFlag,
};
