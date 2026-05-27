import { HTTP } from "@/api/v4/base";
import { serializeParams } from "@/api/v4/common";

/*
 * v4 admin CRUD factory. Differences from v3:
 *   - Paths are plural (``users`` vs ``user``).
 *   - Updates use PATCH (v3 used PUT for partial_update).
 *   - api-key regeneration is POST (v3 used PUT).
 *   - custom-cover endpoints reshuffled to ``custom-covers`` + actions.
 *   - Librarian status moved to ``tasks``; task enqueue is ``tasks/run``.
 */
const makeAdminCRUD = (entity) => {
  const path = `/admin/${entity}`;
  return {
    create: (data) => HTTP.post(path, data),
    getAll: () => HTTP.get(path, { params: serializeParams() }),
    update: (pk, data) => HTTP.patch(`${path}/${pk}`, data),
    destroy: (pk) => HTTP.delete(`${path}/${pk}`),
  };
};

export const TABLES = Object.freeze({
  User: { ...makeAdminCRUD("users"), stateField: "users" },
  Group: { ...makeAdminCRUD("groups"), stateField: "groups" },
  Library: { ...makeAdminCRUD("libraries"), stateField: "libraries" },
  Flag: {
    getAll: () => HTTP.get("/admin/flags", { params: serializeParams() }),
    update: (key, data) => HTTP.patch(`/admin/flags/${key}`, data),
    stateField: "flags",
  },
  FailedImport: {
    getAll: () =>
      HTTP.get("/admin/failed-imports", { params: serializeParams() }),
    stateField: "failedImports",
  },
  ActiveLibrarianStatus: {
    getAll: () => HTTP.get("/admin/tasks", { params: { ts: Date.now() } }),
    stateField: "activeLibrarianStatuses",
  },
  AgeRatingMetron: {
    getAll: () => HTTP.get("/admin/age-ratings"),
    stateField: "ageRatingMetrons",
  },
  CustomCover: {
    getAll: () =>
      HTTP.get("/admin/custom-covers", { params: serializeParams() }),
    destroy: (pk) => HTTP.delete(`/admin/custom-covers/${pk}`),
    stateField: "customCovers",
  },
});

export const uploadCustomCover = ({ group, pks, file }) => {
  const form = new FormData();
  form.append("group", group);
  form.append("pks", Array.isArray(pks) ? pks.join(",") : String(pks));
  form.append("image", file);
  return HTTP.post("/admin/custom-covers/upload", form);
};

export const removeCustomCover = ({ group, pks }) =>
  HTTP.post("/admin/custom-covers/bulk-delete", {
    group,
    pks: Array.isArray(pks) ? pks.join(",") : String(pks),
  });

export const changeUserPassword = (pk, data) =>
  HTTP.post(`/admin/users/${pk}/password`, data);

export const sendUserVerificationEmail = (pk) =>
  HTTP.post(`/admin/users/${pk}/send-verification`);

export const getFolders = (path, showHidden) =>
  HTTP.get("/admin/folders", { params: { path, showHidden } });

export const postLibrarianTask = (data) => HTTP.post("/admin/tasks/run", data);

export const getAllLibrarianStatuses = () =>
  HTTP.get("/admin/tasks", { params: { ts: Date.now() } });

export const getStats = () =>
  HTTP.get("/admin/stats", { params: { ts: Date.now() } });

export const getAPIKey = () =>
  HTTP.get("/admin/api-key", { params: { ts: Date.now() } });

export const updateAPIKey = () => HTTP.post("/admin/api-key");

export const getTaggingDefaults = () =>
  HTTP.get("/admin/tagging-defaults", { params: { ts: Date.now() } });

export const updateTaggingDefaults = (data) =>
  HTTP.patch("/admin/tagging-defaults", data);

export const validateTaggingCredentials = (data) =>
  HTTP.post("/admin/tagging-defaults/validate", data);

export const getEmailSettings = () =>
  HTTP.get("/admin/email-settings", { params: { ts: Date.now() } });

export const updateEmailSettings = (data) =>
  HTTP.patch("/admin/email-settings", data);

export const sendEmailTest = (data) =>
  HTTP.post("/admin/email-settings/test", data);

export const getThrottleSettings = () =>
  HTTP.get("/admin/throttle-settings", { params: { ts: Date.now() } });

export const updateThrottleSettings = (data) =>
  HTTP.patch("/admin/throttle-settings", data);

export const postDumpUserData = () => HTTP.post("/admin/user-data/export");

export const postRestoreUserData = ({ dryRun = false } = {}) =>
  HTTP.post("/admin/user-data/import", { dry_run: dryRun });
