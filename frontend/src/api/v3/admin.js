import { getTSParams } from "@/api/v3/common";

import { HTTP } from "./base";

// USERS

const createUser = (data) => {
  return HTTP.post("/admin/user", data);
};

const getUsers = () => {
  const params = getTSParams();
  return HTTP.get("/admin/user", { params });
};

const updateUser = (pk, data) => {
  return HTTP.put(`/admin/user/${pk}/`, data);
};

const changeUserPassword = (pk, data) => {
  return HTTP.put(`/admin/user/${pk}/password`, data);
};

const deleteUser = (pk) => {
  return HTTP.delete(`/admin/user/${pk}/`);
};

// GROUP
const createGroup = (data) => {
  return HTTP.post("/admin/group", data);
};

const getGroups = () => {
  const params = getTSParams();
  return HTTP.get("/admin/group", { params });
};

const updateGroup = (pk, data) => {
  return HTTP.put(`/admin/group/${pk}/`, data);
};
const deleteGroup = (pk) => {
  return HTTP.delete(`/admin/group/${pk}/`);
};

// LIBRARIES

const createLibrary = (data) => {
  return HTTP.post("/admin/library", data);
};
const getLibraries = () => {
  const params = getTSParams();
  return HTTP.get("/admin/library", { params });
};

const updateLibrary = (pk, data) => {
  return HTTP.put(`/admin/library/${pk}/`, data);
};

const deleteLibrary = (pk) => {
  return HTTP.delete(`/admin/library/${pk}/`);
};

// LIBRARIES MISC

const getFolders = (path, showHidden) => {
  const params = { ...getTSParams(), path, showHidden };
  return HTTP.get("/admin/folders", { params });
};

const getFailedImports = () => {
  const params = getTSParams();
  return HTTP.get("/admin/failed-import", { params });
};

// FLAGS

const getFlags = () => {
  const params = getTSParams();
  return HTTP.get("/admin/flag", { params });
};

const updateFlag = (pk, data) => {
  return HTTP.put(`/admin/flag/${pk}/`, data);
};

// TASKS

const postLibrarianTask = async (task) => {
  return await HTTP.post("/admin/librarian/task", { task });
};

// STATUSES

const getLibrarianStatuses = () => {
  const params = { ts: Date.now() };
  return HTTP.get("/admin/librarian/status", { params });
};

// TASKS

const librarianTask = (task, library_id) => {
  return HTTP.post("/admin/librarian/task", { task, library_id });
};

const getStats = () => {
  return HTTP.get("/admin/stats");
};

const updateAPIKey = () => {
  return HTTP.post("/admin/api_key");
};

export default {
  changeUserPassword,
  createGroup,
  createLibrary,
  createUser,
  deleteLibrary,
  deleteGroup,
  deleteUser,
  getFailedImports,
  getFlags,
  getFolders,
  getGroups,
  getLibrarianStatuses,
  getLibraries,
  getStats,
  getUsers,
  librarianTask,
  postLibrarianTask,
  updateAPIKey,
  updateFlag,
  updateGroup,
  updateLibrary,
  updateUser,
};
