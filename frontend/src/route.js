/*
 * Single-char group code <-> v4 collection name, mirroring codex/group.py.
 * Root resolves to the publisher hierarchy, matching the backend
 * RouteSerializer (r -> publishers) and AuthMixin (publishers + no
 * parentIds -> r) so a route round-trips through either dialect.
 */
const GROUP_TO_COLLECTION = Object.freeze({
  r: "publishers",
  p: "publishers",
  i: "imprints",
  s: "series",
  v: "volumes",
  c: "comics",
  f: "folders",
  a: "arcs",
});
const COLLECTION_TO_GROUP = Object.freeze({
  publishers: "p",
  imprints: "i",
  series: "s",
  volumes: "v",
  comics: "c",
  folders: "f",
  arcs: "a",
});

/*
 * Normalize a pks value (array, or "5,7"/"0" string) to a clean array of
 * positive integer strings; the dummy 0 and empties drop out (root = []).
 */
export const normalizeParentIds = (pks) => {
  if (pks === undefined || pks === null) return [];
  const raw = Array.isArray(pks) ? pks : String(pks).split(",");
  const ids = [];
  for (const entry of raw) {
    const str = String(entry).trim();
    if (!str || str === "0") continue;
    ids.push(str);
  }
  return ids;
};

/* Legacy {group, pks} -> v4 {collection, parentIds}. */
export const routeForGroup = ({ group, pks }) => ({
  collection: GROUP_TO_COLLECTION[group] || group,
  parentIds: normalizeParentIds(pks),
});

/*
 * v4 {collection, parentIds} -> legacy {group, pks}. Root (publishers with
 * no parentIds) maps back to the "r" nav group, mirroring the backend.
 */
export const groupForRoute = ({ collection, parentIds }) => {
  const ids = normalizeParentIds(parentIds);
  if (collection === "publishers" && !ids.length) {
    return { group: "r", pks: ids };
  }
  return { group: COLLECTION_TO_GROUP[collection] || collection, pks: ids };
};

const REVERSE_READING_DIRECTIONS = Object.freeze(new Set("rtl", "btt"));
export const getReaderRoute = (
  { ids, page, readingDirection, pageCount },
  importMetadata,
) => {
  // Get the route to a comic with the correct entry page.
  if (ids.length === 0 || (importMetadata && !pageCount)) {
    return "";
  }
  const pk = ids[0];
  if (page) {
    page = Number(page);
  } else if (REVERSE_READING_DIRECTIONS.has(readingDirection)) {
    const maxPage = Number(pageCount) - 1;
    page = Math.max(maxPage, 0);
  } else {
    page = 0;
  }
  return {
    name: "reader",
    params: { pk, page },
  };
};

export default {
  getReaderRoute,
  groupForRoute,
  normalizeParentIds,
  routeForGroup,
};
