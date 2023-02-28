// Date & time formats
// ISO 8601, en-CA has a comma for time delimiter, sv-SE does not.
// but en-CA has p.m. as a 12hr suffix.
const TWELVE_HOUR_LOCALE = "en-NZ";
const TWENTY_FOUR_HOUR_LOCALE = "sv-SE";
export const DATE_FORMAT = new Intl.DateTimeFormat(TWENTY_FOUR_HOUR_LOCALE, {
  timeZone: "UTC",
}); // prevents off by one error using browser tz
export const getTimeFormat = function (twentyFourHourTime) {
  const locale = twentyFourHourTime
    ? TWENTY_FOUR_HOUR_LOCALE
    : TWELVE_HOUR_LOCALE;
  return new Intl.DateTimeFormat(locale, {
    timeStyle: "medium",
  });
};

export const getDateTime = function (dttm, twentyFourHourTime, br = false) {
  const date = new Date(dttm);
  const dttm_date = DATE_FORMAT.format(date);
  const timeFormat = getTimeFormat(twentyFourHourTime);
  const dttm_time = timeFormat.format(date);
  const divider = br ? "<br />" : ", ";
  return dttm_date + divider + dttm_time;
};

export default {
  DATE_FORMAT,
  getDateTime,
  getTimeFormat,
};
