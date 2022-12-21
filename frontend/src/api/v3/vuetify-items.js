// Shared functions for most metadata components.
import CHOICES from "@/choices";
const VUETIFY_NULL_CODE = CHOICES.browser.vuetifyNullCode;
const NULL_NAME = "None";
const NULL_ITEM = { value: VUETIFY_NULL_CODE, title: NULL_NAME };

const toVuetifyItem = function (item, charPk) {
  // Translates an raw value or an item item into a vuetify item.
  let vuetifyItem;
  if (item === undefined) {
    vuetifyItem = item;
  } else if (item instanceof Object) {
    vuetifyItem = { value: item.pk, title: item.name };
    if (item.pk === null || item.name === undefined) {
      vuetifyItem.value = VUETIFY_NULL_CODE;
    } else if (!charPk) {
      vuetifyItem.value = +item.pk;
    }
    if (vuetifyItem.title === null || vuetifyItem.value === undefined) {
      vuetifyItem.title = NULL_NAME;
    }
  } else if (item === null) {
    vuetifyItem = NULL_ITEM;
  } else {
    vuetifyItem = { value: item, title: item.toString() };
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

export const toVuetifyItems = function (
  items,
  filter,
  numeric = false,
  charPk = false
) {
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
        (vuetifyItem.title &&
          vuetifyItem.title.toLowerCase().includes(lowerCaseFilter)))
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
