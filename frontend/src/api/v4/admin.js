import { HTTP } from "@/api/v4/base";
import { serializeParams } from "@/api/v4/common";

export function flattenJsonApi(body) {
  if (Array.isArray(body)) {
    return body.map((entry) => flattenResource(entry));
  }
  return body && typeof body === "object" && "type" in body && "id" in body
    ? flattenResource(body)
    : body;
}

/*
 * v4 admin resource endpoints render in JSON:API
 * (``{data: {type, id, attributes, relationships}}``) rather than
 * the envelope view-endpoints use. This helper flattens a single
 * resource into the ``{pk, ...fields}`` shape the admin store
 * components consume. Relationships collapse to id arrays (or a
 * single id) so ``library.groups`` reads as a plain pk list.
 * Singletons / RPC actions stay on the envelope and don't route
 * through here.
 */
function flattenRelationships(rels) {
  if (!rels) return {};
  const out = {};
  for (const [key, rel] of Object.entries(rels)) {
    const d = rel?.data;
    if (Array.isArray(d)) {
      out[key] = d.map((entry) => Math.trunc(Number(entry.id)));
    } else if (d) {
      out[key] = Math.trunc(Number(d.id));
    } else {
      out[key] = null;
    }
  }
  return out;
}

function flattenResource(item) {
  if (!item) return item;
  const pkRaw = item.id;
  const pk = /^\d+$/u.test(String(pkRaw)) ? Number(pkRaw) : pkRaw;
  return {
    pk,
    ...item.attributes,
    ...flattenRelationships(item.relationships),
  };
}

async function jsonApiResponse(request) {
  const response = await request;
  response.data = flattenJsonApi(response.data);
  return response;
}

/*
 * Build a JSON:API request body for a write to a resource viewset.
 *
 * The backend parser (``codex/views/admin/json_api.py::AdminJSONAPIParser``)
 * expects ``{data: {type, [id], attributes}}`` with the resource
 * ``type`` matching the JSONAPIMeta resource_name and (for
 * PATCH/PUT) the ``id`` matching the URL pk. Everything the admin
 * store writes — including M2M id lists like ``groups`` /
 * ``user_set`` — goes into ``attributes`` and lands on the backend
 * serializer as a flat dict; the DRF ``PrimaryKeyRelatedField`` the
 * auto-generated ModelSerializer uses for those relations only
 * understands plain int pks, so we avoid the formal
 * ``relationships`` block.
 */
function wrapJsonApi(resourceType, data, { pk } = {}) {
  const body = {
    data: { type: resourceType, attributes: { ...data } },
  };
  if (pk !== undefined && pk !== null) {
    body.data.id = String(pk);
  }
  return body;
}

/*
 * v4 admin CRUD factory. Conventions:
 *   - Paths are plural (``users``, ``groups``, ``libraries``).
 *   - Updates use PATCH (partial_update).
 *   - api-key regeneration is POST.
 *   - custom-cover endpoints live under ``custom-covers`` + actions.
 *   - Librarian status lives under ``tasks``; task enqueue is ``tasks/run``.
 */
const makeAdminCRUD = (entity) => {
  const path = `/admin/${entity}`;
  return {
    create: (data) =>
      jsonApiResponse(HTTP.post(path, wrapJsonApi(entity, data))),
    getAll: () =>
      jsonApiResponse(HTTP.get(path, { params: serializeParams() })),
    update: (pk, data) =>
      jsonApiResponse(
        HTTP.patch(`${path}/${pk}`, wrapJsonApi(entity, data, { pk })),
      ),
    destroy: (pk) => HTTP.delete(`${path}/${pk}`),
  };
};

export const TABLES = Object.freeze({
  User: { ...makeAdminCRUD("users"), stateField: "users" },
  Group: { ...makeAdminCRUD("groups"), stateField: "groups" },
  Library: { ...makeAdminCRUD("libraries"), stateField: "libraries" },
  Flag: {
    getAll: () =>
      jsonApiResponse(HTTP.get("/admin/flags", { params: serializeParams() })),
    update: (key, data) =>
      jsonApiResponse(
        HTTP.patch(
          `/admin/flags/${key}`,
          wrapJsonApi("flags", data, { pk: key }),
        ),
      ),
    stateField: "flags",
  },
  FailedImport: {
    getAll: () =>
      jsonApiResponse(
        HTTP.get("/admin/failed-imports", { params: serializeParams() }),
      ),
    stateField: "failedImports",
  },
  // Comic and Folder rendered into one list, so this is an envelope
  // APIView rather than a JSON:API resource.
  PendingDelete: {
    getAll: () =>
      HTTP.get("/admin/pending-deletes", { params: { ts: Date.now() } }),
    stateField: "pendingDeletes",
  },
  // ActiveLibrarianStatus stays on the envelope (async APIView, not a
  // JSON:API resource).
  ActiveLibrarianStatus: {
    getAll: () => HTTP.get("/admin/tasks", { params: { ts: Date.now() } }),
    stateField: "activeLibrarianStatuses",
  },
  AgeRatingMetron: {
    getAll: () => jsonApiResponse(HTTP.get("/admin/age-ratings")),
    stateField: "ageRatingMetrons",
  },
  CustomCover: {
    getAll: () =>
      jsonApiResponse(
        HTTP.get("/admin/custom-covers", { params: serializeParams() }),
      ),
    destroy: (pk) => HTTP.delete(`/admin/custom-covers/${pk}`),
    stateField: "customCovers",
  },
});

export const uploadCustomCover = ({ collection, pks, file }) => {
  const form = new FormData();
  form.append("collection", collection);
  form.append("pks", Array.isArray(pks) ? pks.join(",") : String(pks));
  form.append("image", file);
  return HTTP.post("/admin/custom-covers/upload", form);
};

export const removeCustomCover = ({ collection, pks }) =>
  HTTP.post("/admin/custom-covers/bulk-delete", {
    collection,
    pks: Array.isArray(pks) ? pks.join(",") : String(pks),
  });

export const changeUserPassword = (pk, data) =>
  HTTP.post(`/admin/users/${pk}/password`, data);

export const sendUserVerificationEmail = (pk) =>
  HTTP.post(`/admin/users/${pk}/send-verification`);

export const getFolders = (path, showHidden) =>
  HTTP.get("/admin/folders", { params: { path, showHidden } });

export const postLibrarianTask = (data) => HTTP.post("/admin/tasks/run", data);

// History view: every librarian status row, not just active ones.
export const getAllLibrarianStatuses = () =>
  HTTP.get("/admin/tasks/all", { params: { ts: Date.now() } });

export const getStats = () =>
  HTTP.get("/admin/stats", { params: { ts: Date.now() } });

export const getAPIKey = () =>
  HTTP.get("/admin/api-key", { params: { ts: Date.now() } });

export const updateAPIKey = () => HTTP.post("/admin/api-key");

export const getTaggingDefaults = () =>
  HTTP.get("/admin/tagging-defaults", { params: { ts: Date.now() } });

export const updateTaggingDefaults = (data) =>
  HTTP.put("/admin/tagging-defaults", data);

export const validateTaggingCredentials = (data) =>
  HTTP.post("/admin/tagging-defaults/validate", data);

export const revivePendingDelete = (collection, pk) =>
  HTTP.post(`/admin/pending-deletes/${collection}/${pk}/revive`);

export const getTagWriteErrors = () =>
  HTTP.get("/admin/tag-write/errors", { params: { ts: Date.now() } });

export const clearTagWriteErrors = () => HTTP.delete("/admin/tag-write/errors");

export const getFailedImportsSeen = () =>
  HTTP.get("/admin/failed-imports/seen", { params: { ts: Date.now() } });

export const markFailedImportsSeen = () =>
  HTTP.put("/admin/failed-imports/seen");

export const getEmailSettings = () =>
  HTTP.get("/admin/email-settings", { params: { ts: Date.now() } });

export const updateEmailSettings = (data) =>
  HTTP.put("/admin/email-settings", data);

export const sendEmailTest = (data) =>
  HTTP.post("/admin/email-settings/test", data);

export const getOidcSettings = () =>
  HTTP.get("/admin/oidc-settings", { params: { ts: Date.now() } });

export const updateOidcSettings = (data) =>
  HTTP.put("/admin/oidc-settings", data);

export const testOidcConnection = (data) =>
  HTTP.post("/admin/oidc-settings/test", data);

export const getSettingsDefaults = () =>
  HTTP.get("/admin/settings-defaults", { params: { ts: Date.now() } });

// ``applyToAnonymous`` rides in the body: the catch-up needs the old
// defaults, which only exist until this save commits.
export const updateSettingsDefaults = (data) =>
  HTTP.put("/admin/settings-defaults", data);

export const getSettingsDefaultsReach = () =>
  HTTP.get("/admin/settings-defaults/reach", { params: { ts: Date.now() } });

export const getThrottleSettings = () =>
  HTTP.get("/admin/throttle-settings", { params: { ts: Date.now() } });

export const updateThrottleSettings = (data) =>
  HTTP.put("/admin/throttle-settings", data);

export const postDumpUserData = () => HTTP.post("/admin/user-data/export");

export const getUserDataBackups = () =>
  HTTP.get("/admin/user-data/backups", { params: { ts: Date.now() } });

export const postRestoreUserData = ({ dryRun = false, filename } = {}) => {
  const body = { dry_run: dryRun };
  if (filename) body.filename = filename;
  return HTTP.post("/admin/user-data/import", body);
};
