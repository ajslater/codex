// Date & time formats
const LOCALE = "en-CA";
export const DATE_FORMAT = new Intl.DateTimeFormat(LOCALE, { timeZone: 'UTC'});
export const DATETIME_FORMAT = new Intl.DateTimeFormat(LOCALE, {
  dateStyle: "short",
  timeStyle: "medium",
  hour12: false,
});

export default {
  DATE_FORMAT,
  DATETIME_FORMAT,
};
