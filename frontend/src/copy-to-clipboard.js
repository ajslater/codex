export const copyToClipboard = function (text, showTooltip) {
  navigator.clipboard
    .writeText(text)
    .then(() => {
      showTooltip.show = true;
      setTimeout(() => {
        showTooltip.show = false;
      }, 5000);
      return true;
    })
    .catch(console.warn);
};

export default { copyToClipboard };
