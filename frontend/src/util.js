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

/*
 * An Enter that ends an IME composition picks the composed text; it is
 * not a submit. Safari reports it as keyCode 229 with isComposing false.
 */
export const isImeEnter = (event) =>
  Boolean(event?.isComposing) || event?.keyCode === 229;
