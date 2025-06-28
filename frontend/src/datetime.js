/*
 * Date & time formats
 * Date is forced to YYYY-MM-DD with sv-SE
 * Time is by default undefined and browser based but can be forced to sv-SE 24 HR.
 * XXX Force to 24 hr is probably superfluous at this point
 * const TWELVE_HOUR_LOCALE = "en-NZ";
 */
const TWENTY_FOUR_HOUR_LOCALE = "sv-SE";
export const DATE_FORMAT = new Intl.DateTimeFormat(TWENTY_FOUR_HOUR_LOCALE);
export const NUMBER_FORMAT = new Intl.NumberFormat();
export const DURATION_FORMAT = new Intl.DurationFormat("en", {
  style: "digital",
});
export const getTimeFormat = function (twentyFourHourTime) {
  const locale = twentyFourHourTime ? TWENTY_FOUR_HOUR_LOCALE : undefined;
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

export const getTimestamp = function () {
  return Math.floor(Date.now() / 1000);
};

export const getFormattedDuration = (fromTime, toTime) => {
  const totalSeconds = Math.floor((toTime - fromTime) / 1000);
  days = Math.floor(totalSeconds / (24 * 60 * 60));
  hours = Math.floor((totalSeconds % (24 * 60 * 60)) / (60 * 60));
  minutes = Math.floor((totalSeconds % (60 * 60)) / 60);
  seconds = totalSeconds % 60;

  const duration = {};
  if (days) {
    duration.days = days;
  }
  if (hours || days) {
    duration.hours = hours;
  }
  if (hours || days || minutes) {
    duration.minutes = minutes;
  }
  duration.seconds = seconds;

  return DURATION_FORMAT.format(duration);
};

export default {
  DATE_FORMAT,
  NUMBER_FORMAT,
  getDateTime,
  getFormattedDuration,
  getTimeFormat,
  getTimestamp,
};
