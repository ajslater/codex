import { HTTP } from "@/api/v4/base";

/*
 * Shelves are per-user named groupings of browser items. The items
 * endpoint speaks the collection vocabulary directly
 * (publishers/series/comics/…): ``add`` and ``remove`` are each a
 * ``{collection: [ids]}`` map, either one optional.
 */
export const getShelves = () => HTTP.get("/shelves/");

export const createShelf = (name) => HTTP.post("/shelves/", { name });

export const renameShelf = (pk, name) => HTTP.patch(`/shelves/${pk}`, { name });

export const deleteShelf = (pk) => HTTP.delete(`/shelves/${pk}`);

export const updateShelfItems = (pk, { add, remove }) => {
  const body = {};
  if (add) body.add = add;
  if (remove) body.remove = remove;
  return HTTP.patch(`/shelves/${pk}/items`, body);
};
