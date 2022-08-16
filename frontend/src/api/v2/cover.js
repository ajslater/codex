import { getComicBaseURL } from "./comic";

export const getCoverSource = (pk, updatedAt) => {
  if (pk) {
    const comicBaseURL = getComicBaseURL(pk);
    return `${comicBaseURL}/cover.webp?${updatedAt}`;
  } else {
    return window.CODEX.MISSING_COVER;
  }
};
