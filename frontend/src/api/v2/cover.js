import { ROOT_PATH } from "./base";

const MISSING_COVER_PATH = window.missingCover;

export const getCoverSource = (pk, updatedAt) => {
  let src = ROOT_PATH;
  src += pk ? `api/v2/c/${pk}/thumb` : MISSING_COVER_PATH;
  if (pk && updatedAt) {
    src += `?${updatedAt}`;
  } else {
    console.log(src);
  }
  return src;
};
