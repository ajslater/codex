// To Title Case functions
import titleize from "titleize";

export const camelToTitleCase = function (string) {
  string = string.replaceAll(/([A-Z])/g, " $1");
  return titleize(string);
};

export default {
  camelToTitleCase,
};
