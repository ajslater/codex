// Shared functions for most metadata components.

export const toVuetifyItem = function (item) {
  // Translates an raw value or an item item into a vuetify
  // autocomplete/combobox item.
  let vuetifyItem;
  if (item == null || item instanceof Object) {
    vuetifyItem = item;
  } else {
    vuetifyItem = { pk: item, name: item };
  }
  return vuetifyItem;
};

export const computedItems = function (value, items) {
  // Takes a value (can be a list) and a list of items and
  // Returns a list of valid items with items arg having preference.
  let computedItems = new Array();
  let sourceItems;
  if (items) {
    sourceItems = items;
  } else if (value) {
    if (Array.isArray(value)) {
      sourceItems = value;
    } else {
      sourceItems = [value];
    }
  } else {
    sourceItems = new Array();
  }
  for (const item of sourceItems) {
    const vuetifyItem = toVuetifyItem(item);
    computedItems.push(vuetifyItem);
  }
  return computedItems;
};

export default {
  computedItems,
  toVuetifyItem,
};
