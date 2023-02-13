// Identify platform for special behaviors
const IOS_PLATFORMS = new Set([
  "iPad",
  "iPad Simulator",
  "iPhone",
  "iPhone Simulator",
  "iPod",
  "iPod Simulator",
]);
export const IS_IOS = IOS_PLATFORMS.has(navigator.platform);
/*
* Removed to test if KDE browser sets this off
  ||
  // iPad on iOS 13 detection
  (navigator.userAgent.includes("Mac") && "ontouchend" in document);
*/
export const IS_TOUCH =
  "ontouchstart" in window ||
  navigator.maxTouchPoints > 0 ||
  navigator.msMaxTouchPoints > 0 ||
  window.matchMedia("(any-hover: none)").matches;

export default { IS_IOS, IS_TOUCH };
