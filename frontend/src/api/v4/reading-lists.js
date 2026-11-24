/*
 * Reading lists: the admin import and review endpoints and the owner's own.
 */
import { HTTP, V4_BASE } from "@/api/v4/base";

const ADMIN = "/admin/reading-lists";
const LISTS = "/reading-lists";

const fresh = (params = {}) => ({ params: { ...params, ts: Date.now() } });

// Admin.
export const getAdminLists = () => HTTP.get(ADMIN, fresh());
export const getAdminList = (pk) => HTTP.get(`${ADMIN}/${pk}`, fresh());
export const updateAdminList = (pk, data) => HTTP.patch(`${ADMIN}/${pk}`, data);
export const deleteAdminList = (pk) => HTTP.delete(`${ADMIN}/${pk}`);
export const searchLists = (source, q, curator = "") =>
  HTTP.get(`${ADMIN}/search`, fresh({ source, q, curator }));
export const previewLists = (files, sources) => {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  form.append("sources", JSON.stringify(sources));
  return HTTP.post(`${ADMIN}/preview`, form);
};
export const importLists = (items) => HTTP.post(`${ADMIN}/import`, { items });
export const listAction = (pk, action) => HTTP.post(`${ADMIN}/${pk}/${action}`);
export const bulkAction = (action, pks) =>
  HTTP.post(`${ADMIN}/bulk`, { action, pks });
export const rankSources = (pk, order) =>
  HTTP.put(`${ADMIN}/${pk}/sources`, { order });
export const refreshSource = (pk, sourcePk) =>
  HTTP.post(`${ADMIN}/${pk}/sources/${sourcePk}`);
export const removeSource = (pk, sourcePk) =>
  HTTP.delete(`${ADMIN}/${pk}/sources/${sourcePk}`);
export const combineLists = (primary, others, dryRun) =>
  HTTP.post(`${ADMIN}/combine`, { primary, others, dryRun });
export const getSuggestions = () => HTTP.get(`${ADMIN}/suggestions`, fresh());
export const getMappings = () => HTTP.get(`${ADMIN}/series-mappings`, fresh());
export const createMapping = (list, entry, series) =>
  HTTP.post(`${ADMIN}/series-mappings`, { list, entry, series });
export const deleteMapping = (pk) =>
  HTTP.delete(`${ADMIN}/series-mappings`, { params: { pk } });
export const getErrors = () => HTTP.get(`${ADMIN}/errors`, fresh());
export const clearErrors = () => HTTP.delete(`${ADMIN}/errors`);
export const abortFetch = () => HTTP.post(`${ADMIN}/abort`);

// Owners and admins.
export const getMyLists = () => HTTP.get(`${LISTS}/`, fresh());
export const createList = (name, comics = []) =>
  HTTP.post(`${LISTS}/`, { name, comics });
export const renameList = (pk, name) => HTTP.patch(`${LISTS}/${pk}`, { name });
export const deleteList = (pk) => HTTP.delete(`${LISTS}/${pk}`);
export const duplicateList = (pk, name) =>
  HTTP.post(`${LISTS}/${pk}/duplicate`, name ? { name } : {});
export const getEntries = (pk, filter = "all") =>
  HTTP.get(`${LISTS}/${pk}/entries`, fresh({ filter }));
/*
 * A list's items, speaking the collection vocabulary: ``add`` and
 * ``remove`` are each a ``{collection: [pks]}`` map, either one optional.
 * Comics are issues added by hand; a publisher, imprint, series, volume,
 * folder or list is held whole and stays current.
 */
export const updateItems = (pk, { add, remove }) => {
  const body = {};
  if (add) body.add = add;
  if (remove) body.remove = remove;
  return HTTP.patch(`${LISTS}/${pk}/items`, body);
};
export const addEntries = (pk, comics, position) =>
  HTTP.post(`${LISTS}/${pk}/entries`, { comics, position });
export const updateEntry = (pk, entryPk, data) =>
  HTTP.patch(`${LISTS}/${pk}/entries/${entryPk}`, data);
export const deleteEntry = (pk, entryPk) =>
  HTTP.delete(`${LISTS}/${pk}/entries/${entryPk}`);
export const reorderEntry = (pk, entry, position) =>
  HTTP.post(`${LISTS}/${pk}/entries/reorder`, { entry, position });
export const acceptEntries = (pk) => HTTP.post(`${LISTS}/${pk}/entries/accept`);
export const getCandidates = (pk, entryPk, q = "") =>
  HTTP.get(`${LISTS}/${pk}/entries/${entryPk}/candidates`, fresh({ q }));
// ``missing``: only the issues the library lacks, to hunt for.
export const exportURL = (pk, fmt, isMissing = false) =>
  `${V4_BASE}reading-lists/${pk}/export?fmt=${encodeURIComponent(fmt)}${isMissing ? "&missing=1" : ""}`;
export const getContinue = (pk) => HTTP.get(`${LISTS}/${pk}/continue`, fresh());
