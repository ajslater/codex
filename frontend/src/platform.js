// Identify platform for special behaviors
export const IS_TOUCH =
  "ontouchstart" in window ||
  navigator.maxTouchPoints > 0 ||
  navigator.msMaxTouchPoints > 0 ||
  window.matchMedia("(any-hover: none)").matches;
const IOS_PLATFORMS = ["iPad", "iPhone", "iPod"];
export const IS_IOS = IOS_PLATFORMS.some((word) =>
  navigator.userAgent.includes(word),
);
const IS_MAC = navigator.userAgent.includes("Mac OS");
export const IS_IOS_DESKTOP_MODE = IS_MAC && IS_TOUCH;
export default { IS_IOS, IS_TOUCH, IS_IOS_DESKTOP_MODE };
