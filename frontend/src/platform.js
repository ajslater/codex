// Identify platform for special behaviors
const IOS_PLATFORMS = new Set([
  "iPad Simulator",
  "iPhone Simulator",
  "iPod Simulator",
  "iPad",
  "iPhone",
  "iPod",
]);
export const IS_IOS =
  IOS_PLATFORMS.has(navigator.platform) ||
  // iPad on iOS 13 detection
  (navigator.userAgent.includes("Mac") && "ontouchend" in document);
export const IS_TOUCH =
  "ontouchstart" in window ||
  navigator.maxTouchPoints > 0 ||
  navigator.msMaxTouchPoints > 0;

export default { IS_IOS, IS_TOUCH };
