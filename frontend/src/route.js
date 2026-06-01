/*
 * Group value -> v4 collection URL segment. The browser now speaks the
 * collection vocabulary, so this is mostly an identity map; the entries
 * that earn their keep are ``root`` (the synthetic top level resolves to
 * the publishers hierarchy) plus the legacy single-char codes, kept so a
 * still-char reader breadcrumb / arc value round-trips through here too.
 */
const GROUP_TO_COLLECTION = Object.freeze({
  root: "publishers",
  r: "publishers",
  p: "publishers",
  i: "imprints",
  s: "series",
  v: "volumes",
  c: "comics",
  f: "folders",
  a: "arcs",
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

/* {group, pks} -> v4 {collection, parentIds}. Idempotent for collection input. */
export const routeForGroup = ({ group, pks }) => ({
  collection: GROUP_TO_COLLECTION[group] || group,
  parentIds: normalizeParentIds(pks),
});

/*
 * v4 {collection, parentIds} -> internal {group, pks}. The group is the
 * collection value itself; publishers with no parentIds is the synthetic
 * ``root`` nav group, mirroring the backend AuthMixin.
 */
export const groupForRoute = ({ collection, parentIds }) => {
  const ids = normalizeParentIds(parentIds);
  if (collection === "publishers" && !ids.length) {
    return { group: "root", pks: ids };
  }
  return { group: collection, pks: ids };
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
    params: { pk },
    query: { page },
  };
};

export default {
  getReaderRoute,
  groupForRoute,
  normalizeParentIds,
  routeForGroup,
};
