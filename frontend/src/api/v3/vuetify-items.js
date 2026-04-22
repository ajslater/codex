// Shared functions for most metadata components.
import { VUETIFY_NULL_CODE } from "@/choices/browser-choices.json";
export const NULL_PKS = new Set(["", VUETIFY_NULL_CODE, undefined, null]);

const toVuetifyItem = function (item) {
  /*
   * Translates an raw value or an item item into a vuetify item.
   * Removes nulls, they're detected directly from the choices source.
   */
  let vuetifyItem;
  if (NULL_PKS.has(item)) {
    vuetifyItem = item;
  } else if (item instanceof Object) {
    if ("ids" in item) {
      const idSet = new Set(item.ids);
      if (NULL_PKS.intersection(idSet).size > 0) {
        vuetifyItem = undefined;
      } else {
        const value = item.ids.join(",");
        vuetifyItem = { value, title: item.name };
      }
    } else if (NULL_PKS.has(item.pk)) {
      vuetifyItem = { value: item.pk, title: "None" };
    } else {
      vuetifyItem = { value: item.pk, title: item.name };
    }
  } else {
    vuetifyItem = { value: item, title: item.toString() };
  }
  if (item?.url) {
    vuetifyItem.url = item.url;
  }
  return vuetifyItem;
};

const vuetifyItemCompareTitle = function (itemA, itemB) {
  return itemA.title.localeCompare(itemB.title);
};

const vuetifyItemCompareNumeric = function (itemA, itemB) {
  return Number.parseFloat(itemA.title) - Number.parseFloat(itemB.title);
};

const SORT_BY_FUNC_MAP = Object.freeze({
  title: vuetifyItemCompareTitle,
  numeric: vuetifyItemCompareNumeric,
});

export const toVuetifyItems = function ({ items, filter, sortBy = "title" }) {
  /*
   * Takes a value (can be a list) and a list of items and
   * Returns a list of valid items with items arg having preference.
   */
  const sourceItems = items || [];

  // Case insensitive search for filter-sub-menu
  const lowerCaseFilter = filter ? filter.toLowerCase() : filter;
  let noneItem;

  let computedItems = [];
  for (const item of sourceItems) {
    const vuetifyItem = toVuetifyItem(item);
    if (
      vuetifyItem != undefined &&
      (!lowerCaseFilter ||
        vuetifyItem?.title?.toLowerCase().includes(lowerCaseFilter))
    ) {
      if (NULL_PKS.has(vuetifyItem.value)) {
        noneItem = vuetifyItem;
        noneItem.value = VUETIFY_NULL_CODE;
      } else {
        computedItems.push(vuetifyItem);
      }
    }
  }
  if (sortBy) {
    const sortFunc = SORT_BY_FUNC_MAP[sortBy];
    computedItems = computedItems.sort(sortFunc);
  }
  if (noneItem) {
    // Prepend noneItem if it exists.
    computedItems.unshift(noneItem);
  }
  return computedItems;
};

export default {
  toVuetifyItems,
  NULL_PKS,
};
