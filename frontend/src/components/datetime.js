// Date & time formats
const LOCALE = "sv-SE"; // ISO 8601, en-CA has a comma for time delimiter
export const DATE_FORMAT = new Intl.DateTimeFormat(LOCALE, {
  timeZone: "UTC", // prevents off by one error using browser tz
});
export const DATETIME_FORMAT = new Intl.DateTimeFormat(LOCALE, {
  dateStyle: "short",
  timeStyle: "medium",
});

export default {
  DATE_FORMAT,
  DATETIME_FORMAT,
};
