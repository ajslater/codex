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
  return HTTP.get("/admin/failed-import");
};

// FLAGS

const getFlags = () => {
  return HTTP.get("/admin/flag");
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
  const ts = Date.now();
  return HTTP.get(`/admin/librarian/status?ts=${ts}`);
};

// TASKS

const librarianTask = (task, library_id) => {
  return HTTP.post("/admin/librarian/task", { task, library_id });
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
  getUsers,
  librarianTask,
  postLibrarianTask,
  updateFlag,
  updateGroup,
  updateLibrary,
  updateUser,
};
