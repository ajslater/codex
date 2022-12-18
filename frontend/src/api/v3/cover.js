import { getReaderBasePath } from "./common";

export const getCoverSource = (pk, updatedAt) => {
  if (pk) {
    const basePath = getReaderBasePath(pk);
    return `${basePath}/cover.webp?${updatedAt}`;
  } else {
    return window.CODEX.MISSING_COVER;
  }
};
