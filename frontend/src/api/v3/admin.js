import { HTTP } from "@/api/v3/base";
import { serializeParams } from "@/api/v3/common";

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

// One descriptor per admin table, keyed by the PascalCase table name
// the admin store / components pass to ``loadTable`` / ``createRow`` /
// ``updateRow`` / ``deleteRow``. Each descriptor exposes the subset of
// ``create`` / ``getAll`` / ``update`` / ``destroy`` HTTP ops the
// table actually supports plus the camelCase ``stateField`` the admin
// store stores the loaded rows under. Letting the API surface own the
// table names eliminates the IRREGULAR_PLURALS map + string-concat
// lookup the admin store used to need on the consumer side.
export const TABLES = Object.freeze({
  User: { ...makeAdminCRUD("user"), stateField: "users" },
  Group: { ...makeAdminCRUD("group"), stateField: "groups" },
  Library: { ...makeAdminCRUD("library"), stateField: "libraries" },
  Flag: {
    getAll: () => HTTP.get("/admin/flag", { params: serializeParams() }),
    update: (key, data) => HTTP.put(`/admin/flag/${key}/`, data),
    stateField: "flags",
  },
  FailedImport: {
    getAll: () =>
      HTTP.get("/admin/failed-import", { params: serializeParams() }),
    stateField: "failedImports",
  },
  ActiveLibrarianStatus: {
    getAll: () =>
      HTTP.get("/admin/librarian/status", { params: { ts: Date.now() } }),
    stateField: "activeLibrarianStatuses",
  },
  // AgeRatingMetron is an effectively-static enum lookup — rows
  // don't change at runtime — so we skip the ``serializeParams()``
  // cache-buster. Browser-cacheable; the admin store also keeps a
  // sticky in-memory cache (``TABLE_TTL_MS = Infinity``) for the
  // session, so a typical visitor hits this endpoint at most once.
  AgeRatingMetron: {
    getAll: () => HTTP.get("/admin/age-rating-metron"),
    stateField: "ageRatingMetrons",
  },
});

// One-off endpoints that don't fit the table CRUD shape.

export const changeUserPassword = (pk, data) =>
  HTTP.put(`/admin/user/${pk}/password`, data);

export const getFolders = (path, showHidden) =>
  HTTP.get("/admin/folders", { params: { path, showHidden } });

export const postLibrarianTask = (data) =>
  HTTP.post("/admin/librarian/task", data);

export const getAllLibrarianStatuses = () =>
  HTTP.get("/admin/librarian/status/all", { params: { ts: Date.now() } });

export const getStats = () =>
  HTTP.get("/admin/stats", { params: { ts: Date.now() } });

export const updateAPIKey = () => HTTP.put("/admin/api_key");
