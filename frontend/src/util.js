// Utility functions
export const range = (start, end = 0) => {
  start = Number.isInteger(start) && start >= 0 ? start : 0;
  end = Number.isInteger(end) && end >= 0 ? end : 0;
  const size = end > start ? Math.max(end - start, 0) : start;
  let result = [...Array(size).keys()];
  if (end > 0) {
    result = result.map((i) => i + start);
  }
  return result;
};
