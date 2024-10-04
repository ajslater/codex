// Shared functions for most metadata components.
import { vuetifyNullCode } from "@/choices/browser-choices.json";
export const NULL_PKS = new Set([
  "",
  vuetifyNullCode,
  vuetifyNullCode.toString(),
  undefined,
]);

const toVuetifyItem = function (item) {
  // Translates an raw value or an item item into a vuetify item.
  // Removes nulls, they're detected directly from the choices source.
  let vuetifyItem;
  if (NULL_PKS.has(item)) {
    vuetifyItem = item;
  } else if (item instanceof Object) {
    if (NULL_PKS.has(item.pk)) {
      vuetifyItem = undefined;
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

const vuetifyItemCompare = function (itemA, itemB) {
  if (itemA.title < itemB.title) return -1;
  if (itemA.title > itemB.title) return 1;
  return 0;
};

const vuetifyItemCompareNumeric = function (itemA, itemB) {
  return Number.parseFloat(itemA.title) - Number.parseFloat(itemB.title);
};

export const toVuetifyItems = function (items, filter, numeric = false) {
  // Takes a value (can be a list) and a list of items and
  // Returns a list of valid items with items arg having preference.
  const sourceItems = items || [];

  // Case insensitive search for filter-sub-menu
  const lowerCaseFilter = filter ? filter.toLowerCase() : filter;

  let computedItems = [];
  for (const item of sourceItems) {
    const vuetifyItem = toVuetifyItem(item);
    if (
      vuetifyItem != undefined &&
      (!lowerCaseFilter ||
        vuetifyItem?.title?.toLowerCase().includes(lowerCaseFilter))
    ) {
      computedItems.push(vuetifyItem);
    }
  }
  const sortFunc = numeric ? vuetifyItemCompareNumeric : vuetifyItemCompare;
  return computedItems.sort(sortFunc);
};

export default {
  toVuetifyItems,
  NULL_PKS,
};
