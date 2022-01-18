// Shared functions for most metadata components.
import CHOICES from "@/choices";
const VUETIFY_NULL_CODE = CHOICES.browser.vuetifyNullCode;
const NULL_NAME = "None";
const NULL_ITEM = { pk: VUETIFY_NULL_CODE, name: NULL_NAME };

export const toVuetifyItem = function (item) {
  // Translates an raw value or an item item into a vuetify item.
  let vuetifyItem;
  if (item === undefined) {
    vuetifyItem = item;
  } else if (item instanceof Object) {
    vuetifyItem = item;
    if (vuetifyItem.pk === null || vuetifyItem.pk === undefined) {
      vuetifyItem.pk = VUETIFY_NULL_CODE;
    }
    if (vuetifyItem.name === null || vuetifyItem.pk === undefined) {
      vuetifyItem.name = NULL_NAME;
    }
  } else if (item === null) {
    vuetifyItem = NULL_ITEM;
  } else {
    vuetifyItem = { pk: item, name: item.toString() };
  }
  return vuetifyItem;
};

const vuetifyItemCompare = function (itemA, itemB) {
  if (itemA.name < itemB.name) return -1;
  if (itemA.name > itemB.name) return 1;
  return 0;
};

export const toVuetifyItems = function (value, items, filter) {
  // Takes a value (can be a list) and a list of items and
  // Returns a list of valid items with items arg having preference.
  let computedItems = [];
  let sourceItems;
  if (items) {
    sourceItems = items;
  } else if (value) {
    sourceItems = Array.isArray(value) ? value : [value];
  } else {
    sourceItems = [];
  }
  // Case insensitive search
  const finalFilter = filter ? filter.toLowerCase() : filter;

  for (const item of sourceItems) {
    const vuetifyItem = toVuetifyItem(item);
    if (
      vuetifyItem &&
      (!finalFilter || vuetifyItem.name.toLowerCase().includes(finalFilter))
    ) {
      computedItems.push(vuetifyItem);
    }
  }
  return computedItems.sort(vuetifyItemCompare);
};

export default {
  toVuetifyItems,
  toVuetifyItem,
};
