// Transform dicts and values into Vuetify choices for Vuetify input components

export const keyValueToVuetifyChoice = function (value, text) {
  return { value, text };
};

export const valueToVuetifyChoice = function (value) {
  return { value, text: value };
};

export const valueListToVuetifyChoices = function (valueList) {
  if (valueList == null) {
    return null;
  }
  const choices = new Array();
  for (const value of valueList) {
    const choice = valueToVuetifyChoice(value);
    choices.push(choice);
  }
  return choices;
};

export const dictToVuetifyChoices = function (dict) {
  if (dict == null) {
    return null;
  }
  const choices = new Array();
  for (const [key, value] of dict.entries()) {
    const choice = keyValueToVuetifyChoice(key, value);
    choices.push(choice);
  }
  return choices;
};

export default {
  valueListToVuetifyChoices,
  dictToVuetifyChoices,
};
