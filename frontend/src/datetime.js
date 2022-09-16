// Date & time formats
// ISO 8601, en-CA has a comma for time delimiter, sv-SE does not.
// but en-CA has p.m. as a 12hr suffix.
const LOCALE = "en-CA";
export const DATE_FORMAT = new Intl.DateTimeFormat(LOCALE, {
  timeZone: "UTC", // prevents off by one error using browser tz
});
export const DATETIME_FORMAT = new Intl.DateTimeFormat(LOCALE, {
  dateStyle: "short",
  timeStyle: "medium",
});
export const TIME_FORMAT = new Intl.DateTimeFormat(LOCALE, {
  timeStyle: "medium",
});

export default {
  DATE_FORMAT,
  DATETIME_FORMAT,
  TIME_FORMAT,
};
