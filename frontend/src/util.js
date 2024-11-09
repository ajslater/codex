// Utility functions
export const range = (start, end = 0) => {
  const size = end > 0 ? end - start : start;
  let result = [...Array(size).keys()];
  if (end) {
    result = result.map((i) => i + start);
  }
  return result;
};
