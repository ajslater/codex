// Identify platform for special behaviors
export const IS_TOUCH =
  "ontouchstart" in window ||
  navigator.maxTouchPoints > 0 ||
  navigator.msMaxTouchPoints > 0 ||
  window.matchMedia("(any-hover: none)").matches;
const IOS_PLATFORMS = ["iPad", "iPhone", "iPod"];
export const IS_IOS =
  IOS_PLATFORMS.some((word) => navigator.userAgent.includes(word)) ||
  // iOS in Desktop mode
  (IS_TOUCH && navigator.userAgent.includes("Mac OS"));
export default { IS_IOS, IS_TOUCH };
