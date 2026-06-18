/**
 * Shared status display helpers for admin status components.
 *
 * Used by: job-tab.vue, status-list-item.vue
 */
import STATUS_TITLES from "@/choices/admin-status-titles.json";
import { getFormattedDuration, NUMBER_FORMAT } from "@/datetime";

/** Format an integer for display, or "?" if not an integer. */
export const nf = (val) => {
  return Number.isInteger(val) ? NUMBER_FORMAT.format(val) : "?";
};

/** Whether a status has displayable numeric progress. */
export const hasNumbers = (status) => {
  return Number.isInteger(status.complete) || Number.isInteger(status.total);
};

/** Whether the progress bar should be indeterminate. */
export const isIndeterminate = (status) => {
  return status.active && (!status.total || !Number.isInteger(status.complete));
};

/** Compute 0–100 progress percentage for a status. */
export const statusProgress = (status) => {
  if (!status.total || isIndeterminate(status)) {
    return 0;
  }
  return (100 * +status.complete) / +status.total;
};

/** Human-readable title for a statusType code. */
export const statusTitle = (statusType) => {
  return STATUS_TITLES[statusType] || statusType;
};

/** Duration string since status became active, or "pending". */
export const statusDuration = (status, now) => {
  if (status.active) {
    const activeTime = new Date(status.active).getTime();
    return getFormattedDuration(activeTime, now);
  }
  if (status.preactive) {
    return "pending";
  }
  return "";
};

/** Whole seconds remaining from `now` until an ISO target, clamped at 0. */
const secondsUntil = (iso, now) => {
  if (!iso) {
    return null;
  }
  return Math.max(0, Math.round((new Date(iso).getTime() - now) / 1000));
};

/** Format a countdown as "m:ss" (>= 60s) or "Ns". */
const formatCountdown = (secs) => {
  if (secs < 60) {
    return `${secs}s`;
  }
  const minutes = Math.floor(secs / 60);
  const seconds = secs % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

/** Format a coarse "time left" as "~Xh Ym" / "~Xm Ys" / "~Ys". */
const formatRemaining = (secs) => {
  if (secs >= 3600) {
    const hours = Math.floor(secs / 3600);
    const minutes = Math.round((secs % 3600) / 60);
    return minutes ? `~${hours}h ${minutes}m` : `~${hours}h`;
  }
  if (secs >= 60) {
    const minutes = Math.floor(secs / 60);
    const seconds = secs % 60;
    return seconds ? `~${minutes}m ${seconds}s` : `~${minutes}m`;
  }
  return `~${secs}s`;
};

/**
 * Live "retrying in M:SS" countdown for a rate-limited status, or "".
 *
 * The backend stamps `retryAt` once per retry attempt; we tick down to it
 * client-side so a multi-minute rate-limit wait reads as a live countdown
 * (the admin can see it's waiting, not hung) instead of a frozen number.
 */
export const retryRemaining = (status, now) => {
  const secs = secondsUntil(status.retryAt, now);
  if (secs === null) {
    return "";
  }
  return secs <= 0 ? "retrying now…" : `retrying in ${formatCountdown(secs)}`;
};

/**
 * Live "~Xm Ys left" total-time-remaining countdown, or "".
 *
 * Carries forward the launcher dialog's time estimate and ticks it down to
 * the backend-computed `eta`, which the backend re-estimates as comics
 * complete and pushes out by rate-limit waits.
 */
export const etaRemaining = (status, now) => {
  if (!status.active) {
    return "";
  }
  const secs = secondsUntil(status.eta, now);
  if (secs === null) {
    return "";
  }
  return secs <= 0 ? "finishing…" : `${formatRemaining(secs)} left`;
};

/** "X ago" string since status.updatedAt, or "". */
export const statusUpdatedAgo = (status, now) => {
  if (!status.updatedAt) {
    return "";
  }
  const updatedTime = new Date(status.updatedAt).getTime();
  const ago = getFormattedDuration(updatedTime, now);
  return `${ago} ago`;
};
