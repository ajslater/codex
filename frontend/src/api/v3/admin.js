import { getTSParams } from "@/api/v3/common";

import { HTTP } from "./base";

// USERS

const createUser = (data) => {
  return HTTP.post("/admin/user", data);
};

const getUsers = () => {
  return HTTP.get("/admin/user");
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
  return HTTP.get("/admin/group");
};

const updateGroup = (pk, data) => {
  return HTTP.put(`/admin/group/${pk}/`, data);
};
const deleteGroup = (pk) => {
  return HTTP.delete(`/admin/group/${pk}/`);
};

// Custom Cover Dir

const getCustomCoversDirs = () => {
  return HTTP.get("/admin/custom-cover-dir");
};

const updateCustomCoversDir = (pk, data) => {
  return HTTP.put(`/admin/custom-cover-dir`, data);
};

// LIBRARIES

const createLibrary = (data) => {
  return HTTP.post("/admin/library", data);
};
const getLibraries = () => {
  return HTTP.get("/admin/library");
};

const updateLibrary = (pk, data) => {
  return HTTP.put(`/admin/library/${pk}/`, data);
};

const deleteLibrary = (pk) => {
  return HTTP.delete(`/admin/library/${pk}/`);
};

// LIBRARIES MISC

const getFolders = (path, showHidden) => {
  const params = { path, showHidden };
  return HTTP.get("/admin/folders", { params });
};

const getFailedImports = () => {
  const params = getTSParams();
  return HTTP.get("/admin/failed-import", { params });
};

// FLAGS

const getFlags = () => {
  return HTTP.get("/admin/flag");
};

const updateFlag = (key, data) => {
  return HTTP.put(`/admin/flag/${key}/`, data);
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
  getCustomCoversDirs,
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
  updateCustomCoversDir,
  updateFlag,
  updateGroup,
  updateLibrary,
  updateUser,
};
