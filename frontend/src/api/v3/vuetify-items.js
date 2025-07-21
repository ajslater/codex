// Shared functions for most metadata components.
import { vuetifyNullCode } from "@/choices/browser-choices.json";
export const NULL_PKS = new Set([
  "",
  vuetifyNullCode,
  vuetifyNullCode.toString(),
  undefined,
]);

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
  return itemA.title.localeCompare(itemB.title);
};

const vuetifyItemCompareNumeric = function (itemA, itemB) {
  return Number.parseFloat(itemA.title) - Number.parseFloat(itemB.title);
};

export const toVuetifyItems = function ({
  items,
  filter,
  numeric = false,
  sort = true,
}) {
  /*
   * Takes a value (can be a list) and a list of items and
   * Returns a list of valid items with items arg having preference.
   */
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
  if (sort) {
    const sortFunc = numeric ? vuetifyItemCompareNumeric : vuetifyItemCompare;
    computedItems = computedItems.sort(sortFunc);
  }
  return computedItems;
};

export default {
  toVuetifyItems,
  NULL_PKS,
};
