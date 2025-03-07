// Identify platforms for special behaviors

const _IS_MOBILE_RE = /iP(?:ad|hone|od)|Android/; // codespell:ignore od

const _IS_MOBILE_UA = _IS_MOBILE_RE.test(navigator.userAgent);

export const IS_MOBILE = _IS_MOBILE_UA || globalThis.orientation !== undefined;

/*
 *export const IS_TOUCH =
 *  "ontouchstart" in window ||
 *  navigator.maxTouchPoints > 0 ||
 *  navigator.msMaxTouchPoints > 0 ||
 *  window.matchMedia("(any-hover: none)").matches;
 */
