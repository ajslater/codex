// Shared function for most metadata components.

export const computedItems = function (items, values) {
  // TODO should i use the composition api?
  let computedItems;
  if (items) {
    computedItems = items;
  } else if (values) {
    computedItems = new Array();
    values.forEach(function (value) {
      if (value != null) {
        const item = { value, text: value };
        computedItems.push(item);
      }
    });
  } else {
    computedItems = new Array();
  }
  return computedItems;
};

export const initialItem = function (items) {
  if (items && items.length === 1) {
    const singleItem = items[0];
    if (singleItem && singleItem.value != null) {
      return singleItem;
    }
  }
  return null;
};

export const initialValue = function (values) {
  if (values && values.length === 1) {
    return values[0];
  }
  return null;
};

export default {
  computedItems,
  initialItem,
  initialValue,
};
