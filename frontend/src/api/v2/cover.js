import { ROOT_PATH } from "./base";

const MISSING_COVER_FN = "missing_cover.webp";
const MISSING_COVER_PATH = `static/img/${MISSING_COVER_FN}`;
/*
export const getCoverSource = (coverPath, updatedAt) => {
  let src = `${ROOT_PATH}`;
  src +=
    coverPath === MISSING_COVER_FN ? MISSING_COVER_PATH : `covers/${coverPath}`;
  if (updatedAt) {
    src += `?${updatedAt}`;
  }
  return src;
};
*/

export const getCoverSource = (pk, updatedAt) => {
  let src = `${ROOT_PATH}`;
  src += pk ? `api/v2/c/${pk}/thumb` : MISSING_COVER_PATH;
  if (updatedAt) {
    src += `?${updatedAt}`;
  }
  return src;
};
