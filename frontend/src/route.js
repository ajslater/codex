/*
 * Normalize a pks value (array, or "5,7" string) to a clean array of
 * positive integer strings; empties drop out (root = []).
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

/*
 * Engine {collection, pks} -> v4 route {collection, parentIds}. The
 * synthetic ``root`` collection resolves to the publishers hierarchy.
 */
export const routeForCollection = ({ collection, pks }) => ({
  collection: collection === "root" ? "publishers" : collection,
  parentIds: normalizeParentIds(pks),
});

/*
 * v4 route {collection, parentIds} -> engine {collection, pks}. Publishers
 * with no parentIds is the synthetic ``root`` nav collection, mirroring the
 * backend AuthMixin.
 */
export const collectionForRoute = ({ collection, parentIds }) => {
  const ids = normalizeParentIds(parentIds);
  if (collection === "publishers" && !ids.length) {
    return { collection: "root", pks: ids };
  }
  return { collection, pks: ids };
};

/*
 * Build vue-router params for the ``browser`` route from any
 * {collection, parentIds|pks} source. The route's ``parentIds`` segment is a
 * single optional token, so it must be a ``"1,2"`` string or omitted entirely
 * — handing vue-router an array throws "Provided param parentIds is an array
 * but it is not repeatable". Mirrors the breadcrumb / LAST_ROUTE shaping.
 */
export const browserRouteParams = ({ collection, parentIds, pks }) => {
  const ids = normalizeParentIds(parentIds ?? pks);
  return ids.length ? { collection, parentIds: ids.join(",") } : { collection };
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
  browserRouteParams,
  collectionForRoute,
  getReaderRoute,
  normalizeParentIds,
  routeForCollection,
};
