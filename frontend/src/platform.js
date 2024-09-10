// Identify platforms for special behaviors

const IS_APPLE_OR_ANDROID_IN_DESKTOP_MODE_RE =
  /iP(?:ad|hone|od)|Mac OS|X11; Linux/; // codespell:ignore od

const noDoubleTapForHover = () => {
  const IS_TOUCH =
    "ontouchstart" in window ||
    navigator.maxTouchPoints > 0 ||
    navigator.msMaxTouchPoints > 0 ||
    window.matchMedia("(any-hover: none)").matches;

  if (!IS_TOUCH) {
    return true;
  }

  // Touch device. Check for an Apple product or Android browser in desktop mode.
  return IS_APPLE_OR_ANDROID_IN_DESKTOP_MODE_RE.test(navigator.userAgent);
};

export const NO_DOUBLE_TAP_FOR_HOVER = noDoubleTapForHover();

export default { NO_DOUBLE_TAP_FOR_HOVER };
