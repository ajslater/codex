/**
 * Shared status display helpers for admin status components.
 *
 * Used by: job-tab.vue, status-list-item.vue, stats-table.vue
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

/** "X ago" string since status.updatedAt, or "". */
export const statusUpdatedAgo = (status, now) => {
  if (!status.updatedAt) {
    return "";
  }
  const updatedTime = new Date(status.updatedAt).getTime();
  const ago = getFormattedDuration(updatedTime, now);
  return `${ago} ago`;
};
