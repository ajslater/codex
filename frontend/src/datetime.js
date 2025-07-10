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
  daysDisplay: "auto",
  hoursDisplay: "auto",
  minutesDisplay: "auto",
});
const MINUTE_SECONDS = 60;
const HOUR_SECONDS = MINUTE_SECONDS * 60;
const DAY_SECONDS = HOUR_SECONDS * 24;
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
  const duration = {
    days: Math.floor(totalSeconds / DAY_SECONDS),
    hours: Math.floor((totalSeconds % DAY_SECONDS) / HOUR_SECONDS),
    minutes: Math.floor((totalSeconds % HOUR_SECONDS) / MINUTE_SECONDS),
    seconds: totalSeconds % MINUTE_SECONDS,
  };
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
