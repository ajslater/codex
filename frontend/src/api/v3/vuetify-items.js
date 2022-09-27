// Shared functions for most metadata components.
import CHOICES from "@/choices";
const VUETIFY_NULL_CODE = CHOICES.browser.vuetifyNullCode;
const NULL_NAME = "None";
const NULL_ITEM = { pk: VUETIFY_NULL_CODE, name: NULL_NAME };

const toVuetifyItem = function (item, charPk) {
  // Translates an raw value or an item item into a vuetify item.
  let vuetifyItem;
  if (item === undefined) {
    vuetifyItem = item;
  } else if (item instanceof Object) {
    vuetifyItem = item;
    if (vuetifyItem.pk === null || vuetifyItem.pk === undefined) {
      vuetifyItem.pk = VUETIFY_NULL_CODE;
    } else if (!charPk) {
      vuetifyItem.pk = +vuetifyItem.pk;
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

const vuetifyItemCompareNumeric = function (itemA, itemB) {
  return Number.parseFloat(itemA.name) - Number.parseFloat(itemB.name);
};

export const toVuetifyItems = function (items, filter, numeric = false, charPk = false) {
  // Takes a value (can be a list) and a list of items and
  // Returns a list of valid items with items arg having preference.
  const sourceItems = items || [];

  // Case insensitive search for filter-sub-menu
  const lowerCaseFilter = filter ? filter.toLowerCase() : filter;

  let computedItems = [];
  for (const item of sourceItems) {
    const vuetifyItem = toVuetifyItem(item, charPk);
    if (
      vuetifyItem &&
      (!lowerCaseFilter ||
        vuetifyItem.name.toLowerCase().includes(lowerCaseFilter))
    ) {
      computedItems.push(vuetifyItem);
    }
  }
  const sortFunc = numeric ? vuetifyItemCompareNumeric : vuetifyItemCompare;
  return computedItems.sort(sortFunc);
};

export default {
  toVuetifyItems,
};
