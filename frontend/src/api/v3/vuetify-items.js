// Shared functions for most metadata components.
import { VUETIFY_NULL_CODE } from "@/choices/browser-choices.json";
export const NULL_PKS = new Set(["", VUETIFY_NULL_CODE, undefined, null]);

const toVuetifyItem = function (item, copyKeys = undefined) {
  /*
   * Translate a raw value or item into a vuetify item.
   *
   * Returns ``undefined`` for inputs that should be dropped (null-ish
   * primitives, ``{ids: [...]}`` rows that contain null ids — both are
   * defensive: backend payloads never produce them today). "None" rows
   * (``{pk: null, ...}``) are returned with ``value`` already set to
   * ``VUETIFY_NULL_CODE`` so ``toVuetifyItems`` can discriminate on a
   * single equality check rather than re-running the ``NULL_PKS`` test.
   */
  if (NULL_PKS.has(item)) {
    return undefined;
  }
  if (typeof item !== "object") {
    // Scalar (e.g. a year). Numbers + strings only — null was caught above.
    return { value: item, title: item.toString() };
  }
  let vuetifyItem;
  if ("ids" in item) {
    // ``ids`` comes from ``JsonGroupArray("id")`` over PK columns, so
    // null members can't happen in practice — keep the guard cheap
    // (``some`` short-circuits) rather than constructing a Set just to
    // call ``intersection`` (an ES2024 method Vite doesn't polyfill).
    if (item.ids.some((id) => NULL_PKS.has(id))) {
      return undefined;
    }
    vuetifyItem = { value: item.ids.join(","), title: item.name };
  } else if (NULL_PKS.has(item.pk)) {
    vuetifyItem = { value: VUETIFY_NULL_CODE, title: "None" };
  } else {
    vuetifyItem = { value: item.pk, title: item.name };
  }
  if (item.url) {
    vuetifyItem.url = item.url;
  }
  if (copyKeys) {
    for (const key of copyKeys) {
      vuetifyItem[key] = item[key];
    }
  }
  return vuetifyItem;
};

const vuetifyItemCompareTitle = function (itemA, itemB) {
  return itemA.title.localeCompare(itemB.title);
};

const vuetifyItemCompareNumeric = function (itemA, itemB) {
  return Number.parseFloat(itemA.title) - Number.parseFloat(itemB.title);
};
const vuetifyItemCompareMetronIndex = function (itemA, itemB) {
  return Number.parseFloat(itemA.index) - Number.parseFloat(itemB.index);
};

const SORT_BY_FUNC_MAP = Object.freeze({
  title: vuetifyItemCompareTitle,
  numeric: vuetifyItemCompareNumeric,
  index: vuetifyItemCompareMetronIndex,
});

export const toVuetifyItems = function ({
  items,
  filter,
  sortBy = "title",
  copyKeys = undefined,
}) {
  /*
   * Map a list of raw items to vuetify items, filter by ``filter``,
   * sort by ``sortBy``, and prepend the synthetic "None" row (if
   * present) so it always sorts first regardless of the comparator.
   */
  const sourceItems = items || [];
  const lowerCaseFilter = filter ? filter.toLowerCase() : filter;

  const computedItems = [];
  let noneItem;
  for (const item of sourceItems) {
    const vuetifyItem = toVuetifyItem(item, copyKeys);
    if (vuetifyItem == undefined) {
      continue;
    }
    if (
      lowerCaseFilter &&
      !vuetifyItem.title.toLowerCase().includes(lowerCaseFilter)
    ) {
      continue;
    }
    // ``toVuetifyItem`` sets ``value`` to ``VUETIFY_NULL_CODE`` for the
    // synthetic "None" row; everything else carries a real pk / id-list.
    if (vuetifyItem.value === VUETIFY_NULL_CODE) {
      noneItem = vuetifyItem;
    } else {
      computedItems.push(vuetifyItem);
    }
  }
  if (sortBy) {
    computedItems.sort(SORT_BY_FUNC_MAP[sortBy]);
  }
  if (noneItem) {
    computedItems.unshift(noneItem);
  }
  return computedItems;
};

export default {
  toVuetifyItems,
  NULL_PKS,
};
