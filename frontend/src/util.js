// Utility functions
export const range = (start, end = 0) => {
  start = Number.isSafeInteger(start) && start >= 0 ? start : 0;
  end = Number.isSafeInteger(end) && end >= 0 ? end : 0;
  const length = end > start ? Math.max(end - start, 0) : start;
  let result = Array.from({ length }, (_, index) => index);
  if (end > 0) {
    result = result.map((i) => i + start);
  }
  return result;
};
